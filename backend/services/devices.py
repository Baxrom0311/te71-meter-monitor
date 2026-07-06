from fastapi import HTTPException
from sqlalchemy import and_, desc, inspect, select

from core.config import settings
from core.database import SessionLocal
from core.security import generate_secret_token, hash_password, verify_password
from core.time import now_ts
from models.entities import Building, Device, DeviceProvisioningToken, MeasurementPoint
from models.schemas import DeviceProvisioningTokenCreate, DeviceRegister, DeviceStatus, DeviceUpdate
from services.websocket import ws_manager


def _as_dict(obj) -> dict:
    return {attr.key: getattr(obj, attr.key) for attr in inspect(obj).mapper.column_attrs}


def _online(last_seen: int | None) -> bool:
    return (now_ts() - (last_seen or 0)) < settings.offline_sec


def online_status(last_seen: int | None) -> bool:
    return _online(last_seen)


def _global_device_token_ok(token: str | None) -> bool:
    return bool(settings.device_api_token and token and token == settings.device_api_token)


def _server_targets() -> list[dict]:
    return [
        {"url": url, "priority": index + 1, "enabled": True}
        for index, url in enumerate(settings.public_server_urls)
    ]


async def verify_device_access(device_id: str | None, token: str | None) -> None:
    if not device_id:
        raise HTTPException(400, "device_id kerak")
    async with SessionLocal() as session:
        device = await session.get(Device, device_id)
    if device and not device.is_active:
        raise HTTPException(403, "Qurilma o'chirilgan")
    if device and device.api_token_hash:
        if token and verify_password(token, device.api_token_hash):
            return
        raise HTTPException(401, "Device token noto'g'ri")
    if device and device.token_revoked_at:
        raise HTTPException(401, "Device token bekor qilingan")
    if _global_device_token_ok(token):
        return
    if settings.device_api_token:
        raise HTTPException(401, "Device token noto'g'ri")


async def get_device_config(device_id: str) -> dict:
    async with SessionLocal() as session:
        device = await session.get(Device, device_id)
        point = await session.get(MeasurementPoint, device.point_id) if device and device.point_id else None
        building = await session.get(Building, device.building_id) if device and device.building_id else None

    mode = device.firmware_mode if device else "auto"
    utility_type = device.utility_type if device else "electricity"
    return {
        "device_id": device_id,
        "registered": device is not None,
        "firmware_mode": mode,
        "utility_type": utility_type,
        "device_role": device.device_role if device else None,
        "building_id": device.building_id if device else None,
        "building": _as_dict(building) if building else None,
        "measurement_point_id": device.point_id if device else None,
        "measurement_point": _as_dict(point) if point else None,
        "hardware_version": device.hardware_version if device else None,
        "software_version": device.software_version if device else None,
        "token_required": bool(settings.device_api_token or (device and device.api_token_hash)),
        "intervals": {
            "telemetry_sec": settings.telemetry_interval_sec,
            "status_sec": settings.status_interval_sec,
            "command_poll_sec": settings.command_poll_interval_sec,
        },
        "servers": _server_targets(),
        "endpoints": {
            "register": "/api/register",
            "readings": "/api/readings",
            "status": "/api/device-status",
            "commands": f"/api/commands/{device_id}",
            "ota_check": f"/api/ota/check/{device_id}",
        },
    }


async def _consume_provisioning_token(session, body: DeviceRegister, ts: int) -> dict | None:
    if not body.provisioning_token:
        return None
    rows = (
        await session.scalars(
            select(DeviceProvisioningToken).where(
                and_(
                    DeviceProvisioningToken.used_at.is_(None),
                    DeviceProvisioningToken.revoked_at.is_(None),
                    DeviceProvisioningToken.expires_at > ts,
                )
            )
        )
    ).all()
    matched = next((row for row in rows if verify_password(body.provisioning_token, row.token_hash)), None)
    if not matched:
        raise HTTPException(401, "Provisioning token noto'g'ri yoki muddati tugagan")
    if matched.device_id and matched.device_id != body.device_id:
        raise HTTPException(403, "Provisioning token boshqa device uchun")
    matched.used_at = ts
    matched.used_by_device_id = body.device_id
    return {
        "building_id": matched.building_id,
        "point_id": matched.point_id,
        "utility_type": matched.utility_type,
        "device_role": matched.device_role,
        "firmware_mode": matched.firmware_mode,
    }


async def register_device(body: DeviceRegister) -> dict:
    ts = now_ts()
    device_token = None
    applied_utility_type = body.utility_type
    applied_device_role = body.device_role
    applied_firmware_mode = body.firmware_mode
    async with SessionLocal() as session:
        provisioned = await _consume_provisioning_token(session, body, ts)
        if provisioned:
            applied_utility_type = provisioned.get("utility_type") or body.utility_type
            applied_device_role = provisioned.get("device_role") or body.device_role
            applied_firmware_mode = provisioned.get("firmware_mode") or body.firmware_mode

        device = await session.get(Device, body.device_id)
        if not device:
            device = Device(id=body.device_id, name=body.name or body.device_id, registered=ts, created_at=ts)
            session.add(device)

        if provisioned:
            device_token = generate_secret_token()
            device.api_token_hash = hash_password(device_token)
            device.token_created_at = ts
            device.token_revoked_at = None
            device.token_revoked_by_user_id = None
            device.token_revoked_by_username = None

        device.name = device.name or body.name or body.device_id
        device.utility_type = applied_utility_type
        device.device_role = applied_device_role
        device.firmware_mode = applied_firmware_mode
        device.meter_type = body.meter_type
        device.meter_serial = body.meter_serial or device.meter_serial
        device.serial_number = body.serial_number or device.serial_number
        device.hardware_version = body.hardware_version or device.hardware_version
        device.software_version = body.software_version or body.fw_version or device.software_version
        device.build_number = body.build_number or device.build_number
        device.baud_rate = body.baud_rate or device.baud_rate
        device.chip_model = body.chip_model or device.chip_model
        device.rssi = body.rssi
        device.fw_version = body.fw_version or device.fw_version
        device.ip = body.ip or device.ip
        device.building_id = (
            provisioned.get("building_id") or body.building_id or device.building_id
            if provisioned
            else body.building_id or device.building_id
        )
        device.point_id = (
            provisioned.get("point_id") or body.point_id or device.point_id
            if provisioned
            else body.point_id or device.point_id
        )
        device.last_seen = ts
        device.updated_at = ts
        await session.commit()

    await ws_manager.broadcast(
        {
            "type": "device_online",
            "device_id": body.device_id,
            "utility_type": applied_utility_type,
            "firmware_mode": applied_firmware_mode,
        }
    )
    result = {"ok": True, "device_id": body.device_id, "provisioned": bool(provisioned)}
    if device_token:
        result["device_token"] = device_token
        result["token_type"] = "device"
    return result


async def update_device_status(body: DeviceStatus) -> dict:
    ts = now_ts()
    async with SessionLocal() as session:
        device = await session.get(Device, body.device_id)
        if not device:
            device = Device(id=body.device_id, name=body.device_id, registered=ts, created_at=ts)
            session.add(device)
        device.ip = body.ip or device.ip
        device.rssi = body.rssi
        device.hardware_version = body.hardware_version or device.hardware_version
        device.software_version = body.software_version or device.software_version
        device.firmware_mode = body.firmware_mode or device.firmware_mode
        device.build_number = body.build_number or device.build_number
        device.last_seen = ts if body.online else device.last_seen
        device.updated_at = ts
        await session.commit()
    await ws_manager.broadcast({"type": "status", "device_id": body.device_id, "online": body.online})
    return {"ok": True}


async def list_devices(
    online: bool | None = None,
    meter_type: str | None = None,
    group: str | None = None,
    building: str | None = None,
    utility_type: str | None = None,
) -> dict:
    stmt = select(Device).where(Device.is_active.is_(True)).order_by(desc(Device.last_seen))
    if meter_type:
        stmt = stmt.where(Device.meter_type == meter_type)
    if group:
        stmt = stmt.where(Device.group_name == group)
    if building:
        stmt = stmt.where(Device.building_text == building)
    if utility_type:
        stmt = stmt.where(Device.utility_type == utility_type)
    async with SessionLocal() as session:
        rows = (await session.scalars(stmt)).all()

    devices = []
    for device in rows:
        row = _as_dict(device) | {"online": _online(device.last_seen)}
        if online is not None and row["online"] != online:
            continue
        devices.append(row)
    return {"devices": devices, "total": len(devices)}


async def get_device(device_id: str) -> dict:
    async with SessionLocal() as session:
        device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(404, "Qurilma topilmadi")
    return _as_dict(device) | {"online": _online(device.last_seen)}


async def update_device(device_id: str, body: DeviceUpdate) -> dict:
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "Yangilanadigan maydon yo'q")
    async with SessionLocal() as session:
        device = await session.get(Device, device_id)
        if not device:
            raise HTTPException(404, "Qurilma topilmadi")
        if fields.get("building_id") and not await session.get(Building, fields["building_id"]):
            raise HTTPException(404, "Building topilmadi")
        if fields.get("point_id"):
            point = await session.get(MeasurementPoint, fields["point_id"])
            if not point:
                raise HTTPException(404, "Measurement point topilmadi")
            building_id = fields.get("building_id") or device.building_id
            if building_id and point.building_id and point.building_id != building_id:
                raise HTTPException(422, "Measurement point boshqa buildingga tegishli")
        for key, value in fields.items():
            setattr(device, key, value)
        device.updated_at = now_ts()
        await session.commit()
    return {"ok": True}


async def rotate_device_token(device_id: str) -> dict:
    token = generate_secret_token()
    ts = now_ts()
    async with SessionLocal() as session:
        device = await session.get(Device, device_id)
        if not device:
            device = Device(id=device_id, name=device_id, registered=ts, created_at=ts)
            session.add(device)
        device.api_token_hash = hash_password(token)
        device.token_created_at = ts
        device.token_revoked_at = None
        device.token_revoked_by_user_id = None
        device.token_revoked_by_username = None
        device.updated_at = ts
        await session.commit()
    return {"device_id": device_id, "device_token": token, "token_type": "device"}


async def revoke_device_token(device_id: str, admin: dict) -> dict:
    ts = now_ts()
    async with SessionLocal() as session:
        device = await session.get(Device, device_id)
        if not device:
            raise HTTPException(404, "Qurilma topilmadi")
        if not device.api_token_hash and device.token_revoked_at:
            return {"ok": True, "device_id": device_id, "token_revoked_at": device.token_revoked_at}
        device.api_token_hash = None
        device.token_created_at = None
        device.token_revoked_at = ts
        device.token_revoked_by_user_id = admin.get("sub")
        device.token_revoked_by_username = admin.get("username")
        device.updated_at = ts
        await session.commit()
    return {"ok": True, "device_id": device_id, "token_revoked_at": ts}


async def create_provisioning_token(body: DeviceProvisioningTokenCreate, admin: dict) -> dict:
    token = generate_secret_token()
    ts = now_ts()
    async with SessionLocal() as session:
        if body.building_id and not await session.get(Building, body.building_id):
            raise HTTPException(404, "Building topilmadi")
        if body.point_id:
            point = await session.get(MeasurementPoint, body.point_id)
            if not point:
                raise HTTPException(404, "Measurement point topilmadi")
            if body.building_id and point.building_id and point.building_id != body.building_id:
                raise HTTPException(422, "Measurement point boshqa buildingga tegishli")

        row = DeviceProvisioningToken(
            token_hash=hash_password(token),
            device_id=body.device_id,
            building_id=body.building_id,
            point_id=body.point_id,
            utility_type=body.utility_type,
            device_role=body.device_role,
            firmware_mode=body.firmware_mode,
            expires_at=ts + body.ttl_sec,
            created_by_user_id=admin.get("sub"),
            created_by_username=admin.get("username"),
            created_at=ts,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return {
        "ok": True,
        "id": row.id,
        "provisioning_token": token,
        "expires_at": row.expires_at,
        "device_id": row.device_id,
        "building_id": row.building_id,
        "point_id": row.point_id,
        "utility_type": row.utility_type,
        "device_role": row.device_role,
        "firmware_mode": row.firmware_mode,
    }


async def list_provisioning_tokens(active_only: bool = True, limit: int = 100) -> dict:
    ts = now_ts()
    stmt = select(DeviceProvisioningToken).order_by(desc(DeviceProvisioningToken.id)).limit(limit)
    if active_only:
        stmt = stmt.where(
            and_(
                DeviceProvisioningToken.used_at.is_(None),
                DeviceProvisioningToken.revoked_at.is_(None),
                DeviceProvisioningToken.expires_at > ts,
            )
        )
    async with SessionLocal() as session:
        rows = (await session.scalars(stmt)).all()
    result = []
    for row in rows:
        data = _as_dict(row)
        data.pop("token_hash", None)
        result.append(data)
    return {"tokens": result}


async def revoke_provisioning_token(token_id: int, admin: dict) -> dict:
    ts = now_ts()
    async with SessionLocal() as session:
        row = await session.get(DeviceProvisioningToken, token_id)
        if not row:
            raise HTTPException(404, "Provisioning token topilmadi")
        if row.used_at:
            raise HTTPException(409, "Ishlatilgan provisioning token revoke qilinmaydi")
        if not row.revoked_at:
            row.revoked_at = ts
            row.revoked_by_user_id = admin.get("sub")
            row.revoked_by_username = admin.get("username")
            await session.commit()
            await session.refresh(row)
    data = _as_dict(row)
    data.pop("token_hash", None)
    return {"ok": True, "token": data}
