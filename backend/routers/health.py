from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from sqlalchemy import text

from core.database import SessionLocal
from models.schemas import HealthResponse, ReadyResponse
from services import monitoring

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    return await monitoring.health()


@router.get("/ready", response_model=ReadyResponse)
async def ready():
    async with SessionLocal() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ready", "checks": {"database": "ok"}}


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    return PlainTextResponse(await monitoring.metrics_text(), media_type="text/plain; version=0.0.4")
