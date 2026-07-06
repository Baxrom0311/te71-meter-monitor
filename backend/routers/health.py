from fastapi import APIRouter

from services import platform

router = APIRouter()


@router.get("/health")
async def health():
    return await platform.health()
