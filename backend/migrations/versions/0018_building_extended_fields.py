"""Add extended building fields (own + urganchshahar integration).

Revision ID: 0018_building_extended_fields
Revises: 0017_building_map_fields
Create Date: 2026-07-11
"""

from alembic import op
import sqlalchemy as sa


revision = "0018_building_extended_fields"
down_revision = "0017_building_map_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # O'zimizdan qo'shimcha
    op.add_column("buildings", sa.Column("image_url", sa.String(length=1000), nullable=True))
    op.add_column("buildings", sa.Column("total_apartments", sa.Integer(), nullable=True))
    op.add_column("buildings", sa.Column("construction_year", sa.Integer(), nullable=True))

    # Urganchshahar integratsiya maydonlari
    op.add_column("buildings", sa.Column("organization_name", sa.String(length=255), nullable=True))
    op.add_column("buildings", sa.Column("mahalla_name", sa.String(length=255), nullable=True))
    op.add_column("buildings", sa.Column("street_name", sa.String(length=255), nullable=True))
    op.add_column("buildings", sa.Column("object_type", sa.String(length=255), nullable=True))
    op.add_column("buildings", sa.Column("polygon_coordinate", sa.Text(), nullable=True))
    op.add_column("buildings", sa.Column("is_official", sa.Boolean(), nullable=True))
    op.add_column("buildings", sa.Column("ext_sensor_temp_out", sa.Float(), nullable=True))
    op.add_column("buildings", sa.Column("ext_sensor_temp_in", sa.Float(), nullable=True))
    op.add_column("buildings", sa.Column("ext_sensor_pressure", sa.String(length=50), nullable=True))
    op.add_column("buildings", sa.Column("ext_sensor_online", sa.Boolean(), nullable=True))
    op.add_column("buildings", sa.Column("ext_sensor_updated_at", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("buildings", "ext_sensor_updated_at")
    op.drop_column("buildings", "ext_sensor_online")
    op.drop_column("buildings", "ext_sensor_pressure")
    op.drop_column("buildings", "ext_sensor_temp_in")
    op.drop_column("buildings", "ext_sensor_temp_out")
    op.drop_column("buildings", "is_official")
    op.drop_column("buildings", "polygon_coordinate")
    op.drop_column("buildings", "object_type")
    op.drop_column("buildings", "street_name")
    op.drop_column("buildings", "mahalla_name")
    op.drop_column("buildings", "organization_name")
    op.drop_column("buildings", "construction_year")
    op.drop_column("buildings", "total_apartments")
    op.drop_column("buildings", "image_url")
