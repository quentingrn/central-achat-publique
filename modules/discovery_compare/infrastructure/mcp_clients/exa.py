from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ExaSearchRequest:
    query: str
    limit: int
    timeout_seconds: int


@dataclass(frozen=True)
class ExaSearchResponse:
    results: list[dict]
    metadata: dict


class ExaMcpClient(Protocol):
    def search(self, request: ExaSearchRequest) -> ExaSearchResponse:
        raise NotImplementedError


class ExaMcpError(RuntimeError):
    pass


class HttpExaMcpClient:
    def __init__(self, endpoint: str, api_key: str | None = None) -> None:
        self.endpoint = endpoint
        self.api_key = api_key

    def _build_url(self) -> str:
        if not self.api_key:
            return self.endpoint
        parsed = urlparse(self.endpoint)
        query = dict(parse_qsl(parsed.query))
        query["exaApiKey"] = self.api_key
        return urlunparse(parsed._replace(query=urlencode(query)))

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def search(self, request: ExaSearchRequest) -> ExaSearchResponse:
        payload = {
            "query": request.query,
            "limit": request.limit,
            "timeout_seconds": request.timeout_seconds,
        }
        data = self.search_raw(payload, timeout_seconds=request.timeout_seconds)

        results = data.get("results") or data.get("items") or []
        metadata = data.get("metadata") or {}
        return ExaSearchResponse(results=list(results), metadata=metadata)

    def search_raw(self, payload: dict, timeout_seconds: int) -> dict:
        body = json.dumps(payload).encode("utf-8")
        http_request = Request(
            self._build_url(),
            data=body,
            headers=self._build_headers(),
            method="POST",
        )
        try:
            with urlopen(http_request, timeout=timeout_seconds) as response:
                raw = response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            raise ExaMcpError(f"exa_request_failed: {exc}") from exc

        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ExaMcpError("exa_response_invalid_json") from exc
        return data
