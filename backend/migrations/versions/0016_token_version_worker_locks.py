"""token version and worker locks

Revision ID: 0016_token_version_worker_locks
Revises: 0015_ota_batches
Create Date: 2026-07-07
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_token_version_worker_locks"
down_revision = "0015_ota_batches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="1"))
    op.create_table(
        "worker_locks",
        sa.Column("name", sa.String(128), primary_key=True),
        sa.Column("locked_until", sa.Integer(), nullable=False),
        sa.Column("owner", sa.String(128), nullable=True),
        sa.Column("updated_at", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("worker_locks")
    op.drop_column("users", "token_version")
