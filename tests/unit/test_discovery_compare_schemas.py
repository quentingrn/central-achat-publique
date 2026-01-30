from modules.discovery_compare.adapters.schemas import (
    AgentRunOutputV1,
    ComparableV1,
    FairnessMetricsV1,
    OfferV1,
    PhaseDiagnosticsV1,
    PhaseNameV1,
    ProductDigestV1,
    RunDiagnosticsV1,
)


def test_phase_names_count() -> None:
    assert len(list(PhaseNameV1)) == 9


def test_agent_run_output_minimal_valid() -> None:
    source = ProductDigestV1(brand="ACME", model="X1", source_url="https://example.com/p")
    phases = [PhaseDiagnosticsV1(name=phase, status="skipped") for phase in PhaseNameV1]
    diagnostics = RunDiagnosticsV1(phases=phases, fairness=FairnessMetricsV1())

    payload = AgentRunOutputV1(
        source_product=source,
        comparables=[ComparableV1(product=source, comparability_score=0.9)],
        offers=[OfferV1(offer_url="https://example.com/o", price_amount=1.0, price_currency="EUR")],
        diagnostics=diagnostics,
    )

    dumped = payload.model_dump()
    assert dumped["source_product"]["brand"] == "ACME"
    assert dumped["diagnostics"]["phases"]
