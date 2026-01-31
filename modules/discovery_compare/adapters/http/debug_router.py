import time
import uuid
from datetime import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, tuple_

from apps.api.guards import require_debug_access
from modules.discovery_compare.adapters.schemas.debug_candidate_judge_v1 import (
    CandidateJudgeRequestV1,
    CandidateJudgeResponseV1,
    CandidateJudgeResultV1,
    HardFilterResultV1,
    JudgeVerdictV1,
    ProductDigestInputV1,
)
from modules.discovery_compare.adapters.schemas.debug_exa_recall_v1 import (
    ExaRecallRequestV1,
    ExaRecallResponseV1,
    ExaResultItemV1,
)
from modules.discovery_compare.adapters.schemas.debug_run_diff_v1 import (
    CompareRunDiffResponseV1,
    DiffSeverityV1,
    RunCountsDiffV1,
    RunErrorTopDiffV1,
    RunFieldDiffV1,
    RunPhaseDiffItemV1,
    RunRefSetDiffV1,
)
from modules.discovery_compare.adapters.schemas.debug_run_v1 import (
    CompareRunListItemV1,
    CompareRunListResponseV1,
    CompareRunSummaryResponseV1,
    RunErrorTopV1,
    RunPhaseCountsV1,
    RunRefsV1,
    RunTimelineItemV1,
)
from modules.discovery_compare.adapters.schemas.v1 import PhaseNameV1, ProductDigestV1
from modules.discovery_compare.application.settings import get_discovery_compare_settings
from modules.discovery_compare.domain import comparability as comparability_domain
from modules.discovery_compare.infrastructure.mcp_clients.exa import (
    ExaMcpError,
    HttpExaMcpClient,
)
from modules.discovery_compare.infrastructure.persistence.models import (
    CompareRun,
    LlmRun,
    PageSnapshot,
    Prompt,
    RunEvent,
    ToolRun,
)
from shared.db.session import get_session

router = APIRouter(
    prefix="/v1/debug",
    tags=["debug"],
    dependencies=[Depends(require_debug_access)],
)

_CURSOR_SEPARATOR = "|"
_ERROR_STATUSES = {"error", "warning"}
_PHASE_STATUS_KEYS = ("ok", "warning", "error", "skipped")
_STATUS_SEVERITY = {"error": 3, "warning": 2, "ok": 1, "skipped": 0}
_PHASE_ORDER = {phase.value: index for index, phase in enumerate(PhaseNameV1)}


def _encode_cursor(created_at: datetime, run_id: uuid.UUID) -> str:
    return f"{created_at.isoformat()}{_CURSOR_SEPARATOR}{run_id}"


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        created_raw, run_raw = cursor.split(_CURSOR_SEPARATOR, 1)
        created_at = datetime.fromisoformat(created_raw)
        run_id = uuid.UUID(run_raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid cursor") from exc
    return created_at, run_id


def _build_phase_counts(events: list[RunEvent]) -> dict[uuid.UUID, RunPhaseCountsV1]:
    counts: dict[uuid.UUID, RunPhaseCountsV1] = {}
    for event in events:
        run_counts = counts.setdefault(event.run_id, RunPhaseCountsV1())
        if event.status in _PHASE_STATUS_KEYS:
            setattr(run_counts, event.status, getattr(run_counts, event.status) + 1)
    return counts


def _build_error_top(events: list[RunEvent]) -> dict[uuid.UUID, RunErrorTopV1]:
    error_top: dict[uuid.UUID, RunErrorTopV1] = {}
    sorted_events = sorted(events, key=lambda evt: evt.created_at)
    for event in sorted_events:
        if event.status not in _ERROR_STATUSES:
            continue
        if event.run_id in error_top:
            continue
        error_top[event.run_id] = RunErrorTopV1(
            phase_name=event.phase_name,
            status=event.status,
            message=event.message or "",
        )
    return error_top


def _diff_severity(left: object | None, right: object | None) -> DiffSeverityV1:
    if left == right:
        return DiffSeverityV1.same
    if left is None and right is not None:
        return DiffSeverityV1.added
    if left is not None and right is None:
        return DiffSeverityV1.removed
    return DiffSeverityV1.changed


def _build_phase_index(events: list[RunEvent]) -> dict[str, RunEvent]:
    phases: dict[str, RunEvent] = {}
    for event in events:
        current = phases.get(event.phase_name)
        if current is None:
            phases[event.phase_name] = event
            continue
        current_severity = _STATUS_SEVERITY.get(current.status, 0)
        new_severity = _STATUS_SEVERITY.get(event.status, 0)
        if new_severity > current_severity:
            phases[event.phase_name] = event
            continue
        if new_severity == current_severity and event.created_at >= current.created_at:
            phases[event.phase_name] = event
    return phases


def _build_ref_diff(left_ids: list[uuid.UUID], right_ids: list[uuid.UUID]) -> RunRefSetDiffV1:
    left_set = {str(value) for value in left_ids}
    right_set = {str(value) for value in right_ids}
    added = sorted(right_set - left_set)
    removed = sorted(left_set - right_set)
    common_count = len(left_set & right_set)
    return RunRefSetDiffV1(
        added_ids=added,
        removed_ids=removed,
        common_count=common_count,
    )


def _parse_exa_datetime(value: object | None) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _normalize_exa_domain(url: str, domain: str | None) -> str | None:
    if domain:
        return domain.strip().lower()
    parsed = urlparse(url)
    if parsed.netloc:
        return parsed.netloc.lower()
    return None


def _normalize_exa_items(results: list[dict]) -> list[ExaResultItemV1]:
    items: list[ExaResultItemV1] = []
    for item in results:
        url = item.get("url") or item.get("link")
        if not isinstance(url, str) or not url.strip():
            continue
        domain = _normalize_exa_domain(url, item.get("domain"))
        items.append(
            ExaResultItemV1(
                rank=len(items) + 1,
                title=item.get("title"),
                url=url,
                domain=domain,
                score=item.get("score"),
                snippet=item.get("snippet") or item.get("summary"),
                published_at=_parse_exa_datetime(
                    item.get("published_at") or item.get("publishedAt")
                ),
            )
        )
    return items


def _build_exa_metrics(items: list[ExaResultItemV1]) -> dict:
    domains: list[str] = [item.domain for item in items if item.domain]
    domain_counts: dict[str, int] = {}
    for domain in domains:
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
    top_domains = [
        {"domain": domain, "count": count}
        for domain, count in sorted(domain_counts.items(), key=lambda pair: (-pair[1], pair[0]))
    ]
    urls = [item.url for item in items]
    has_duplicate_urls = len(urls) != len(set(urls))
    return {
        "unique_domains_count": len(domain_counts),
        "top_domains": top_domains,
        "has_duplicate_urls": has_duplicate_urls,
    }


def _stub_exa_results(limit: int) -> list[dict]:
    base = [
        {
            "title": "Example A",
            "url": "https://example.com/item-a",
            "domain": "example.com",
            "score": 0.92,
            "snippet": "Example A snippet",
        },
        {
            "title": "Example B",
            "url": "https://example.org/item-b",
            "domain": "example.org",
            "score": 0.81,
            "snippet": "Example B snippet",
        },
        {
            "title": "Example A duplicate",
            "url": "https://example.com/item-a",
            "domain": "example.com",
            "score": 0.78,
            "snippet": "Duplicate URL",
        },
    ]
    return base[: max(1, min(limit, len(base)))]


def _missing_from_payload(payload: object | None) -> list[str]:
    if isinstance(payload, dict):
        value = payload.get("missing")
        if isinstance(value, list):
            return [str(item) for item in value]
    if isinstance(payload, list):
        return [str(item) for item in payload]
    return []


def _errors_from_payload(payload: object | None) -> list[dict]:
    if isinstance(payload, dict):
        value = payload.get("errors")
        if isinstance(value, list):
            return value
        if payload:
            return [payload]
    if isinstance(payload, list):
        return payload
    return []


def _build_digest_from_inputs(
    url: str | None,
    digest_v1: dict | None,
    extraction_v1: dict | None,
) -> ProductDigestV1 | None:
    identity = {}
    product = {}
    if isinstance(digest_v1, dict):
        identity = digest_v1.get("product_identity") or {}
    if isinstance(extraction_v1, dict):
        product = extraction_v1.get("product") or {}

    brand = identity.get("brand") or product.get("brand") or "UNKNOWN"
    model = identity.get("model") or product.get("model") or "UNKNOWN"
    attributes: dict[str, str | int | float | bool | None] = {}
    if isinstance(product, dict):
        for key, value in product.items():
            if key in {"brand", "model"}:
                continue
            attributes[key] = value

    return ProductDigestV1(
        brand=brand,
        model=model,
        source_url=url,
        attributes=attributes,
    )


def _resolve_digest_input(
    payload: ProductDigestInputV1,
    session,
) -> tuple[ProductDigestV1 | None, dict]:
    errors: list[dict] = []
    missing: list[str] = []
    digest_v1 = payload.digest_v1
    extraction_v1 = payload.extraction_v1
    url = payload.url
    snapshot_id = payload.snapshot_id

    if snapshot_id:
        try:
            snapshot_uuid = uuid.UUID(snapshot_id)
        except ValueError:
            errors.append({"kind": "snapshot_id_invalid", "snapshot_id": snapshot_id})
            snapshot_uuid = None
        if snapshot_uuid:
            snapshot = session.get(PageSnapshot, snapshot_uuid)
            if snapshot is None:
                errors.append({"kind": "snapshot_not_found", "snapshot_id": snapshot_id})
            else:
                if url is None:
                    url = snapshot.final_url or snapshot.url
                extracted = snapshot.extracted_json or {}
                if extraction_v1 is None and isinstance(extracted, dict):
                    if extracted.get("extraction_version") == "v1":
                        extraction_v1 = extracted
                if digest_v1 is None and isinstance(extracted, dict):
                    digest_v1 = extracted.get("digest")
                missing.extend(_missing_from_payload(snapshot.missing_critical_json))
                errors.extend(_errors_from_payload(snapshot.errors_json))

    if extraction_v1 and isinstance(extraction_v1, dict):
        missing.extend(_missing_from_payload(extraction_v1.get("missing_critical")))
        errors.extend(_errors_from_payload(extraction_v1.get("errors")))

    if digest_v1 is None and extraction_v1 is None:
        missing.append("digest_missing")
        errors.append({"kind": "digest_missing", "message": "digest_v1 or extraction_v1 required"})
        return None, {
            "snapshot_id": snapshot_id,
            "url": url,
            "missing": missing,
            "errors": errors,
        }

    digest = _build_digest_from_inputs(url, digest_v1, extraction_v1)
    return digest, {
        "snapshot_id": snapshot_id,
        "url": url,
        "missing": missing,
        "errors": errors,
    }


def _duration_ms(run: CompareRun) -> int | None:
    if not run.created_at or not run.updated_at:
        return None
    delta = run.updated_at - run.created_at
    return int(delta.total_seconds() * 1000)


def _build_list_item(
    run: CompareRun,
    phase_counts: RunPhaseCountsV1 | None,
    error_top: RunErrorTopV1 | None,
) -> CompareRunListItemV1:
    return CompareRunListItemV1(
        run_id=run.id,
        created_at=run.created_at,
        status=run.status,
        source_url=run.source_url,
        agent_version=run.agent_version,
        duration_ms=_duration_ms(run),
        phase_counts=phase_counts or RunPhaseCountsV1(),
        error_top=error_top,
    )


def _serialize_run(run: CompareRun, events: list[RunEvent]) -> dict:
    return {
        "id": str(run.id),
        "status": run.status,
        "source_url": run.source_url,
        "agent_version": run.agent_version,
        "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat(),
        "events": [
            {
                "id": str(event.id),
                "phase_name": event.phase_name,
                "status": event.status,
                "message": event.message,
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ],
    }


def _serialize_prompt(prompt: Prompt) -> dict:
    return {
        "id": str(prompt.id),
        "name": prompt.name,
        "version": prompt.version,
        "content": prompt.content,
        "created_at": prompt.created_at.isoformat(),
    }


def _serialize_tool_run(tool_run: ToolRun) -> dict:
    return {
        "id": str(tool_run.id),
        "run_id": str(tool_run.run_id),
        "tool_name": tool_run.tool_name,
        "status": tool_run.status,
        "input_json": tool_run.input_json,
        "output_json": tool_run.output_json,
        "created_at": tool_run.created_at.isoformat(),
    }


def _serialize_llm_run(llm_run: LlmRun) -> dict:
    return {
        "id": str(llm_run.id),
        "run_id": str(llm_run.run_id),
        "prompt_id": str(llm_run.prompt_id) if llm_run.prompt_id else None,
        "prompt_content": llm_run.prompt_content,
        "prompt_hash": llm_run.prompt_hash,
        "model_name": llm_run.model_name,
        "status": llm_run.status,
        "model_params": llm_run.model_params,
        "json_schema": llm_run.json_schema,
        "json_schema_hash": llm_run.json_schema_hash,
        "input_json": llm_run.input_json,
        "output_json": llm_run.output_json,
        "output_validated_json": llm_run.output_validated_json,
        "validation_errors": llm_run.validation_errors,
        "created_at": llm_run.created_at.isoformat(),
    }


@router.get("/compare-runs", response_model=CompareRunListResponseV1)
def list_compare_runs(
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> CompareRunListResponseV1:
    session = get_session()
    try:
        query = session.query(CompareRun).order_by(
            CompareRun.created_at.desc(), CompareRun.id.desc()
        )
        if cursor:
            cursor_created_at, cursor_run_id = _decode_cursor(cursor)
            query = query.filter(
                tuple_(CompareRun.created_at, CompareRun.id) < (cursor_created_at, cursor_run_id)
            )
        runs = query.limit(limit + 1).all()
        page = runs[:limit]
        next_cursor = None
        if len(runs) > limit and page:
            last = page[-1]
            next_cursor = _encode_cursor(last.created_at, last.id)

        run_ids = [run.id for run in page]
        phase_counts_map: dict[uuid.UUID, RunPhaseCountsV1] = {}
        error_top_map: dict[uuid.UUID, RunErrorTopV1] = {}
        if run_ids:
            events = (
                session.query(RunEvent)
                .filter(RunEvent.run_id.in_(run_ids))
                .order_by(RunEvent.created_at.asc())
                .all()
            )
            phase_counts_map = _build_phase_counts(events)
            error_top_map = _build_error_top(events)

        items = [
            _build_list_item(run, phase_counts_map.get(run.id), error_top_map.get(run.id))
            for run in page
        ]
        return CompareRunListResponseV1(items=items, next_cursor=next_cursor)
    finally:
        session.close()


@router.get("/compare-runs/{run_id}:summary", response_model=CompareRunSummaryResponseV1)
def get_compare_run_summary(run_id: str) -> CompareRunSummaryResponseV1:
    session = get_session()
    try:
        run = session.get(CompareRun, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")

        events = (
            session.query(RunEvent)
            .filter(RunEvent.run_id == run.id)
            .order_by(RunEvent.created_at.asc())
            .all()
        )
        phase_counts_map = _build_phase_counts(events)
        error_top_map = _build_error_top(events)
        item = _build_list_item(
            run,
            phase_counts_map.get(run.id),
            error_top_map.get(run.id),
        )
        timeline = [
            RunTimelineItemV1(
                phase_name=event.phase_name,
                status=event.status,
                created_at=event.created_at,
                message=event.message,
            )
            for event in events
        ]

        snapshot_ids = [
            row[0]
            for row in session.query(PageSnapshot.id).filter(PageSnapshot.run_id == run.id).all()
        ]
        tool_run_ids = [
            row[0] for row in session.query(ToolRun.id).filter(ToolRun.run_id == run.id).all()
        ]
        llm_run_ids = [
            row[0] for row in session.query(LlmRun.id).filter(LlmRun.run_id == run.id).all()
        ]
        prompt_ids = [
            row[0]
            for row in session.query(func.distinct(LlmRun.prompt_id))
            .filter(LlmRun.run_id == run.id)
            .filter(LlmRun.prompt_id.isnot(None))
            .all()
        ]

        refs = RunRefsV1(
            snapshot_ids=snapshot_ids,
            tool_run_ids=tool_run_ids,
            llm_run_ids=llm_run_ids,
            prompt_ids=prompt_ids,
        )

        return CompareRunSummaryResponseV1(item=item, timeline=timeline, refs=refs)
    finally:
        session.close()


@router.get("/compare-runs:diff", response_model=CompareRunDiffResponseV1)
def diff_compare_runs(
    left_run_id: str | None = Query(default=None),
    right_run_id: str | None = Query(default=None),
    left: str | None = Query(default=None),
    right: str | None = Query(default=None),
) -> CompareRunDiffResponseV1:
    left_id = left_run_id or left
    right_id = right_run_id or right
    if not left_id or not right_id:
        raise HTTPException(status_code=400, detail="left_run_id and right_run_id required")

    session = get_session()
    try:
        left_run = session.get(CompareRun, left_id)
        right_run = session.get(CompareRun, right_id)
        if left_run is None or right_run is None:
            raise HTTPException(status_code=404, detail="run not found")

        left_events = (
            session.query(RunEvent)
            .filter(RunEvent.run_id == left_run.id)
            .order_by(RunEvent.created_at.asc())
            .all()
        )
        right_events = (
            session.query(RunEvent)
            .filter(RunEvent.run_id == right_run.id)
            .order_by(RunEvent.created_at.asc())
            .all()
        )

        left_phase_counts = _build_phase_counts(left_events).get(left_run.id, RunPhaseCountsV1())
        right_phase_counts = _build_phase_counts(right_events).get(right_run.id, RunPhaseCountsV1())
        phase_counts = RunCountsDiffV1(
            left=left_phase_counts,
            right=right_phase_counts,
            severity=_diff_severity(left_phase_counts, right_phase_counts),
        )

        left_error_top = _build_error_top(left_events).get(left_run.id)
        right_error_top = _build_error_top(right_events).get(right_run.id)
        error_top = RunErrorTopDiffV1(
            left=left_error_top,
            right=right_error_top,
            severity=_diff_severity(left_error_top, right_error_top),
        )

        left_index = _build_phase_index(left_events)
        right_index = _build_phase_index(right_events)
        phase_names = sorted(
            set(left_index.keys()) | set(right_index.keys()),
            key=lambda phase: (_PHASE_ORDER.get(phase, 999), phase),
        )
        timeline: list[RunPhaseDiffItemV1] = []
        for phase_name in phase_names:
            left_event = left_index.get(phase_name)
            right_event = right_index.get(phase_name)
            left_status = left_event.status if left_event else None
            right_status = right_event.status if right_event else None
            timeline.append(
                RunPhaseDiffItemV1(
                    phase_name=phase_name,
                    left_status=left_status,
                    right_status=right_status,
                    severity=_diff_severity(left_status, right_status),
                    left_message=left_event.message if left_event else None,
                    right_message=right_event.message if right_event else None,
                )
            )

        left_snapshot_ids = [
            row[0]
            for row in session.query(PageSnapshot.id)
            .filter(PageSnapshot.run_id == left_run.id)
            .all()
        ]
        right_snapshot_ids = [
            row[0]
            for row in session.query(PageSnapshot.id)
            .filter(PageSnapshot.run_id == right_run.id)
            .all()
        ]
        left_tool_run_ids = [
            row[0] for row in session.query(ToolRun.id).filter(ToolRun.run_id == left_run.id).all()
        ]
        right_tool_run_ids = [
            row[0] for row in session.query(ToolRun.id).filter(ToolRun.run_id == right_run.id).all()
        ]
        left_llm_run_ids = [
            row[0] for row in session.query(LlmRun.id).filter(LlmRun.run_id == left_run.id).all()
        ]
        right_llm_run_ids = [
            row[0] for row in session.query(LlmRun.id).filter(LlmRun.run_id == right_run.id).all()
        ]
        left_prompt_ids = [
            row[0]
            for row in session.query(func.distinct(LlmRun.prompt_id))
            .filter(LlmRun.run_id == left_run.id)
            .filter(LlmRun.prompt_id.isnot(None))
            .all()
        ]
        right_prompt_ids = [
            row[0]
            for row in session.query(func.distinct(LlmRun.prompt_id))
            .filter(LlmRun.run_id == right_run.id)
            .filter(LlmRun.prompt_id.isnot(None))
            .all()
        ]

        refs = {
            "snapshots": _build_ref_diff(left_snapshot_ids, right_snapshot_ids),
            "tool_runs": _build_ref_diff(left_tool_run_ids, right_tool_run_ids),
            "llm_runs": _build_ref_diff(left_llm_run_ids, right_llm_run_ids),
            "prompts": _build_ref_diff(left_prompt_ids, right_prompt_ids),
        }

        status_diff = RunFieldDiffV1(
            left=left_run.status,
            right=right_run.status,
            severity=_diff_severity(left_run.status, right_run.status),
        )
        source_url_diff = RunFieldDiffV1(
            left=left_run.source_url,
            right=right_run.source_url,
            severity=_diff_severity(left_run.source_url, right_run.source_url),
        )
        agent_version_diff = RunFieldDiffV1(
            left=left_run.agent_version,
            right=right_run.agent_version,
            severity=_diff_severity(left_run.agent_version, right_run.agent_version),
        )

        notes = ["timeline built from run_events only"]

        return CompareRunDiffResponseV1(
            left_run_id=str(left_run.id),
            right_run_id=str(right_run.id),
            left_created_at=left_run.created_at,
            right_created_at=right_run.created_at,
            status_diff=status_diff,
            source_url_diff=source_url_diff,
            agent_version_diff=agent_version_diff,
            phase_counts=phase_counts,
            error_top=error_top,
            timeline=timeline,
            refs=refs,
            notes=notes,
        )
    finally:
        session.close()


@router.post("/recall/exa", response_model=ExaRecallResponseV1)
def debug_exa_recall(payload: ExaRecallRequestV1) -> ExaRecallResponseV1:
    settings = get_discovery_compare_settings()
    start = time.perf_counter()
    errors: list[dict] = []
    raw: dict | None = None
    items: list[ExaResultItemV1] = []

    request_payload = payload.model_dump(exclude_none=True)
    limit = request_payload.pop("num_results", payload.num_results)
    request_payload["limit"] = limit
    request_payload["timeout_seconds"] = settings.exa_mcp_timeout_seconds

    if settings.exa_mcp_url == "stub":
        raw = {"results": _stub_exa_results(limit)}
    elif not settings.exa_mcp_url:
        errors.append({"kind": "config", "message": "EXA_MCP_URL not configured", "status": 500})
    else:
        client = HttpExaMcpClient(settings.exa_mcp_url, api_key=settings.exa_api_key)
        try:
            raw = client.search_raw(
                request_payload,
                timeout_seconds=settings.exa_mcp_timeout_seconds,
            )
        except ExaMcpError as exc:
            errors.append({"kind": "provider", "message": str(exc)})
        except Exception as exc:  # pragma: no cover - defensive
            errors.append({"kind": "provider", "message": str(exc)})

    if raw:
        results = raw.get("results") or raw.get("items") or []
        if isinstance(results, list):
            items = _normalize_exa_items(results)

    metrics = _build_exa_metrics(items)
    took_ms = int((time.perf_counter() - start) * 1000)
    return ExaRecallResponseV1(
        request=payload,
        provider="exa",
        took_ms=took_ms,
        items=items,
        raw=raw,
        errors=errors,
        metrics=metrics,
    )


@router.post("/judge/candidates", response_model=CandidateJudgeResponseV1)
def debug_candidate_judge(payload: CandidateJudgeRequestV1) -> CandidateJudgeResponseV1:
    session = get_session()
    try:
        source_digest, source_meta = _resolve_digest_input(payload.source, session)
        results: list[CandidateJudgeResultV1 | None] = [None] * len(payload.candidates)
        ranked_indices: list[int] = []
        scored_candidates = []
        scored_meta: dict[uuid.UUID, dict] = {}

        if source_digest is None:
            for index, candidate in enumerate(payload.candidates):
                _, meta = _resolve_digest_input(candidate, session)
                errors = meta["errors"] + [
                    {"kind": "source_missing", "message": "source digest missing"}
                ]
                results[index] = CandidateJudgeResultV1(
                    candidate_index=index,
                    candidate_snapshot_id=meta["snapshot_id"],
                    candidate_url=meta["url"],
                    verdict=JudgeVerdictV1.indeterminate,
                    hard_filters=[],
                    reasons_short=[],
                    signals_used=[],
                    missing_critical=meta["missing"],
                    breakdown={},
                    errors=errors,
                )
            return CandidateJudgeResponseV1(
                request=payload,
                source_snapshot_id=source_meta["snapshot_id"],
                results=[result for result in results if result is not None],
                ranked_top_k=[],
                metrics={"limitations": ["source_missing"]},
                raw=None,
            )

        for index, candidate in enumerate(payload.candidates):
            digest, meta = _resolve_digest_input(candidate, session)
            if digest is None:
                results[index] = CandidateJudgeResultV1(
                    candidate_index=index,
                    candidate_snapshot_id=meta["snapshot_id"],
                    candidate_url=meta["url"],
                    verdict=JudgeVerdictV1.indeterminate,
                    hard_filters=[],
                    reasons_short=[],
                    signals_used=[],
                    missing_critical=meta["missing"],
                    breakdown={},
                    errors=meta["errors"],
                )
                continue

            hard_reason = comparability_domain._hard_filter_reason(source_digest, digest)
            if hard_reason:
                results[index] = CandidateJudgeResultV1(
                    candidate_index=index,
                    candidate_snapshot_id=meta["snapshot_id"],
                    candidate_url=meta["url"] or digest.source_url,
                    verdict=JudgeVerdictV1.no,
                    hard_filters=[
                        HardFilterResultV1(
                            passed=False,
                            reason_code=hard_reason,
                            details=None,
                        )
                    ],
                    reasons_short=[hard_reason],
                    signals_used=[],
                    missing_critical=meta["missing"],
                    breakdown={"hard_filter": hard_reason},
                    errors=meta["errors"],
                )
                continue

            scored = comparability_domain._score_candidate(source_digest, digest)
            scored_candidates.append(scored)
            scored_meta[scored.candidate.id] = {
                "index": index,
                "meta": meta,
            }

        if scored_candidates:
            adjusted = comparability_domain._apply_diversity_penalty(scored_candidates)
            ranked = comparability_domain._rank_candidates(adjusted)
            for scored in adjusted:
                meta_entry = scored_meta.get(scored.candidate.id)
                if not meta_entry:
                    continue
                index = meta_entry["index"]
                meta = meta_entry["meta"]
                results[index] = CandidateJudgeResultV1(
                    candidate_index=index,
                    candidate_snapshot_id=meta["snapshot_id"],
                    candidate_url=meta["url"] or scored.candidate.source_url,
                    verdict=JudgeVerdictV1.yes,
                    comparability_score=scored.comparability_score,
                    coverage_score=scored.coverage_score,
                    identity_strength=scored.identity_strength,
                    final_score=scored.comparability_score,
                    hard_filters=[],
                    reasons_short=scored.reasons,
                    signals_used=scored.signals,
                    missing_critical=meta["missing"],
                    breakdown={
                        "reasons": scored.reasons,
                        "diversity_penalty": scored.diversity_penalty,
                    },
                    errors=meta["errors"],
                )

            ranked_indices = [scored_meta[candidate.candidate.id]["index"] for candidate in ranked]

        results_clean = [result for result in results if result is not None]
        yes_count = sum(1 for result in results_clean if result.verdict == JudgeVerdictV1.yes)
        no_count = sum(1 for result in results_clean if result.verdict == JudgeVerdictV1.no)
        indeterminate_count = sum(
            1 for result in results_clean if result.verdict == JudgeVerdictV1.indeterminate
        )
        scores = [result.final_score for result in results_clean if result.final_score is not None]
        avg_score = round(sum(scores) / len(scores), 4) if scores else None
        metrics = {
            "yes_count": yes_count,
            "no_count": no_count,
            "indeterminate_count": indeterminate_count,
            "avg_score": avg_score,
        }

        return CandidateJudgeResponseV1(
            request=payload,
            source_snapshot_id=source_meta["snapshot_id"],
            results=results_clean,
            ranked_top_k=ranked_indices[: payload.ranking_top_k],
            metrics=metrics,
            raw=None,
        )
    finally:
        session.close()


@router.get("/compare-runs/{run_id}")
def get_compare_run(run_id: str) -> dict:
    session = get_session()
    try:
        run = session.get(CompareRun, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        events = (
            session.query(RunEvent)
            .filter(RunEvent.run_id == run.id)
            .order_by(RunEvent.created_at.asc())
            .all()
        )
        return _serialize_run(run, events)
    finally:
        session.close()


@router.get("/llm-runs/{run_id}")
def get_llm_run(run_id: str) -> dict:
    session = get_session()
    try:
        llm_run = session.get(LlmRun, run_id)
        if llm_run is None:
            raise HTTPException(status_code=404, detail="llm run not found")
        return _serialize_llm_run(llm_run)
    finally:
        session.close()


@router.get("/tool-runs/{run_id}")
def get_tool_run(run_id: str) -> dict:
    session = get_session()
    try:
        tool_run = session.get(ToolRun, run_id)
        if tool_run is None:
            raise HTTPException(status_code=404, detail="tool run not found")
        return _serialize_tool_run(tool_run)
    finally:
        session.close()


@router.get("/prompts/{prompt_id}")
def get_prompt(prompt_id: str) -> dict:
    session = get_session()
    try:
        prompt = session.get(Prompt, prompt_id)
        if prompt is None:
            raise HTTPException(status_code=404, detail="prompt not found")
        return _serialize_prompt(prompt)
    finally:
        session.close()
