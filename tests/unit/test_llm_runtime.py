from modules.discovery_compare.adapters.schemas import (
    ComparabilityGateOutputV1,
    ComparableV1,
    ProductDigestV1,
)
from modules.discovery_compare.application.llm_runtime import (
    compute_agent_version,
    json_schema_for_model,
    validate_against_schema,
)


def test_agent_version_deterministic() -> None:
    version_a = compute_agent_version("mistral", ["p1"], ["s1"])
    version_b = compute_agent_version("mistral", ["p1"], ["s1"])
    version_c = compute_agent_version("mistral", ["p1"], ["s2"])

    assert version_a == version_b
    assert version_a != version_c


def test_json_schema_generation() -> None:
    schema = json_schema_for_model(ComparabilityGateOutputV1)
    assert "properties" in schema
    assert "comparables" in schema["properties"]


def test_validation_errors() -> None:
    schema = json_schema_for_model(ComparabilityGateOutputV1)
    errors = validate_against_schema(schema, {"unexpected": 1})
    assert errors


def test_validation_ok() -> None:
    candidate = ProductDigestV1(brand="ACME", model="X1")
    payload = ComparabilityGateOutputV1(
        comparables=[ComparableV1(product=candidate, comparability_score=0.8)]
    ).model_dump(mode="json")
    schema = json_schema_for_model(ComparabilityGateOutputV1)
    errors = validate_against_schema(schema, payload)
    assert errors == []
