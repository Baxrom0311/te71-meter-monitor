"""Add building map link and coordinates.

Revision ID: 0017_building_map_fields
Revises: 0016_token_version_worker_locks
Create Date: 2026-07-08
"""

from alembic import op
import sqlalchemy as sa


revision = "0017_building_map_fields"
down_revision = "0016_token_version_worker_locks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("buildings", sa.Column("maps_url", sa.String(length=1000), nullable=True))
    op.add_column("buildings", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("buildings", sa.Column("longitude", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("buildings", "longitude")
    op.drop_column("buildings", "latitude")
    op.drop_column("buildings", "maps_url")
