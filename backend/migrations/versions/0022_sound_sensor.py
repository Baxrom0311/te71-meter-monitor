"""Add sound sensor support: level column to readings, avg/min/max_level to hourly_utility_stats.

Revision ID: 0022_sound_sensor
Revises: 0021_hourly_stats_avg_humidity
Create Date: 2026-07-21
"""

from alembic import op
import sqlalchemy as sa


revision = "0022_sound_sensor"
down_revision = "0021_hourly_stats_avg_humidity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("readings", sa.Column("level", sa.Float(), nullable=True))
    op.add_column("hourly_utility_stats", sa.Column("avg_level", sa.Float(), nullable=True))
    op.add_column("hourly_utility_stats", sa.Column("min_level", sa.Float(), nullable=True))
    op.add_column("hourly_utility_stats", sa.Column("max_level", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("hourly_utility_stats", "max_level")
    op.drop_column("hourly_utility_stats", "min_level")
    op.drop_column("hourly_utility_stats", "avg_level")
    op.drop_column("readings", "level")
