from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from sqlalchemy import text

from core.database import SessionLocal
from services import platform

router = APIRouter()


@router.get("/health")
async def health():
    return await platform.health()


@router.get("/ready")
async def ready():
    async with SessionLocal() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ready"}


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    return PlainTextResponse(await platform.metrics_text(), media_type="text/plain; version=0.0.4")
