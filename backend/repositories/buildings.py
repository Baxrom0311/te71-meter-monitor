from sqlalchemy import and_, desc, select

from models.entities import Building, BuildingUtility, MeasurementPoint, Premise
from repositories.base import BaseRepository


class BuildingRepository(BaseRepository[Building]):
    model = Building

    async def list_ordered(self) -> list[Building]:
        return list((await self.session.scalars(select(Building).order_by(desc(Building.id)))).all())

    async def list_active(self) -> list[Building]:
        return list(
            (await self.session.scalars(select(Building).where(Building.is_active.is_(True)).order_by(desc(Building.id)))).all()
        )


class BuildingUtilityRepository(BaseRepository[BuildingUtility]):
    model = BuildingUtility

    async def get_for_building(self, building_id: int, utility_id: int) -> BuildingUtility | None:
        return await self.session.scalar(
            select(BuildingUtility).where(
                and_(BuildingUtility.id == utility_id, BuildingUtility.building_id == building_id)
            )
        )

    async def get_by_building_type(self, building_id: int, utility_type: str) -> BuildingUtility | None:
        return await self.session.scalar(
            select(BuildingUtility).where(
                and_(BuildingUtility.building_id == building_id, BuildingUtility.utility_type == utility_type)
            )
        )

    async def list_by_building(self, building_id: int) -> list[BuildingUtility]:
        return list(
            (
                await self.session.scalars(
                    select(BuildingUtility)
                    .where(BuildingUtility.building_id == building_id)
                    .order_by(BuildingUtility.utility_type)
                )
            ).all()
        )


class PremiseRepository(BaseRepository[Premise]):
    model = Premise

    async def list_by_building(self, building_id: int | None = None) -> list[Premise]:
        stmt = select(Premise).order_by(Premise.building_id, Premise.floor, Premise.number)
        if building_id:
            stmt = stmt.where(Premise.building_id == building_id)
        return list((await self.session.scalars(stmt)).all())


class MeasurementPointRepository(BaseRepository[MeasurementPoint]):
    model = MeasurementPoint

    async def active_for_building_role(
        self,
        building_id: int,
        utility_type: str,
        role: str,
    ) -> MeasurementPoint | None:
        return await self.session.scalar(
            select(MeasurementPoint).where(
                and_(
                    MeasurementPoint.building_id == building_id,
                    MeasurementPoint.utility_type == utility_type,
                    MeasurementPoint.role == role,
                    MeasurementPoint.is_active.is_(True),
                )
            )
        )

    async def list_filtered(
        self,
        building_id: int | None = None,
        utility_type: str | None = None,
        role: str | None = None,
    ) -> list[MeasurementPoint]:
        stmt = select(MeasurementPoint).where(MeasurementPoint.is_active.is_(True)).order_by(desc(MeasurementPoint.id))
        if building_id:
            stmt = stmt.where(MeasurementPoint.building_id == building_id)
        if utility_type:
            stmt = stmt.where(MeasurementPoint.utility_type == utility_type)
        if role:
            stmt = stmt.where(MeasurementPoint.role == role)
        return list((await self.session.scalars(stmt)).all())
