import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from core.config import settings
from core.database import init_db
from routers.auth import router as auth_router
from routers.api import router as api_router
from routers.health import router as health_router
from routers.websocket import router as websocket_router
from services.auth import bootstrap_admin
from services.background import data_cleanup, offline_detector
from services.platform import build_snapshot
from services.websocket import ws_manager

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await bootstrap_admin()
    ws_manager.set_snapshot_provider(build_snapshot)
    if settings.run_inline_workers:
        asyncio.create_task(offline_detector())
        asyncio.create_task(data_cleanup())
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

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
