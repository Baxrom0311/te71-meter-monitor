"""audit indexes

Revision ID: 0007_audit_indexes
Revises: 0006_command_lifecycle
Create Date: 2026-07-06
"""
from alembic import op

revision = "0007_audit_indexes"
down_revision = "0006_command_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("idx_audit_logs_action_ts", "audit_logs", ["action", "ts"])
    op.create_index("idx_audit_logs_entity_ts", "audit_logs", ["entity_type", "entity_id", "ts"])
    op.create_index("idx_audit_logs_user_ts", "audit_logs", ["user_id", "ts"])


def downgrade() -> None:
    op.drop_index("idx_audit_logs_user_ts", table_name="audit_logs")
    op.drop_index("idx_audit_logs_entity_ts", table_name="audit_logs")
    op.drop_index("idx_audit_logs_action_ts", table_name="audit_logs")
