import json

from fastapi import HTTPException

from core.config import settings
from core.database import SessionLocal
from core.time import now_ts
from models.entities import Command, Device
from repositories.base import model_to_dict
from repositories.devices import CommandRepository, DeviceRepository
from services import devices as devices_service


async def verify_command_access(command_id: int, token: str | None) -> None:
    async with SessionLocal() as session:
        command = await CommandRepository(session).get(command_id)
    if not command:
        raise HTTPException(404, "Command topilmadi")
    await devices_service.verify_device_access(command.device_id, token)


async def create_relay_command(device_id: str, action_value: str) -> dict:
    if action_value not in ("on", "off"):
        raise HTTPException(400, "action: 'on' yoki 'off'")
    return await create_command(device_id, f"relay_{action_value}", None)


async def create_command(device_id: str, action: str, params: dict | None = None) -> dict:
    ts = now_ts()
    async with SessionLocal() as session:
        device = await DeviceRepository(session).get(device_id)
        if not device:
            raise HTTPException(404, "Qurilma topilmadi")
        if not device.is_active:
            raise HTTPException(400, "O'chirilgan qurilmaga command yuborilmaydi")

        command = Command(
            device_id=device_id,
            action=action,
            param=json.dumps(params, ensure_ascii=False) if params else None,
            status="pending",
            created=ts,
            expires_at=ts + settings.command_ttl_sec,
            max_attempts=3,
        )
        repo = CommandRepository(session)
        pending_count = await repo.active_pending_count(device_id, ts)
        if pending_count >= settings.command_max_pending_per_device:
            raise HTTPException(429, "Bu qurilma uchun pending command limiti oshib ketdi")
        repo.add(command)
        await session.commit()
        await session.refresh(command)
    return {"ok": True, "cmd_id": command.id, "expires_at": command.expires_at}


async def reboot_device(device_id: str) -> dict:
    return await create_command(device_id, "reboot", None)


async def pending_commands(device_id: str) -> dict:
    ts = now_ts()
    async with SessionLocal() as session:
        repo = CommandRepository(session)
        await repo.expire_due(ts, device_id)
        rows = await repo.pollable_for_device(device_id, ts, 5)
        for row in rows:
            row.sent = ts
            row.status = "sent"
            row.attempts = (row.attempts or 0) + 1
        await session.commit()
    return {
        "commands": [
            {
                "id": row.id,
                "action": row.action,
                "param": row.param,
                "expires_at": row.expires_at,
                "attempts": row.attempts,
                "max_attempts": row.max_attempts,
            }
            for row in rows
        ]
    }


async def ack_command(command_id: int, result: str) -> dict:
    async with SessionLocal() as session:
        command = await CommandRepository(session).get(command_id)
        if command:
            command.acked = now_ts()
            command.ack_result = result
            command.status = "acked"
            await session.commit()
    return {"ok": True}


async def list_commands(device_id: str | None = None, status: str | None = None, limit: int = 100, offset: int = 0) -> dict:
    async with SessionLocal() as session:
        rows = await CommandRepository(session).list_filtered(device_id, status, limit, offset)
    return {"commands": [model_to_dict(row) for row in rows]}


async def cleanup_expired_commands_once() -> dict:
    ts = now_ts()
    async with SessionLocal() as session:
        expired = await CommandRepository(session).expire_due(ts)
        await session.commit()
    return {"ok": True, "expired_commands": expired}
