import csv
import io

from core.database import SessionLocal
from core.time import now_ts
from repositories.base import model_to_dict
from repositories.analytics import AnalyticsRepository
from repositories.buildings import BuildingRepository
from repositories.readings import ReadingRepository




async def reading_stats(device_id: str, hours: int) -> dict:
    cutoff = now_ts() - hours * 3600
    async with SessionLocal() as session:
        rows = await AnalyticsRepository(session).reading_stats(device_id, cutoff)
    return {"stats": rows, "hours": hours}


async def building_analytics(building_id: int, hours: int) -> dict:
    cutoff = now_ts() - hours * 3600
    async with SessionLocal() as session:
        result = await AnalyticsRepository(session).building_utility_analytics(building_id, cutoff)

    return {
        "building_id": building_id,
        "hours": hours,
        **result,
    }


async def aggregate_hourly_stats_once(hours: int = 48) -> dict:
    ts = now_ts()
    cutoff = ts - hours * 3600
    async with SessionLocal() as session:
        repo = AnalyticsRepository(session)
        rows = await repo.aggregate_hourly_rows(cutoff)
        await repo.replace_hourly_stats_since(cutoff, rows, ts)
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
    async with SessionLocal() as session:
        rows = await AnalyticsRepository(session).list_hourly_stats(
            cutoff, building_id, utility_type, device_id, limit
        )
    return {"stats": [model_to_dict(row) for row in rows], "hours": hours, "total": len(rows)}


async def energy_by_building(
    from_ts: int,
    to_ts: int,
    building_id: int | None = None,
    granularity: str = "day",
) -> dict:
    """
    Kunlik/soatlik energiya sarfi — har bir bino bo'yicha.
    granularity: 'hour' | 'day' | 'month'
    """
    if granularity == "hour":
        bucket_sec = 3600
    elif granularity == "month":
        bucket_sec = 30 * 86400
    else:
        bucket_sec = 86400

    if from_ts > to_ts:
        return {"from_ts": from_ts, "to_ts": to_ts, "granularity": granularity, "total": 0, "data": []}

    async with SessionLocal() as session:
        rows = await AnalyticsRepository(session).energy_by_building_rows(from_ts, to_ts, bucket_sec, building_id)
        # building nomi uchun
        bld_ids = {r["building_id"] for r in rows if r["building_id"]}
        bld_names: dict[int, str] = {}
        if bld_ids:
            bld_rows = await BuildingRepository(session).list_by_ids(bld_ids)
            bld_names = {b.id: b.name for b in bld_rows}

    result = []
    for row in rows:
        d = dict(row)
        d["building_name"] = bld_names.get(d["building_id"], str(d["building_id"]) if d["building_id"] else "Noma'lum")
        result.append(d)

    return {
        "from_ts": from_ts,
        "to_ts": to_ts,
        "granularity": granularity,
        "total": len(result),
        "data": result,
    }


async def buildings_energy_summary() -> dict:
    """
    Barcha binolar uchun oxirgi 30 kun energiya sarfi xulasasi (dashboard uchun).
    """
    to_ts = now_ts()
    from_ts = to_ts - 30 * 86400

    async with SessionLocal() as session:
        rows = await AnalyticsRepository(session).buildings_energy_summary_rows(from_ts)
        bld_ids = {r["building_id"] for r in rows if r["building_id"]}
        bld_names: dict[int, str] = {}
        if bld_ids:
            bld_rows = await BuildingRepository(session).list_by_ids(bld_ids)
            bld_names = {b.id: b.name for b in bld_rows}
        all_buildings = await BuildingRepository(session).list_all()

    summary = []
    seen = {r["building_id"] for r in rows}
    for row in rows:
        d = dict(row)
        d["building_name"] = bld_names.get(d["building_id"], "Noma'lum")
        summary.append(d)
    for b in all_buildings:
        if b.id not in seen:
            summary.append({
                "building_id": b.id,
                "building_name": b.name,
                "total_energy_kwh": 0,
                "avg_power_w": 0,
                "readings": 0,
            })

    summary.sort(key=lambda x: (x.get("total_energy_kwh") or 0), reverse=True)
    return {"summary": summary, "days": 30}


async def export_csv(device_id: str, hours: int) -> tuple[str, str]:
    cutoff = now_ts() - hours * 3600
    async with SessionLocal() as session:
        rows = await ReadingRepository(session).export_for_device(device_id, cutoff)
    buf = io.StringIO()
    writer = csv.writer(buf)
    dict_rows = [model_to_dict(row) for row in rows]
    if dict_rows:
        writer.writerow(dict_rows[0].keys())
        for row in dict_rows:
            writer.writerow(row.values())
    filename = f"{device_id.replace(':', '')}_{hours}h.csv"
    return filename, buf.getvalue()
