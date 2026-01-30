from urllib.request import Request

from modules.discovery_compare.infrastructure.mcp_clients.exa import HttpExaMcpClient


class DummyResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return False

    def read(self) -> bytes:
        return self.payload


def test_http_client_includes_api_key(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request: Request, timeout: int):  # type: ignore[no-untyped-def]
        captured["url"] = request.full_url
        captured["headers"] = dict(request.headers)
        return DummyResponse(b'{"results": [], "metadata": {}}')

    monkeypatch.setattr(
        "modules.discovery_compare.infrastructure.mcp_clients.exa.urlopen", fake_urlopen
    )
    client = HttpExaMcpClient("https://exa.example/mcp", api_key="fake-key")
    from modules.discovery_compare.infrastructure.mcp_clients.exa import ExaSearchRequest

    client.search(ExaSearchRequest(query="q", limit=1, timeout_seconds=1))

    assert "exaApiKey=fake-key" in captured["url"]
    lowered = {key.lower(): value for key, value in captured["headers"].items()}
    assert lowered.get("x-api-key") == "fake-key"
