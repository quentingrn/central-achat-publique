from fastapi import APIRouter

from modules.discovery_compare.application.agent_runner import AgentRunner, AgentRunnerConfig
from modules.discovery_compare.application.llm_runtime import StubLlmClient
from modules.discovery_compare.application.settings import get_discovery_compare_settings
from modules.discovery_compare.infrastructure.providers import (
    ExaMcpProductCandidateProvider,
    PlaywrightMcpSnapshotProvider,
    StubOfferCandidateProvider,
    StubProductCandidateProvider,
    StubSnapshotProvider,
)
from shared.db.session import get_session

router = APIRouter(prefix="/v1/discovery", tags=["discovery_compare"])


@router.post("/compare")
def compare_stub() -> dict:
    settings = get_discovery_compare_settings()
    session = get_session()
    try:
        if settings.snapshot_provider == "stub":
            snapshot_provider = StubSnapshotProvider()
        elif settings.snapshot_provider == "playwright":
            snapshot_provider = PlaywrightMcpSnapshotProvider(settings)
        else:
            raise RuntimeError(f"Unknown snapshot provider: {settings.snapshot_provider}")
        if settings.product_candidate_provider == "stub":
            product_candidate_provider = StubProductCandidateProvider()
        elif settings.product_candidate_provider == "exa":
            product_candidate_provider = ExaMcpProductCandidateProvider(settings)
        else:
            raise RuntimeError(
                f"Unknown product candidate provider: {settings.product_candidate_provider}"
            )
        runner = AgentRunner(
            session=session,
            snapshot_provider=snapshot_provider,
            product_candidate_provider=product_candidate_provider,
            offer_candidate_provider=StubOfferCandidateProvider(),
            llm_client=StubLlmClient(),
        )
        output = runner.run(AgentRunnerConfig(source_url="https://example.com/source"))
        return output.model_dump()
    finally:
        session.close()
