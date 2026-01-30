from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from modules.discovery_compare.adapters.schemas import (
    AgentRunOutputV1,
    ComparabilityGateOutputV1,
    PhaseDiagnosticsV1,
    PhaseNameV1,
    ProductDigestV1,
    RunDiagnosticsV1,
)
from modules.discovery_compare.application.llm_runtime import (
    LlmClient,
    StubLlmClient,
    compute_hash,
    get_agent_config,
    json_schema_for_model,
    schema_hash,
    validate_against_schema,
)
from modules.discovery_compare.application.ports import (
    OfferCandidateProvider,
    ProductCandidate,
    ProductCandidateProvider,
    SnapshotProvider,
    SnapshotResult,
)
from modules.discovery_compare.application.prompts import COMPARABILITY_GATE_PROMPT_V1
from modules.discovery_compare.application.run_recorder import RunRecorder
from modules.discovery_compare.application.settings import get_discovery_compare_settings
from modules.discovery_compare.domain.comparability import evaluate_comparability
from modules.discovery_compare.infrastructure.persistence.models import (
    ComparableCandidate,
    PageSnapshot,
    Product,
)
from modules.discovery_compare.infrastructure.providers.playwright_mcp import SnapshotCaptureError


@dataclass(frozen=True)
class AgentRunnerConfig:
    source_url: str | None = None


class AgentRunner:
    def __init__(
        self,
        session: Session,
        snapshot_provider: SnapshotProvider,
        product_candidate_provider: ProductCandidateProvider,
        offer_candidate_provider: OfferCandidateProvider,
        llm_client: LlmClient | None = None,
    ) -> None:
        self.session = session
        self.recorder = RunRecorder(session)
        self.snapshot_provider = snapshot_provider
        self.product_candidate_provider = product_candidate_provider
        self.offer_candidate_provider = offer_candidate_provider
        self.settings = get_discovery_compare_settings()
        self.llm_client = llm_client or StubLlmClient()

    def run(self, config: AgentRunnerConfig) -> AgentRunOutputV1:
        prompt_hash = compute_hash(COMPARABILITY_GATE_PROMPT_V1)
        prompt_version = f"v1-{prompt_hash[:8]}"
        prompt = self.recorder.get_or_create_prompt(
            "comparability_gate",
            prompt_version,
            COMPARABILITY_GATE_PROMPT_V1,
        )
        schema = json_schema_for_model(ComparabilityGateOutputV1)
        schema_hash_value = schema_hash(schema)
        prompt_hash = prompt.content_hash or prompt_hash
        agent_config = get_agent_config(
            self.settings.mistral_model,
            [prompt_hash],
            [schema_hash_value],
        )

        run = self.recorder.create_run(
            source_url=config.source_url, agent_version=agent_config.version
        )
        phases: list[PhaseDiagnosticsV1] = []
        comparables = []
        offers = []

        def record_phase(phase: PhaseNameV1, status: str, message: str | None = None) -> None:
            self.recorder.add_event(run.id, phase.value, status, message)
            phases.append(PhaseDiagnosticsV1(name=phase, status=status, message=message))

        def get_or_create_product(brand: str, model: str, source_url: str | None) -> Product:
            if source_url:
                existing = (
                    self.session.query(Product)
                    .filter(Product.source_url == source_url)
                    .one_or_none()
                )
                if existing is not None:
                    return existing
            product = Product(brand=brand, model=model, source_url=source_url)
            self.session.add(product)
            self.session.commit()
            self.session.refresh(product)
            return product

        def get_or_create_snapshot(
            product_id: uuid.UUID, url: str, extracted_json: dict
        ) -> PageSnapshot:
            existing = (
                self.session.query(PageSnapshot).filter(PageSnapshot.url == url).one_or_none()
            )
            if existing is not None:
                payload = existing.extracted_json or {}
                if "digest" not in payload:
                    existing.extracted_json = extracted_json
                    self.session.commit()
                return existing
            snapshot_row = PageSnapshot(
                product_id=product_id,
                url=url,
                extracted_json=extracted_json,
            )
            self.session.add(snapshot_row)
            self.session.commit()
            self.session.refresh(snapshot_row)
            return snapshot_row

        def resolve_product(snapshot: SnapshotResult) -> ProductDigestV1:
            digest = snapshot.digest_json or {}
            brand = digest.get("brand") or snapshot.extracted_json.get("brand")
            model = digest.get("model") or snapshot.extracted_json.get("model")
            return ProductDigestV1(
                brand=brand or "UNKNOWN",
                model=model or "UNKNOWN",
                source_url=snapshot.url_final,
            )

        def derive_candidate_digest(
            source: ProductDigestV1, candidate: ProductCandidate
        ) -> ProductDigestV1:
            signals = candidate.signals_json or {}
            title = str(signals.get("title") or "")
            snippet = str(signals.get("snippet") or "")
            score = signals.get("score")
            text = f"{title} {snippet}".lower()
            brand = source.brand if source.brand and source.brand.lower() in text else "UNKNOWN"
            model = source.model if source.model and source.model.lower() in text else "UNKNOWN"
            attributes: dict[str, str | int | float | bool | None] = {}
            if title:
                attributes["title"] = title
            if snippet:
                attributes["snippet"] = snippet
            if score is not None:
                attributes["score"] = score
            return ProductDigestV1(
                brand=brand,
                model=model,
                source_url=candidate.candidate_url,
                attributes=attributes,
            )

        def record_candidate(product_id: uuid.UUID, candidate: ProductCandidate) -> None:
            existing = (
                self.session.query(ComparableCandidate)
                .filter(
                    ComparableCandidate.product_id == product_id,
                    ComparableCandidate.candidate_url == candidate.candidate_url,
                )
                .one_or_none()
            )
            if existing is None:
                row = ComparableCandidate(
                    product_id=product_id,
                    candidate_url=candidate.candidate_url,
                    signals_json=candidate.signals_json,
                )
                self.session.add(row)
                self.session.commit()

        def snapshot_payload(snapshot: SnapshotResult) -> dict:
            html_excerpt = snapshot.html[:1000] if snapshot.html else None
            return {
                "digest": snapshot.digest_json,
                "extracted": snapshot.extracted_json,
                "metadata": snapshot.metadata,
                "html_excerpt": html_excerpt,
            }

        def snapshot_request_options() -> dict:
            return {
                "provider": self.settings.snapshot_provider,
                "timeout_seconds": self.settings.playwright_mcp_timeout_seconds,
                "screenshot": self.settings.snapshot_screenshot_enabled,
                "max_bytes": self.settings.snapshot_max_bytes,
                "user_agent": self.settings.snapshot_user_agent,
            }

        try:
            phase = PhaseNameV1.source_snapshot_capture
            snapshot = self.snapshot_provider.capture(
                config.source_url or "https://example.com/source"
            )
            source_product = resolve_product(snapshot)
            product_row = get_or_create_product(
                source_product.brand,
                source_product.model,
                snapshot.url_final,
            )
            snapshot_row = get_or_create_snapshot(
                product_row.id,
                snapshot.url_final,
                snapshot_payload(snapshot),
            )
            self.recorder.add_tool_run(
                run.id,
                "snapshot_capture",
                "ok",
                input_json={
                    "url": snapshot.requested_url,
                    "url_final": snapshot.url_final,
                    "options": snapshot_request_options(),
                },
                output_json={
                    "snapshot_id": str(snapshot_row.id),
                    "status_code": snapshot.status_code,
                    "metadata": snapshot.metadata,
                },
            )
            record_phase(phase, "ok")

            phase = PhaseNameV1.product_candidates_recall
            recall = self.product_candidate_provider.recall(source_product)
            candidates = recall.candidates
            self.recorder.add_tool_run(
                run.id,
                "exa_mcp_recall",
                recall.status,
                input_json=recall.request_json,
                output_json=recall.response_json,
            )
            if recall.status != "ok":
                record_phase(phase, "error", recall.error_message)
            else:
                record_phase(phase, "ok", f"candidates={len(candidates)}")

            phase = PhaseNameV1.candidate_snapshot_capture
            candidate_digests = []
            for candidate in candidates:
                candidate_digest = derive_candidate_digest(source_product, candidate)
                candidate_digests.append(candidate_digest)
                candidate_row = get_or_create_product(
                    candidate_digest.brand,
                    candidate_digest.model,
                    candidate_digest.source_url,
                )
                record_candidate(product_row.id, candidate)
                candidate_snapshot = self.snapshot_provider.capture(
                    candidate_digest.source_url or "https://example.com/c"
                )
                candidate_snapshot_row = get_or_create_snapshot(
                    candidate_row.id,
                    candidate_snapshot.url_final,
                    snapshot_payload(candidate_snapshot),
                )
                self.recorder.add_tool_run(
                    run.id,
                    "candidate_snapshot_capture",
                    "ok",
                    input_json={
                        "url": candidate_snapshot.requested_url,
                        "url_final": candidate_snapshot.url_final,
                        "options": snapshot_request_options(),
                    },
                    output_json={
                        "snapshot_id": str(candidate_snapshot_row.id),
                        "status_code": candidate_snapshot.status_code,
                        "metadata": candidate_snapshot.metadata,
                    },
                )
            record_phase(phase, "ok")

            phase = PhaseNameV1.comparability_gate
            comparables, fairness, summary = evaluate_comparability(
                source_product, candidate_digests
            )
            input_payload = {
                "source": source_product.model_dump(mode="json"),
                "candidates": [
                    candidate.model_dump(mode="json") for candidate in candidate_digests
                ],
            }
            expected_output = ComparabilityGateOutputV1(comparables=comparables).model_dump(
                mode="json"
            )

            raw_output = self.llm_client.generate_json(
                prompt=prompt.content,
                schema=schema,
                input_json=input_payload,
                model_name=self.settings.mistral_model,
                params={
                    "response_format": "json-schema",
                    "timeout_seconds": self.settings.llm_timeout_seconds,
                    "enabled": self.settings.llm_enabled,
                },
                expected_output=expected_output,
            )
            errors = validate_against_schema(schema, raw_output)
            validated_output = raw_output if not errors else None

            self.recorder.add_llm_run(
                run.id,
                model_name=self.settings.mistral_model,
                status="ok" if not errors else "error",
                prompt_id=prompt.id,
                prompt_content=prompt.content,
                prompt_hash=prompt_hash,
                model_params={
                    "response_format": "json-schema",
                    "timeout_seconds": self.settings.llm_timeout_seconds,
                    "enabled": self.settings.llm_enabled,
                },
                json_schema=schema,
                json_schema_hash=schema_hash_value,
                input_json=input_payload,
                output_json=raw_output,
                output_validated_json=validated_output,
                validation_errors=errors or None,
            )

            self.recorder.add_tool_run(
                run.id,
                "comparability_scoring",
                "ok" if not errors else "error",
                input_json={"summary": summary},
                output_json={"comparables": len(comparables), "summary": summary},
            )

            if errors:
                record_phase(phase, "error", "validation_error")
                raise ValueError("LLM output validation failed")

            gate_output = ComparabilityGateOutputV1.model_validate(validated_output)
            comparables = gate_output.comparables
            record_phase(phase, "ok", summary)

            phase = PhaseNameV1.criteria_selection
            record_phase(phase, "ok")

            phase = PhaseNameV1.product_comparison_build
            record_phase(phase, "ok")

            phase = PhaseNameV1.offers_recall_and_fetch
            for comparable in comparables:
                offers.extend(self.offer_candidate_provider.recall(comparable.product))
            self.recorder.add_tool_run(
                run.id,
                "offers_recall",
                "ok",
                input_json={"comparables": len(comparables)},
                output_json={"offers": len(offers)},
            )
            record_phase(phase, "ok")

            phase = PhaseNameV1.offers_normalize_and_dedupe
            record_phase(phase, "ok")

            phase = PhaseNameV1.final_response_assemble
            record_phase(phase, "ok")

            diagnostics = RunDiagnosticsV1(
                phases=phases,
                fairness=fairness,
                agent_version=agent_config.version,
            )
            output = AgentRunOutputV1(
                run_id=run.id,
                source_product=source_product,
                comparables=comparables,
                offers=offers,
                diagnostics=diagnostics,
            )
            run.status = "completed"
            self.session.commit()
            return output
        except SnapshotCaptureError as exc:
            self.session.rollback()
            record_phase(phase, "error", str(exc))
            tool_name = (
                "candidate_snapshot_capture"
                if phase == PhaseNameV1.candidate_snapshot_capture
                else "snapshot_capture"
            )
            self.recorder.add_tool_run(
                run.id,
                tool_name,
                "error",
                input_json={"phase": phase.value, "options": snapshot_request_options()},
                output_json={"error": str(exc), "details": exc.details},
            )
            run.status = "error"
            self.session.commit()
            raise
        except Exception as exc:  # noqa: BLE001
            self.session.rollback()
            record_phase(phase, "error", str(exc))
            run.status = "error"
            self.session.commit()
            raise
