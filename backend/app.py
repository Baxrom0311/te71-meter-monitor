import asyncio
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
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
from routers.alerts import router as alerts_router
from routers.audit import router as audit_router
from routers.auth import router as auth_router
from routers.backups import router as backups_router
from routers.buildings import router as buildings_router
from routers.commands import router as commands_router
from routers.devices import router as devices_router
from routers.health import router as health_router
from routers.ota import router as ota_router
from routers.telemetry import router as telemetry_router
from routers.websocket import router as websocket_router
from routers.chat import router as chat_router
from services.auth import bootstrap_admin
from services.background import (
    alert_notification_worker,
    analytics_worker,
    audit_cleanup_worker,
    command_cleanup_worker,
    data_cleanup,
    offline_detector,
    ota_batch_worker,
)
from services.monitoring import build_snapshot
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
        asyncio.create_task(alert_notification_worker())
        asyncio.create_task(command_cleanup_worker())
        asyncio.create_task(audit_cleanup_worker())
        asyncio.create_task(analytics_worker())
        asyncio.create_task(ota_batch_worker())
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(InMemoryRateLimitMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
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

app.include_router(alerts_router)
app.include_router(audit_router)
app.include_router(backups_router)
app.include_router(buildings_router)
app.include_router(devices_router)
app.include_router(commands_router)
app.include_router(telemetry_router)
app.include_router(ota_router)
app.include_router(auth_router)
app.include_router(websocket_router)
app.include_router(health_router)
app.include_router(chat_router)

# Vite frontend static assets.
if settings.static_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(settings.static_dir / "assets")), name="assets")

# SPA catch-all — barcha /api/* dan tashqari yo'llar index.html qaytaradi
@app.get("/{full_path:path}", response_class=HTMLResponse)
async def spa_fallback(full_path: str):
    index_file = settings.static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse(f"<h1>{settings.app_name} v{settings.app_version}</h1>")
