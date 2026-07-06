"""firmware compatibility catalog

Revision ID: 0004_firmware_compatibility
Revises: 0003_audit_logs
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_firmware_compatibility"
down_revision = "0003_audit_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("measurement_points", sa.Column("converter_type", sa.String(64), nullable=True))
    op.add_column("firmware", sa.Column("device_role", sa.String(64), nullable=True))
    op.add_column("firmware", sa.Column("utility_type", sa.String(32), nullable=True))
    op.add_column("firmware", sa.Column("sensor_type", sa.String(64), nullable=True))
    op.add_column("firmware", sa.Column("converter_type", sa.String(64), nullable=True))
    op.add_column("firmware", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("firmware", sa.Column("release_notes", sa.Text(), nullable=True))
    op.add_column("firmware", sa.Column("compatibility_notes", sa.Text(), nullable=True))
    op.create_table(
        "firmware_compatibilities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("firmware_id", sa.Integer(), sa.ForeignKey("firmware.id"), nullable=False),
        sa.Column("utility_type", sa.String(32), nullable=True),
        sa.Column("firmware_mode", sa.String(32), nullable=True),
        sa.Column("device_role", sa.String(64), nullable=True),
        sa.Column("hardware_version", sa.String(64), nullable=True),
        sa.Column("sensor_type", sa.String(64), nullable=True),
        sa.Column("converter_type", sa.String(64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=True),
    )
    op.create_index(
        "idx_fw_compat_lookup",
        "firmware_compatibilities",
        ["firmware_mode", "hardware_version", "sensor_type", "converter_type"],
    )


def downgrade() -> None:
    op.drop_index("idx_fw_compat_lookup", table_name="firmware_compatibilities")
    op.drop_table("firmware_compatibilities")
    op.drop_column("firmware", "compatibility_notes")
    op.drop_column("firmware", "release_notes")
    op.drop_column("firmware", "description")
    op.drop_column("firmware", "converter_type")
    op.drop_column("firmware", "sensor_type")
    op.drop_column("firmware", "utility_type")
    op.drop_column("firmware", "device_role")
    op.drop_column("measurement_points", "converter_type")
