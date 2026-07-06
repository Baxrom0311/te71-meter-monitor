"""device token revoke

Revision ID: 0010_device_token_revoke
Revises: 0009_provisioning_token_revoke
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_device_token_revoke"
down_revision = "0009_provisioning_token_revoke"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("token_revoked_at", sa.Integer(), nullable=True))
    op.add_column("devices", sa.Column("token_revoked_by_user_id", sa.Integer(), nullable=True))
    op.add_column("devices", sa.Column("token_revoked_by_username", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("devices", "token_revoked_by_username")
    op.drop_column("devices", "token_revoked_by_user_id")
    op.drop_column("devices", "token_revoked_at")
