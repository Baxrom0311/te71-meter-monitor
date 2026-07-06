import asyncio
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.config import settings
from core.logging import configure_logging
from core.database import init_db
from core.middleware import (
    InMemoryRateLimitMiddleware,
    RequestContextMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)
from routers.auth import router as auth_router
from routers.api import router as api_router
from routers.health import router as health_router
from routers.websocket import router as websocket_router
from services.auth import bootstrap_admin
from services.background import data_cleanup, offline_detector
from services.platform import build_snapshot
from services.websocket import ws_manager

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_runtime()
    await init_db()
    await bootstrap_admin()
    ws_manager.set_snapshot_provider(build_snapshot)
    if settings.run_inline_workers:
        asyncio.create_task(offline_detector())
        asyncio.create_task(data_cleanup())
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(InMemoryRateLimitMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        {"detail": exc.detail, "request_id": getattr(request.state, "request_id", None)},
        status_code=exc.status_code,
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logging.exception("Unhandled error request_id=%s", getattr(request.state, "request_id", None))
    return JSONResponse(
        {"detail": "Ichki server xatosi", "request_id": getattr(request.state, "request_id", None)},
        status_code=500,
    )

app.include_router(api_router)
app.include_router(auth_router)
app.include_router(websocket_router)
app.include_router(health_router)

if settings.static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    index_file = settings.static_dir / "index.html"
    if index_file.exists():
        return HTMLResponse(index_file.read_text(encoding="utf-8"))
    return HTMLResponse(f"<h1>{settings.app_name} v{settings.app_version}</h1>")
