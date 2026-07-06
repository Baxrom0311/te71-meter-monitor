"""alert notifications

Revision ID: 0014_alert_notifications
Revises: 0013_alert_rules
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0014_alert_notifications"
down_revision = "0013_alert_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alert_id", sa.Integer(), sa.ForeignKey("alerts.id"), nullable=True),
        sa.Column("device_id", sa.String(128), nullable=False),
        sa.Column("building_id", sa.Integer(), sa.ForeignKey("buildings.id"), nullable=True),
        sa.Column("point_id", sa.Integer(), sa.ForeignKey("measurement_points.id"), nullable=True),
        sa.Column("utility_type", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False, server_default="internal"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("message", sa.String(500), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("sent_at", sa.Integer(), nullable=True),
    )
    op.create_index(
        "idx_alert_notifications_status_created",
        "alert_notifications",
        ["status", "created_at"],
    )
    op.create_index("idx_alert_notifications_alert", "alert_notifications", ["alert_id"])


def downgrade() -> None:
    op.drop_index("idx_alert_notifications_alert", table_name="alert_notifications")
    op.drop_index("idx_alert_notifications_status_created", table_name="alert_notifications")
    op.drop_table("alert_notifications")
