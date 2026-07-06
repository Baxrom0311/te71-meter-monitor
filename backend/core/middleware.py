import logging
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from core.config import settings

logger = logging.getLogger("meter_monitor.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "%s %s %s %.2fms request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if request.url.path in {"/health", "/ready"} or request.url.path.startswith("/static/"):
            return await call_next(request)

        limit = settings.device_rate_limit_per_minute if self._is_device_path(request.url.path) else settings.rate_limit_per_minute
        if limit > 0 and self._too_many_requests(request, limit):
            return JSONResponse(
                {"detail": "Rate limit oshib ketdi"},
                status_code=429,
                headers={"Retry-After": "60"},
            )
        return await call_next(request)

    def _too_many_requests(self, request: Request, limit: int) -> bool:
        now = time.monotonic()
        window_start = now - 60
        key = self._client_key(request)
        hits = self._hits[key]
        while hits and hits[0] < window_start:
            hits.popleft()
        if len(hits) >= limit:
            return True
        hits.append(now)
        return False

    @staticmethod
    def _is_device_path(path: str) -> bool:
        return path in {"/api/register", "/api/device-status"} or path.startswith(
            ("/api/status/", "/api/commands/", "/api/device-config/", "/api/ota/check/", "/api/ota/firmware/")
        ) or path.startswith("/api/readings")

    @staticmethod
    def _client_key(request: Request) -> str:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            host = forwarded_for.split(",", 1)[0].strip()
        elif request.client:
            host = request.client.host
        else:
            host = "unknown"
        return f"{host}:{request.url.path}"
