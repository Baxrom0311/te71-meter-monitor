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
            "created_at": "INTEGER",
            "updated_at": "INTEGER",
        },
        "readings": {
            "reading_id": "VARCHAR(128)",
            "sequence_no": "INTEGER",
            "building_id": "INTEGER",
            "sensor_type": "VARCHAR(64)",
            "pressure_bottom_bar": "FLOAT",
            "pressure_top_bar": "FLOAT",
            "leak_detected": "BOOLEAN",
            "valve_open": "BOOLEAN",
            "raw_payload": "TEXT",
            "created_at": "INTEGER",
        },
        "alerts": {
            "building_id": "INTEGER",
            "severity": "VARCHAR(32) DEFAULT 'warning'",
            "cleared_at": "INTEGER",
        },
        "commands": {
            "status": "VARCHAR(32) DEFAULT 'pending'",
            "sent": "INTEGER",
        },
        "firmware": {
            "hardware_version": "VARCHAR(64)",
            "firmware_mode": "VARCHAR(32) DEFAULT 'auto'",
        },
        "users": {
            "failed_login_count": "INTEGER DEFAULT 0",
            "locked_until": "INTEGER",
            "last_login": "INTEGER",
        },
    }

    for table, columns in table_columns.items():
        existing = await conn.execute(text(f"PRAGMA table_info({table})"))
        existing_names = {row[1] for row in existing.fetchall()}
        for column, column_type in columns.items():
            if column not in existing_names:
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}"))
