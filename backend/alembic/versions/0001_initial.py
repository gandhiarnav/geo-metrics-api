"""Initial schema: files and features tables

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    json_type = sa.JSON().with_variant(postgresql.JSONB, "postgresql")

    op.create_table(
        "files",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("crs", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("feature_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warnings", json_type, nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_files_status", "files", ["status"], unique=False)

    op.create_table(
        "features",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("file_id", sa.String(length=36), nullable=False),
        sa.Column("feature_index", sa.Integer(), nullable=False),
        sa.Column("geometry_type", sa.String(length=64), nullable=False),
        sa.Column("geometry", json_type, nullable=True),
        sa.Column("properties", json_type, nullable=False),
        sa.Column("source_crs", sa.String(length=64), nullable=False),
        sa.Column("measurement_status", sa.String(length=32), nullable=False),
        sa.Column("area_sq_m", sa.Float(), nullable=True),
        sa.Column("length_m", sa.Float(), nullable=True),
        sa.Column("perimeter_m", sa.Float(), nullable=True),
        sa.Column("geodesic_area_sq_m", sa.Float(), nullable=True),
        sa.Column("geodesic_length_m", sa.Float(), nullable=True),
        sa.Column("measurement_crs", sa.Text(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_features_file_id", "features", ["file_id"], unique=False)
    op.create_index("ix_features_measurement_status", "features", ["measurement_status"], unique=False)
    op.create_index("ix_features_file_feature_index", "features", ["file_id", "feature_index"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_features_file_feature_index", table_name="features")
    op.drop_index("ix_features_measurement_status", table_name="features")
    op.drop_index("ix_features_file_id", table_name="features")
    op.drop_table("features")
    op.drop_index("ix_files_status", table_name="files")
    op.drop_table("files")
