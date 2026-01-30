from modules.discovery_compare.infrastructure.mcp_clients import playwright as playwright_mod


class DummyStdioClient:
    def __init__(self, command, cwd, timeout_seconds) -> None:  # type: ignore[no-untyped-def]
        self.command = command
        self.cwd = cwd
        self.timeout_seconds = timeout_seconds
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_stdio_registry_caches_clients(monkeypatch) -> None:
    monkeypatch.setattr(playwright_mod, "StdioPlaywrightMcpClient", DummyStdioClient)
    registry = playwright_mod.PlaywrightMcpRegistry
    registry._stdio_client = None
    registry._signature = None

    first = registry.get_stdio_client(["npx", "a"], None, 30)
    second = registry.get_stdio_client(["npx", "a"], None, 30)
    assert first is second

    third = registry.get_stdio_client(["npx", "b"], None, 30)
    assert third is not first
