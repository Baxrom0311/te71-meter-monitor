"""alert rules

Revision ID: 0013_alert_rules
Revises: 0012_firmware_install_events
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_alert_rules"
down_revision = "0012_firmware_install_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("building_id", sa.Integer(), sa.ForeignKey("buildings.id"), nullable=True),
        sa.Column("utility_type", sa.String(32), nullable=True),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("min_value", sa.Float(), nullable=True),
        sa.Column("max_value", sa.Float(), nullable=True),
        sa.Column("severity", sa.String(32), nullable=False, server_default="warning"),
        sa.Column("dedupe_sec", sa.Integer(), nullable=True),
        sa.Column("message", sa.String(500), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.Integer(), nullable=True),
    )
    op.create_index(
        "idx_alert_rules_lookup",
        "alert_rules",
        ["enabled", "building_id", "utility_type", "kind"],
    )
    op.create_index("idx_alert_rules_kind", "alert_rules", ["kind"])


def downgrade() -> None:
    op.drop_index("idx_alert_rules_kind", table_name="alert_rules")
    op.drop_index("idx_alert_rules_lookup", table_name="alert_rules")
    op.drop_table("alert_rules")
