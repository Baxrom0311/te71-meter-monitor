from fastapi import UploadFile
from sqlalchemy import and_, desc, func, inspect, select

from core.config import settings
from core.database import SessionLocal
from core.metrics import render_http_metrics
from core.time import now_ts
from models.entities import (
    Alert,
    Building,
    Command,
    Device,
    MeasurementPoint,
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
from services import buildings as buildings_service
from services import commands as commands_service
from services import devices as devices_service
from services import ota as ota_service
from services import readings as readings_service
from services.websocket import ws_manager


def _as_dict(obj) -> dict:
    return {attr.key: getattr(obj, attr.key) for attr in inspect(obj).mapper.column_attrs}


async def verify_device_access(device_id: str | None, token: str | None) -> None:
    return await devices_service.verify_device_access(device_id, token)


async def verify_command_access(command_id: int, token: str | None) -> None:
    return await commands_service.verify_command_access(command_id, token)


async def build_snapshot() -> dict:
    async with SessionLocal() as session:
        devices = (await session.scalars(select(Device).where(Device.is_active.is_(True)))).all()
        alerts = (await session.scalars(select(Alert).order_by(desc(Alert.ts)).limit(20))).all()
    device_rows = [_as_dict(device) | {"online": devices_service.online_status(device.last_seen)} for device in devices]
    return {"devices": device_rows, "alerts": [_as_dict(alert) for alert in alerts]}


async def get_device_config(device_id: str) -> dict:
    return await devices_service.get_device_config(device_id)


async def create_building(body: BuildingCreate) -> dict:
    return await buildings_service.create_building(body)


async def list_buildings() -> dict:
    return await buildings_service.list_buildings()


async def get_building(building_id: int) -> dict:
    return await buildings_service.get_building(building_id)


async def update_building(building_id: int, body: BuildingUpdate) -> dict:
    return await buildings_service.update_building(building_id, body)


async def delete_building(building_id: int) -> dict:
    return await buildings_service.delete_building(building_id)


async def create_building_utility(body: BuildingUtilityCreate) -> dict:
    return await buildings_service.create_building_utility(body)


async def list_building_utilities(building_id: int) -> dict:
    return await buildings_service.list_building_utilities(building_id)


async def update_building_utility(building_id: int, utility_id: int, body: BuildingUtilityUpdate) -> dict:
    return await buildings_service.update_building_utility(building_id, utility_id, body)


async def provision_building_defaults(building_id: int, body: BuildingDefaultProvision) -> dict:
    return await buildings_service.provision_building_defaults(building_id, body)


async def create_premise(body: PremiseCreate) -> dict:
    return await buildings_service.create_premise(body)


async def list_premises(building_id: int | None = None) -> dict:
    return await buildings_service.list_premises(building_id)


async def create_measurement_point(body: MeasurementPointCreate) -> dict:
    return await buildings_service.create_measurement_point(body)


async def get_measurement_point(point_id: int) -> dict:
    return await buildings_service.get_measurement_point(point_id)


async def update_measurement_point(point_id: int, body: MeasurementPointUpdate) -> dict:
    return await buildings_service.update_measurement_point(point_id, body)


async def bind_measurement_point_device(point_id: int, body: MeasurementPointDeviceBind) -> dict:
    return await buildings_service.bind_measurement_point_device(point_id, body)


async def delete_measurement_point(point_id: int) -> dict:
    return await buildings_service.delete_measurement_point(point_id)


async def list_measurement_points(
    building_id: int | None = None,
    utility_type: str | None = None,
    role: str | None = None,
) -> dict:
    return await buildings_service.list_measurement_points(building_id, utility_type, role)


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
    return await commands_service.create_relay_command(device_id, action_value)


async def create_command(device_id: str, action: str, params: dict | None = None) -> dict:
    return await commands_service.create_command(device_id, action, params)


async def reboot_device(device_id: str) -> dict:
    return await commands_service.reboot_device(device_id)


async def pending_commands(device_id: str) -> dict:
    return await commands_service.pending_commands(device_id)


async def ack_command(command_id: int, result: str) -> dict:
    return await commands_service.ack_command(command_id, result)


async def list_commands(device_id: str | None = None, status: str | None = None, limit: int = 100) -> dict:
    return await commands_service.list_commands(device_id, status, limit)


async def cleanup_expired_commands_once() -> dict:
    return await commands_service.cleanup_expired_commands_once()


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
    return await commands_service.create_command(device_id, "ota_check", None)


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
