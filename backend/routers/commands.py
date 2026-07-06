from typing import Optional

from fastapi import APIRouter, Depends, Header, Query

from core.security import require_admin
from models.schemas import CommandCreate, RelayCommand
from services import audit
from services import commands as command_service
from services import devices as device_service

router = APIRouter(prefix="/api")


@router.post("/devices/{device_id}/relay")
async def relay_command(device_id: str, body: RelayCommand, admin: dict = Depends(require_admin)):
    result = await command_service.create_relay_command(device_id, body.action)
    await audit.record(admin, "device.relay", "device", device_id, body.model_dump())
    return result


@router.post("/devices/{device_id}/reboot")
async def reboot_device(device_id: str, admin: dict = Depends(require_admin)):
    result = await command_service.reboot_device(device_id)
    await audit.record(admin, "device.reboot", "device", device_id)
    return result


@router.post("/devices/{device_id}/commands")
async def create_device_command(device_id: str, body: CommandCreate, admin: dict = Depends(require_admin)):
    result = await command_service.create_command(device_id, body.action, body.params)
    await audit.record(admin, "device.command", "device", device_id, body.model_dump())
    return result


@router.get("/commands/admin/list")
async def list_commands(
    device_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    _: dict = Depends(require_admin),
):
    return await command_service.list_commands(device_id, status, limit)


@router.get("/commands/{device_id}")
async def get_commands(device_id: str, x_device_token: Optional[str] = Header(None)):
    await device_service.verify_device_access(device_id, x_device_token)
    return await command_service.pending_commands(device_id)


@router.post("/commands/{cmd_id}/ack")
async def ack_command(cmd_id: int, result: str = "ok", x_device_token: Optional[str] = Header(None)):
    await command_service.verify_command_access(cmd_id, x_device_token)
    return await command_service.ack_command(cmd_id, result)
