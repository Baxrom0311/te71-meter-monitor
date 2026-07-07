"""ota batches and rollout metadata

Revision ID: 0015_ota_batches
Revises: 0014_alert_notifications
Create Date: 2026-07-07
"""
from alembic import op
import sqlalchemy as sa

revision = "0015_ota_batches"
down_revision = "0014_alert_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("firmware", sa.Column("is_stable", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("firmware", sa.Column("min_version", sa.String(64), nullable=True))
    op.add_column("firmware", sa.Column("rollout_percentage", sa.Integer(), nullable=False, server_default="100"))

    op.create_table(
        "ota_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("firmware_id", sa.Integer(), sa.ForeignKey("firmware.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("devices_per_hour", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("scheduled_at", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.Integer(), nullable=True),
        sa.Column("total_devices", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_by_username", sa.String(64), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.Integer(), nullable=True),
    )
    op.create_index("idx_ota_batches_status_scheduled", "ota_batches", ["status", "scheduled_at"])
    op.create_index("idx_ota_batches_firmware", "ota_batches", ["firmware_id"])

    op.create_table(
        "ota_batch_devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("ota_batches.id"), nullable=False),
        sa.Column("device_id", sa.String(128), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("notified_at", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.Integer(), nullable=True),
        sa.Column("previous_version", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.Integer(), nullable=True),
        sa.UniqueConstraint("batch_id", "device_id", name="uq_ota_batch_device"),
    )
    op.create_index("idx_ota_batch_devices_batch_status", "ota_batch_devices", ["batch_id", "status"])
    op.create_index("idx_ota_batch_devices_device_status", "ota_batch_devices", ["device_id", "status"])


def downgrade() -> None:
    op.drop_index("idx_ota_batch_devices_device_status", table_name="ota_batch_devices")
    op.drop_index("idx_ota_batch_devices_batch_status", table_name="ota_batch_devices")
    op.drop_table("ota_batch_devices")
    op.drop_index("idx_ota_batches_firmware", table_name="ota_batches")
    op.drop_index("idx_ota_batches_status_scheduled", table_name="ota_batches")
    op.drop_table("ota_batches")
    op.drop_column("firmware", "rollout_percentage")
    op.drop_column("firmware", "min_version")
    op.drop_column("firmware", "is_stable")
