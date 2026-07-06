import json

from fastapi import HTTPException
from sqlalchemy import and_, desc, func, inspect, select

from core.config import settings
from core.database import SessionLocal
from core.time import now_ts
from models.entities import Device, MeasurementPoint, Reading
from models.schemas import MeterReading, MeterReadingBatch
from services import alerts as alert_service


def _as_dict(obj) -> dict:
    return {attr.key: getattr(obj, attr.key) for attr in inspect(obj).mapper.column_attrs}


def _validate_range(name: str, value: float | None, minimum: float | None = None, maximum: float | None = None) -> None:
    if value is None:
        return
    if minimum is not None and value < minimum:
        raise HTTPException(422, f"{name} minimal qiymatdan kichik: {value}")
    if maximum is not None and value > maximum:
        raise HTTPException(422, f"{name} maksimal qiymatdan katta: {value}")


def _validate_reading(body: MeterReading) -> None:
    if not body.device_id.strip():
        raise HTTPException(422, "device_id kerak")

    for name in ("voltage_l1", "voltage_l2", "voltage_l3"):
        _validate_range(name, getattr(body, name), 0, settings.max_voltage)
    for name in ("current_l1", "current_l2", "current_l3"):
        _validate_range(name, getattr(body, name), 0, settings.max_current)
    _validate_range("frequency", body.frequency, 0, 100)
    _validate_range("pf", body.pf, -1, 1)
    for name in ("energy_kwh", "energy_t1", "energy_t2", "energy_t3", "energy_t4"):
        _validate_range(name, getattr(body, name), 0, None)
    for name in ("pressure_bar", "pressure_bottom_bar", "pressure_top_bar"):
        _validate_range(name, getattr(body, name), 0, settings.max_pressure_bar)
    for name in ("flow_rate", "volume_m3"):
        _validate_range(name, getattr(body, name), 0, None)
    _validate_range("temperature_c", body.temperature_c, settings.min_temperature_c, settings.max_temperature_c)


async def save_reading(body: MeterReading) -> int:
    _validate_reading(body)
    ts = now_ts()
    async with SessionLocal() as session:
        if body.reading_id:
            existing = await session.scalar(
                select(Reading.id).where(and_(Reading.device_id == body.device_id, Reading.reading_id == body.reading_id))
            )
            if existing:
                return ts

        device = await session.get(Device, body.device_id)
        if not device:
            device = Device(
                id=body.device_id,
                name=body.device_id,
                utility_type=body.utility_type,
                registered=ts,
                created_at=ts,
            )
            session.add(device)

        device.last_seen = ts
        device.utility_type = body.utility_type or device.utility_type
        device.software_version = body.software_version or body.fw_version or device.software_version
        device.hardware_version = body.hardware_version or device.hardware_version
        device.fw_version = body.fw_version or device.fw_version
        device.building_id = body.building_id or device.building_id
        device.point_id = body.point_id or device.point_id
        device.updated_at = ts

        reading = Reading(
            device_id=body.device_id,
            reading_id=body.reading_id,
            sequence_no=body.sequence_no,
            building_id=body.building_id or device.building_id,
            point_id=body.point_id or device.point_id,
            utility_type=body.utility_type,
            sensor_type=body.sensor_type,
            ts=ts,
            voltage_l1=body.voltage_l1,
            voltage_l2=body.voltage_l2,
            voltage_l3=body.voltage_l3,
            current_l1=body.current_l1,
            current_l2=body.current_l2,
            current_l3=body.current_l3,
            power_w=body.power_w,
            power_var=body.power_var,
            frequency=body.frequency,
            pf=body.pf,
            energy_kwh=body.energy_kwh,
            energy_t1=body.energy_t1,
            energy_t2=body.energy_t2,
            energy_t3=body.energy_t3,
            energy_t4=body.energy_t4,
            relay_on=body.relay_on,
            pressure_bar=body.pressure_bar,
            pressure_bottom_bar=body.pressure_bottom_bar,
            pressure_top_bar=body.pressure_top_bar,
            flow_rate=body.flow_rate,
            volume_m3=body.volume_m3,
            temperature_c=body.temperature_c,
            leak_detected=body.leak_detected,
            valve_open=body.valve_open,
            raw_payload=json.dumps(body.model_dump(), ensure_ascii=False, default=str),
            created_at=ts,
        )
        session.add(reading)
        await alert_service.check_alerts(session, body)
        await session.commit()
    return ts


async def save_reading_batch(body: MeterReadingBatch) -> dict:
    if not body.readings:
        raise HTTPException(422, "readings bo'sh bo'lmasin")
    expected_device_id = body.device_id or body.readings[0].device_id
    if not expected_device_id:
        raise HTTPException(422, "device_id kerak")
    mismatched = [
        index
        for index, reading in enumerate(body.readings)
        if reading.device_id != expected_device_id
    ]
    if mismatched:
        raise HTTPException(403, "Batch ichida boshqa device_id bor")

    accepted = 0
    skipped = 0
    errors: list[dict] = []
    timestamps: list[int] = []

    for index, reading in enumerate(body.readings):
        try:
            if reading.reading_id:
                async with SessionLocal() as session:
                    exists = await session.scalar(
                        select(Reading.id).where(
                            and_(Reading.device_id == reading.device_id, Reading.reading_id == reading.reading_id)
                        )
                    )
                if exists:
                    skipped += 1
                    continue
            ts = await save_reading(reading)
            timestamps.append(ts)
            accepted += 1
        except Exception as exc:
            errors.append({"index": index, "error": str(exc)})

    return {
        "ok": not errors,
        "accepted": accepted,
        "skipped": skipped,
        "errors": errors,
        "last_ts": timestamps[-1] if timestamps else None,
    }


async def latest_reading(device_id: str) -> dict:
    async with SessionLocal() as session:
        row = await session.scalar(
            select(Reading).where(Reading.device_id == device_id).order_by(desc(Reading.ts)).limit(1)
        )
    if not row:
        raise HTTPException(404, "Ma'lumot yo'q")
    return _as_dict(row)


async def reading_history(device_id: str, page: int, limit: int, hours: int | None) -> dict:
    offset = (page - 1) * limit
    stmt = select(Reading).where(Reading.device_id == device_id)
    count_stmt = select(func.count()).select_from(Reading).where(Reading.device_id == device_id)
    if hours:
        cutoff = now_ts() - hours * 3600
        stmt = stmt.where(Reading.ts > cutoff)
        count_stmt = count_stmt.where(Reading.ts > cutoff)
    stmt = stmt.order_by(desc(Reading.ts)).limit(limit).offset(offset)
    async with SessionLocal() as session:
        total = await session.scalar(count_stmt) or 0
        rows = (await session.scalars(stmt)).all()
    return {"readings": [_as_dict(row) for row in rows], "total": total, "page": page, "pages": (total + limit - 1) // limit}


async def building_latest_readings(building_id: int, utility_type: str | None = None) -> dict:
    async with SessionLocal() as session:
        points_stmt = select(MeasurementPoint).where(
            and_(MeasurementPoint.building_id == building_id, MeasurementPoint.is_active.is_(True))
        )
        if utility_type:
            points_stmt = points_stmt.where(MeasurementPoint.utility_type == utility_type)
        points = (await session.scalars(points_stmt.order_by(MeasurementPoint.utility_type, MeasurementPoint.role))).all()

        result = []
        for point in points:
            reading = await session.scalar(
                select(Reading)
                .where(Reading.point_id == point.id)
                .order_by(desc(Reading.ts))
                .limit(1)
            )
            row = _as_dict(point)
            row["latest_reading"] = _as_dict(reading) if reading else None
            result.append(row)
    return {"building_id": building_id, "points": result}


async def building_reading_history(
    building_id: int,
    utility_type: str | None,
    page: int,
    limit: int,
    hours: int | None,
) -> dict:
    offset = (page - 1) * limit
    stmt = select(Reading).where(Reading.building_id == building_id)
    count_stmt = select(func.count()).select_from(Reading).where(Reading.building_id == building_id)
    if utility_type:
        stmt = stmt.where(Reading.utility_type == utility_type)
        count_stmt = count_stmt.where(Reading.utility_type == utility_type)
    if hours:
        cutoff = now_ts() - hours * 3600
        stmt = stmt.where(Reading.ts > cutoff)
        count_stmt = count_stmt.where(Reading.ts > cutoff)
    stmt = stmt.order_by(desc(Reading.ts)).limit(limit).offset(offset)
    async with SessionLocal() as session:
        total = await session.scalar(count_stmt) or 0
        rows = (await session.scalars(stmt)).all()
    return {
        "building_id": building_id,
        "readings": [_as_dict(row) for row in rows],
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit,
    }
