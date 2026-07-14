from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from core.config import settings
from core.security import current_token_payload, require_admin
from models.schemas import (
    AnalyticsAggregateResponse,
    BuildingsEnergySummaryResponse,
    EnergyByBuildingResponse,
    HourlyUtilityStatsResponse,
    MeterReading,
    MeterReadingBatch,
    ReadingBatchResponse,
    ReadingIngestResponse,
    SummaryResponse,
    TestDeviceSimulationRequest,
    TestDeviceSimulationResponse,
)
from services import analytics as analytics_service
from services import audit
from services import devices as device_service
from services import monitoring as monitoring_service
from services import readings as reading_service
from services.websocket import ws_manager

router = APIRouter(prefix="/api")


@router.get("/summary", response_model=SummaryResponse)
async def summary(_: dict = Depends(current_token_payload)):
    return await monitoring_service.summary()


@router.get("/analytics/hourly", response_model=HourlyUtilityStatsResponse)
async def hourly_stats(
    building_id: Optional[int] = None,
    utility_type: Optional[str] = None,
    device_id: Optional[str] = None,
    hours: int = Query(24, ge=1, le=720),
    limit: int = Query(500, ge=1, le=2000),
    _: dict = Depends(current_token_payload),
):
    return await analytics_service.list_hourly_stats(building_id, utility_type, device_id, hours, limit)


@router.get("/analytics/energy", response_model=EnergyByBuildingResponse)
async def energy_by_building(
    from_ts: int = Query(..., description="Boshlang'ich unix timestamp"),
    to_ts: int = Query(..., description="Tugash unix timestamp"),
    building_id: Optional[int] = None,
    granularity: str = Query("day", pattern="^(hour|day|month)$"),
    _: dict = Depends(current_token_payload),
):
    return await analytics_service.energy_by_building(from_ts, to_ts, building_id, granularity)


@router.get("/analytics/energy/summary", response_model=BuildingsEnergySummaryResponse)
async def buildings_energy_summary(_: dict = Depends(current_token_payload)):
    return await analytics_service.buildings_energy_summary()


@router.post("/analytics/hourly/aggregate", response_model=AnalyticsAggregateResponse)
async def aggregate_hourly_stats(
    hours: int = Query(48, ge=1, le=720),
    admin: dict = Depends(require_admin),
):
    result = await analytics_service.aggregate_hourly_stats_once(hours)
    await audit.record(admin, "analytics.aggregate_hourly", "hourly_utility_stats", None, {"hours": hours, **result})
    return result


@router.post("/readings", response_model=ReadingIngestResponse)
async def post_readings(body: MeterReading, x_device_token: Optional[str] = Header(None)):
    await device_service.verify_device_access(body.device_id, x_device_token)
    ts = await reading_service.save_reading(body, test_mode=device_service.is_test_device_token(x_device_token))
    await ws_manager.broadcast(
        {"type": "reading", "device_id": body.device_id, "ts": ts, "data": body.model_dump()}
    )
    return {"ok": True, "ts": ts}


@router.post("/readings/batch", response_model=ReadingBatchResponse)
async def post_readings_batch(body: MeterReadingBatch, x_device_token: Optional[str] = Header(None)):
    device_id = body.device_id or (body.readings[0].device_id if body.readings else None)
    await device_service.verify_device_access(device_id, x_device_token)
    result = await reading_service.save_reading_batch(body, test_mode=device_service.is_test_device_token(x_device_token))
    await ws_manager.broadcast({"type": "readings_batch", "device_id": device_id, "result": result})
    return result


@router.post("/test-devices/simulate-reading", response_model=TestDeviceSimulationResponse)
async def simulate_test_device_reading(body: TestDeviceSimulationRequest, admin: dict = Depends(require_admin)):
    if body.production_guard_only:
        try:
            await device_service.verify_device_access(body.device_id, settings.test_device_api_token)
        except HTTPException as exc:
            await audit.record(
                admin,
                "test_device.guard_check",
                "device",
                body.device_id,
                {"guarded": True, "message": str(getattr(exc, "detail", exc))},
            )
            return {
                "ok": True,
                "saved": False,
                "guarded": True,
                "message": "Test token bu device uchun yozishga ruxsat olmadi.",
            }
        return {
            "ok": True,
            "saved": False,
            "guarded": False,
            "message": "Bu MAC yangi yoki avvaldan test device: test token bilan yozish mumkin.",
        }

    reading = MeterReading(
        device_id=body.device_id,
        utility_type=body.utility_type,
        meter_serial=body.meter_serial,
        energy_kwh=body.energy_kwh,
        voltage_l1=220,
        frequency=50,
        pf=0.98,
        fw_version="simulator",
        hardware_version="admin-test",
    )
    ts = await reading_service.save_reading(reading, test_mode=True)
    device = await device_service.get_device(body.device_id)
    await audit.record(
        admin,
        "test_device.simulate_reading",
        "device",
        body.device_id,
        {"meter_serial": body.meter_serial, "ts": ts},
    )
    await ws_manager.broadcast({"type": "reading", "device_id": body.device_id, "ts": ts, "data": reading.model_dump()})
    return {
        "ok": True,
        "saved": True,
        "guarded": False,
        "message": "Test reading saqlandi.",
        "ts": ts,
        "device": device,
    }
