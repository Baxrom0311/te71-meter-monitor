import hashlib
import json
from pathlib import Path

from fastapi import HTTPException, UploadFile

from core.config import settings
from core.database import SessionLocal
from core.time import now_ts
from models.entities import (
    Command,
    Firmware,
    FirmwareCompatibility,
    FirmwareInstallEvent,
    OTABatch,
    OTABatchDevice,
)
from models.schemas import OTABatchCreate, OtaInstallReport
from repositories.base import model_to_dict
from repositories.buildings import MeasurementPointRepository
from repositories.devices import CommandRepository, DeviceRepository
from repositories.firmware import FirmwareRepository
from repositories.ota import FirmwareInstallEventRepository, OTABatchDeviceRepository, OTABatchRepository




def _version_tuple(version: str | None) -> tuple[int, int, int] | None:
    if not version:
        return None
    parts = str(version).strip().split(".")
    if len(parts) != 3:
        return None
    try:
        return tuple(int(part) for part in parts)
    except ValueError:
        return None


def _is_newer_version(target_version: str, current_version: str | None) -> bool:
    target = _version_tuple(target_version)
    current = _version_tuple(current_version)
    if target and current:
        return target > current
    return target_version != (current_version or "")


def _can_upgrade_from(firmware: Firmware, current_version: str | None) -> bool:
    if not firmware.min_version:
        return True
    minimum = _version_tuple(firmware.min_version)
    current = _version_tuple(current_version)
    if minimum and current:
        return current >= minimum
    return True


def _device_in_rollout(device_id: str, firmware: Firmware) -> bool:
    percentage = firmware.rollout_percentage
    if percentage >= 100:
        return True
    if percentage <= 0:
        return False
    digest = hashlib.sha256(f"{firmware.id}:{device_id}".encode()).hexdigest()
    bucket = int(digest[:8], 16) % 100
    return bucket < percentage


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
    data = model_to_dict(firmware)
    data["compatibilities"] = [model_to_dict(row) for row in firmware.compatibilities]
    if device_id:
        data["url"] = f"/api/ota/firmware/{firmware.filename}?device_id={device_id}"
    else:
        data["url"] = f"/api/ota/firmware/{firmware.filename}"
    return data


def _batch_response(batch: OTABatch) -> dict:
    data = model_to_dict(batch)
    processed = (batch.success_count or 0) + (batch.failure_count or 0) + (batch.skipped_count or 0)
    data["progress_percentage"] = round((processed / batch.total_devices) * 100, 1) if batch.total_devices else 0.0
    data["pending_count"] = max((batch.total_devices or 0) - processed, 0)
    return data


def _batch_detail_response(batch: OTABatch) -> dict:
    return {
        **_batch_response(batch),
        "firmware": _firmware_response(batch.firmware),
        "devices": [model_to_dict(device) for device in batch.devices],
    }


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
    is_stable: bool = False,
    min_version: str | None = None,
    rollout_percentage: int = 100,
) -> dict:
    if _version_tuple(version) is None:
        raise HTTPException(422, "Firmware version X.Y.Z formatida bo'lishi kerak")
    if min_version and _version_tuple(min_version) is None:
        raise HTTPException(422, "min_version X.Y.Z formatida bo'lishi kerak")
    if rollout_percentage < 0 or rollout_percentage > 100:
        raise HTTPException(422, "rollout_percentage 0 dan 100 gacha bo'lishi kerak")

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
        is_stable=is_stable,
        min_version=_clean_meta(min_version),
        rollout_percentage=rollout_percentage,
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
        FirmwareRepository(session).add(firmware)
        await session.flush()
        response = {"ok": True, **_firmware_response(firmware)}
        await session.commit()
    return response


async def ota_list() -> dict:
    async with SessionLocal() as session:
        rows = await FirmwareRepository(session).list_latest_with_compatibilities()
    return {"firmware": [_firmware_response(row) for row in rows]}


async def ota_delete(firmware_id: int) -> dict:
    async with SessionLocal() as session:
        firmware = await FirmwareRepository(session).get(firmware_id)
        if not firmware:
            raise HTTPException(404, "Topilmadi")
        if firmware.active:
            raise HTTPException(400, "Aktiv firmwareni o'chirib bo'lmaydi")
        path = Path(settings.ota_dir) / firmware.filename
        if path.exists():
            path.unlink()
        await FirmwareRepository(session).delete(firmware)
        await session.commit()
    return {"ok": True}


async def ota_check(device_id: str, current_version: str) -> dict:
    async with SessionLocal() as session:
        device = await DeviceRepository(session).get(device_id)
        point = await MeasurementPointRepository(session).get(device.point_id) if device and device.point_id else None
        target = {
            "utility_type": device.utility_type if device else None,
            "firmware_mode": device.firmware_mode if device else "auto",
            "device_role": device.device_role if device else None,
            "hardware_version": device.hardware_version if device else None,
            "sensor_type": point.sensor_type if point else None,
            "converter_type": point.converter_type if point else None,
        }
        candidates = await FirmwareRepository(session).list_active_with_compatibilities()
        firmware = next(
            (
                row
                for row in candidates
                if _firmware_matches_device(row, target)
                and _device_in_rollout(device_id, row)
                and _is_newer_version(row.version, current_version)
                and _can_upgrade_from(row, current_version)
            ),
            None,
        )
    if not firmware:
        return {"update": False}
    return {"update": True, **_firmware_response(firmware, device_id=device_id)}


async def ota_report(body: OtaInstallReport) -> dict:
    ts = now_ts()
    async with SessionLocal() as session:
        device = await DeviceRepository(session).get(body.device_id)
        if not device:
            raise HTTPException(404, "Qurilma topilmadi")
        if body.firmware_id and not await FirmwareRepository(session).get(body.firmware_id):
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
        FirmwareInstallEventRepository(session).add(event)
        if body.firmware_id:
            batch_device = await OTABatchDeviceRepository(session).latest_for_report(
                body.firmware_id,
                body.device_id,
            )
            if batch_device:
                batch_device.updated_at = ts
                if body.status == "started":
                    batch_device.status = "downloading"
                    batch_device.error_message = None
                elif body.status == "success":
                    batch_device.status = "success"
                    batch_device.completed_at = ts
                    batch_device.error_message = None
                elif body.status == "failed":
                    batch_device.status = "failed"
                    batch_device.completed_at = ts
                    batch_device.error_message = body.message
                    batch_device.retry_count = (batch_device.retry_count or 0) + 1
        if body.status == "success" and body.target_version:
            device.software_version = body.target_version
            device.fw_version = body.target_version
            device.updated_at = ts
        if body.firmware_id:
            await _refresh_batch_counts(session, body.firmware_id)
        await session.commit()
        await session.refresh(event)
    return {"ok": True, "id": event.id, "ts": ts}


async def ota_events(device_id: str | None = None, status: str | None = None, limit: int = 100) -> dict:
    async with SessionLocal() as session:
        rows = await FirmwareInstallEventRepository(session).list_filtered(device_id, status, limit)
    return {"events": [model_to_dict(row) for row in rows], "total": len(rows)}


async def _refresh_batch_counts(session, firmware_id: int | None = None, batch_id: int | None = None) -> None:
    batch_repo = OTABatchRepository(session)
    device_repo = OTABatchDeviceRepository(session)
    batches = await batch_repo.list_refresh_targets(firmware_id, batch_id)
    ts = now_ts()
    for batch in batches:
        success = await device_repo.status_count(batch.id, "success")
        failed = await device_repo.status_count(batch.id, "failed", settings.ota_batch_max_retries)
        skipped = await device_repo.status_count(batch.id, "skipped")
        total = await device_repo.total_count(batch.id)
        batch.success_count = success
        batch.failure_count = failed
        batch.skipped_count = skipped
        batch.total_devices = total
        if total and success + failed + skipped >= total and batch.status != "cancelled":
            batch.status = "completed" if failed == 0 else "failed"
            batch.completed_at = batch.completed_at or ts
        batch.updated_at = ts


async def _prepare_batch_retries(session, batch_id: int, ts: int) -> dict:
    timeout_cutoff = ts - settings.ota_batch_retry_timeout_sec
    retryable = await OTABatchDeviceRepository(session).retryable(batch_id)
    reset = 0
    skipped = 0
    for row in retryable:
        is_stale = row.status == "failed" or (row.updated_at or row.notified_at or 0) <= timeout_cutoff
        if not is_stale:
            continue
        if (row.retry_count or 0) >= settings.ota_batch_max_retries:
            row.status = "skipped"
            row.error_message = row.error_message or "OTA retry limit reached"
            row.updated_at = ts
            skipped += 1
            continue
        if row.status in {"notified", "downloading"}:
            row.retry_count = (row.retry_count or 0) + 1
        row.status = "pending"
        row.completed_at = None
        row.error_message = None
        row.updated_at = ts
        reset += 1
    return {"retry_reset": reset, "retry_skipped": skipped}


async def _claim_pending_batch_devices(batch_id: int, limit: int, ts: int) -> list[int]:
    if limit <= 0:
        return []

    async with SessionLocal() as session:
        repo = OTABatchDeviceRepository(session)
        candidate_ids = await repo.candidate_pending_ids(batch_id, limit)
        claimed_ids: list[int] = []
        for row_id in candidate_ids:
            if await repo.claim_pending(row_id, ts):
                claimed_ids.append(row_id)
        await session.commit()
    return claimed_ids


async def create_ota_batch(body: OTABatchCreate, admin: dict) -> dict:
    device_ids = list(dict.fromkeys(body.device_ids))
    if not device_ids:
        raise HTTPException(422, "device_ids bo'sh bo'lmasin")
    ts = now_ts()
    async with SessionLocal() as session:
        firmware = await FirmwareRepository(session).get(body.firmware_id)
        if not firmware:
            raise HTTPException(404, "Firmware topilmadi")
        devices = await DeviceRepository(session).list_active_by_ids(device_ids)
        found_ids = {device.id for device in devices}
        missing = [device_id for device_id in device_ids if device_id not in found_ids]
        if missing:
            raise HTTPException(404, f"Qurilmalar topilmadi: {', '.join(missing)}")
        batch = OTABatch(
            name=body.name,
            firmware_id=body.firmware_id,
            status="pending",
            devices_per_hour=body.devices_per_hour,
            scheduled_at=body.scheduled_at,
            total_devices=len(devices),
            created_by_user_id=admin.get("sub") or admin.get("user_id"),
            created_by_username=admin.get("username"),
            created_at=ts,
            updated_at=ts,
        )
        OTABatchRepository(session).add(batch)
        await session.flush()
        for device in devices:
            OTABatchDeviceRepository(session).add(
                OTABatchDevice(
                    batch_id=batch.id,
                    device_id=device.id,
                    status="pending",
                    previous_version=device.software_version or device.fw_version,
                    created_at=ts,
                    updated_at=ts,
                )
            )
        await session.commit()
        batch = await OTABatchRepository(session).get_detail(batch.id)
    return {"ok": True, "batch": _batch_detail_response(batch)}


async def list_ota_batches(status: str | None = None, limit: int = 100) -> dict:
    async with SessionLocal() as session:
        rows = await OTABatchRepository(session).list_filtered(status, limit)
    return {"batches": [_batch_response(row) for row in rows], "total": len(rows)}


async def get_ota_batch(batch_id: int) -> dict:
    async with SessionLocal() as session:
        batch = await OTABatchRepository(session).get_detail(batch_id)
    if not batch:
        raise HTTPException(404, "OTA batch topilmadi")
    return _batch_detail_response(batch)


async def process_ota_batch(batch_id: int, limit: int | None = None) -> dict:
    ts = now_ts()
    async with SessionLocal() as session:
        batch = await OTABatchRepository(session).get_with_firmware(batch_id)
        if not batch:
            raise HTTPException(404, "OTA batch topilmadi")
        if batch.status in {"completed", "failed", "cancelled"}:
            raise HTTPException(400, "Bu OTA batch yakunlangan")
        if batch.scheduled_at and batch.scheduled_at > ts:
            raise HTTPException(400, "OTA batch hali schedule vaqtiga yetmadi")

        retry_result = await _prepare_batch_retries(session, batch.id, ts)
        await _refresh_batch_counts(session, batch_id=batch.id)
        checked_batch_id = batch.id
        devices_per_hour = batch.devices_per_hour or 1
        await session.commit()

        notified_last_hour = await OTABatchDeviceRepository(session).notified_count_since(checked_batch_id, ts - 3600)
        available = max(devices_per_hour - notified_last_hour, 0)
        if limit is not None:
            available = min(available, limit)

    claimed_ids = await _claim_pending_batch_devices(batch_id, available, ts)

    async with SessionLocal() as session:
        batch = await OTABatchRepository(session).get_with_firmware(batch_id)
        if not batch:
            raise HTTPException(404, "OTA batch topilmadi")
        rows = await OTABatchDeviceRepository(session).claimed_processing(batch.id, claimed_ids)

        queued = 0
        skipped = retry_result["retry_skipped"]
        command_repo = CommandRepository(session)
        for row in rows:
            device = await DeviceRepository(session).get(row.device_id)
            if not device or not device.is_active:
                row.status = "skipped"
                row.error_message = "Device inactive or missing"
                row.updated_at = ts
                skipped += 1
                continue
            pending_count = await command_repo.active_pending_count(row.device_id, ts)
            if pending_count >= settings.command_max_pending_per_device:
                row.status = "pending"
                row.error_message = "Pending command limit reached"
                row.updated_at = ts
                skipped += 1
                continue
            command = Command(
                device_id=row.device_id,
                action="ota_check",
                param=json.dumps({"firmware_id": batch.firmware_id, "version": batch.firmware.version}, ensure_ascii=False),
                status="pending",
                created=ts,
                expires_at=ts + settings.command_ttl_sec,
                max_attempts=3,
            )
            command_repo.add(command)
            row.status = "notified"
            row.notified_at = ts
            row.updated_at = ts
            queued += 1

        if queued and batch.status == "pending":
            batch.status = "in_progress"
            batch.started_at = batch.started_at or ts
        await _refresh_batch_counts(session, batch_id=batch.id)
        remaining = await OTABatchDeviceRepository(session).pending_count(batch.id)
        await session.commit()
    return {"ok": True, "batch_id": batch_id, "queued": queued, "skipped": skipped, "remaining": remaining}


async def process_due_ota_batches_once(limit_per_batch: int | None = None) -> dict:
    ts = now_ts()
    async with SessionLocal() as session:
        batch_ids = await OTABatchRepository(session).due_ids(ts)

    processed = []
    errors = []
    for batch_id in batch_ids:
        try:
            processed.append(await process_ota_batch(batch_id, limit_per_batch))
        except HTTPException as exc:
            errors.append({"batch_id": batch_id, "error": exc.detail})
        except Exception as exc:
            errors.append({"batch_id": batch_id, "error": str(exc)})
    return {"ok": not errors, "batches": len(batch_ids), "processed": processed, "errors": errors}


async def cancel_ota_batch(batch_id: int) -> dict:
    ts = now_ts()
    async with SessionLocal() as session:
        batch = await OTABatchRepository(session).get(batch_id)
        if not batch:
            raise HTTPException(404, "OTA batch topilmadi")
        if batch.status in {"completed", "failed", "cancelled"}:
            return {"ok": True, "batch_id": batch.id, "status": batch.status}
        batch.status = "cancelled"
        batch.completed_at = ts
        batch.updated_at = ts
        pending = await OTABatchDeviceRepository(session).pending_rows(batch.id)
        for row in pending:
            row.status = "skipped"
            row.error_message = "Batch cancelled"
            row.updated_at = ts
        await session.commit()
    return {"ok": True, "batch_id": batch_id, "status": "cancelled"}
