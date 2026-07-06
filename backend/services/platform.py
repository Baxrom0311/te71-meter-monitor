import csv
import hashlib
import io
import json
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import Integer, and_, desc, func, inspect, select, update
from sqlalchemy.orm import selectinload

from core.config import settings
from core.database import SessionLocal
from core.security import generate_secret_token, hash_password, verify_password
from core.time import now_ts
from models.entities import (
    Alert,
    Building,
    BuildingUtility,
    Command,
    Device,
    Firmware,
    FirmwareCompatibility,
    MeasurementPoint,
    Premise,
    Reading,
)
from models.schemas import (
    BuildingCreate,
    BuildingDefaultProvision,
    BuildingUtilityCreate,
    BuildingUtilityUpdate,
    BuildingUpdate,
    DeviceRegister,
    DeviceStatus,
    DeviceUpdate,
    MeasurementPointCreate,
    MeasurementPointDeviceBind,
    MeasurementPointUpdate,
    MeterReadingBatch,
    MeterReading,
    PremiseCreate,
)
from services.websocket import ws_manager


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


def _online(last_seen: int | None) -> bool:
    return (now_ts() - (last_seen or 0)) < settings.offline_sec


def _global_device_token_ok(token: str | None) -> bool:
    return bool(settings.device_api_token and token and token == settings.device_api_token)


async def verify_device_access(device_id: str | None, token: str | None) -> None:
    if not device_id:
        raise HTTPException(400, "device_id kerak")
    if _global_device_token_ok(token):
        return
    async with SessionLocal() as session:
        device = await session.get(Device, device_id)
    if device and device.api_token_hash:
        if token and verify_password(token, device.api_token_hash):
            return
        raise HTTPException(401, "Device token noto'g'ri")
    if settings.device_api_token:
        raise HTTPException(401, "Device token noto'g'ri")


async def verify_command_access(command_id: int, token: str | None) -> None:
    async with SessionLocal() as session:
        command = await session.get(Command, command_id)
    if not command:
        raise HTTPException(404, "Command topilmadi")
    await verify_device_access(command.device_id, token)


def _server_targets() -> list[dict]:
    return [
        {"url": url, "priority": index + 1, "enabled": True}
        for index, url in enumerate(settings.public_server_urls)
    ]


async def build_snapshot() -> dict:
    async with SessionLocal() as session:
        devices = (await session.scalars(select(Device).where(Device.is_active.is_(True)))).all()
        alerts = (await session.scalars(select(Alert).order_by(desc(Alert.ts)).limit(20))).all()
    device_rows = [_as_dict(device) | {"online": _online(device.last_seen)} for device in devices]
    return {"devices": device_rows, "alerts": [_as_dict(alert) for alert in alerts]}


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


async def create_building(body: BuildingCreate) -> dict:
    ts = now_ts()
    building = Building(
        name=body.name,
        address=body.address,
        floors=body.floors,
        entrances_count=body.entrances_count,
        description=body.description,
        created_at=ts,
        updated_at=ts,
    )
    async with SessionLocal() as session:
        session.add(building)
        await session.commit()
        await session.refresh(building)
    return {"ok": True, "id": building.id}


async def list_buildings() -> dict:
    async with SessionLocal() as session:
        rows = (await session.scalars(select(Building).order_by(desc(Building.id)))).all()
    return {"buildings": [_as_dict(row) for row in rows]}


async def get_building(building_id: int) -> dict:
    async with SessionLocal() as session:
        building = await session.get(Building, building_id)
    if not building:
        raise HTTPException(404, "Dom topilmadi")
    return _as_dict(building)


async def update_building(building_id: int, body: BuildingUpdate) -> dict:
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "Yangilanadigan maydon yo'q")
    fields["updated_at"] = now_ts()
    async with SessionLocal() as session:
        building = await session.get(Building, building_id)
        if not building:
            raise HTTPException(404, "Dom topilmadi")
        for key, value in fields.items():
            setattr(building, key, value)
        await session.commit()
    return {"ok": True}


async def delete_building(building_id: int) -> dict:
    async with SessionLocal() as session:
        building = await session.get(Building, building_id)
        if not building:
            raise HTTPException(404, "Dom topilmadi")
        building.is_active = False
        building.updated_at = now_ts()
        await session.commit()
    return {"ok": True}


async def create_building_utility(body: BuildingUtilityCreate) -> dict:
    ts = now_ts()
    item = BuildingUtility(
        building_id=body.building_id,
        utility_type=body.utility_type,
        name=body.name,
        status=body.status,
        created_at=ts,
        updated_at=ts,
    )
    async with SessionLocal() as session:
        session.add(item)
        await session.commit()
        await session.refresh(item)
    return {"ok": True, "id": item.id}


async def list_building_utilities(building_id: int) -> dict:
    async with SessionLocal() as session:
        rows = (
            await session.scalars(
                select(BuildingUtility)
                .where(BuildingUtility.building_id == building_id)
                .order_by(BuildingUtility.utility_type)
            )
        ).all()
    return {"utilities": [_as_dict(row) for row in rows]}


async def update_building_utility(building_id: int, utility_id: int, body: BuildingUtilityUpdate) -> dict:
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "Yangilanadigan maydon yo'q")
    fields["updated_at"] = now_ts()
    async with SessionLocal() as session:
        utility = await session.get(BuildingUtility, utility_id)
        if not utility or utility.building_id != building_id:
            raise HTTPException(404, "Utility topilmadi")
        for key, value in fields.items():
            setattr(utility, key, value)
        await session.commit()
    return {"ok": True}


async def provision_building_defaults(building_id: int, body: BuildingDefaultProvision) -> dict:
    ts = now_ts()
    async with SessionLocal() as session:
        building = await session.get(Building, building_id)
        if not building:
            raise HTTPException(404, "Dom topilmadi")

        utilities: dict[str, BuildingUtility] = {}
        for utility_type in ("electricity", "water", "gas"):
            existing = await session.scalar(
                select(BuildingUtility).where(
                    and_(
                        BuildingUtility.building_id == building_id,
                        BuildingUtility.utility_type == utility_type,
                    )
                )
            )
            if existing:
                utilities[utility_type] = existing
                continue
            item = BuildingUtility(
                building_id=building_id,
                utility_type=utility_type,
                name=f"{building.name} {utility_type}",
                status="active",
                created_at=ts,
                updated_at=ts,
            )
            session.add(item)
            await session.flush()
            utilities[utility_type] = item

        point_specs = [
            {
                "utility_type": "electricity",
            "role": "electricity_main_meter",
            "sensor_type": "electric_meter",
            "converter_type": None,
                "location_name": "Asosiy elektr hisoblagich",
                "floor": 1,
                "device_id": body.electricity_device_id,
            },
            {
                "utility_type": "water",
            "role": "water_pressure_bottom",
            "sensor_type": "pressure_sensor",
            "converter_type": None,
                "location_name": "Pastki suv bosimi sensori",
                "floor": 1,
                "device_id": body.water_device_id,
            },
            {
                "utility_type": "water",
            "role": "water_pressure_top",
            "sensor_type": "pressure_sensor",
            "converter_type": None,
                "location_name": "Yuqori suv bosimi sensori",
                "floor": body.top_floor or building.floors,
                "device_id": body.water_device_id,
            },
            {
                "utility_type": "gas",
            "role": "gas_pressure_main",
            "sensor_type": "pressure_sensor",
            "converter_type": None,
                "location_name": "Asosiy gaz bosimi sensori",
                "floor": 1,
                "device_id": body.gas_device_id,
            },
        ]

        created_points = []
        existing_points = []
        for spec in point_specs:
            existing_point = await session.scalar(
                select(MeasurementPoint).where(
                    and_(
                        MeasurementPoint.building_id == building_id,
                        MeasurementPoint.utility_type == spec["utility_type"],
                        MeasurementPoint.role == spec["role"],
                        MeasurementPoint.is_active.is_(True),
                    )
                )
            )
            if existing_point:
                existing_points.append(existing_point)
                continue

            point = MeasurementPoint(
                name=spec["location_name"],
                building_id=building_id,
                utility_module_id=utilities[spec["utility_type"]].id,
                utility_type=spec["utility_type"],
                role=spec["role"],
                sensor_type=spec["sensor_type"],
                converter_type=spec["converter_type"],
                location_name=spec["location_name"],
                floor=spec["floor"],
                device_id=spec["device_id"],
                created_at=ts,
                updated_at=ts,
            )
            session.add(point)
            await session.flush()
            created_points.append(point)

        for device_id, utility_type, device_role, firmware_mode in [
            (body.electricity_device_id, "electricity", "electricity_node", "electricity"),
            (body.water_device_id, "water", "water_node", "water"),
            (body.gas_device_id, "gas", "gas_node", "gas"),
        ]:
            if not device_id:
                continue
            device = await session.get(Device, device_id)
            if not device:
                device = Device(id=device_id, name=device_id, registered=ts, created_at=ts)
                session.add(device)
            device.building_id = building_id
            device.utility_type = utility_type
            device.device_role = device_role
            device.firmware_mode = firmware_mode
            device.updated_at = ts

        await session.commit()

    return {
        "ok": True,
        "building_id": building_id,
        "utilities": [_as_dict(item) for item in utilities.values()],
        "created_points": [_as_dict(point) for point in created_points],
        "existing_points": [_as_dict(point) for point in existing_points],
    }


async def create_premise(body: PremiseCreate) -> dict:
    ts = now_ts()
    premise = Premise(
        building_id=body.building_id,
        number=body.number,
        floor=body.floor,
        premise_type=body.premise_type,
        created_at=ts,
        updated_at=ts,
    )
    async with SessionLocal() as session:
        session.add(premise)
        await session.commit()
        await session.refresh(premise)
    return {"ok": True, "id": premise.id}


async def list_premises(building_id: int | None = None) -> dict:
    stmt = select(Premise).order_by(Premise.building_id, Premise.floor, Premise.number)
    if building_id:
        stmt = stmt.where(Premise.building_id == building_id)
    async with SessionLocal() as session:
        rows = (await session.scalars(stmt)).all()
    return {"premises": [_as_dict(row) for row in rows]}


async def create_measurement_point(body: MeasurementPointCreate) -> dict:
    ts = now_ts()
    point = MeasurementPoint(
        name=body.name,
        utility_type=body.utility_type,
        role=body.role,
        sensor_type=body.sensor_type,
        converter_type=body.converter_type,
        location_name=body.location_name,
        building_id=body.building_id,
        utility_module_id=body.utility_module_id,
        premise_id=body.premise_id,
        parent_id=body.parent_id,
        device_id=body.device_id,
        meter_serial=body.meter_serial,
        floor=body.floor,
        created_at=ts,
        updated_at=ts,
    )
    async with SessionLocal() as session:
        session.add(point)
        await session.flush()
        if body.device_id:
            await session.execute(
                update(Device).where(Device.id == body.device_id).values(point_id=point.id)
            )
        await session.commit()
        await session.refresh(point)
    return {"ok": True, "id": point.id}


async def get_measurement_point(point_id: int) -> dict:
    async with SessionLocal() as session:
        point = await session.get(MeasurementPoint, point_id)
    if not point:
        raise HTTPException(404, "Measurement point topilmadi")
    return _as_dict(point)


async def update_measurement_point(point_id: int, body: MeasurementPointUpdate) -> dict:
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "Yangilanadigan maydon yo'q")
    fields["updated_at"] = now_ts()
    async with SessionLocal() as session:
        point = await session.get(MeasurementPoint, point_id)
        if not point:
            raise HTTPException(404, "Measurement point topilmadi")
        for key, value in fields.items():
            setattr(point, key, value)
        if "device_id" in fields and fields["device_id"]:
            device = await session.get(Device, fields["device_id"])
            if device:
                device.point_id = point.id
                device.building_id = point.building_id or device.building_id
                device.utility_type = point.utility_type
                device.updated_at = now_ts()
        await session.commit()
    return {"ok": True}


async def bind_measurement_point_device(point_id: int, body: MeasurementPointDeviceBind) -> dict:
    async with SessionLocal() as session:
        point = await session.get(MeasurementPoint, point_id)
        if not point:
            raise HTTPException(404, "Measurement point topilmadi")
        device = await session.get(Device, body.device_id)
        ts = now_ts()
        if not device:
            device = Device(id=body.device_id, name=body.device_id, registered=ts, created_at=ts)
            session.add(device)
        point.device_id = body.device_id
        point.updated_at = ts
        device.point_id = point.id
        device.building_id = point.building_id
        device.utility_type = point.utility_type
        if point.utility_type in ("electricity", "water", "gas"):
            device.firmware_mode = point.utility_type
            device.device_role = f"{point.utility_type}_node"
        device.updated_at = ts
        await session.commit()
    return {"ok": True}


async def delete_measurement_point(point_id: int) -> dict:
    async with SessionLocal() as session:
        point = await session.get(MeasurementPoint, point_id)
        if not point:
            raise HTTPException(404, "Measurement point topilmadi")
        point.is_active = False
        point.updated_at = now_ts()
        await session.commit()
    return {"ok": True}


async def list_measurement_points(
    building_id: int | None = None,
    utility_type: str | None = None,
    role: str | None = None,
) -> dict:
    stmt = select(MeasurementPoint).where(MeasurementPoint.is_active.is_(True)).order_by(desc(MeasurementPoint.id))
    if building_id:
        stmt = stmt.where(MeasurementPoint.building_id == building_id)
    if utility_type:
        stmt = stmt.where(MeasurementPoint.utility_type == utility_type)
    if role:
        stmt = stmt.where(MeasurementPoint.role == role)
    async with SessionLocal() as session:
        rows = (await session.scalars(stmt)).all()
    return {"points": [_as_dict(row) for row in rows]}


async def register_device(body: DeviceRegister) -> dict:
    ts = now_ts()
    async with SessionLocal() as session:
        device = await session.get(Device, body.device_id)
        if not device:
            device = Device(id=body.device_id, name=body.name or body.device_id, registered=ts, created_at=ts)
            session.add(device)

        device.name = device.name or body.name or body.device_id
        device.utility_type = body.utility_type
        device.device_role = body.device_role
        device.firmware_mode = body.firmware_mode
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
        device.building_id = body.building_id or device.building_id
        device.point_id = body.point_id or device.point_id
        device.last_seen = ts
        device.updated_at = ts
        await session.commit()

    await ws_manager.broadcast(
        {
            "type": "device_online",
            "device_id": body.device_id,
            "utility_type": body.utility_type,
            "firmware_mode": body.firmware_mode,
        }
    )
    return {"ok": True}


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
    fields["updated_at"] = now_ts()
    async with SessionLocal() as session:
        await session.execute(update(Device).where(Device.id == device_id).values(**fields))
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
        device.updated_at = ts
        await session.commit()
    return {"device_id": device_id, "device_token": token, "token_type": "device"}


async def _check_alerts(session, reading: MeterReading) -> None:
    ts = now_ts()
    alerts: list[Alert] = []
    if reading.utility_type == "electricity":
        for phase, voltage in [("L1", reading.voltage_l1), ("L2", reading.voltage_l2), ("L3", reading.voltage_l3)]:
            if voltage is None:
                continue
            if voltage < settings.voltage_min or voltage > settings.voltage_max:
                kind = "overvoltage" if voltage > settings.voltage_max else "undervoltage"
                alerts.append(
                    Alert(
                        device_id=reading.device_id,
                        building_id=reading.building_id,
                        point_id=reading.point_id,
                        utility_type=reading.utility_type,
                        severity="warning",
                        ts=ts,
                        kind=kind,
                        value=voltage,
                        message=f"{phase}: {voltage:.1f}V",
                    )
                )
        if reading.frequency and (
            reading.frequency < settings.frequency_min or reading.frequency > settings.frequency_max
        ):
            alerts.append(
                Alert(
                    device_id=reading.device_id,
                    building_id=reading.building_id,
                    point_id=reading.point_id,
                    utility_type=reading.utility_type,
                    severity="warning",
                    ts=ts,
                    kind="frequency",
                    value=reading.frequency,
                    message=f"Chastota: {reading.frequency:.2f}Hz",
                )
            )
    elif reading.utility_type == "water":
        if reading.pressure_bottom_bar is not None and reading.pressure_top_bar is not None:
            if reading.pressure_bottom_bar > 1.0 and reading.pressure_top_bar < 0.5:
                alerts.append(
                    Alert(
                        device_id=reading.device_id,
                        building_id=reading.building_id,
                        point_id=reading.point_id,
                        utility_type="water",
                        severity="critical",
                        ts=ts,
                        kind="water_not_reaching_top",
                        value=reading.pressure_top_bar,
                        message="Pastda bosim bor, yuqorida suv bosimi past",
                    )
                )
    elif reading.utility_type == "gas" and reading.leak_detected:
        alerts.append(
            Alert(
                device_id=reading.device_id,
                building_id=reading.building_id,
                point_id=reading.point_id,
                utility_type="gas",
                severity="critical",
                ts=ts,
                kind="gas_leak",
                message="Gaz sizishi aniqlandi",
            )
        )

    for alert in alerts:
        session.add(alert)
        await ws_manager.broadcast(
            {
                "type": "alert",
                "kind": alert.kind,
                "severity": alert.severity,
                "utility_type": alert.utility_type,
                "device_id": alert.device_id,
                "message": alert.message,
            }
        )


async def save_reading(body: MeterReading) -> int:
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
        await _check_alerts(session, body)
        await session.commit()
    return ts


async def save_reading_batch(body: MeterReadingBatch) -> dict:
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


async def reading_stats(device_id: str, hours: int) -> dict:
    cutoff = now_ts() - hours * 3600
    hour_ts = (Reading.ts / 3600).cast(Integer) * 3600
    stmt = (
        select(
            hour_ts.label("hour_ts"),
            func.round(func.avg(Reading.voltage_l1), 1).label("avg_v1"),
            func.round(func.min(Reading.voltage_l1), 1).label("min_v1"),
            func.round(func.max(Reading.voltage_l1), 1).label("max_v1"),
            func.round(func.avg(Reading.current_l1), 3).label("avg_i1"),
            func.round(func.avg(Reading.power_w), 0).label("avg_pw"),
            func.round(func.max(Reading.power_w), 0).label("max_pw"),
            func.round(func.avg(Reading.frequency), 2).label("avg_freq"),
            func.round(func.max(Reading.energy_kwh), 3).label("energy_kwh"),
            func.round(func.avg(Reading.pressure_bar), 3).label("avg_pressure_bar"),
            func.round(func.avg(Reading.pressure_bottom_bar), 3).label("avg_pressure_bottom_bar"),
            func.round(func.avg(Reading.pressure_top_bar), 3).label("avg_pressure_top_bar"),
            func.round(func.avg(Reading.flow_rate), 3).label("avg_flow_rate"),
            func.round(func.max(Reading.volume_m3), 3).label("volume_m3"),
            func.count().label("samples"),
        )
        .where(and_(Reading.device_id == device_id, Reading.ts > cutoff))
        .group_by(hour_ts)
        .order_by(hour_ts)
    )
    async with SessionLocal() as session:
        rows = (await session.execute(stmt)).mappings().all()
    return {"stats": [dict(row) for row in rows], "hours": hours}


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


async def building_analytics(building_id: int, hours: int) -> dict:
    cutoff = now_ts() - hours * 3600
    async with SessionLocal() as session:
        electricity = (
            await session.execute(
                select(
                    func.count().label("samples"),
                    func.round(func.max(Reading.energy_kwh), 3).label("energy_kwh"),
                    func.round(func.avg(Reading.power_w), 2).label("avg_power_w"),
                    func.round(func.max(Reading.power_w), 2).label("max_power_w"),
                    func.round(func.avg(Reading.voltage_l1), 2).label("avg_voltage_l1"),
                ).where(
                    and_(
                        Reading.building_id == building_id,
                        Reading.utility_type == "electricity",
                        Reading.ts > cutoff,
                    )
                )
            )
        ).mappings().one()

        water = (
            await session.execute(
                select(
                    func.count().label("samples"),
                    func.round(func.avg(Reading.pressure_bottom_bar), 3).label("avg_pressure_bottom_bar"),
                    func.round(func.avg(Reading.pressure_top_bar), 3).label("avg_pressure_top_bar"),
                    func.round(
                        func.avg(Reading.pressure_bottom_bar - Reading.pressure_top_bar), 3
                    ).label("avg_pressure_delta_bar"),
                    func.sum(
                        ((Reading.pressure_bottom_bar > 1.0) & (Reading.pressure_top_bar < 0.5)).cast(Integer)
                    ).label("top_pressure_problem_count"),
                ).where(
                    and_(
                        Reading.building_id == building_id,
                        Reading.utility_type == "water",
                        Reading.ts > cutoff,
                    )
                )
            )
        ).mappings().one()

        gas = (
            await session.execute(
                select(
                    func.count().label("samples"),
                    func.round(func.avg(Reading.pressure_bar), 4).label("avg_pressure_bar"),
                    func.round(func.min(Reading.pressure_bar), 4).label("min_pressure_bar"),
                    func.round(func.max(Reading.pressure_bar), 4).label("max_pressure_bar"),
                    func.sum(Reading.leak_detected.cast(Integer)).label("leak_count"),
                ).where(
                    and_(
                        Reading.building_id == building_id,
                        Reading.utility_type == "gas",
                        Reading.ts > cutoff,
                    )
                )
            )
        ).mappings().one()

        active_alerts = (
            await session.scalar(
                select(func.count()).select_from(Alert).where(
                    and_(Alert.building_id == building_id, Alert.cleared.is_(False), Alert.ts > cutoff)
                )
            )
            or 0
        )

    return {
        "building_id": building_id,
        "hours": hours,
        "active_alerts": active_alerts,
        "electricity": dict(electricity),
        "water": dict(water),
        "gas": dict(gas),
    }


async def export_csv(device_id: str, hours: int) -> tuple[str, str]:
    cutoff = now_ts() - hours * 3600
    async with SessionLocal() as session:
        rows = (
            await session.scalars(
                select(Reading).where(and_(Reading.device_id == device_id, Reading.ts > cutoff)).order_by(Reading.ts)
            )
        ).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    dict_rows = [_as_dict(row) for row in rows]
    if dict_rows:
        writer.writerow(dict_rows[0].keys())
        for row in dict_rows:
            writer.writerow(row.values())
    filename = f"{device_id.replace(':', '')}_{hours}h.csv"
    return filename, buf.getvalue()


async def summary() -> dict:
    n = now_ts()
    async with SessionLocal() as session:
        total = await session.scalar(select(func.count()).select_from(Device).where(Device.is_active.is_(True))) or 0
        online = (
            await session.scalar(
                select(func.count()).select_from(Device).where(and_(Device.is_active.is_(True), Device.last_seen > n - settings.offline_sec))
            )
            or 0
        )
        active_alerts = (
            await session.scalar(select(func.count()).select_from(Alert).where(and_(Alert.cleared.is_(False), Alert.ts > n - 86400)))
            or 0
        )
        reads_last_hour = await session.scalar(select(func.count()).select_from(Reading).where(Reading.ts > n - 3600)) or 0
        total_energy = await session.scalar(select(func.sum(Reading.energy_kwh))) or 0
        buildings = await session.scalar(select(func.count()).select_from(Building)) or 0
        points = await session.scalar(select(func.count()).select_from(MeasurementPoint).where(MeasurementPoint.is_active.is_(True))) or 0
    return {
        "devices_total": total,
        "devices_online": online,
        "devices_offline": total - online,
        "alerts_active": active_alerts,
        "reads_last_hour": reads_last_hour,
        "total_energy_kwh": round(total_energy, 2),
        "buildings": buildings,
        "measurement_points": points,
        "ws_clients": ws_manager.count,
    }


async def create_relay_command(device_id: str, action_value: str) -> dict:
    if action_value not in ("on", "off"):
        raise HTTPException(400, "action: 'on' yoki 'off'")
    return await create_command(device_id, f"relay_{action_value}", None)


async def create_command(device_id: str, action: str, params: dict | None = None) -> dict:
    command = Command(
        device_id=device_id,
        action=action,
        param=json.dumps(params, ensure_ascii=False) if params else None,
        status="pending",
        created=now_ts(),
    )
    async with SessionLocal() as session:
        session.add(command)
        await session.commit()
        await session.refresh(command)
    return {"ok": True, "cmd_id": command.id}


async def reboot_device(device_id: str) -> dict:
    return await create_command(device_id, "reboot", None)


async def pending_commands(device_id: str) -> dict:
    async with SessionLocal() as session:
        rows = (
            await session.scalars(
                select(Command)
                .where(and_(Command.device_id == device_id, Command.acked.is_(None)))
                .order_by(Command.id)
                .limit(5)
            )
        ).all()
        for row in rows:
            if row.sent is None:
                row.sent = now_ts()
                row.status = "sent"
        await session.commit()
    return {"commands": [{"id": row.id, "action": row.action, "param": row.param} for row in rows]}


async def ack_command(command_id: int, result: str) -> dict:
    async with SessionLocal() as session:
        command = await session.get(Command, command_id)
        if command:
            command.acked = now_ts()
            command.ack_result = result
            command.status = "acked"
            await session.commit()
    return {"ok": True}


async def get_alerts(device_id: str | None, kind: str | None, cleared: bool, limit: int) -> dict:
    stmt = select(Alert).where(Alert.cleared.is_(cleared)).order_by(desc(Alert.ts)).limit(limit)
    if device_id:
        stmt = stmt.where(Alert.device_id == device_id)
    if kind:
        stmt = stmt.where(Alert.kind == kind)
    async with SessionLocal() as session:
        rows = (await session.scalars(stmt)).all()
    return {"alerts": [_as_dict(row) for row in rows]}


async def clear_alert(alert_id: int) -> dict:
    async with SessionLocal() as session:
        alert = await session.get(Alert, alert_id)
        if alert:
            alert.cleared = True
            alert.cleared_at = now_ts()
            await session.commit()
    return {"ok": True}


async def clear_all_alerts(device_id: str | None) -> dict:
    values = {"cleared": True, "cleared_at": now_ts()}
    stmt = update(Alert).values(**values)
    if device_id:
        stmt = stmt.where(Alert.device_id == device_id)
    async with SessionLocal() as session:
        await session.execute(stmt)
        await session.commit()
    return {"ok": True}


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


async def ota_push(device_id: str) -> dict:
    return await create_command(device_id, "ota_check", None)


async def health() -> dict:
    async with SessionLocal() as session:
        dev_count = await session.scalar(select(func.count()).select_from(Device)) or 0
        reading_count = await session.scalar(select(func.count()).select_from(Reading)) or 0
        alert_count = await session.scalar(select(func.count()).select_from(Alert).where(Alert.cleared.is_(False))) or 0
        command_count = await session.scalar(select(func.count()).select_from(Command).where(Command.status == "pending")) or 0
    return {
        "status": "ok",
        "ts": now_ts(),
        "devices": dev_count,
        "readings": reading_count,
        "open_alerts": alert_count,
        "pending_commands": command_count,
        "ws_clients": ws_manager.count,
        "version": settings.app_version,
        "data_keep_days": settings.data_keep_days,
        "workers": {
            "inline": settings.run_inline_workers,
            "celery_broker": bool(settings.celery_broker_url),
        },
    }


async def metrics_text() -> str:
    data = await health()
    lines = [
        "# HELP meter_monitor_devices_total Total registered devices.",
        "# TYPE meter_monitor_devices_total gauge",
        f"meter_monitor_devices_total {data['devices']}",
        "# HELP meter_monitor_readings_total Total stored readings.",
        "# TYPE meter_monitor_readings_total gauge",
        f"meter_monitor_readings_total {data['readings']}",
        "# HELP meter_monitor_open_alerts Open alerts.",
        "# TYPE meter_monitor_open_alerts gauge",
        f"meter_monitor_open_alerts {data['open_alerts']}",
        "# HELP meter_monitor_pending_commands Pending commands.",
        "# TYPE meter_monitor_pending_commands gauge",
        f"meter_monitor_pending_commands {data['pending_commands']}",
        "# HELP meter_monitor_ws_clients Connected websocket clients.",
        "# TYPE meter_monitor_ws_clients gauge",
        f"meter_monitor_ws_clients {data['ws_clients']}",
    ]
    return "\n".join(lines) + "\n"
