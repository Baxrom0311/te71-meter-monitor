from fastapi import APIRouter
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
