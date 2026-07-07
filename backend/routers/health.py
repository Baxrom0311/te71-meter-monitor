from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from redis.asyncio import Redis
from sqlalchemy import text

from core.config import settings
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
    checks = {"database": "ok"}
    if settings.ready_check_redis:
        redis = Redis.from_url(settings.celery_broker_url, socket_connect_timeout=2, socket_timeout=2)
        try:
            await redis.ping()
            checks["redis"] = "ok"
        finally:
            await redis.aclose()
    else:
        checks["redis"] = "skipped"
    return {"status": "ready", "checks": checks}


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    return PlainTextResponse(await monitoring.metrics_text(), media_type="text/plain; version=0.0.4")
