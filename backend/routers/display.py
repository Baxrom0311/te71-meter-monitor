from fastapi import APIRouter
from services import analytics as analytics_service

router = APIRouter(prefix="/api/public")


@router.get("/display")
async def public_display():
    """Ko'rgazma uchun ochiq endpoint — auth talab qilinmaydi."""
    electricity = await analytics_service.list_hourly_stats(utility_type="electricity", hours=24, limit=500)
    water = await analytics_service.list_hourly_stats(utility_type="water", hours=24, limit=500)
    gas = await analytics_service.list_hourly_stats(utility_type="gas", hours=24, limit=500)
    return {
        "electricity": electricity["stats"],
        "water": water["stats"],
        "gas": gas["stats"],
    }
