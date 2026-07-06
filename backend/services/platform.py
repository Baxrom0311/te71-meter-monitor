import json

from fastapi import HTTPException, UploadFile
from sqlalchemy import and_, desc, func, inspect, select, update

from core.config import settings
from core.database import SessionLocal
from core.metrics import render_http_metrics
from core.security import generate_secret_token, hash_password, verify_password
from core.time import now_ts
from models.entities import (
    Alert,
    Building,
    BuildingUtility,
    Command,
    Device,
    DeviceProvisioningToken,
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
    DeviceProvisioningTokenCreate,
    DeviceStatus,
    DeviceUpdate,
    MeasurementPointCreate,
    MeasurementPointDeviceBind,
    MeasurementPointUpdate,
    MeterReadingBatch,
    MeterReading,
    OtaInstallReport,
    PremiseCreate,
)
from services import alerts as alert_service
from services import analytics as analytics_service
from services import ota as ota_service
from services.websocket import ws_manager


def _as_dict(obj) -> dict:
    return {attr.key: getattr(obj, attr.key) for attr in inspect(obj).mapper.column_attrs}


def _online(last_seen: int | None) -> bool:
    return (now_ts() - (last_seen or 0)) < settings.offline_sec


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


def _global_device_token_ok(token: str | None) -> bool:
    return bool(settings.device_api_token and token and token == settings.device_api_token)


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
    async with SessionLocal() as session:
        if not await session.get(Building, body.building_id):
            raise HTTPException(404, "Dom topilmadi")
        existing = await session.scalar(
            select(BuildingUtility.id).where(
                and_(
                    BuildingUtility.building_id == body.building_id,
                    BuildingUtility.utility_type == body.utility_type,
                )
            )
        )
        if existing:
            raise HTTPException(409, "Bu utility buildingda allaqachon bor")
        item = BuildingUtility(
            building_id=body.building_id,
            utility_type=body.utility_type,
            name=body.name,
            status=body.status,
            created_at=ts,
            updated_at=ts,
        )
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
    async with SessionLocal() as session:
        if not await session.get(Building, body.building_id):
            raise HTTPException(404, "Dom topilmadi")
        premise = Premise(
            building_id=body.building_id,
            number=body.number,
            floor=body.floor,
            premise_type=body.premise_type,
            created_at=ts,
            updated_at=ts,
        )
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


async def _validate_measurement_point_refs(
    session,
    *,
    building_id: int | None = None,
    utility_module_id: int | None = None,
    premise_id: int | None = None,
    parent_id: int | None = None,
    device_id: str | None = None,
) -> None:
    if building_id and not await session.get(Building, building_id):
        raise HTTPException(404, "Building topilmadi")
    if utility_module_id:
        utility = await session.get(BuildingUtility, utility_module_id)
        if not utility:
            raise HTTPException(404, "Utility topilmadi")
        if building_id and utility.building_id != building_id:
            raise HTTPException(422, "Utility boshqa buildingga tegishli")
    if premise_id:
        premise = await session.get(Premise, premise_id)
        if not premise:
            raise HTTPException(404, "Premise topilmadi")
        if building_id and premise.building_id != building_id:
            raise HTTPException(422, "Premise boshqa buildingga tegishli")
    if parent_id and not await session.get(MeasurementPoint, parent_id):
        raise HTTPException(404, "Parent measurement point topilmadi")
    if device_id and not await session.get(Device, device_id):
        raise HTTPException(404, "Qurilma topilmadi")


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
        await _validate_measurement_point_refs(
            session,
            building_id=body.building_id,
            utility_module_id=body.utility_module_id,
            premise_id=body.premise_id,
            parent_id=body.parent_id,
            device_id=body.device_id,
        )
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
        next_building_id = fields.get("building_id", point.building_id)
        await _validate_measurement_point_refs(
            session,
            building_id=next_building_id,
            utility_module_id=fields.get("utility_module_id", point.utility_module_id),
            premise_id=fields.get("premise_id", point.premise_id),
            parent_id=fields.get("parent_id", point.parent_id),
            device_id=fields.get("device_id"),
        )
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


async def reading_stats(device_id: str, hours: int) -> dict:
    return await analytics_service.reading_stats(device_id, hours)


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
    return await analytics_service.building_analytics(building_id, hours)


async def aggregate_hourly_stats_once(hours: int = 48) -> dict:
    return await analytics_service.aggregate_hourly_stats_once(hours)


async def list_hourly_stats(
    building_id: int | None = None,
    utility_type: str | None = None,
    device_id: str | None = None,
    hours: int = 24,
    limit: int = 500,
) -> dict:
    return await analytics_service.list_hourly_stats(building_id, utility_type, device_id, hours, limit)


async def export_csv(device_id: str, hours: int) -> tuple[str, str]:
    return await analytics_service.export_csv(device_id, hours)


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
    ts = now_ts()
    async with SessionLocal() as session:
        device = await session.get(Device, device_id)
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
        pending_count = await session.scalar(
            select(func.count()).select_from(Command).where(
                and_(
                    Command.device_id == device_id,
                    Command.acked.is_(None),
                    Command.status.in_(["pending", "sent"]),
                    (Command.expires_at.is_(None)) | (Command.expires_at > ts),
                )
            )
        ) or 0
        if pending_count >= settings.command_max_pending_per_device:
            raise HTTPException(429, "Bu qurilma uchun pending command limiti oshib ketdi")
        session.add(command)
        await session.commit()
        await session.refresh(command)
    return {"ok": True, "cmd_id": command.id, "expires_at": command.expires_at}


async def reboot_device(device_id: str) -> dict:
    return await create_command(device_id, "reboot", None)


async def pending_commands(device_id: str) -> dict:
    ts = now_ts()
    async with SessionLocal() as session:
        await session.execute(
            update(Command)
            .where(
                and_(
                    Command.device_id == device_id,
                    Command.acked.is_(None),
                    Command.status.in_(["pending", "sent"]),
                    Command.expires_at.is_not(None),
                    Command.expires_at <= ts,
                )
            )
            .values(status="expired", ack_result="expired")
        )
        rows = (
            await session.scalars(
                select(Command)
                .where(
                    and_(
                        Command.device_id == device_id,
                        Command.acked.is_(None),
                        Command.status.in_(["pending", "sent"]),
                        (Command.expires_at.is_(None)) | (Command.expires_at > ts),
                        Command.attempts < Command.max_attempts,
                    )
                )
                .order_by(Command.id)
                .limit(5)
            )
        ).all()
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
        command = await session.get(Command, command_id)
        if command:
            command.acked = now_ts()
            command.ack_result = result
            command.status = "acked"
            await session.commit()
    return {"ok": True}


async def list_commands(device_id: str | None = None, status: str | None = None, limit: int = 100) -> dict:
    stmt = select(Command).order_by(desc(Command.id)).limit(limit)
    if device_id:
        stmt = stmt.where(Command.device_id == device_id)
    if status:
        stmt = stmt.where(Command.status == status)
    async with SessionLocal() as session:
        rows = (await session.scalars(stmt)).all()
    return {"commands": [_as_dict(row) for row in rows]}


async def cleanup_expired_commands_once() -> dict:
    ts = now_ts()
    async with SessionLocal() as session:
        result = await session.execute(
            update(Command)
            .where(
                and_(
                    Command.acked.is_(None),
                    Command.status.in_(["pending", "sent"]),
                    Command.expires_at.is_not(None),
                    Command.expires_at <= ts,
                )
            )
            .values(status="expired", ack_result="expired")
        )
        await session.commit()
    return {"ok": True, "expired_commands": result.rowcount or 0}


async def get_alerts(device_id: str | None, kind: str | None, cleared: bool, limit: int) -> dict:
    return await alert_service.get_alerts(device_id, kind, cleared, limit)


async def list_alert_notifications(status: str | None = None, limit: int = 100) -> dict:
    return await alert_service.list_alert_notifications(status, limit)


async def list_alert_rules(
    utility_type: str | None = None,
    building_id: int | None = None,
    enabled: bool | None = None,
    limit: int = 200,
) -> dict:
    return await alert_service.list_alert_rules(utility_type, building_id, enabled, limit)


async def create_alert_rule(body) -> dict:
    return await alert_service.create_alert_rule(body)


async def update_alert_rule(rule_id: int, body) -> dict:
    return await alert_service.update_alert_rule(rule_id, body)


async def disable_alert_rule(rule_id: int) -> dict:
    return await alert_service.disable_alert_rule(rule_id)


async def clear_alert(alert_id: int) -> dict:
    return await alert_service.clear_alert(alert_id)


async def clear_all_alerts(device_id: str | None) -> dict:
    return await alert_service.clear_all_alerts(device_id)


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
    return await ota_service.ota_upload(
        version,
        notes,
        file,
        hardware_version,
        firmware_mode,
        utility_type,
        device_role,
        sensor_type,
        converter_type,
        description,
        release_notes,
        compatibility_notes,
    )


async def ota_list() -> dict:
    return await ota_service.ota_list()


async def ota_delete(firmware_id: int) -> dict:
    return await ota_service.ota_delete(firmware_id)


async def ota_check(device_id: str, current_version: str) -> dict:
    return await ota_service.ota_check(device_id, current_version)


async def ota_report(body: OtaInstallReport) -> dict:
    return await ota_service.ota_report(body)


async def ota_events(device_id: str | None = None, status: str | None = None, limit: int = 100) -> dict:
    return await ota_service.ota_events(device_id, status, limit)


async def ota_push(device_id: str) -> dict:
    return await create_command(device_id, "ota_check", None)


async def health() -> dict:
    async with SessionLocal() as session:
        dev_count = await session.scalar(select(func.count()).select_from(Device)) or 0
        reading_count = await session.scalar(select(func.count()).select_from(Reading)) or 0
        alert_count = await session.scalar(select(func.count()).select_from(Alert).where(Alert.cleared.is_(False))) or 0
        command_count = await session.scalar(
            select(func.count()).select_from(Command).where(Command.status.in_(["pending", "sent"]))
        ) or 0
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
    lines.extend(render_http_metrics())
    return "\n".join(lines) + "\n"
