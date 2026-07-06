"""operational indexes

Revision ID: 0005_operational_indexes
Revises: 0004_firmware_compatibility
Create Date: 2026-07-06
"""
from alembic import op

revision = "0005_operational_indexes"
down_revision = "0004_firmware_compatibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("idx_devices_active_last_seen", "devices", ["is_active", "last_seen"])
    op.create_index("idx_devices_utility_active", "devices", ["utility_type", "is_active"])
    op.create_index("idx_devices_building_active", "devices", ["building_id", "is_active"])
    op.create_index("idx_measurement_points_building_utility", "measurement_points", ["building_id", "utility_type", "is_active"])
    op.create_index("idx_measurement_points_role", "measurement_points", ["role"])
    op.create_index("idx_premises_building_floor", "premises", ["building_id", "floor", "number"])
    op.create_index("idx_readings_ts", "readings", ["ts"])
    op.create_index("idx_readings_building_utility_ts", "readings", ["building_id", "utility_type", "ts"])
    op.create_index("idx_alerts_device_kind_ts", "alerts", ["device_id", "kind", "ts"])
    op.create_index("idx_alerts_building_cleared_ts", "alerts", ["building_id", "cleared", "ts"])
    op.create_index("idx_commands_device_status", "commands", ["device_id", "status", "id"])
    op.create_index("idx_firmware_active_uploaded", "firmware", ["active", "uploaded"])


def downgrade() -> None:
    op.drop_index("idx_firmware_active_uploaded", table_name="firmware")
    op.drop_index("idx_commands_device_status", table_name="commands")
    op.drop_index("idx_alerts_building_cleared_ts", table_name="alerts")
    op.drop_index("idx_alerts_device_kind_ts", table_name="alerts")
    op.drop_index("idx_readings_building_utility_ts", table_name="readings")
    op.drop_index("idx_readings_ts", table_name="readings")
    op.drop_index("idx_premises_building_floor", table_name="premises")
    op.drop_index("idx_measurement_points_role", table_name="measurement_points")
    op.drop_index("idx_measurement_points_building_utility", table_name="measurement_points")
    op.drop_index("idx_devices_building_active", table_name="devices")
    op.drop_index("idx_devices_utility_active", table_name="devices")
    op.drop_index("idx_devices_active_last_seen", table_name="devices")
