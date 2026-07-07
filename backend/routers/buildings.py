from typing import Optional

from fastapi import APIRouter, Depends, Query

from core.security import current_token_payload, require_admin
from models.schemas import (
    BuildingAnalyticsResponse,
    BuildingCreate,
    BuildingCreateResponse,
    BuildingDefaultProvision,
    BuildingDefaultProvisionResponse,
    BuildingDeleteResponse,
    BuildingLatestReadingsResponse,
    BuildingListResponse,
    BuildingReadingHistoryResponse,
    BuildingResponse,
    BuildingUtilityCreate,
    BuildingUtilityCreateResponse,
    BuildingUtilityListResponse,
    BuildingUtilityUpdateResponse,
    BuildingUtilityUpdate,
    BuildingUpdate,
    BuildingUpdateResponse,
    MeasurementPointCreate,
    MeasurementPointCreateResponse,
    MeasurementPointDeviceBind,
    MeasurementPointListResponse,
    MeasurementPointResponse,
    MeasurementPointUpdateResponse,
    MeasurementPointUpdate,
    PremiseCreate,
    PremiseCreateResponse,
    PremiseListResponse,
)
from services import analytics as analytics_service
from services import audit
from services import buildings as building_service
from services import readings as reading_service

router = APIRouter(prefix="/api")


@router.post("/buildings", response_model=BuildingCreateResponse)
async def create_building(body: BuildingCreate, admin: dict = Depends(require_admin)):
    result = await building_service.create_building(body)
    await audit.record(admin, "building.create", "building", result.get("id"), body.model_dump())
    return result


@router.get("/buildings", response_model=BuildingListResponse)
async def list_buildings(_: dict = Depends(current_token_payload)):
    return await building_service.list_buildings()


@router.get("/buildings/{building_id}", response_model=BuildingResponse)
async def get_building(building_id: int, _: dict = Depends(current_token_payload)):
    return await building_service.get_building(building_id)


@router.put("/buildings/{building_id}", response_model=BuildingUpdateResponse)
async def update_building(
    building_id: int,
    body: BuildingUpdate,
    admin: dict = Depends(require_admin),
):
    result = await building_service.update_building(building_id, body)
    await audit.record(admin, "building.update", "building", building_id, body.model_dump(exclude_none=True))
    return result


@router.delete("/buildings/{building_id}", response_model=BuildingDeleteResponse)
async def delete_building(building_id: int, admin: dict = Depends(require_admin)):
    result = await building_service.delete_building(building_id)
    await audit.record(admin, "building.delete", "building", building_id)
    return result


@router.post("/buildings/{building_id}/utilities", response_model=BuildingUtilityCreateResponse)
async def create_building_utility(
    building_id: int,
    body: BuildingUtilityCreate,
    admin: dict = Depends(require_admin),
):
    body.building_id = building_id
    result = await building_service.create_building_utility(body)
    await audit.record(admin, "building_utility.create", "building", building_id, body.model_dump())
    return result


@router.get("/buildings/{building_id}/utilities", response_model=BuildingUtilityListResponse)
async def list_building_utilities(building_id: int, _: dict = Depends(current_token_payload)):
    return await building_service.list_building_utilities(building_id)


@router.put("/buildings/{building_id}/utilities/{utility_id}", response_model=BuildingUtilityUpdateResponse)
async def update_building_utility(
    building_id: int,
    utility_id: int,
    body: BuildingUtilityUpdate,
    admin: dict = Depends(require_admin),
):
    result = await building_service.update_building_utility(building_id, utility_id, body)
    await audit.record(admin, "building_utility.update", "building_utility", utility_id, body.model_dump(exclude_none=True))
    return result


@router.post("/buildings/{building_id}/provision-defaults", response_model=BuildingDefaultProvisionResponse)
async def provision_building_defaults(
    building_id: int,
    body: BuildingDefaultProvision,
    admin: dict = Depends(require_admin),
):
    result = await building_service.provision_building_defaults(building_id, body)
    await audit.record(admin, "building.provision_defaults", "building", building_id, body.model_dump())
    return result


@router.get("/buildings/{building_id}/readings/latest", response_model=BuildingLatestReadingsResponse)
async def building_latest_readings(
    building_id: int,
    utility_type: Optional[str] = None,
    _: dict = Depends(current_token_payload),
):
    return await reading_service.building_latest_readings(building_id, utility_type)


@router.get("/buildings/{building_id}/readings/history", response_model=BuildingReadingHistoryResponse)
async def building_reading_history(
    building_id: int,
    utility_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=1000),
    hours: Optional[int] = None,
    _: dict = Depends(current_token_payload),
):
    return await reading_service.building_reading_history(building_id, utility_type, page, limit, hours)


@router.get("/buildings/{building_id}/analytics", response_model=BuildingAnalyticsResponse)
async def building_analytics(
    building_id: int,
    hours: int = Query(24, ge=1, le=720),
    _: dict = Depends(current_token_payload),
):
    return await analytics_service.building_analytics(building_id, hours)


@router.post("/premises", response_model=PremiseCreateResponse)
async def create_premise(body: PremiseCreate, admin: dict = Depends(require_admin)):
    result = await building_service.create_premise(body)
    await audit.record(admin, "premise.create", "premise", result.get("id"), body.model_dump())
    return result


@router.get("/premises", response_model=PremiseListResponse)
async def list_premises(building_id: Optional[int] = None, _: dict = Depends(current_token_payload)):
    return await building_service.list_premises(building_id)


@router.post("/measurement-points", response_model=MeasurementPointCreateResponse)
async def create_measurement_point(body: MeasurementPointCreate, admin: dict = Depends(require_admin)):
    result = await building_service.create_measurement_point(body)
    await audit.record(admin, "measurement_point.create", "measurement_point", result.get("id"), body.model_dump())
    return result


@router.get("/measurement-points", response_model=MeasurementPointListResponse)
async def list_measurement_points(
    building_id: Optional[int] = None,
    utility_type: Optional[str] = None,
    role: Optional[str] = None,
    _: dict = Depends(current_token_payload),
):
    return await building_service.list_measurement_points(building_id, utility_type, role)


@router.get("/measurement-points/{point_id}", response_model=MeasurementPointResponse)
async def get_measurement_point(point_id: int, _: dict = Depends(current_token_payload)):
    return await building_service.get_measurement_point(point_id)


@router.put("/measurement-points/{point_id}", response_model=MeasurementPointUpdateResponse)
async def update_measurement_point(
    point_id: int,
    body: MeasurementPointUpdate,
    admin: dict = Depends(require_admin),
):
    result = await building_service.update_measurement_point(point_id, body)
    await audit.record(admin, "measurement_point.update", "measurement_point", point_id, body.model_dump(exclude_none=True))
    return result


@router.post("/measurement-points/{point_id}/bind-device", response_model=MeasurementPointUpdateResponse)
async def bind_measurement_point_device(
    point_id: int,
    body: MeasurementPointDeviceBind,
    admin: dict = Depends(require_admin),
):
    result = await building_service.bind_measurement_point_device(point_id, body)
    await audit.record(admin, "measurement_point.bind_device", "measurement_point", point_id, body.model_dump())
    return result


@router.delete("/measurement-points/{point_id}", response_model=MeasurementPointUpdateResponse)
async def delete_measurement_point(point_id: int, admin: dict = Depends(require_admin)):
    result = await building_service.delete_measurement_point(point_id)
    await audit.record(admin, "measurement_point.delete", "measurement_point", point_id)
    return result
