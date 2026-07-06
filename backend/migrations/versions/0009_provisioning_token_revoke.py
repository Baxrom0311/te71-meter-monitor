"""provisioning token revoke

Revision ID: 0009_provisioning_token_revoke
Revises: 0008_device_provisioning_tokens
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_provisioning_token_revoke"
down_revision = "0008_device_provisioning_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("device_provisioning_tokens", sa.Column("revoked_at", sa.Integer(), nullable=True))
    op.add_column("device_provisioning_tokens", sa.Column("revoked_by_user_id", sa.Integer(), nullable=True))
    op.add_column("device_provisioning_tokens", sa.Column("revoked_by_username", sa.String(64), nullable=True))
    op.drop_index("idx_prov_tokens_expires_used", table_name="device_provisioning_tokens")
    op.create_index(
        "idx_prov_tokens_expires_used",
        "device_provisioning_tokens",
        ["expires_at", "used_at", "revoked_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_prov_tokens_expires_used", table_name="device_provisioning_tokens")
    op.create_index("idx_prov_tokens_expires_used", "device_provisioning_tokens", ["expires_at", "used_at"])
    op.drop_column("device_provisioning_tokens", "revoked_by_username")
    op.drop_column("device_provisioning_tokens", "revoked_by_user_id")
    op.drop_column("device_provisioning_tokens", "revoked_at")
