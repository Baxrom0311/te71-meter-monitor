from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import Response

from core.security import current_token_payload, require_admin
from models.schemas import DeviceProvisioningTokenCreate, DeviceRegister, DeviceStatus, DeviceUpdate
from services import analytics as analytics_service
from services import audit
from services import devices as device_service
from services import readings as reading_service

router = APIRouter(prefix="/api")


@router.post("/register")
async def register_device(body: DeviceRegister, x_device_token: Optional[str] = Header(None)):
    if not body.provisioning_token:
        await device_service.verify_device_access(body.device_id, x_device_token)
    return await device_service.register_device(body)


@router.post("/device-status")
async def device_status(body: DeviceStatus, x_device_token: Optional[str] = Header(None)):
    await device_service.verify_device_access(body.device_id, x_device_token)
    return await device_service.update_device_status(body)


@router.get("/device-config/{device_id}")
async def device_config(device_id: str, x_device_token: Optional[str] = Header(None)):
    await device_service.verify_device_access(device_id, x_device_token)
    return await device_service.get_device_config(device_id)


@router.get("/devices")
async def list_devices(
    online: Optional[bool] = None,
    type: Optional[str] = None,
    group: Optional[str] = None,
    building: Optional[str] = None,
    utility_type: Optional[str] = None,
    _: dict = Depends(current_token_payload),
):
    return await device_service.list_devices(online, type, group, building, utility_type)


@router.post("/devices/provisioning-tokens")
async def create_device_provisioning_token(
    body: DeviceProvisioningTokenCreate,
    admin: dict = Depends(require_admin),
):
    result = await device_service.create_provisioning_token(body, admin)
    audit_detail = {k: v for k, v in result.items() if k != "provisioning_token"}
    await audit.record(admin, "device.provisioning_token.create", "device_provisioning_token", result["id"], audit_detail)
    return result


@router.get("/devices/provisioning-tokens")
async def list_device_provisioning_tokens(
    active_only: bool = True,
    limit: int = Query(100, ge=1, le=500),
    _: dict = Depends(require_admin),
):
    return await device_service.list_provisioning_tokens(active_only=active_only, limit=limit)


@router.delete("/devices/provisioning-tokens/{token_id}")
async def revoke_device_provisioning_token(token_id: int, admin: dict = Depends(require_admin)):
    result = await device_service.revoke_provisioning_token(token_id, admin)
    await audit.record(admin, "device.provisioning_token.revoke", "device_provisioning_token", token_id)
    return result


@router.get("/devices/{device_id}")
async def get_device(device_id: str, _: dict = Depends(current_token_payload)):
    return await device_service.get_device(device_id)


@router.put("/devices/{device_id}")
async def update_device(device_id: str, body: DeviceUpdate, admin: dict = Depends(require_admin)):
    result = await device_service.update_device(device_id, body)
    await audit.record(admin, "device.update", "device", device_id, body.model_dump(exclude_none=True))
    return result


@router.post("/devices/{device_id}/token")
async def rotate_device_token(device_id: str, admin: dict = Depends(require_admin)):
    result = await device_service.rotate_device_token(device_id)
    await audit.record(admin, "device.rotate_token", "device", device_id)
    return result


@router.delete("/devices/{device_id}/token")
async def revoke_device_token(device_id: str, admin: dict = Depends(require_admin)):
    result = await device_service.revoke_device_token(device_id, admin)
    await audit.record(admin, "device.revoke_token", "device", device_id)
    return result


@router.get("/devices/{device_id}/latest")
async def device_latest(device_id: str, _: dict = Depends(current_token_payload)):
    return await reading_service.latest_reading(device_id)


@router.get("/devices/{device_id}/history")
async def device_history(
    device_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=1000),
    hours: Optional[int] = None,
    _: dict = Depends(current_token_payload),
):
    return await reading_service.reading_history(device_id, page, limit, hours)


@router.get("/devices/{device_id}/stats")
async def device_stats(
    device_id: str,
    hours: int = Query(24, ge=1, le=720),
    _: dict = Depends(current_token_payload),
):
    return await analytics_service.reading_stats(device_id, hours)


@router.get("/devices/{device_id}/export")
async def export_csv(
    device_id: str,
    hours: int = Query(24, ge=1, le=720),
    _: dict = Depends(current_token_payload),
):
    filename, content = await analytics_service.export_csv(device_id, hours)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
