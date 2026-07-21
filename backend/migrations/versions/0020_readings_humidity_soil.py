"""Add humidity column to readings for soil sensor.

Revision ID: 0020_readings_humidity_soil
Revises: 0019_test_device_meter_tracking
Create Date: 2026-07-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0020_readings_humidity_soil"
down_revision = "0019_test_device_meter_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("readings", sa.Column("humidity", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("readings", "humidity")
