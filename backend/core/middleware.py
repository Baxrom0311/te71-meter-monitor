import logging
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from core.config import settings
from core.metrics import observe_http_request

logger = logging.getLogger("meter_monitor.access")


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _route_path(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path or request.url.path


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_seconds = time.perf_counter() - started
        elapsed_ms = round(elapsed_seconds * 1000, 2)
        route = _route_path(request)
        observe_http_request(request.method, route, response.status_code, elapsed_seconds)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "%s %s %s %.2fms request_id=%s",
            request.method,
            route,
            response.status_code,
            elapsed_ms,
            request_id,
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": route,
                "status_code": response.status_code,
                "elapsed_ms": elapsed_ms,
                "client_ip": _client_ip(request),
                "user_agent": request.headers.get("User-Agent"),
            },
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


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        content_length = request.headers.get("Content-Length")
        if content_length and settings.max_request_body_bytes > 0:
            try:
                size = int(content_length)
            except ValueError:
                size = 0
            if size > settings.max_request_body_bytes:
                return JSONResponse(
                    {"detail": "Request body juda katta"},
                    status_code=413,
                )
        return await call_next(request)


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    _CLEANUP_INTERVAL = 300  # har 5 daqiqada tozalash

    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._last_cleanup: float = time.monotonic()

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if request.url.path in {"/health", "/ready"} or request.url.path.startswith("/static/"):
            return await call_next(request)

        # Periodic cleanup — eski va bo'sh entrylarni tozalash
        now = time.monotonic()
        if now - self._last_cleanup > self._CLEANUP_INTERVAL:
            self._cleanup_stale_entries(now)
            self._last_cleanup = now

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

    def _cleanup_stale_entries(self, now: float) -> None:
        """Bo'sh yoki 60s dan eski entrylarni tozalash — memory leak oldini olish."""
        window_start = now - 60
        stale_keys = [
            key for key, hits in self._hits.items()
            if not hits or hits[-1] < window_start
        ]
        for key in stale_keys:
            del self._hits[key]

    @staticmethod
    def _is_device_path(path: str) -> bool:
        return path in {"/api/register", "/api/device-status"} or path.startswith(
            ("/api/status/", "/api/commands/", "/api/device-config/", "/api/ota/check/", "/api/ota/firmware/")
        ) or path.startswith("/api/readings")

    @staticmethod
    def _client_key(request: Request) -> str:
        host = _client_ip(request)
        return f"{host}:{request.url.path}"
