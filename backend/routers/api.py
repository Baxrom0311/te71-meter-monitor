from pathlib import Path
from typing import Optional

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile
from fastapi import HTTPException
from fastapi.responses import FileResponse, Response

from core.celery_app import celery_app
from core.config import settings
from core.security import current_token_payload, require_admin, require_device_token
from models.schemas import (
    BuildingCreate,
    BuildingDefaultProvision,
    BuildingUtilityCreate,
    BuildingUtilityUpdate,
    BuildingUpdate,
    CommandCreate,
    DeviceProvisioningTokenCreate,
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
from services import audit
from services.backup import backup_file_path, delete_backup, list_backups
from tasks.backup import cleanup_old_backups as cleanup_old_backups_task
from tasks.backup import create_backup as create_backup_task
from services.websocket import ws_manager

router = APIRouter(prefix="/api")


@router.post("/buildings")
async def create_building(body: BuildingCreate, admin: dict = Depends(require_admin)):
    result = await platform.create_building(body)
    await audit.record(admin, "building.create", "building", result.get("id"), body.model_dump())
    return result


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
    admin: dict = Depends(require_admin),
):
    result = await platform.update_building(building_id, body)
    await audit.record(admin, "building.update", "building", building_id, body.model_dump(exclude_none=True))
    return result


@router.delete("/buildings/{building_id}")
async def delete_building(building_id: int, admin: dict = Depends(require_admin)):
    result = await platform.delete_building(building_id)
    await audit.record(admin, "building.delete", "building", building_id)
    return result


@router.post("/buildings/{building_id}/utilities")
async def create_building_utility(
    building_id: int,
    body: BuildingUtilityCreate,
    admin: dict = Depends(require_admin),
):
    body.building_id = building_id
    result = await platform.create_building_utility(body)
    await audit.record(admin, "building_utility.create", "building", building_id, body.model_dump())
    return result


@router.get("/buildings/{building_id}/utilities")
async def list_building_utilities(building_id: int, _: dict = Depends(current_token_payload)):
    return await platform.list_building_utilities(building_id)


@router.put("/buildings/{building_id}/utilities/{utility_id}")
async def update_building_utility(
    building_id: int,
    utility_id: int,
    body: BuildingUtilityUpdate,
    admin: dict = Depends(require_admin),
):
    result = await platform.update_building_utility(building_id, utility_id, body)
    await audit.record(admin, "building_utility.update", "building_utility", utility_id, body.model_dump(exclude_none=True))
    return result


@router.post("/buildings/{building_id}/provision-defaults")
async def provision_building_defaults(
    building_id: int,
    body: BuildingDefaultProvision,
    admin: dict = Depends(require_admin),
):
    result = await platform.provision_building_defaults(building_id, body)
    await audit.record(admin, "building.provision_defaults", "building", building_id, body.model_dump())
    return result


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
async def create_premise(body: PremiseCreate, admin: dict = Depends(require_admin)):
    result = await platform.create_premise(body)
    await audit.record(admin, "premise.create", "premise", result.get("id"), body.model_dump())
    return result


@router.get("/premises")
async def list_premises(building_id: Optional[int] = None, _: dict = Depends(current_token_payload)):
    return await platform.list_premises(building_id)


@router.post("/measurement-points")
async def create_measurement_point(body: MeasurementPointCreate, admin: dict = Depends(require_admin)):
    result = await platform.create_measurement_point(body)
    await audit.record(admin, "measurement_point.create", "measurement_point", result.get("id"), body.model_dump())
    return result


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
    admin: dict = Depends(require_admin),
):
    result = await platform.update_measurement_point(point_id, body)
    await audit.record(admin, "measurement_point.update", "measurement_point", point_id, body.model_dump(exclude_none=True))
    return result


@router.post("/measurement-points/{point_id}/bind-device")
async def bind_measurement_point_device(
    point_id: int,
    body: MeasurementPointDeviceBind,
    admin: dict = Depends(require_admin),
):
    result = await platform.bind_measurement_point_device(point_id, body)
    await audit.record(admin, "measurement_point.bind_device", "measurement_point", point_id, body.model_dump())
    return result


@router.delete("/measurement-points/{point_id}")
async def delete_measurement_point(point_id: int, admin: dict = Depends(require_admin)):
    result = await platform.delete_measurement_point(point_id)
    await audit.record(admin, "measurement_point.delete", "measurement_point", point_id)
    return result


@router.post("/register")
async def register_device(body: DeviceRegister, x_device_token: Optional[str] = Header(None)):
    if not body.provisioning_token:
        await platform.verify_device_access(body.device_id, x_device_token)
    return await platform.register_device(body)


@router.post("/device-status")
async def device_status(body: DeviceStatus, x_device_token: Optional[str] = Header(None)):
    await platform.verify_device_access(body.device_id, x_device_token)
    return await platform.update_device_status(body)


@router.get("/device-config/{device_id}")
async def device_config(device_id: str, x_device_token: Optional[str] = Header(None)):
    await platform.verify_device_access(device_id, x_device_token)
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


@router.post("/devices/provisioning-tokens")
async def create_device_provisioning_token(
    body: DeviceProvisioningTokenCreate,
    admin: dict = Depends(require_admin),
):
    result = await platform.create_provisioning_token(body, admin)
    audit_detail = {k: v for k, v in result.items() if k != "provisioning_token"}
    await audit.record(admin, "device.provisioning_token.create", "device_provisioning_token", result["id"], audit_detail)
    return result


@router.get("/devices/provisioning-tokens")
async def list_device_provisioning_tokens(
    active_only: bool = True,
    limit: int = Query(100, ge=1, le=500),
    _: dict = Depends(require_admin),
):
    return await platform.list_provisioning_tokens(active_only=active_only, limit=limit)


@router.get("/devices/{device_id}")
async def get_device(device_id: str, _: dict = Depends(current_token_payload)):
    return await platform.get_device(device_id)


@router.put("/devices/{device_id}")
async def update_device(device_id: str, body: DeviceUpdate, admin: dict = Depends(require_admin)):
    result = await platform.update_device(device_id, body)
    await audit.record(admin, "device.update", "device", device_id, body.model_dump(exclude_none=True))
    return result


@router.post("/devices/{device_id}/token")
async def rotate_device_token(device_id: str, admin: dict = Depends(require_admin)):
    result = await platform.rotate_device_token(device_id)
    await audit.record(admin, "device.rotate_token", "device", device_id)
    return result


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
async def relay_command(device_id: str, body: RelayCommand, admin: dict = Depends(require_admin)):
    result = await platform.create_relay_command(device_id, body.action)
    await audit.record(admin, "device.relay", "device", device_id, body.model_dump())
    return result


@router.post("/devices/{device_id}/reboot")
async def reboot_device(device_id: str, admin: dict = Depends(require_admin)):
    result = await platform.reboot_device(device_id)
    await audit.record(admin, "device.reboot", "device", device_id)
    return result


@router.post("/devices/{device_id}/commands")
async def create_device_command(device_id: str, body: CommandCreate, admin: dict = Depends(require_admin)):
    result = await platform.create_command(device_id, body.action, body.params)
    await audit.record(admin, "device.command", "device", device_id, body.model_dump())
    return result


@router.get("/commands/admin/list")
async def list_commands(
    device_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    _: dict = Depends(require_admin),
):
    return await platform.list_commands(device_id, status, limit)


@router.get("/commands/{device_id}")
async def get_commands(device_id: str, x_device_token: Optional[str] = Header(None)):
    await platform.verify_device_access(device_id, x_device_token)
    return await platform.pending_commands(device_id)


@router.post("/commands/{cmd_id}/ack")
async def ack_command(cmd_id: int, result: str = "ok", x_device_token: Optional[str] = Header(None)):
    await platform.verify_command_access(cmd_id, x_device_token)
    return await platform.ack_command(cmd_id, result)


@router.post("/readings")
async def post_readings(body: MeterReading, x_device_token: Optional[str] = Header(None)):
    await platform.verify_device_access(body.device_id, x_device_token)
    ts = await platform.save_reading(body)
    await ws_manager.broadcast(
        {"type": "reading", "device_id": body.device_id, "ts": ts, "data": body.model_dump()}
    )
    return {"ok": True, "ts": ts}


@router.post("/readings/batch")
async def post_readings_batch(body: MeterReadingBatch, x_device_token: Optional[str] = Header(None)):
    device_id = body.device_id or (body.readings[0].device_id if body.readings else None)
    await platform.verify_device_access(device_id, x_device_token)
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
async def clear_alert(alert_id: int, admin: dict = Depends(require_admin)):
    result = await platform.clear_alert(alert_id)
    await audit.record(admin, "alert.clear", "alert", alert_id)
    return result


@router.post("/alerts/clear-all")
async def clear_all_alerts(device_id: Optional[str] = None, admin: dict = Depends(require_admin)):
    result = await platform.clear_all_alerts(device_id)
    await audit.record(admin, "alert.clear_all", "alert", device_id, {"device_id": device_id})
    return result


@router.post("/ota/upload")
async def ota_upload(
    version: str = Form(...),
    notes: str = Form(""),
    hardware_version: Optional[str] = Form(None),
    firmware_mode: str = Form("auto"),
    utility_type: Optional[str] = Form(None),
    device_role: Optional[str] = Form(None),
    sensor_type: Optional[str] = Form(None),
    converter_type: Optional[str] = Form(None),
    description: str = Form(""),
    release_notes: str = Form(""),
    compatibility_notes: str = Form(""),
    file: UploadFile = File(...),
    admin: dict = Depends(require_admin),
):
    result = await platform.ota_upload(
        version=version,
        notes=notes,
        file=file,
        hardware_version=hardware_version,
        firmware_mode=firmware_mode,
        utility_type=utility_type,
        device_role=device_role,
        sensor_type=sensor_type,
        converter_type=converter_type,
        description=description,
        release_notes=release_notes,
        compatibility_notes=compatibility_notes,
    )
    await audit.record(
        admin,
        "ota.upload",
        "firmware",
        result.get("id"),
        {
            "version": version,
            "hardware_version": hardware_version,
            "firmware_mode": firmware_mode,
            "utility_type": utility_type,
            "device_role": device_role,
            "sensor_type": sensor_type,
            "converter_type": converter_type,
        },
    )
    return result


@router.get("/ota/list")
async def ota_list(_: dict = Depends(current_token_payload)):
    return await platform.ota_list()


@router.delete("/ota/{fw_id}")
async def ota_delete(fw_id: int, admin: dict = Depends(require_admin)):
    result = await platform.ota_delete(fw_id)
    await audit.record(admin, "ota.delete", "firmware", fw_id)
    return result


@router.get("/ota/check/{device_id}")
async def ota_check(device_id: str, current_version: str = "", x_device_token: Optional[str] = Header(None)):
    await platform.verify_device_access(device_id, x_device_token)
    return await platform.ota_check(device_id, current_version)


@router.get("/ota/firmware/{filename}")
async def ota_download(
    filename: str,
    device_id: Optional[str] = None,
    x_device_token: Optional[str] = Header(None),
):
    if device_id:
        await platform.verify_device_access(device_id, x_device_token)
    else:
        await require_device_token(x_device_token)
    path = Path(settings.ota_dir) / filename
    if not path.exists():
        from fastapi import HTTPException

        raise HTTPException(404, "Firmware topilmadi")
    return FileResponse(str(path), media_type="application/octet-stream")


@router.post("/ota/push/{device_id}")
async def ota_push(device_id: str, admin: dict = Depends(require_admin)):
    result = await platform.ota_push(device_id)
    await audit.record(admin, "ota.push", "device", device_id)
    return result


@router.get("/audit-logs")
async def audit_logs(
    limit: int = Query(100, ge=1, le=500),
    page: int = Query(1, ge=1),
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    username: Optional[str] = None,
    user_id: Optional[int] = None,
    since_ts: Optional[int] = None,
    until_ts: Optional[int] = None,
    _: dict = Depends(require_admin),
):
    return await audit.list_logs(limit, page, action, entity_type, entity_id, username, user_id, since_ts, until_ts)


@router.post("/backups")
async def create_backup(reason: str = "manual", admin: dict = Depends(require_admin)):
    task = create_backup_task.delay(reason)
    await audit.record(admin, "backup.create", "backup", task.id, {"reason": reason})
    return {"ok": True, "task_id": task.id, "status": "queued"}


@router.get("/backups")
async def backups(limit: int = Query(100, ge=1, le=500), _: dict = Depends(require_admin)):
    return list_backups(limit)


@router.get("/backups/tasks/{task_id}")
async def backup_status(task_id: str, _: dict = Depends(require_admin)):
    result = AsyncResult(task_id, app=celery_app)
    response = {"task_id": task_id, "status": result.status}
    if result.ready():
        if result.failed():
            response["error"] = str(result.result)
        else:
            response["result"] = result.result
    return response


@router.post("/backups/cleanup")
async def cleanup_backups(keep_days: Optional[int] = None, admin: dict = Depends(require_admin)):
    task = cleanup_old_backups_task.delay(keep_days)
    await audit.record(admin, "backup.cleanup", "backup", task.id, {"keep_days": keep_days})
    return {"ok": True, "task_id": task.id, "status": "queued"}


@router.get("/backups/download/{filename}")
async def download_backup(filename: str, _: dict = Depends(require_admin)):
    try:
        path = backup_file_path(filename)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "Backup topilmadi")
    return FileResponse(
        str(path),
        media_type="application/gzip",
        filename=path.name,
    )


@router.delete("/backups/{filename}")
async def remove_backup(filename: str, admin: dict = Depends(require_admin)):
    try:
        result = delete_backup(filename)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "Backup topilmadi")
    await audit.record(admin, "backup.delete", "backup", filename, {"size": result["size"]})
    return result
