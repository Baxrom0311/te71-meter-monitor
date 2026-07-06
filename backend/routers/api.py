from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, Response

from core.config import settings
from core.security import current_token_payload, require_admin, require_device_token
from models.schemas import (
    BuildingCreate,
    BuildingDefaultProvision,
    BuildingUtilityCreate,
    BuildingUtilityUpdate,
    BuildingUpdate,
    CommandCreate,
    DeviceRegister,
    DeviceStatus,
    DeviceUpdate,
    MeasurementPointCreate,
    MeasurementPointDeviceBind,
    MeasurementPointUpdate,
    MeterReadingBatch,
    MeterReading,
    PremiseCreate,
    RelayCommand,
)
from services import platform
from services.websocket import ws_manager

router = APIRouter(prefix="/api")


@router.post("/buildings")
async def create_building(body: BuildingCreate, _: dict = Depends(require_admin)):
    return await platform.create_building(body)


@router.get("/buildings")
async def list_buildings(_: dict = Depends(current_token_payload)):
    return await platform.list_buildings()


@router.get("/buildings/{building_id}")
async def get_building(building_id: int, _: dict = Depends(current_token_payload)):
    return await platform.get_building(building_id)


@router.put("/buildings/{building_id}")
async def update_building(
    building_id: int,
    body: BuildingUpdate,
    _: dict = Depends(require_admin),
):
    return await platform.update_building(building_id, body)


@router.delete("/buildings/{building_id}")
async def delete_building(building_id: int, _: dict = Depends(require_admin)):
    return await platform.delete_building(building_id)


@router.post("/buildings/{building_id}/utilities")
async def create_building_utility(
    building_id: int,
    body: BuildingUtilityCreate,
    _: dict = Depends(require_admin),
):
    body.building_id = building_id
    return await platform.create_building_utility(body)


@router.get("/buildings/{building_id}/utilities")
async def list_building_utilities(building_id: int, _: dict = Depends(current_token_payload)):
    return await platform.list_building_utilities(building_id)


@router.put("/buildings/{building_id}/utilities/{utility_id}")
async def update_building_utility(
    building_id: int,
    utility_id: int,
    body: BuildingUtilityUpdate,
    _: dict = Depends(require_admin),
):
    return await platform.update_building_utility(building_id, utility_id, body)


@router.post("/buildings/{building_id}/provision-defaults")
async def provision_building_defaults(
    building_id: int,
    body: BuildingDefaultProvision,
    _: dict = Depends(require_admin),
):
    return await platform.provision_building_defaults(building_id, body)


@router.get("/buildings/{building_id}/readings/latest")
async def building_latest_readings(
    building_id: int,
    utility_type: Optional[str] = None,
    _: dict = Depends(current_token_payload),
):
    return await platform.building_latest_readings(building_id, utility_type)


@router.get("/buildings/{building_id}/readings/history")
async def building_reading_history(
    building_id: int,
    utility_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=1000),
    hours: Optional[int] = None,
    _: dict = Depends(current_token_payload),
):
    return await platform.building_reading_history(building_id, utility_type, page, limit, hours)


@router.get("/buildings/{building_id}/analytics")
async def building_analytics(
    building_id: int,
    hours: int = Query(24, ge=1, le=720),
    _: dict = Depends(current_token_payload),
):
    return await platform.building_analytics(building_id, hours)


@router.post("/premises")
async def create_premise(body: PremiseCreate, _: dict = Depends(require_admin)):
    return await platform.create_premise(body)


@router.get("/premises")
async def list_premises(building_id: Optional[int] = None, _: dict = Depends(current_token_payload)):
    return await platform.list_premises(building_id)


@router.post("/measurement-points")
async def create_measurement_point(body: MeasurementPointCreate, _: dict = Depends(require_admin)):
    return await platform.create_measurement_point(body)


@router.get("/measurement-points")
async def list_measurement_points(
    building_id: Optional[int] = None,
    utility_type: Optional[str] = None,
    role: Optional[str] = None,
    _: dict = Depends(current_token_payload),
):
    return await platform.list_measurement_points(building_id, utility_type, role)


@router.get("/measurement-points/{point_id}")
async def get_measurement_point(point_id: int, _: dict = Depends(current_token_payload)):
    return await platform.get_measurement_point(point_id)


@router.put("/measurement-points/{point_id}")
async def update_measurement_point(
    point_id: int,
    body: MeasurementPointUpdate,
    _: dict = Depends(require_admin),
):
    return await platform.update_measurement_point(point_id, body)


@router.post("/measurement-points/{point_id}/bind-device")
async def bind_measurement_point_device(
    point_id: int,
    body: MeasurementPointDeviceBind,
    _: dict = Depends(require_admin),
):
    return await platform.bind_measurement_point_device(point_id, body)


@router.delete("/measurement-points/{point_id}")
async def delete_measurement_point(point_id: int, _: dict = Depends(require_admin)):
    return await platform.delete_measurement_point(point_id)


@router.post("/register")
async def register_device(body: DeviceRegister, _: bool = Depends(require_device_token)):
    return await platform.register_device(body)


@router.post("/device-status")
async def device_status(body: DeviceStatus, _: bool = Depends(require_device_token)):
    return await platform.update_device_status(body)


@router.get("/device-config/{device_id}")
async def device_config(device_id: str, _: bool = Depends(require_device_token)):
    return await platform.get_device_config(device_id)


@router.get("/devices")
async def list_devices(
    online: Optional[bool] = None,
    type: Optional[str] = None,
    group: Optional[str] = None,
    building: Optional[str] = None,
    utility_type: Optional[str] = None,
    _: dict = Depends(current_token_payload),
):
    return await platform.list_devices(online, type, group, building, utility_type)


@router.get("/devices/{device_id}")
async def get_device(device_id: str, _: dict = Depends(current_token_payload)):
    return await platform.get_device(device_id)


@router.put("/devices/{device_id}")
async def update_device(device_id: str, body: DeviceUpdate, _: dict = Depends(require_admin)):
    return await platform.update_device(device_id, body)


@router.get("/devices/{device_id}/latest")
async def device_latest(device_id: str, _: dict = Depends(current_token_payload)):
    return await platform.latest_reading(device_id)


@router.get("/devices/{device_id}/history")
async def device_history(
    device_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=1000),
    hours: Optional[int] = None,
    _: dict = Depends(current_token_payload),
):
    return await platform.reading_history(device_id, page, limit, hours)


@router.get("/devices/{device_id}/stats")
async def device_stats(
    device_id: str,
    hours: int = Query(24, ge=1, le=720),
    _: dict = Depends(current_token_payload),
):
    return await platform.reading_stats(device_id, hours)


@router.get("/devices/{device_id}/export")
async def export_csv(
    device_id: str,
    hours: int = Query(24, ge=1, le=720),
    _: dict = Depends(current_token_payload),
):
    filename, content = await platform.export_csv(device_id, hours)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/summary")
async def summary(_: dict = Depends(current_token_payload)):
    return await platform.summary()


@router.post("/devices/{device_id}/relay")
async def relay_command(device_id: str, body: RelayCommand, _: dict = Depends(require_admin)):
    return await platform.create_relay_command(device_id, body.action)


@router.post("/devices/{device_id}/reboot")
async def reboot_device(device_id: str, _: dict = Depends(require_admin)):
    return await platform.reboot_device(device_id)


@router.post("/devices/{device_id}/commands")
async def create_device_command(device_id: str, body: CommandCreate, _: dict = Depends(require_admin)):
    return await platform.create_command(device_id, body.action, body.params)


@router.get("/commands/{device_id}")
async def get_commands(device_id: str, _: bool = Depends(require_device_token)):
    return await platform.pending_commands(device_id)


@router.post("/commands/{cmd_id}/ack")
async def ack_command(cmd_id: int, result: str = "ok", _: bool = Depends(require_device_token)):
    return await platform.ack_command(cmd_id, result)


@router.post("/readings")
async def post_readings(body: MeterReading, _: bool = Depends(require_device_token)):
    ts = await platform.save_reading(body)
    await ws_manager.broadcast(
        {"type": "reading", "device_id": body.device_id, "ts": ts, "data": body.model_dump()}
    )
    return {"ok": True, "ts": ts}


@router.post("/readings/batch")
async def post_readings_batch(body: MeterReadingBatch, _: bool = Depends(require_device_token)):
    result = await platform.save_reading_batch(body)
    await ws_manager.broadcast({"type": "readings_batch", "device_id": body.device_id, "result": result})
    return result


@router.get("/alerts")
async def get_alerts(
    device_id: Optional[str] = None,
    kind: Optional[str] = None,
    cleared: bool = False,
    limit: int = Query(50, ge=1, le=500),
    _: dict = Depends(current_token_payload),
):
    return await platform.get_alerts(device_id, kind, cleared, limit)


@router.post("/alerts/{alert_id}/clear")
async def clear_alert(alert_id: int, _: dict = Depends(require_admin)):
    return await platform.clear_alert(alert_id)


@router.post("/alerts/clear-all")
async def clear_all_alerts(device_id: Optional[str] = None, _: dict = Depends(require_admin)):
    return await platform.clear_all_alerts(device_id)


@router.post("/ota/upload")
async def ota_upload(
    version: str = Form(...),
    notes: str = Form(""),
    hardware_version: Optional[str] = Form(None),
    firmware_mode: str = Form("auto"),
    file: UploadFile = File(...),
    _: dict = Depends(require_admin),
):
    return await platform.ota_upload(version, notes, file, hardware_version, firmware_mode)


@router.get("/ota/list")
async def ota_list(_: dict = Depends(current_token_payload)):
    return await platform.ota_list()


@router.delete("/ota/{fw_id}")
async def ota_delete(fw_id: int, _: dict = Depends(require_admin)):
    return await platform.ota_delete(fw_id)


@router.get("/ota/check/{device_id}")
async def ota_check(device_id: str, current_version: str = "", _: bool = Depends(require_device_token)):
    return await platform.ota_check(device_id, current_version)


@router.get("/ota/firmware/{filename}")
async def ota_download(filename: str, _: bool = Depends(require_device_token)):
    path = Path(settings.ota_dir) / filename
    if not path.exists():
        from fastapi import HTTPException

        raise HTTPException(404, "Firmware topilmadi")
    return FileResponse(str(path), media_type="application/octet-stream")


@router.post("/ota/push/{device_id}")
async def ota_push(device_id: str, _: dict = Depends(require_admin)):
    return await platform.ota_push(device_id)
