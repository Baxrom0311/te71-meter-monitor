from fastapi import HTTPException
from sqlalchemy import and_, desc, inspect, select, update

from core.database import SessionLocal
from core.time import now_ts
from models.entities import Building, BuildingUtility, Device, MeasurementPoint, Premise
from models.schemas import (
    BuildingCreate,
    BuildingDefaultProvision,
    BuildingUtilityCreate,
    BuildingUtilityUpdate,
    BuildingUpdate,
    MeasurementPointCreate,
    MeasurementPointDeviceBind,
    MeasurementPointUpdate,
    PremiseCreate,
)


def _as_dict(obj) -> dict:
    return {attr.key: getattr(obj, attr.key) for attr in inspect(obj).mapper.column_attrs}


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
            await session.execute(update(Device).where(Device.id == body.device_id).values(point_id=point.id))
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
