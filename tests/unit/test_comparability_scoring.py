from modules.discovery_compare.adapters.schemas import ProductDigestV1
from modules.discovery_compare.domain.comparability import evaluate_comparability


def test_hard_filter_category_mismatch() -> None:
    source = ProductDigestV1(brand="ACME", model="X1", attributes={"category": "phone"})
    candidate = ProductDigestV1(brand="ACME", model="X2", attributes={"category": "laptop"})

    comparables, fairness, summary = evaluate_comparability(source, [candidate])

    assert comparables == []
    assert "category_mismatch" in summary
    assert "no_comparables" in fairness.notes


def test_hard_filter_brand_model_conflict() -> None:
    source = ProductDigestV1(brand="ACME", model="X1")
    candidate = ProductDigestV1(brand="OTHER", model="X1")

    comparables, _, summary = evaluate_comparability(source, [candidate])

    assert comparables == []
    assert "brand_model_conflict" in summary


def test_ranking_deterministic() -> None:
    source = ProductDigestV1(brand="ACME", model="X1", attributes={"category": "phone"})
    candidate_a = ProductDigestV1(
        brand="ACME",
        model="X1 Pro",
        source_url="https://example.com/a",
        attributes={"category": "phone"},
    )
    candidate_b = ProductDigestV1(
        brand="OTHER",
        model="Z9",
        source_url="https://example.com/b",
        attributes={"category": "phone"},
    )

    comparables, _, _ = evaluate_comparability(source, [candidate_b, candidate_a])

    assert len(comparables) == 2
    assert comparables[0].product.model == "X1 Pro"
    assert comparables[0].comparability_score >= comparables[1].comparability_score
