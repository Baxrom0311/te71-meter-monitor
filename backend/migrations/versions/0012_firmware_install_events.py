"""firmware install events

Revision ID: 0012_firmware_install_events
Revises: 0011_hourly_utility_stats
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_firmware_install_events"
down_revision = "0011_hourly_utility_stats"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "firmware_install_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.String(128), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("firmware_id", sa.Integer(), sa.ForeignKey("firmware.id"), nullable=True),
        sa.Column("from_version", sa.String(64), nullable=True),
        sa.Column("target_version", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("ts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=True),
    )
    op.create_index("idx_firmware_events_device_ts", "firmware_install_events", ["device_id", "ts"])
    op.create_index("idx_firmware_events_status_ts", "firmware_install_events", ["status", "ts"])


def downgrade() -> None:
    op.drop_index("idx_firmware_events_status_ts", table_name="firmware_install_events")
    op.drop_index("idx_firmware_events_device_ts", table_name="firmware_install_events")
    op.drop_table("firmware_install_events")
