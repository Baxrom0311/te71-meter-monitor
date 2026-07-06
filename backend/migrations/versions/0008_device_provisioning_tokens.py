"""device provisioning tokens

Revision ID: 0008_device_provisioning_tokens
Revises: 0007_audit_indexes
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_device_provisioning_tokens"
down_revision = "0007_audit_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_provisioning_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("device_id", sa.String(128), nullable=True),
        sa.Column("building_id", sa.Integer(), sa.ForeignKey("buildings.id"), nullable=True),
        sa.Column("point_id", sa.Integer(), sa.ForeignKey("measurement_points.id"), nullable=True),
        sa.Column("utility_type", sa.String(32), nullable=True),
        sa.Column("device_role", sa.String(64), nullable=True),
        sa.Column("firmware_mode", sa.String(32), nullable=True),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.Column("used_at", sa.Integer(), nullable=True),
        sa.Column("used_by_device_id", sa.String(128), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_by_username", sa.String(64), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=True),
    )
    op.create_index("idx_prov_tokens_device", "device_provisioning_tokens", ["device_id"])
    op.create_index("idx_prov_tokens_expires_used", "device_provisioning_tokens", ["expires_at", "used_at"])


def downgrade() -> None:
    op.drop_index("idx_prov_tokens_expires_used", table_name="device_provisioning_tokens")
    op.drop_index("idx_prov_tokens_device", table_name="device_provisioning_tokens")
    op.drop_table("device_provisioning_tokens")
