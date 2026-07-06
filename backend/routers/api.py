from pathlib import Path
from typing import Optional

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile
from fastapi import HTTPException
from fastapi.responses import FileResponse

from core.celery_app import celery_app
from core.config import settings
from core.security import current_token_payload, require_admin, require_device_token
from models.schemas import (
    AlertListResponse,
    AlertNotificationListResponse,
    AlertRuleListResponse,
    AlertRuleMutationResponse,
    AlertRuleCreate,
    AlertRuleUpdate,
    BackupDeleteResponse,
    BackupListResponse,
    BackupTaskStatusResponse,
    OtaInstallReport,
    OkResponse,
    TaskQueuedResponse,
)
from services import alerts as alert_service
from services import commands as command_service
from services import devices as device_service
from services import ota as ota_service
from services import audit
from services.backup import backup_file_path, delete_backup, list_backups
from tasks.backup import cleanup_old_backups as cleanup_old_backups_task
from tasks.backup import create_backup as create_backup_task
from tasks.backup import restore_backup as restore_backup_task

router = APIRouter(prefix="/api")


def _safe_ota_path(filename: str) -> Path:
    if Path(filename).name != filename:
        raise HTTPException(400, "Firmware filename noto'g'ri")
    root = Path(settings.ota_dir).resolve()
    path = (root / filename).resolve()
    if root not in path.parents and path != root:
        raise HTTPException(400, "Firmware filename noto'g'ri")
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "Firmware topilmadi")
    return path


@router.get("/alerts", response_model=AlertListResponse)
async def get_alerts(
    device_id: Optional[str] = None,
    kind: Optional[str] = None,
    cleared: bool = False,
    limit: int = Query(50, ge=1, le=500),
    _: dict = Depends(current_token_payload),
):
    return await alert_service.get_alerts(device_id, kind, cleared, limit)


@router.get("/alert-notifications", response_model=AlertNotificationListResponse)
async def list_alert_notifications(
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    _: dict = Depends(require_admin),
):
    return await alert_service.list_alert_notifications(status, limit)


@router.get("/alert-rules", response_model=AlertRuleListResponse)
async def list_alert_rules(
    utility_type: Optional[str] = None,
    building_id: Optional[int] = None,
    enabled: Optional[bool] = None,
    limit: int = Query(200, ge=1, le=500),
    _: dict = Depends(current_token_payload),
):
    return await alert_service.list_alert_rules(utility_type, building_id, enabled, limit)


@router.post("/alert-rules", response_model=AlertRuleMutationResponse)
async def create_alert_rule(body: AlertRuleCreate, admin: dict = Depends(require_admin)):
    result = await alert_service.create_alert_rule(body)
    await audit.record(admin, "alert_rule.create", "alert_rule", result["rule"]["id"], result["rule"])
    return result


@router.put("/alert-rules/{rule_id}", response_model=AlertRuleMutationResponse)
async def update_alert_rule(rule_id: int, body: AlertRuleUpdate, admin: dict = Depends(require_admin)):
    result = await alert_service.update_alert_rule(rule_id, body)
    await audit.record(admin, "alert_rule.update", "alert_rule", rule_id, result["rule"])
    return result


@router.delete("/alert-rules/{rule_id}", response_model=OkResponse)
async def disable_alert_rule(rule_id: int, admin: dict = Depends(require_admin)):
    result = await alert_service.disable_alert_rule(rule_id)
    await audit.record(admin, "alert_rule.disable", "alert_rule", rule_id)
    return result


@router.post("/alerts/{alert_id}/clear", response_model=OkResponse)
async def clear_alert(alert_id: int, admin: dict = Depends(require_admin)):
    result = await alert_service.clear_alert(alert_id)
    await audit.record(admin, "alert.clear", "alert", alert_id)
    return result


@router.post("/alerts/clear-all", response_model=OkResponse)
async def clear_all_alerts(device_id: Optional[str] = None, admin: dict = Depends(require_admin)):
    result = await alert_service.clear_all_alerts(device_id)
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
    result = await ota_service.ota_upload(
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
    return await ota_service.ota_list()


@router.delete("/ota/{fw_id}")
async def ota_delete(fw_id: int, admin: dict = Depends(require_admin)):
    result = await ota_service.ota_delete(fw_id)
    await audit.record(admin, "ota.delete", "firmware", fw_id)
    return result


@router.get("/ota/check/{device_id}")
async def ota_check(device_id: str, current_version: str = "", x_device_token: Optional[str] = Header(None)):
    await device_service.verify_device_access(device_id, x_device_token)
    return await ota_service.ota_check(device_id, current_version)


@router.post("/ota/report")
async def ota_report(body: OtaInstallReport, x_device_token: Optional[str] = Header(None)):
    await device_service.verify_device_access(body.device_id, x_device_token)
    return await ota_service.ota_report(body)


@router.get("/ota/events")
async def ota_events(
    device_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    _: dict = Depends(require_admin),
):
    return await ota_service.ota_events(device_id, status, limit)


@router.get("/ota/firmware/{filename}")
async def ota_download(
    filename: str,
    device_id: Optional[str] = None,
    x_device_token: Optional[str] = Header(None),
):
    if device_id:
        await device_service.verify_device_access(device_id, x_device_token)
    else:
        await require_device_token(x_device_token)
    path = _safe_ota_path(filename)
    return FileResponse(str(path), media_type="application/octet-stream")


@router.post("/ota/push/{device_id}")
async def ota_push(device_id: str, admin: dict = Depends(require_admin)):
    result = await command_service.create_command(device_id, "ota_check", None)
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


@router.post("/backups", response_model=TaskQueuedResponse)
async def create_backup(reason: str = "manual", admin: dict = Depends(require_admin)):
    task = create_backup_task.delay(reason)
    await audit.record(admin, "backup.create", "backup", task.id, {"reason": reason})
    return {"ok": True, "task_id": task.id, "status": "queued"}


@router.get("/backups", response_model=BackupListResponse)
async def backups(limit: int = Query(100, ge=1, le=500), _: dict = Depends(require_admin)):
    return list_backups(limit)


@router.get("/backups/tasks/{task_id}", response_model=BackupTaskStatusResponse)
async def backup_status(task_id: str, _: dict = Depends(require_admin)):
    result = AsyncResult(task_id, app=celery_app)
    response = {"task_id": task_id, "status": result.status}
    if result.ready():
        if result.failed():
            response["error"] = str(result.result)
        else:
            response["result"] = result.result
    return response


@router.post("/backups/cleanup", response_model=TaskQueuedResponse)
async def cleanup_backups(keep_days: Optional[int] = None, admin: dict = Depends(require_admin)):
    task = cleanup_old_backups_task.delay(keep_days)
    await audit.record(admin, "backup.cleanup", "backup", task.id, {"keep_days": keep_days})
    return {"ok": True, "task_id": task.id, "status": "queued"}


@router.post("/backups/restore/{filename}", response_model=TaskQueuedResponse)
async def restore_backup(filename: str, confirm: str = "", admin: dict = Depends(require_admin)):
    if confirm != "RESTORE":
        raise HTTPException(400, "Restore uchun confirm=RESTORE kerak")
    try:
        backup_file_path(filename)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "Backup topilmadi")
    task = restore_backup_task.delay(filename, confirm)
    await audit.record(admin, "backup.restore", "backup", filename, {"task_id": task.id})
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


@router.delete("/backups/{filename}", response_model=BackupDeleteResponse)
async def remove_backup(filename: str, admin: dict = Depends(require_admin)):
    try:
        result = delete_backup(filename)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "Backup topilmadi")
    await audit.record(admin, "backup.delete", "backup", filename, {"size": result["size"]})
    return result
