"""audit logs

Revision ID: 0003_audit_logs
Revises: 0002_device_tokens
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_audit_logs"
down_revision = "0002_device_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ts", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("username", sa.String(64), nullable=True),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=True),
        sa.Column("entity_id", sa.String(128), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
    )
    op.create_index("idx_audit_logs_ts", "audit_logs", ["ts"])


def downgrade() -> None:
    op.drop_index("idx_audit_logs_ts", table_name="audit_logs")
    op.drop_table("audit_logs")
