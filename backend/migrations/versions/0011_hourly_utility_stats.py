"""hourly utility stats

Revision ID: 0011_hourly_utility_stats
Revises: 0010_device_token_revoke
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_hourly_utility_stats"
down_revision = "0010_device_token_revoke"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hourly_utility_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bucket_ts", sa.Integer(), nullable=False),
        sa.Column("building_id", sa.Integer(), sa.ForeignKey("buildings.id"), nullable=True),
        sa.Column("point_id", sa.Integer(), sa.ForeignKey("measurement_points.id"), nullable=True),
        sa.Column("device_id", sa.String(128), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("utility_type", sa.String(32), nullable=False),
        sa.Column("samples", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_voltage_l1", sa.Float(), nullable=True),
        sa.Column("avg_power_w", sa.Float(), nullable=True),
        sa.Column("max_energy_kwh", sa.Float(), nullable=True),
        sa.Column("avg_pressure_bar", sa.Float(), nullable=True),
        sa.Column("avg_pressure_bottom_bar", sa.Float(), nullable=True),
        sa.Column("avg_pressure_top_bar", sa.Float(), nullable=True),
        sa.Column("avg_flow_rate", sa.Float(), nullable=True),
        sa.Column("max_volume_m3", sa.Float(), nullable=True),
        sa.Column("leak_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.Integer(), nullable=True),
        sa.UniqueConstraint("bucket_ts", "device_id", "utility_type", name="uq_hourly_stats_device_utility"),
    )
    op.create_index(
        "idx_hourly_stats_building_utility_bucket",
        "hourly_utility_stats",
        ["building_id", "utility_type", "bucket_ts"],
    )
    op.create_index("idx_hourly_stats_device_bucket", "hourly_utility_stats", ["device_id", "bucket_ts"])


def downgrade() -> None:
    op.drop_index("idx_hourly_stats_device_bucket", table_name="hourly_utility_stats")
    op.drop_index("idx_hourly_stats_building_utility_bucket", table_name="hourly_utility_stats")
    op.drop_table("hourly_utility_stats")
