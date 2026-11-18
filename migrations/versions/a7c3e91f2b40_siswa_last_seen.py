"""Siswa: waktu sinyal terakhir (status online di pantau guru)

Revision ID: a7c3e91f2b40
Revises: e5a1c9d3b7f2
Create Date: 2026-11-18
"""
from alembic import op
import sqlalchemy as sa

revision = "a7c3e91f2b40"
down_revision = "e5a1c9d3b7f2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("students", sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("students", "last_seen")
