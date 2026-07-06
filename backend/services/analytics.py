import csv
import io

from sqlalchemy import Integer, and_, delete, desc, func, inspect, select

from core.database import SessionLocal
from core.time import now_ts
from models.entities import Alert, HourlyUtilityStats, Reading


def _as_dict(obj) -> dict:
    return {attr.key: getattr(obj, attr.key) for attr in inspect(obj).mapper.column_attrs}


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
                    func.round(func.avg(Reading.pressure_bottom_bar - Reading.pressure_top_bar), 3).label(
                        "avg_pressure_delta_bar"
                    ),
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


async def aggregate_hourly_stats_once(hours: int = 48) -> dict:
    ts = now_ts()
    cutoff = ts - hours * 3600
    hour_ts = (Reading.ts / 3600).cast(Integer) * 3600
    stmt = (
        select(
            hour_ts.label("bucket_ts"),
            Reading.building_id,
            Reading.point_id,
            Reading.device_id,
            Reading.utility_type,
            func.count().label("samples"),
            func.avg(Reading.voltage_l1).label("avg_voltage_l1"),
            func.avg(Reading.power_w).label("avg_power_w"),
            func.max(Reading.energy_kwh).label("max_energy_kwh"),
            func.avg(Reading.pressure_bar).label("avg_pressure_bar"),
            func.avg(Reading.pressure_bottom_bar).label("avg_pressure_bottom_bar"),
            func.avg(Reading.pressure_top_bar).label("avg_pressure_top_bar"),
            func.avg(Reading.flow_rate).label("avg_flow_rate"),
            func.max(Reading.volume_m3).label("max_volume_m3"),
            func.sum(Reading.leak_detected.cast(Integer)).label("leak_count"),
        )
        .where(Reading.ts >= cutoff)
        .group_by(hour_ts, Reading.building_id, Reading.point_id, Reading.device_id, Reading.utility_type)
    )
    async with SessionLocal() as session:
        await session.execute(delete(HourlyUtilityStats).where(HourlyUtilityStats.bucket_ts >= cutoff))
        rows = (await session.execute(stmt)).mappings().all()
        for row in rows:
            session.add(
                HourlyUtilityStats(
                    bucket_ts=row["bucket_ts"],
                    building_id=row["building_id"],
                    point_id=row["point_id"],
                    device_id=row["device_id"],
                    utility_type=row["utility_type"],
                    samples=row["samples"],
                    avg_voltage_l1=row["avg_voltage_l1"],
                    avg_power_w=row["avg_power_w"],
                    max_energy_kwh=row["max_energy_kwh"],
                    avg_pressure_bar=row["avg_pressure_bar"],
                    avg_pressure_bottom_bar=row["avg_pressure_bottom_bar"],
                    avg_pressure_top_bar=row["avg_pressure_top_bar"],
                    avg_flow_rate=row["avg_flow_rate"],
                    max_volume_m3=row["max_volume_m3"],
                    leak_count=row["leak_count"],
                    created_at=ts,
                    updated_at=ts,
                )
            )
        await session.commit()
    return {"ok": True, "hours": hours, "buckets": len(rows)}


async def list_hourly_stats(
    building_id: int | None = None,
    utility_type: str | None = None,
    device_id: str | None = None,
    hours: int = 24,
    limit: int = 500,
) -> dict:
    cutoff = now_ts() - hours * 3600
    stmt = select(HourlyUtilityStats).where(HourlyUtilityStats.bucket_ts >= cutoff)
    if building_id:
        stmt = stmt.where(HourlyUtilityStats.building_id == building_id)
    if utility_type:
        stmt = stmt.where(HourlyUtilityStats.utility_type == utility_type)
    if device_id:
        stmt = stmt.where(HourlyUtilityStats.device_id == device_id)
    stmt = stmt.order_by(desc(HourlyUtilityStats.bucket_ts)).limit(limit)
    async with SessionLocal() as session:
        rows = (await session.scalars(stmt)).all()
    return {"stats": [_as_dict(row) for row in rows], "hours": hours, "total": len(rows)}


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
