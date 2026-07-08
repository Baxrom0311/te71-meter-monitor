from fastapi import HTTPException

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
from repositories.base import model_to_dict
from repositories.buildings import (
    BuildingRepository,
    BuildingUtilityRepository,
    MeasurementPointRepository,
    PremiseRepository,
)
from repositories.devices import DeviceRepository




async def create_building(body: BuildingCreate) -> dict:
    ts = now_ts()
    building = Building(
        name=body.name,
        address=body.address,
        maps_url=body.maps_url,
        latitude=body.latitude,
        longitude=body.longitude,
        floors=body.floors,
        entrances_count=body.entrances_count,
        description=body.description,
        created_at=ts,
        updated_at=ts,
    )
    async with SessionLocal() as session:
        BuildingRepository(session).add(building)
        await session.commit()
        await session.refresh(building)
    return {"ok": True, "id": building.id}


async def list_buildings() -> dict:
    async with SessionLocal() as session:
        rows = await BuildingRepository(session).list_ordered()
    return {"buildings": [model_to_dict(row) for row in rows]}


async def get_building(building_id: int) -> dict:
    async with SessionLocal() as session:
        building = await BuildingRepository(session).get(building_id)
    if not building:
        raise HTTPException(404, "Dom topilmadi")
    return model_to_dict(building)


async def update_building(building_id: int, body: BuildingUpdate) -> dict:
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(400, "Yangilanadigan maydon yo'q")
    fields["updated_at"] = now_ts()
    async with SessionLocal() as session:
        building = await BuildingRepository(session).get(building_id)
        if not building:
            raise HTTPException(404, "Dom topilmadi")
        for key, value in fields.items():
            setattr(building, key, value)
        await session.commit()
    return {"ok": True}


async def delete_building(building_id: int) -> dict:
    async with SessionLocal() as session:
        building = await BuildingRepository(session).get(building_id)
        if not building:
            raise HTTPException(404, "Dom topilmadi")
        building.is_active = False
        building.updated_at = now_ts()
        await session.commit()
    return {"ok": True}


async def create_building_utility(body: BuildingUtilityCreate) -> dict:
    ts = now_ts()
    async with SessionLocal() as session:
        building_repo = BuildingRepository(session)
        utility_repo = BuildingUtilityRepository(session)
        if not await building_repo.get(body.building_id):
            raise HTTPException(404, "Dom topilmadi")
        existing = await utility_repo.get_by_building_type(body.building_id, body.utility_type)
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
        utility_repo.add(item)
        await session.commit()
        await session.refresh(item)
    return {"ok": True, "id": item.id}


async def list_building_utilities(building_id: int) -> dict:
    async with SessionLocal() as session:
        rows = await BuildingUtilityRepository(session).list_by_building(building_id)
    return {"utilities": [model_to_dict(row) for row in rows]}


async def update_building_utility(building_id: int, utility_id: int, body: BuildingUtilityUpdate) -> dict:
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(400, "Yangilanadigan maydon yo'q")
    fields["updated_at"] = now_ts()
    async with SessionLocal() as session:
        utility = await BuildingUtilityRepository(session).get_for_building(building_id, utility_id)
        if not utility:
            raise HTTPException(404, "Utility topilmadi")
        for key, value in fields.items():
            setattr(utility, key, value)
        await session.commit()
    return {"ok": True}


async def provision_building_defaults(building_id: int, body: BuildingDefaultProvision) -> dict:
    ts = now_ts()
    async with SessionLocal() as session:
        building_repo = BuildingRepository(session)
        utility_repo = BuildingUtilityRepository(session)
        point_repo = MeasurementPointRepository(session)
        device_repo = DeviceRepository(session)
        building = await building_repo.get(building_id)
        if not building:
            raise HTTPException(404, "Dom topilmadi")

        utilities: dict[str, BuildingUtility] = {}
        for utility_type in ("electricity", "water", "gas"):
            existing = await utility_repo.get_by_building_type(building_id, utility_type)
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
            utility_repo.add(item)
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
            existing_point = await point_repo.active_for_building_role(
                building_id,
                spec["utility_type"],
                spec["role"],
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
            point_repo.add(point)
            await session.flush()
            created_points.append(point)

        for device_id, utility_type, device_role, firmware_mode in [
            (body.electricity_device_id, "electricity", "electricity_node", "electricity"),
            (body.water_device_id, "water", "water_node", "water"),
            (body.gas_device_id, "gas", "gas_node", "gas"),
        ]:
            if not device_id:
                continue
            device = await device_repo.get(device_id)
            if not device:
                device = Device(id=device_id, name=device_id, registered=ts, created_at=ts)
                device_repo.add(device)
            device.building_id = building_id
            device.utility_type = utility_type
            device.device_role = device_role
            device.firmware_mode = firmware_mode
            device.updated_at = ts

        await session.commit()

    return {
        "ok": True,
        "building_id": building_id,
        "utilities": [model_to_dict(item) for item in utilities.values()],
        "created_points": [model_to_dict(point) for point in created_points],
        "existing_points": [model_to_dict(point) for point in existing_points],
    }


async def create_premise(body: PremiseCreate) -> dict:
    ts = now_ts()
    async with SessionLocal() as session:
        if not await BuildingRepository(session).get(body.building_id):
            raise HTTPException(404, "Dom topilmadi")
        premise = Premise(
            building_id=body.building_id,
            number=body.number,
            floor=body.floor,
            premise_type=body.premise_type,
            created_at=ts,
            updated_at=ts,
        )
        PremiseRepository(session).add(premise)
        await session.commit()
        await session.refresh(premise)
    return {"ok": True, "id": premise.id}


async def list_premises(building_id: int | None = None) -> dict:
    async with SessionLocal() as session:
        rows = await PremiseRepository(session).list_by_building(building_id)
    return {"premises": [model_to_dict(row) for row in rows]}


async def _validate_measurement_point_refs(
    session,
    *,
    building_id: int | None = None,
    utility_module_id: int | None = None,
    premise_id: int | None = None,
    parent_id: int | None = None,
    device_id: str | None = None,
) -> None:
    building_repo = BuildingRepository(session)
    utility_repo = BuildingUtilityRepository(session)
    premise_repo = PremiseRepository(session)
    point_repo = MeasurementPointRepository(session)
    device_repo = DeviceRepository(session)
    if building_id and not await building_repo.get(building_id):
        raise HTTPException(404, "Building topilmadi")
    if utility_module_id:
        utility = await utility_repo.get(utility_module_id)
        if not utility:
            raise HTTPException(404, "Utility topilmadi")
        if building_id and utility.building_id != building_id:
            raise HTTPException(422, "Utility boshqa buildingga tegishli")
    if premise_id:
        premise = await premise_repo.get(premise_id)
        if not premise:
            raise HTTPException(404, "Premise topilmadi")
        if building_id and premise.building_id != building_id:
            raise HTTPException(422, "Premise boshqa buildingga tegishli")
    if parent_id and not await point_repo.get(parent_id):
        raise HTTPException(404, "Parent measurement point topilmadi")
    if device_id and not await device_repo.get(device_id):
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
        point_repo = MeasurementPointRepository(session)
        device_repo = DeviceRepository(session)
        await _validate_measurement_point_refs(
            session,
            building_id=body.building_id,
            utility_module_id=body.utility_module_id,
            premise_id=body.premise_id,
            parent_id=body.parent_id,
            device_id=body.device_id,
        )
        point_repo.add(point)
        await session.flush()
        if body.device_id:
            device = await device_repo.get(body.device_id)
            if device:
                device.point_id = point.id
        await session.commit()
        await session.refresh(point)
    return {"ok": True, "id": point.id}


async def get_measurement_point(point_id: int) -> dict:
    async with SessionLocal() as session:
        point = await MeasurementPointRepository(session).get(point_id)
    if not point:
        raise HTTPException(404, "Measurement point topilmadi")
    return model_to_dict(point)


async def update_measurement_point(point_id: int, body: MeasurementPointUpdate) -> dict:
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(400, "Yangilanadigan maydon yo'q")
    fields["updated_at"] = now_ts()
    async with SessionLocal() as session:
        point_repo = MeasurementPointRepository(session)
        device_repo = DeviceRepository(session)
        point = await point_repo.get(point_id)
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
            device = await device_repo.get(fields["device_id"])
            if device:
                device.point_id = point.id
                device.building_id = point.building_id or device.building_id
                device.utility_type = point.utility_type
                device.updated_at = now_ts()
        await session.commit()
    return {"ok": True}


async def bind_measurement_point_device(point_id: int, body: MeasurementPointDeviceBind) -> dict:
    async with SessionLocal() as session:
        point_repo = MeasurementPointRepository(session)
        device_repo = DeviceRepository(session)
        point = await point_repo.get(point_id)
        if not point:
            raise HTTPException(404, "Measurement point topilmadi")
        device = await device_repo.get(body.device_id)
        ts = now_ts()
        if not device:
            device = Device(id=body.device_id, name=body.device_id, registered=ts, created_at=ts)
            device_repo.add(device)
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
        point = await MeasurementPointRepository(session).get(point_id)
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
    async with SessionLocal() as session:
        rows = await MeasurementPointRepository(session).list_filtered(building_id, utility_type, role)
    return {"points": [model_to_dict(row) for row in rows]}
