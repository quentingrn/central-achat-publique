from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from urllib.parse import urlparse

from modules.discovery_compare.adapters.schemas import (
    ComparableV1,
    FairnessMetricsV1,
    ProductDigestV1,
)


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: ProductDigestV1
    comparability_score: float
    coverage_score: float
    identity_strength: float
    domain: str | None
    reasons: list[str]
    signals: list[str]
    diversity_penalty: float


@dataclass(frozen=True)
class ExcludedCandidate:
    candidate: ProductDigestV1
    reason: str


def _normalize(value: str | None) -> str:
    if not value:
        return ""
    lowered = value.strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def _tokens(value: str | None) -> set[str]:
    normalized = _normalize(value)
    return {token for token in normalized.split(" ") if token}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def _attribute_match_score(source: ProductDigestV1, candidate: ProductDigestV1) -> float:
    source_attrs = {k: v for k, v in source.attributes.items() if v is not None}
    if not source_attrs:
        return 0.0
    matches = 0
    for key, value in source_attrs.items():
        cand_value = candidate.attributes.get(key)
        if cand_value is None:
            continue
        if _normalize(str(value)) == _normalize(str(cand_value)):
            matches += 1
    return matches / max(1, len(source_attrs))


def _domain_from_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    return parsed.netloc.lower() if parsed.netloc else None


def _hard_filter_reason(source: ProductDigestV1, candidate: ProductDigestV1) -> str | None:
    source_category = _normalize(str(source.attributes.get("category")))
    candidate_category = _normalize(str(candidate.attributes.get("category")))
    if source_category and candidate_category and source_category != candidate_category:
        return "category_mismatch"

    source_type = _normalize(str(source.attributes.get("type")))
    candidate_type = _normalize(str(candidate.attributes.get("type")))
    if source_type and candidate_type and source_type != candidate_type:
        return "type_mismatch"

    source_model = _normalize(source.model)
    candidate_model = _normalize(candidate.model)
    source_brand = _normalize(source.brand)
    candidate_brand = _normalize(candidate.brand)
    if source_model and candidate_model and source_model == candidate_model:
        if source_brand and candidate_brand and source_brand != candidate_brand:
            return "brand_model_conflict"

    return None


def _category_type_score(source: ProductDigestV1, candidate: ProductDigestV1) -> float:
    scores = []
    for key in ("category", "type"):
        source_val = _normalize(str(source.attributes.get(key)))
        cand_val = _normalize(str(candidate.attributes.get(key)))
        if source_val and cand_val:
            scores.append(1.0 if source_val == cand_val else 0.0)
        else:
            scores.append(0.5)
    return sum(scores) / len(scores)


def _score_candidate(source: ProductDigestV1, candidate: ProductDigestV1) -> ScoredCandidate:
    brand_match = 1.0 if _normalize(source.brand) == _normalize(candidate.brand) else 0.0
    model_similarity = _jaccard(_tokens(source.model), _tokens(candidate.model))
    identity_strength = round(0.6 * brand_match + 0.4 * model_similarity, 4)

    coverage_score = round(_attribute_match_score(source, candidate), 4)
    category_score = _category_type_score(source, candidate)

    base_score = 0.5 * identity_strength + 0.3 * coverage_score + 0.2 * category_score
    penalty = 0.15 if brand_match == 0.0 and model_similarity < 0.3 else 0.0
    comparability_score = max(0.0, min(1.0, round(base_score - penalty, 4)))

    reasons = [
        f"identity_strength={identity_strength}",
        f"coverage_score={coverage_score}",
        f"category_type_score={round(category_score, 4)}",
    ]
    if penalty:
        reasons.append(f"penalty_brand_model={penalty}")

    signals = [
        "brand_match",
        "model_similarity",
        "attribute_overlap",
        "category_match",
        "type_match",
    ]

    return ScoredCandidate(
        candidate=candidate,
        comparability_score=comparability_score,
        coverage_score=coverage_score,
        identity_strength=identity_strength,
        domain=_domain_from_url(candidate.source_url),
        reasons=reasons,
        signals=signals,
        diversity_penalty=0.0,
    )


def _apply_diversity_penalty(candidates: list[ScoredCandidate]) -> list[ScoredCandidate]:
    domain_counts = Counter(c.domain for c in candidates if c.domain)
    adjusted: list[ScoredCandidate] = []
    for candidate in candidates:
        penalty = 0.0
        if candidate.domain and domain_counts[candidate.domain] > 1:
            penalty = min(0.2, 0.05 * (domain_counts[candidate.domain] - 1))
        final_score = max(0.0, min(1.0, round(candidate.comparability_score - penalty, 4)))
        reasons = candidate.reasons.copy()
        if penalty:
            reasons.append(f"diversity_penalty={round(penalty, 3)}")
        adjusted.append(
            ScoredCandidate(
                candidate=candidate.candidate,
                comparability_score=final_score,
                coverage_score=candidate.coverage_score,
                identity_strength=candidate.identity_strength,
                domain=candidate.domain,
                reasons=reasons,
                signals=candidate.signals + ["domain_diversity"],
                diversity_penalty=penalty,
            )
        )
    return adjusted


def _rank_candidates(candidates: list[ScoredCandidate]) -> list[ScoredCandidate]:
    return sorted(
        candidates,
        key=lambda c: (
            -c.comparability_score,
            -c.identity_strength,
            -c.coverage_score,
            _normalize(c.candidate.brand),
            _normalize(c.candidate.model),
        ),
    )


def _fairness_metrics(
    scored: list[ScoredCandidate], excluded: list[ExcludedCandidate]
) -> FairnessMetricsV1:
    if not scored:
        return FairnessMetricsV1(
            comparability_score=0.0,
            coverage_score=0.0,
            diversity_score=0.0,
            notes=["no_comparables"],
        )

    avg_comparability = round(sum(c.comparability_score for c in scored) / len(scored), 4)
    avg_coverage = round(sum(c.coverage_score for c in scored) / len(scored), 4)
    unique_domains = len({c.domain for c in scored if c.domain})
    diversity_score = round(unique_domains / len(scored), 4) if scored else 0.0
    avg_identity = round(sum(c.identity_strength for c in scored) / len(scored), 4)

    notes = [
        f"identity_strength_avg={avg_identity}",
        "diversity_penalty_cap=0.2",
    ]
    if excluded:
        excluded_counts = Counter(e.reason for e in excluded)
        notes.append(f"excluded={sum(excluded_counts.values())}:{dict(excluded_counts)}")

    return FairnessMetricsV1(
        comparability_score=avg_comparability,
        coverage_score=avg_coverage,
        diversity_score=diversity_score,
        notes=notes,
    )


def evaluate_comparability(
    source: ProductDigestV1, candidates: list[ProductDigestV1]
) -> tuple[list[ComparableV1], FairnessMetricsV1, str]:
    excluded: list[ExcludedCandidate] = []
    scored: list[ScoredCandidate] = []

    for candidate in candidates:
        reason = _hard_filter_reason(source, candidate)
        if reason:
            excluded.append(ExcludedCandidate(candidate=candidate, reason=reason))
            continue
        scored.append(_score_candidate(source, candidate))

    scored = _apply_diversity_penalty(scored)
    ranked = _rank_candidates(scored)

    comparables = [
        ComparableV1(
            product=c.candidate,
            comparability_score=c.comparability_score,
            reasons_short=c.reasons,
            signals_used=c.signals,
            missing_critical=[],
        )
        for c in ranked
    ]

    fairness = _fairness_metrics(ranked, excluded)
    excluded_counts = Counter(e.reason for e in excluded)
    summary = f"excluded={sum(excluded_counts.values())} reasons={dict(excluded_counts)}"

    return comparables, fairness, summary
