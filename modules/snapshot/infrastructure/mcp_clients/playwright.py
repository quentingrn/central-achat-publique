from __future__ import annotations

import atexit
import json
import selectors
import subprocess
import threading
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class PlaywrightCaptureRequest:
    url: str
    timeout_seconds: int
    user_agent: str | None
    screenshot: bool | None = None
    max_bytes: int | None = None


@dataclass(frozen=True)
class PlaywrightCaptureResponse:
    url_final: str
    status_code: int | None
    html: str | None
    metadata: dict
    content_type: str | None


class PlaywrightMcpClient(Protocol):
    def capture(self, request: PlaywrightCaptureRequest) -> PlaywrightCaptureResponse:
        raise NotImplementedError


class PlaywrightMcpError(RuntimeError):
    pass


class HttpPlaywrightMcpClient:
    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint

    def capture(self, request: PlaywrightCaptureRequest) -> PlaywrightCaptureResponse:
        payload = {
            "url": request.url,
            "timeout_seconds": request.timeout_seconds,
            "user_agent": request.user_agent,
        }
        if request.screenshot is not None:
            payload["screenshot"] = request.screenshot
        if request.max_bytes is not None:
            payload["max_bytes"] = request.max_bytes
        body = json.dumps(payload).encode("utf-8")
        http_request = Request(
            self.endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(http_request, timeout=request.timeout_seconds) as response:
                raw = response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            raise PlaywrightMcpError(f"mcp_request_failed: {exc}") from exc

        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise PlaywrightMcpError("mcp_response_invalid_json") from exc

        url_final = data.get("url_final") or data.get("final_url") or data.get("url") or request.url
        html = data.get("html") or data.get("content")
        status_code = data.get("status_code") or data.get("status")
        metadata = data.get("metadata") or {}
        content_type = data.get("content_type")

        return PlaywrightCaptureResponse(
            url_final=url_final,
            status_code=status_code,
            html=html,
            metadata=metadata,
            content_type=content_type,
        )


class StdioPlaywrightMcpClient:
    def __init__(self, command: list[str], cwd: str | None, timeout_seconds: int) -> None:
        self._command = command
        self._cwd = cwd
        self._timeout_seconds = timeout_seconds
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()
        atexit.register(self.close)

    def close(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()
        self._process = None

    def _ensure_process(self) -> subprocess.Popen[str]:
        if self._process and self._process.poll() is None:
            return self._process
        self._process = subprocess.Popen(
            self._command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self._cwd,
            text=True,
            bufsize=1,
        )
        return self._process

    def _readline_with_timeout(self, process: subprocess.Popen[str]) -> str:
        assert process.stdout is not None
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        events = selector.select(timeout=self._timeout_seconds)
        if not events:
            raise PlaywrightMcpError("mcp_stdio_timeout")
        line = process.stdout.readline()
        if not line:
            raise PlaywrightMcpError("mcp_stdio_no_output")
        return line

    def capture(self, request: PlaywrightCaptureRequest) -> PlaywrightCaptureResponse:
        payload = {
            "url": request.url,
            "timeout_seconds": request.timeout_seconds,
            "user_agent": request.user_agent,
        }
        if request.screenshot is not None:
            payload["screenshot"] = request.screenshot
        if request.max_bytes is not None:
            payload["max_bytes"] = request.max_bytes
        with self._lock:
            process = self._ensure_process()
            assert process.stdin is not None
            try:
                process.stdin.write(json.dumps(payload) + "\n")
                process.stdin.flush()
            except BrokenPipeError as exc:
                self.close()
                raise PlaywrightMcpError("mcp_stdio_broken_pipe") from exc

            line = self._readline_with_timeout(process)
            try:
                data = json.loads(line.strip())
            except json.JSONDecodeError as exc:
                raise PlaywrightMcpError("mcp_stdio_invalid_json") from exc

        url_final = data.get("url_final") or data.get("final_url") or data.get("url") or request.url
        html = data.get("html") or data.get("content")
        status_code = data.get("status_code") or data.get("status")
        metadata = data.get("metadata") or {}
        content_type = data.get("content_type")

        return PlaywrightCaptureResponse(
            url_final=url_final,
            status_code=status_code,
            html=html,
            metadata=metadata,
            content_type=content_type,
        )


class PlaywrightMcpRegistry:
    _stdio_client: StdioPlaywrightMcpClient | None = None
    _signature: tuple | None = None
    _lock = threading.Lock()

    @classmethod
    def get_stdio_client(
        cls,
        command: list[str],
        cwd: str | None,
        timeout_seconds: int,
    ) -> StdioPlaywrightMcpClient:
        signature = (tuple(command), cwd, timeout_seconds)
        with cls._lock:
            if cls._stdio_client is None or cls._signature != signature:
                if cls._stdio_client is not None:
                    cls._stdio_client.close()
                cls._stdio_client = StdioPlaywrightMcpClient(command, cwd, timeout_seconds)
                cls._signature = signature
            return cls._stdio_client
