from typing import Optional

from fastapi import APIRouter, Depends, Header, Query

from core.security import current_token_payload, require_admin
from models.schemas import MeterReading, MeterReadingBatch
from services import analytics as analytics_service
from services import audit
from services import devices as device_service
from services import monitoring as monitoring_service
from services import readings as reading_service
from services.websocket import ws_manager

router = APIRouter(prefix="/api")


@router.get("/summary")
async def summary(_: dict = Depends(current_token_payload)):
    return await monitoring_service.summary()


@router.get("/analytics/hourly")
async def hourly_stats(
    building_id: Optional[int] = None,
    utility_type: Optional[str] = None,
    device_id: Optional[str] = None,
    hours: int = Query(24, ge=1, le=720),
    limit: int = Query(500, ge=1, le=2000),
    _: dict = Depends(current_token_payload),
):
    return await analytics_service.list_hourly_stats(building_id, utility_type, device_id, hours, limit)


@router.post("/analytics/hourly/aggregate")
async def aggregate_hourly_stats(
    hours: int = Query(48, ge=1, le=720),
    admin: dict = Depends(require_admin),
):
    result = await analytics_service.aggregate_hourly_stats_once(hours)
    await audit.record(admin, "analytics.aggregate_hourly", "hourly_utility_stats", None, {"hours": hours, **result})
    return result


@router.post("/readings")
async def post_readings(body: MeterReading, x_device_token: Optional[str] = Header(None)):
    await device_service.verify_device_access(body.device_id, x_device_token)
    ts = await reading_service.save_reading(body)
    await ws_manager.broadcast(
        {"type": "reading", "device_id": body.device_id, "ts": ts, "data": body.model_dump()}
    )
    return {"ok": True, "ts": ts}


@router.post("/readings/batch")
async def post_readings_batch(body: MeterReadingBatch, x_device_token: Optional[str] = Header(None)):
    device_id = body.device_id or (body.readings[0].device_id if body.readings else None)
    await device_service.verify_device_access(device_id, x_device_token)
    result = await reading_service.save_reading_batch(body)
    await ws_manager.broadcast({"type": "readings_batch", "device_id": body.device_id, "result": result})
    return result
