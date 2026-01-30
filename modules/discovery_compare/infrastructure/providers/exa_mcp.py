from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlparse

from modules.discovery_compare.adapters.schemas import ProductDigestV1
from modules.discovery_compare.application.ports import (
    ProductCandidate,
    ProductCandidateProvider,
    ProductCandidateRecall,
)
from modules.discovery_compare.application.settings import DiscoveryCompareSettings
from modules.discovery_compare.infrastructure.mcp_clients.exa import (
    ExaMcpClient,
    ExaMcpError,
    ExaSearchRequest,
    HttpExaMcpClient,
)


@dataclass(frozen=True)
class ExaCandidateSignals:
    title: str | None
    snippet: str | None
    score: float | None


def _normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        return url.strip()
    path = parsed.path.rstrip("/") or "/"
    return parsed._replace(
        scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower(), path=path
    ).geturl()


def _build_query(source: ProductDigestV1) -> str:
    parts = [source.brand, source.model]
    for key in ("category", "type"):
        value = source.attributes.get(key)
        if value:
            parts.append(str(value))
    return " ".join(part for part in parts if part).strip()


def _normalize_results(results: Iterable[dict]) -> list[ProductCandidate]:
    candidates: list[ProductCandidate] = []
    seen: set[str] = set()
    for item in results:
        url = item.get("url") or item.get("link")
        if not isinstance(url, str) or not url.strip():
            continue
        normalized = _normalize_url(url)
        if normalized in seen:
            continue
        seen.add(normalized)
        signals = {
            "title": item.get("title"),
            "snippet": item.get("snippet") or item.get("summary"),
            "score": item.get("score"),
        }
        candidates.append(ProductCandidate(candidate_url=normalized, signals_json=signals))
    return candidates


class ExaMcpProductCandidateProvider(ProductCandidateProvider):
    def __init__(
        self, settings: DiscoveryCompareSettings, client: ExaMcpClient | None = None
    ) -> None:
        self.settings = settings
        self.client = client or HttpExaMcpClient(
            settings.exa_mcp_url or "",
            api_key=settings.exa_api_key,
        )

    def recall(self, source: ProductDigestV1) -> ProductCandidateRecall:
        query = _build_query(source)
        request_json = {
            "query": query,
            "limit": self.settings.exa_mcp_limit,
            "auth": {
                "method": "header+query" if self.settings.exa_api_key else "none",
                "exa_api_key": self.settings.exa_api_key,
            },
        }
        if not self.settings.exa_mcp_url:
            return ProductCandidateRecall(
                candidates=[],
                request_json=request_json,
                response_json={"error": "EXA_MCP_URL not configured"},
                status="error",
                error_message="EXA_MCP_URL not configured",
            )

        try:
            response = self.client.search(
                ExaSearchRequest(
                    query=query,
                    limit=self.settings.exa_mcp_limit,
                    timeout_seconds=self.settings.exa_mcp_timeout_seconds,
                )
            )
        except ExaMcpError as exc:
            return ProductCandidateRecall(
                candidates=[],
                request_json=request_json,
                response_json={"error": str(exc)},
                status="error",
                error_message=str(exc),
            )

        candidates = _normalize_results(response.results)
        response_json = {"results": response.results, "metadata": response.metadata}
        return ProductCandidateRecall(
            candidates=candidates,
            request_json=request_json,
            response_json=response_json,
            status="ok",
        )
