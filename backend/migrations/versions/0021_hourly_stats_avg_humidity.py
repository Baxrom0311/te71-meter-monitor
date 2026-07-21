"""Add avg_humidity to hourly_utility_stats for soil sensor.

Revision ID: 0021_hourly_stats_avg_humidity
Revises: 0020_readings_humidity_soil
Create Date: 2026-07-20
"""

from alembic import op
import sqlalchemy as sa


revision = "0021_hourly_stats_avg_humidity"
down_revision = "0020_readings_humidity_soil"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("hourly_utility_stats", sa.Column("avg_humidity", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("hourly_utility_stats", "avg_humidity")
