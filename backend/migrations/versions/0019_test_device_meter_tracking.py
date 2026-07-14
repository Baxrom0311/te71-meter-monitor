"""Add test device and meter tracking fields.

Revision ID: 0019_test_device_meter_tracking
Revises: 0018_building_extended_fields
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa


revision = "0019_test_device_meter_tracking"
down_revision = "0018_building_extended_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("previous_meter_serial", sa.String(length=128), nullable=True))
    op.add_column("devices", sa.Column("meter_changed_at", sa.Integer(), nullable=True))
    op.add_column("devices", sa.Column("needs_rebind", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("devices", sa.Column("is_test_device", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("devices", sa.Column("auto_cleanup_at", sa.Integer(), nullable=True))
    op.add_column("readings", sa.Column("meter_serial", sa.String(length=128), nullable=True))
    op.create_index("idx_devices_test_cleanup", "devices", ["is_test_device", "is_active", "auto_cleanup_at"])
    op.create_index("idx_readings_meter_serial_ts", "readings", ["meter_serial", "ts"])


def downgrade() -> None:
    op.drop_index("idx_readings_meter_serial_ts", table_name="readings")
    op.drop_index("idx_devices_test_cleanup", table_name="devices")
    op.drop_column("readings", "meter_serial")
    op.drop_column("devices", "auto_cleanup_at")
    op.drop_column("devices", "is_test_device")
    op.drop_column("devices", "needs_rebind")
    op.drop_column("devices", "meter_changed_at")
    op.drop_column("devices", "previous_meter_serial")
