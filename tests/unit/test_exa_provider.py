from modules.discovery_compare.adapters.schemas import ProductDigestV1
from modules.discovery_compare.application.settings import DiscoveryCompareSettings
from modules.discovery_compare.infrastructure.mcp_clients.exa import ExaSearchResponse
from modules.discovery_compare.infrastructure.providers.exa_mcp import (
    ExaMcpProductCandidateProvider,
)


class DummyExaClient:
    def __init__(self, response: ExaSearchResponse) -> None:
        self.response = response

    def search(self, request):  # type: ignore[no-untyped-def]
        return self.response


def _settings() -> DiscoveryCompareSettings:
    return DiscoveryCompareSettings(
        _env_file=None,
        exa_mcp_url="http://exa",
        exa_mcp_limit=5,
        exa_mcp_timeout_seconds=5,
    )


def test_exa_normalizes_and_dedupes() -> None:
    response = ExaSearchResponse(
        results=[
            {"url": "https://Example.com/p1/", "title": "ACME X1", "snippet": "a", "score": 0.9},
            {"url": "https://example.com/p1", "title": "ACME X1 dup", "snippet": "b", "score": 0.8},
            {"url": "https://example.com/p2", "title": "ACME X1 2", "snippet": "c", "score": 0.7},
        ],
        metadata={},
    )
    provider = ExaMcpProductCandidateProvider(_settings(), client=DummyExaClient(response))
    recall = provider.recall(ProductDigestV1(brand="ACME", model="X1"))
    urls = [candidate.candidate_url for candidate in recall.candidates]
    assert urls == ["https://example.com/p1", "https://example.com/p2"]
    assert recall.request_json["auth"]["exa_api_key"] is None


def test_exa_ignores_missing_url() -> None:
    response = ExaSearchResponse(
        results=[
            {"title": "no url"},
            {"url": "https://example.com/p1", "title": "ok"},
        ],
        metadata={},
    )
    provider = ExaMcpProductCandidateProvider(_settings(), client=DummyExaClient(response))
    recall = provider.recall(ProductDigestV1(brand="ACME", model="X1"))
    assert len(recall.candidates) == 1
    assert recall.request_json["auth"]["exa_api_key"] is None


def test_exa_missing_url_config() -> None:
    settings = DiscoveryCompareSettings(
        _env_file=None,
        exa_mcp_url=None,
        exa_mcp_limit=3,
        exa_mcp_timeout_seconds=5,
    )
    provider = ExaMcpProductCandidateProvider(
        settings, client=DummyExaClient(ExaSearchResponse([], {}))
    )
    recall = provider.recall(ProductDigestV1(brand="ACME", model="X1"))
    assert recall.status == "error"


def test_exa_includes_api_key_in_request_json() -> None:
    settings = DiscoveryCompareSettings(
        _env_file=None,
        exa_mcp_url="http://exa",
        exa_mcp_limit=3,
        exa_mcp_timeout_seconds=5,
        exa_api_key="fake-key",
    )
    provider = ExaMcpProductCandidateProvider(
        settings, client=DummyExaClient(ExaSearchResponse([], {}))
    )
    recall = provider.recall(ProductDigestV1(brand="ACME", model="X1"))
    assert recall.request_json["auth"]["exa_api_key"] == "fake-key"
