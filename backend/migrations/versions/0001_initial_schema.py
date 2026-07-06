"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "buildings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("address", sa.String(500)),
        sa.Column("floors", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("entrances_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.Integer()),
        sa.Column("updated_at", sa.Integer()),
    )
    op.create_table(
        "building_utilities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("building_id", sa.Integer(), sa.ForeignKey("buildings.id"), nullable=False),
        sa.Column("utility_type", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255)),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.Integer()),
        sa.Column("updated_at", sa.Integer()),
        sa.UniqueConstraint("building_id", "utility_type", name="uq_building_utility"),
    )
    op.create_table(
        "premises",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("building_id", sa.Integer(), sa.ForeignKey("buildings.id"), nullable=False),
        sa.Column("number", sa.String(64), nullable=False),
        sa.Column("floor", sa.Integer()),
        sa.Column("premise_type", sa.String(32), nullable=False, server_default="apartment"),
        sa.Column("created_at", sa.Integer()),
        sa.Column("updated_at", sa.Integer()),
    )
    op.create_table(
        "devices",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("building_id", sa.Integer(), sa.ForeignKey("buildings.id")),
        sa.Column("point_id", sa.Integer()),
        sa.Column("name", sa.String(255)),
        sa.Column("utility_type", sa.String(32), nullable=False, server_default="electricity"),
        sa.Column("device_role", sa.String(64)),
        sa.Column("firmware_mode", sa.String(32), nullable=False, server_default="auto"),
        sa.Column("meter_type", sa.String(64), server_default="unknown"),
        sa.Column("meter_serial", sa.String(128)),
        sa.Column("serial_number", sa.String(128)),
        sa.Column("hardware_version", sa.String(64)),
        sa.Column("software_version", sa.String(64)),
        sa.Column("build_number", sa.String(64)),
        sa.Column("baud_rate", sa.Integer(), server_default="9600"),
        sa.Column("chip_model", sa.String(64)),
        sa.Column("rssi", sa.Integer()),
        sa.Column("ip", sa.String(64)),
        sa.Column("fw_version", sa.String(64)),
        sa.Column("building", sa.String(255)),
        sa.Column("floor", sa.String(64)),
        sa.Column("room", sa.String(64)),
        sa.Column("group_name", sa.String(128)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_seen", sa.Integer()),
        sa.Column("registered", sa.Integer()),
        sa.Column("created_at", sa.Integer()),
        sa.Column("updated_at", sa.Integer()),
    )
    op.create_table(
        "measurement_points",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("building_id", sa.Integer(), sa.ForeignKey("buildings.id")),
        sa.Column("utility_module_id", sa.Integer(), sa.ForeignKey("building_utilities.id")),
        sa.Column("premise_id", sa.Integer(), sa.ForeignKey("premises.id")),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("measurement_points.id")),
        sa.Column("device_id", sa.String(128), sa.ForeignKey("devices.id")),
        sa.Column("name", sa.String(255)),
        sa.Column("utility_type", sa.String(32), nullable=False, server_default="electricity"),
        sa.Column("role", sa.String(64), nullable=False),
        sa.Column("sensor_type", sa.String(64)),
        sa.Column("location_name", sa.String(255)),
        sa.Column("meter_serial", sa.String(128)),
        sa.Column("floor", sa.Integer()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.Integer()),
        sa.Column("updated_at", sa.Integer()),
    )
    op.create_table(
        "readings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.String(128), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("reading_id", sa.String(128)),
        sa.Column("sequence_no", sa.Integer()),
        sa.Column("building_id", sa.Integer(), sa.ForeignKey("buildings.id")),
        sa.Column("point_id", sa.Integer(), sa.ForeignKey("measurement_points.id")),
        sa.Column("utility_type", sa.String(32), nullable=False, server_default="electricity"),
        sa.Column("sensor_type", sa.String(64)),
        sa.Column("ts", sa.Integer(), nullable=False),
        sa.Column("voltage_l1", sa.Float()),
        sa.Column("voltage_l2", sa.Float()),
        sa.Column("voltage_l3", sa.Float()),
        sa.Column("current_l1", sa.Float()),
        sa.Column("current_l2", sa.Float()),
        sa.Column("current_l3", sa.Float()),
        sa.Column("power_w", sa.Float()),
        sa.Column("power_var", sa.Float()),
        sa.Column("frequency", sa.Float()),
        sa.Column("pf", sa.Float()),
        sa.Column("energy_kwh", sa.Float()),
        sa.Column("energy_t1", sa.Float()),
        sa.Column("energy_t2", sa.Float()),
        sa.Column("energy_t3", sa.Float()),
        sa.Column("energy_t4", sa.Float()),
        sa.Column("relay_on", sa.Boolean()),
        sa.Column("pressure_bar", sa.Float()),
        sa.Column("pressure_bottom_bar", sa.Float()),
        sa.Column("pressure_top_bar", sa.Float()),
        sa.Column("flow_rate", sa.Float()),
        sa.Column("volume_m3", sa.Float()),
        sa.Column("temperature_c", sa.Float()),
        sa.Column("leak_detected", sa.Boolean()),
        sa.Column("valve_open", sa.Boolean()),
        sa.Column("raw_payload", sa.Text()),
        sa.Column("created_at", sa.Integer()),
        sa.UniqueConstraint("device_id", "reading_id", name="uq_device_reading_id"),
    )
    op.create_index("idx_readings_device_ts", "readings", ["device_id", "ts"])
    op.create_index("idx_readings_point_ts", "readings", ["point_id", "ts"])
    op.create_index("idx_readings_building_ts", "readings", ["building_id", "ts"])
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.String(128), nullable=False),
        sa.Column("building_id", sa.Integer(), sa.ForeignKey("buildings.id")),
        sa.Column("point_id", sa.Integer(), sa.ForeignKey("measurement_points.id")),
        sa.Column("utility_type", sa.String(32), nullable=False, server_default="electricity"),
        sa.Column("severity", sa.String(32), nullable=False, server_default="warning"),
        sa.Column("ts", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("value", sa.Float()),
        sa.Column("message", sa.String(500)),
        sa.Column("cleared", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("cleared_at", sa.Integer()),
    )
    op.create_index("idx_alerts_cleared_ts", "alerts", ["cleared", "ts"])
    op.create_table(
        "commands",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.String(128), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("param", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("created", sa.Integer()),
        sa.Column("sent", sa.Integer()),
        sa.Column("acked", sa.Integer()),
        sa.Column("ack_result", sa.Text()),
    )
    op.create_table(
        "firmware",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("hardware_version", sa.String(64)),
        sa.Column("firmware_mode", sa.String(32), nullable=False, server_default="auto"),
        sa.Column("size", sa.Integer()),
        sa.Column("sha256", sa.String(128)),
        sa.Column("uploaded", sa.Integer()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text()),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.Integer()),
        sa.Column("last_login", sa.Integer()),
        sa.Column("created_at", sa.Integer()),
        sa.Column("updated_at", sa.Integer()),
    )


def downgrade() -> None:
    op.drop_table("users")
    op.drop_table("firmware")
    op.drop_table("commands")
    op.drop_index("idx_alerts_cleared_ts", table_name="alerts")
    op.drop_table("alerts")
    op.drop_index("idx_readings_building_ts", table_name="readings")
    op.drop_index("idx_readings_point_ts", table_name="readings")
    op.drop_index("idx_readings_device_ts", table_name="readings")
    op.drop_table("readings")
    op.drop_table("measurement_points")
    op.drop_table("devices")
    op.drop_table("premises")
    op.drop_table("building_utilities")
    op.drop_table("buildings")
