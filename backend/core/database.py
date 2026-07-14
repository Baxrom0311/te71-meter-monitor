from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings
from models.entities import Base


engine = create_async_engine(settings.database_url, future=True, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if settings.database_url.startswith("sqlite"):
            await _ensure_sqlite_columns(conn)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def _ensure_sqlite_columns(conn) -> None:
    table_columns: dict[str, dict[str, str]] = {
        "buildings": {
            "entrances_count": "INTEGER DEFAULT 1",
            "maps_url": "VARCHAR(1000)",
            "latitude": "FLOAT",
            "longitude": "FLOAT",
            "description": "TEXT",
            "is_active": "BOOLEAN DEFAULT 1",
            "created_at": "INTEGER",
            "updated_at": "INTEGER",
        },
        "building_utilities": {
            "created_at": "INTEGER",
            "updated_at": "INTEGER",
        },
        "measurement_points": {
            "utility_module_id": "INTEGER",
            "sensor_type": "VARCHAR(64)",
            "converter_type": "VARCHAR(64)",
            "location_name": "VARCHAR(255)",
            "floor": "INTEGER",
            "created_at": "INTEGER",
            "updated_at": "INTEGER",
        },
        "devices": {
            "building_id": "INTEGER",
            "device_role": "VARCHAR(64)",
            "firmware_mode": "VARCHAR(32) DEFAULT 'auto'",
            "serial_number": "VARCHAR(128)",
            "hardware_version": "VARCHAR(64)",
            "software_version": "VARCHAR(64)",
            "build_number": "VARCHAR(64)",
            "previous_meter_serial": "VARCHAR(128)",
            "meter_changed_at": "INTEGER",
            "needs_rebind": "BOOLEAN DEFAULT 0",
            "is_test_device": "BOOLEAN DEFAULT 0",
            "auto_cleanup_at": "INTEGER",
            "api_token_hash": "VARCHAR(255)",
            "token_created_at": "INTEGER",
            "token_revoked_at": "INTEGER",
            "token_revoked_by_user_id": "INTEGER",
            "token_revoked_by_username": "VARCHAR(64)",
            "created_at": "INTEGER",
            "updated_at": "INTEGER",
        },
        "device_provisioning_tokens": {
            "revoked_at": "INTEGER",
            "revoked_by_user_id": "INTEGER",
            "revoked_by_username": "VARCHAR(64)",
        },
        "readings": {
            "reading_id": "VARCHAR(128)",
            "sequence_no": "INTEGER",
            "building_id": "INTEGER",
            "sensor_type": "VARCHAR(64)",
            "meter_serial": "VARCHAR(128)",
            "pressure_bottom_bar": "FLOAT",
            "pressure_top_bar": "FLOAT",
            "leak_detected": "BOOLEAN",
            "valve_open": "BOOLEAN",
            "raw_payload": "TEXT",
            "created_at": "INTEGER",
        },
        "hourly_utility_stats": {},
        "alerts": {
            "building_id": "INTEGER",
            "severity": "VARCHAR(32) DEFAULT 'warning'",
            "cleared_at": "INTEGER",
        },
        "alert_rules": {},
        "alert_notifications": {},
        "commands": {
            "status": "VARCHAR(32) DEFAULT 'pending'",
            "expires_at": "INTEGER",
            "sent": "INTEGER",
            "attempts": "INTEGER DEFAULT 0",
            "max_attempts": "INTEGER DEFAULT 3",
        },
        "firmware": {
            "hardware_version": "VARCHAR(64)",
            "firmware_mode": "VARCHAR(32) DEFAULT 'auto'",
            "device_role": "VARCHAR(64)",
            "utility_type": "VARCHAR(32)",
            "sensor_type": "VARCHAR(64)",
            "converter_type": "VARCHAR(64)",
            "is_stable": "BOOLEAN DEFAULT 0",
            "min_version": "VARCHAR(64)",
            "rollout_percentage": "INTEGER DEFAULT 100",
            "description": "TEXT",
            "release_notes": "TEXT",
            "compatibility_notes": "TEXT",
        },
        "firmware_compatibilities": {},
        "firmware_install_events": {},
        "ota_batches": {
            "skipped_count": "INTEGER DEFAULT 0",
        },
        "ota_batch_devices": {},
        "users": {
            "token_version": "INTEGER DEFAULT 1",
            "failed_login_count": "INTEGER DEFAULT 0",
            "locked_until": "INTEGER",
            "last_login": "INTEGER",
        },
        "worker_locks": {},
        "audit_logs": {},
    }

    for table, columns in table_columns.items():
        existing = await conn.execute(text(f"PRAGMA table_info({table})"))
        existing_names = {row[1] for row in existing.fetchall()}
        for column, column_type in columns.items():
            if column not in existing_names:
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}"))

    indexes = {
        "idx_devices_active_last_seen": "CREATE INDEX IF NOT EXISTS idx_devices_active_last_seen ON devices (is_active, last_seen)",
        "idx_devices_utility_active": "CREATE INDEX IF NOT EXISTS idx_devices_utility_active ON devices (utility_type, is_active)",
        "idx_devices_building_active": "CREATE INDEX IF NOT EXISTS idx_devices_building_active ON devices (building_id, is_active)",
        "idx_devices_test_cleanup": "CREATE INDEX IF NOT EXISTS idx_devices_test_cleanup ON devices (is_test_device, is_active, auto_cleanup_at)",
        "idx_measurement_points_building_utility": "CREATE INDEX IF NOT EXISTS idx_measurement_points_building_utility ON measurement_points (building_id, utility_type, is_active)",
        "idx_measurement_points_role": "CREATE INDEX IF NOT EXISTS idx_measurement_points_role ON measurement_points (role)",
        "idx_premises_building_floor": "CREATE INDEX IF NOT EXISTS idx_premises_building_floor ON premises (building_id, floor, number)",
        "idx_readings_ts": "CREATE INDEX IF NOT EXISTS idx_readings_ts ON readings (ts)",
        "idx_readings_building_utility_ts": "CREATE INDEX IF NOT EXISTS idx_readings_building_utility_ts ON readings (building_id, utility_type, ts)",
        "idx_readings_meter_serial_ts": "CREATE INDEX IF NOT EXISTS idx_readings_meter_serial_ts ON readings (meter_serial, ts)",
        "idx_hourly_stats_building_utility_bucket": "CREATE INDEX IF NOT EXISTS idx_hourly_stats_building_utility_bucket ON hourly_utility_stats (building_id, utility_type, bucket_ts)",
        "idx_hourly_stats_device_bucket": "CREATE INDEX IF NOT EXISTS idx_hourly_stats_device_bucket ON hourly_utility_stats (device_id, bucket_ts)",
        "idx_alerts_device_kind_ts": "CREATE INDEX IF NOT EXISTS idx_alerts_device_kind_ts ON alerts (device_id, kind, ts)",
        "idx_alerts_building_cleared_ts": "CREATE INDEX IF NOT EXISTS idx_alerts_building_cleared_ts ON alerts (building_id, cleared, ts)",
        "idx_alert_rules_lookup": "CREATE INDEX IF NOT EXISTS idx_alert_rules_lookup ON alert_rules (enabled, building_id, utility_type, kind)",
        "idx_alert_rules_kind": "CREATE INDEX IF NOT EXISTS idx_alert_rules_kind ON alert_rules (kind)",
        "idx_alert_notifications_status_created": "CREATE INDEX IF NOT EXISTS idx_alert_notifications_status_created ON alert_notifications (status, created_at)",
        "idx_alert_notifications_alert": "CREATE INDEX IF NOT EXISTS idx_alert_notifications_alert ON alert_notifications (alert_id)",
        "idx_commands_device_status": "CREATE INDEX IF NOT EXISTS idx_commands_device_status ON commands (device_id, status, id)",
        "idx_commands_expires_status": "CREATE INDEX IF NOT EXISTS idx_commands_expires_status ON commands (expires_at, status)",
        "idx_firmware_active_uploaded": "CREATE INDEX IF NOT EXISTS idx_firmware_active_uploaded ON firmware (active, uploaded)",
        "idx_firmware_events_device_ts": "CREATE INDEX IF NOT EXISTS idx_firmware_events_device_ts ON firmware_install_events (device_id, ts)",
        "idx_firmware_events_status_ts": "CREATE INDEX IF NOT EXISTS idx_firmware_events_status_ts ON firmware_install_events (status, ts)",
        "idx_ota_batches_status_scheduled": "CREATE INDEX IF NOT EXISTS idx_ota_batches_status_scheduled ON ota_batches (status, scheduled_at)",
        "idx_ota_batches_firmware": "CREATE INDEX IF NOT EXISTS idx_ota_batches_firmware ON ota_batches (firmware_id)",
        "idx_ota_batch_devices_batch_status": "CREATE INDEX IF NOT EXISTS idx_ota_batch_devices_batch_status ON ota_batch_devices (batch_id, status)",
        "idx_ota_batch_devices_device_status": "CREATE INDEX IF NOT EXISTS idx_ota_batch_devices_device_status ON ota_batch_devices (device_id, status)",
        "idx_audit_logs_action_ts": "CREATE INDEX IF NOT EXISTS idx_audit_logs_action_ts ON audit_logs (action, ts)",
        "idx_audit_logs_entity_ts": "CREATE INDEX IF NOT EXISTS idx_audit_logs_entity_ts ON audit_logs (entity_type, entity_id, ts)",
        "idx_audit_logs_user_ts": "CREATE INDEX IF NOT EXISTS idx_audit_logs_user_ts ON audit_logs (user_id, ts)",
        "idx_prov_tokens_device": "CREATE INDEX IF NOT EXISTS idx_prov_tokens_device ON device_provisioning_tokens (device_id)",
        "idx_prov_tokens_expires_used": "CREATE INDEX IF NOT EXISTS idx_prov_tokens_expires_used ON device_provisioning_tokens (expires_at, used_at, revoked_at)",
    }
    for statement in indexes.values():
        await conn.execute(text(statement))
