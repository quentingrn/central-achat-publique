import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("api.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        trace_id = getattr(request.state, "trace_id", "-")
        logger.info(
            "%s %s -> %s (%.2fms) trace_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            trace_id,
        )
        return response
