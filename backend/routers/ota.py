from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from core.config import settings
from core.security import current_token_payload, require_admin, require_device_token
from models.schemas import (
    CommandQueuedResponse,
    FirmwareCheckResponse,
    FirmwareInstallEventListResponse,
    FirmwareListResponse,
    FirmwareUploadResponse,
    OkResponse,
    OTABatchCancelResponse,
    OTABatchCreate,
    OTABatchCreateResponse,
    OTABatchDetailResponse,
    OTABatchListResponse,
    OTABatchProcessResponse,
    OtaInstallReport,
    OtaReportResponse,
)
from services import audit
from services import commands as command_service
from services import devices as device_service
from services import ota as ota_service

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


@router.post("/ota/upload", response_model=FirmwareUploadResponse)
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
    is_stable: bool = Form(False),
    min_version: Optional[str] = Form(None),
    rollout_percentage: int = Form(100),
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
        is_stable=is_stable,
        min_version=min_version,
        rollout_percentage=rollout_percentage,
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
            "is_stable": is_stable,
            "min_version": min_version,
            "rollout_percentage": rollout_percentage,
        },
    )
    return result


@router.get("/ota/list", response_model=FirmwareListResponse)
async def ota_list(_: dict = Depends(current_token_payload)):
    return await ota_service.ota_list()


@router.delete("/ota/{fw_id}", response_model=OkResponse)
async def ota_delete(fw_id: int, admin: dict = Depends(require_admin)):
    result = await ota_service.ota_delete(fw_id)
    await audit.record(admin, "ota.delete", "firmware", fw_id)
    return result


@router.get("/ota/check/{device_id}", response_model=FirmwareCheckResponse)
async def ota_check(device_id: str, current_version: str = "", x_device_token: Optional[str] = Header(None)):
    await device_service.verify_device_access(device_id, x_device_token)
    return await ota_service.ota_check(device_id, current_version)


@router.post("/ota/report", response_model=OtaReportResponse)
async def ota_report(body: OtaInstallReport, x_device_token: Optional[str] = Header(None)):
    await device_service.verify_device_access(body.device_id, x_device_token)
    return await ota_service.ota_report(body)


@router.get("/ota/events", response_model=FirmwareInstallEventListResponse)
async def ota_events(
    device_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    _: dict = Depends(require_admin),
):
    return await ota_service.ota_events(device_id, status, limit)


@router.post("/ota/batches", response_model=OTABatchCreateResponse)
async def create_ota_batch(body: OTABatchCreate, admin: dict = Depends(require_admin)):
    result = await ota_service.create_ota_batch(body, admin)
    await audit.record(admin, "ota_batch.create", "ota_batch", result["batch"]["id"], body.model_dump())
    return result


@router.get("/ota/batches", response_model=OTABatchListResponse)
async def list_ota_batches(
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    _: dict = Depends(require_admin),
):
    return await ota_service.list_ota_batches(status, limit)


@router.get("/ota/batches/{batch_id}", response_model=OTABatchDetailResponse)
async def get_ota_batch(batch_id: int, _: dict = Depends(require_admin)):
    return await ota_service.get_ota_batch(batch_id)


@router.post("/ota/batches/{batch_id}/process", response_model=OTABatchProcessResponse)
async def process_ota_batch(
    batch_id: int,
    limit: Optional[int] = Query(None, ge=1, le=10000),
    admin: dict = Depends(require_admin),
):
    result = await ota_service.process_ota_batch(batch_id, limit)
    await audit.record(admin, "ota_batch.process", "ota_batch", batch_id, result)
    return result


@router.post("/ota/batches/{batch_id}/cancel", response_model=OTABatchCancelResponse)
async def cancel_ota_batch(batch_id: int, admin: dict = Depends(require_admin)):
    result = await ota_service.cancel_ota_batch(batch_id)
    await audit.record(admin, "ota_batch.cancel", "ota_batch", batch_id, result)
    return result


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


@router.post("/ota/push/{device_id}", response_model=CommandQueuedResponse)
async def ota_push(device_id: str, admin: dict = Depends(require_admin)):
    result = await command_service.create_command(device_id, "ota_check", None)
    await audit.record(admin, "ota.push", "device", device_id)
    return result
