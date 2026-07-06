"""device tokens

Revision ID: 0002_device_tokens
Revises: 0001_initial_schema
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_device_tokens"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("api_token_hash", sa.String(255), nullable=True))
    op.add_column("devices", sa.Column("token_created_at", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("devices", "token_created_at")
    op.drop_column("devices", "api_token_hash")
