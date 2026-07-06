import json

from fastapi import HTTPException, UploadFile
from sqlalchemy import and_, desc, func, inspect, select, update

from core.config import settings
from core.database import SessionLocal
from core.metrics import render_http_metrics
from core.time import now_ts
from models.entities import (
    Alert,
    Building,
    BuildingUtility,
    Command,
    Device,
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
from services import devices as devices_service
from services import ota as ota_service
from services import readings as readings_service
from services.websocket import ws_manager


def _as_dict(obj) -> dict:
    return {attr.key: getattr(obj, attr.key) for attr in inspect(obj).mapper.column_attrs}


async def verify_device_access(device_id: str | None, token: str | None) -> None:
    return await devices_service.verify_device_access(device_id, token)


async def verify_command_access(command_id: int, token: str | None) -> None:
    async with SessionLocal() as session:
        command = await session.get(Command, command_id)
    if not command:
        raise HTTPException(404, "Command topilmadi")
    await verify_device_access(command.device_id, token)


async def build_snapshot() -> dict:
    async with SessionLocal() as session:
        devices = (await session.scalars(select(Device).where(Device.is_active.is_(True)))).all()
        alerts = (await session.scalars(select(Alert).order_by(desc(Alert.ts)).limit(20))).all()
    device_rows = [_as_dict(device) | {"online": devices_service.online_status(device.last_seen)} for device in devices]
    return {"devices": device_rows, "alerts": [_as_dict(alert) for alert in alerts]}


async def get_device_config(device_id: str) -> dict:
    return await devices_service.get_device_config(device_id)


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
    return await devices_service.register_device(body)


async def update_device_status(body: DeviceStatus) -> dict:
    return await devices_service.update_device_status(body)


async def list_devices(
    online: bool | None = None,
    meter_type: str | None = None,
    group: str | None = None,
    building: str | None = None,
    utility_type: str | None = None,
) -> dict:
    return await devices_service.list_devices(online, meter_type, group, building, utility_type)


async def get_device(device_id: str) -> dict:
    return await devices_service.get_device(device_id)


async def update_device(device_id: str, body: DeviceUpdate) -> dict:
    return await devices_service.update_device(device_id, body)


async def rotate_device_token(device_id: str) -> dict:
    return await devices_service.rotate_device_token(device_id)


async def revoke_device_token(device_id: str, admin: dict) -> dict:
    return await devices_service.revoke_device_token(device_id, admin)


async def create_provisioning_token(body: DeviceProvisioningTokenCreate, admin: dict) -> dict:
    return await devices_service.create_provisioning_token(body, admin)


async def list_provisioning_tokens(active_only: bool = True, limit: int = 100) -> dict:
    return await devices_service.list_provisioning_tokens(active_only, limit)


async def revoke_provisioning_token(token_id: int, admin: dict) -> dict:
    return await devices_service.revoke_provisioning_token(token_id, admin)


async def save_reading(body: MeterReading) -> int:
    return await readings_service.save_reading(body)


async def save_reading_batch(body: MeterReadingBatch) -> dict:
    return await readings_service.save_reading_batch(body)


async def latest_reading(device_id: str) -> dict:
    return await readings_service.latest_reading(device_id)


async def reading_history(device_id: str, page: int, limit: int, hours: int | None) -> dict:
    return await readings_service.reading_history(device_id, page, limit, hours)


async def reading_stats(device_id: str, hours: int) -> dict:
    return await analytics_service.reading_stats(device_id, hours)


async def building_latest_readings(building_id: int, utility_type: str | None = None) -> dict:
    return await readings_service.building_latest_readings(building_id, utility_type)


async def building_reading_history(
    building_id: int,
    utility_type: str | None,
    page: int,
    limit: int,
    hours: int | None,
) -> dict:
    return await readings_service.building_reading_history(building_id, utility_type, page, limit, hours)


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
