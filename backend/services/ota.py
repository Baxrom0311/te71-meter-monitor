import hashlib
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import desc, inspect, select
from sqlalchemy.orm import selectinload

from core.config import settings
from core.database import SessionLocal
from core.time import now_ts
from models.entities import Device, Firmware, FirmwareCompatibility, FirmwareInstallEvent, MeasurementPoint
from models.schemas import OtaInstallReport


def _as_dict(obj) -> dict:
    return {attr.key: getattr(obj, attr.key) for attr in inspect(obj).mapper.column_attrs}


def _clean_meta(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _is_wildcard(value: str | None) -> bool:
    return value is None or str(value).strip().lower() in {"", "*", "any", "all"}


def _matches_rule(rule: str | None, actual: str | None, *, auto_is_wildcard: bool = False) -> bool:
    if _is_wildcard(rule):
        return True
    if auto_is_wildcard and str(rule).strip().lower() == "auto":
        return True
    return str(rule).strip() == str(actual).strip() if actual is not None else False


def _compat_tuple(
    utility_type: str | None,
    firmware_mode: str | None,
    device_role: str | None,
    hardware_version: str | None,
    sensor_type: str | None,
    converter_type: str | None,
) -> tuple[str | None, ...]:
    return (
        _clean_meta(utility_type),
        _clean_meta(firmware_mode) or "auto",
        _clean_meta(device_role),
        _clean_meta(hardware_version),
        _clean_meta(sensor_type),
        _clean_meta(converter_type),
    )


def _firmware_direct_tuple(firmware: Firmware) -> tuple[str | None, ...]:
    return _compat_tuple(
        firmware.utility_type,
        firmware.firmware_mode,
        firmware.device_role,
        firmware.hardware_version,
        firmware.sensor_type,
        firmware.converter_type,
    )


def _compat_row_tuple(compatibility: FirmwareCompatibility) -> tuple[str | None, ...]:
    return _compat_tuple(
        compatibility.utility_type,
        compatibility.firmware_mode,
        compatibility.device_role,
        compatibility.hardware_version,
        compatibility.sensor_type,
        compatibility.converter_type,
    )


def _compat_matches(compatibility: FirmwareCompatibility | Firmware, target: dict[str, str | None]) -> bool:
    return all(
        (
            _matches_rule(compatibility.utility_type, target["utility_type"]),
            _matches_rule(compatibility.firmware_mode, target["firmware_mode"], auto_is_wildcard=True),
            _matches_rule(compatibility.device_role, target["device_role"]),
            _matches_rule(compatibility.hardware_version, target["hardware_version"]),
            _matches_rule(compatibility.sensor_type, target["sensor_type"]),
            _matches_rule(compatibility.converter_type, target["converter_type"]),
        )
    )


def _firmware_matches_device(firmware: Firmware, target: dict[str, str | None]) -> bool:
    if firmware.compatibilities:
        return any(_compat_matches(row, target) for row in firmware.compatibilities)
    return _compat_matches(firmware, target)


def _firmware_response(firmware: Firmware, *, device_id: str | None = None) -> dict:
    data = _as_dict(firmware)
    data["compatibilities"] = [_as_dict(row) for row in firmware.compatibilities]
    if device_id:
        data["url"] = f"/api/ota/firmware/{firmware.filename}?device_id={device_id}"
    else:
        data["url"] = f"/api/ota/firmware/{firmware.filename}"
    return data


async def ota_upload(
    version: str,
    notes: str,
    file: UploadFile,
    hardware_version: str | None = None,
    firmware_mode: str = "auto",
    utility_type: str | None = None,
    device_role: str | None = None,
    sensor_type: str | None = None,
    converter_type: str | None = None,
    description: str = "",
    release_notes: str = "",
    compatibility_notes: str = "",
) -> dict:
    data = await file.read()
    sha = hashlib.sha256(data).hexdigest()
    target_tuple = _compat_tuple(utility_type, firmware_mode, device_role, hardware_version, sensor_type, converter_type)
    utility_label = target_tuple[0] or "all"
    role_label = target_tuple[2] or "any"
    hardware_label = target_tuple[3] or "any"
    sensor_label = target_tuple[4] or "any"
    converter_label = target_tuple[5] or "any"
    filename = f"{target_tuple[1]}_{utility_label}_{role_label}_{hardware_label}_{sensor_label}_{converter_label}_{version}.bin".replace("/", "_")
    (settings.ota_dir / filename).write_bytes(data)
    firmware = Firmware(
        filename=filename,
        version=version,
        hardware_version=target_tuple[3],
        firmware_mode=target_tuple[1] or "auto",
        utility_type=target_tuple[0],
        device_role=target_tuple[2],
        sensor_type=target_tuple[4],
        converter_type=target_tuple[5],
        size=len(data),
        sha256=sha,
        uploaded=now_ts(),
        active=True,
        notes=notes,
        description=_clean_meta(description),
        release_notes=_clean_meta(release_notes),
        compatibility_notes=_clean_meta(compatibility_notes),
        compatibilities=[
            FirmwareCompatibility(
                utility_type=target_tuple[0],
                firmware_mode=target_tuple[1],
                device_role=target_tuple[2],
                hardware_version=target_tuple[3],
                sensor_type=target_tuple[4],
                converter_type=target_tuple[5],
                notes=_clean_meta(compatibility_notes),
                created_at=now_ts(),
            )
        ],
    )
    async with SessionLocal() as session:
        active_firmware = (
            await session.scalars(
                select(Firmware)
                .options(selectinload(Firmware.compatibilities))
                .where(Firmware.active.is_(True))
            )
        ).all()
        for existing in active_firmware:
            existing_tuples = [_firmware_direct_tuple(existing), *[_compat_row_tuple(row) for row in existing.compatibilities]]
            if target_tuple in existing_tuples:
                existing.active = False
        session.add(firmware)
        await session.flush()
        response = {"ok": True, **_firmware_response(firmware)}
        await session.commit()
    return response


async def ota_list() -> dict:
    async with SessionLocal() as session:
        rows = (
            await session.scalars(
                select(Firmware)
                .options(selectinload(Firmware.compatibilities))
                .order_by(desc(Firmware.uploaded))
            )
        ).all()
    return {"firmware": [_firmware_response(row) for row in rows]}


async def ota_delete(firmware_id: int) -> dict:
    async with SessionLocal() as session:
        firmware = await session.get(Firmware, firmware_id)
        if not firmware:
            raise HTTPException(404, "Topilmadi")
        if firmware.active:
            raise HTTPException(400, "Aktiv firmwareni o'chirib bo'lmaydi")
        path = Path(settings.ota_dir) / firmware.filename
        if path.exists():
            path.unlink()
        await session.delete(firmware)
        await session.commit()
    return {"ok": True}


async def ota_check(device_id: str, current_version: str) -> dict:
    async with SessionLocal() as session:
        device = await session.get(Device, device_id)
        point = await session.get(MeasurementPoint, device.point_id) if device and device.point_id else None
        target = {
            "utility_type": device.utility_type if device else None,
            "firmware_mode": device.firmware_mode if device else "auto",
            "device_role": device.device_role if device else None,
            "hardware_version": device.hardware_version if device else None,
            "sensor_type": point.sensor_type if point else None,
            "converter_type": point.converter_type if point else None,
        }
        candidates = (
            await session.scalars(
                select(Firmware)
                .options(selectinload(Firmware.compatibilities))
                .where(Firmware.active.is_(True))
                .order_by(desc(Firmware.uploaded))
            )
        ).all()
        firmware = next((row for row in candidates if _firmware_matches_device(row, target)), None)
    if not firmware or firmware.version == current_version:
        return {"update": False}
    return {"update": True, **_firmware_response(firmware, device_id=device_id)}


async def ota_report(body: OtaInstallReport) -> dict:
    ts = now_ts()
    async with SessionLocal() as session:
        device = await session.get(Device, body.device_id)
        if not device:
            raise HTTPException(404, "Qurilma topilmadi")
        if body.firmware_id and not await session.get(Firmware, body.firmware_id):
            raise HTTPException(404, "Firmware topilmadi")
        event = FirmwareInstallEvent(
            device_id=body.device_id,
            firmware_id=body.firmware_id,
            from_version=body.from_version,
            target_version=body.target_version,
            status=body.status,
            message=body.message,
            ts=ts,
            created_at=ts,
        )
        session.add(event)
        if body.status == "success" and body.target_version:
            device.software_version = body.target_version
            device.fw_version = body.target_version
            device.updated_at = ts
        await session.commit()
        await session.refresh(event)
    return {"ok": True, "id": event.id, "ts": ts}


async def ota_events(device_id: str | None = None, status: str | None = None, limit: int = 100) -> dict:
    stmt = select(FirmwareInstallEvent).order_by(desc(FirmwareInstallEvent.ts)).limit(limit)
    if device_id:
        stmt = stmt.where(FirmwareInstallEvent.device_id == device_id)
    if status:
        stmt = stmt.where(FirmwareInstallEvent.status == status)
    async with SessionLocal() as session:
        rows = (await session.scalars(stmt)).all()
    return {"events": [_as_dict(row) for row in rows], "total": len(rows)}
