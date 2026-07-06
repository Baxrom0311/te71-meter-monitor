"""command lifecycle

Revision ID: 0006_command_lifecycle
Revises: 0005_operational_indexes
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_command_lifecycle"
down_revision = "0005_operational_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("commands", sa.Column("expires_at", sa.Integer(), nullable=True))
    op.add_column("commands", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("commands", sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"))
    op.create_index("idx_commands_expires_status", "commands", ["expires_at", "status"])


def downgrade() -> None:
    op.drop_index("idx_commands_expires_status", table_name="commands")
    op.drop_column("commands", "max_attempts")
    op.drop_column("commands", "attempts")
    op.drop_column("commands", "expires_at")
