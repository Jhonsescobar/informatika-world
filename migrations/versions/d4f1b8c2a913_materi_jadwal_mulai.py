"""Materi: jadwal mulai tampil (open_at)

Revision ID: d4f1b8c2a913
Revises: c3e9a1d07b52
Create Date: 2026-11-09
"""
from alembic import op
import sqlalchemy as sa

revision = "d4f1b8c2a913"
down_revision = "c3e9a1d07b52"
branch_labels = None
depends_on = None


def upgrade():
    # Kosong = tampil begitu dibuka guru (perilaku lama tetap sama)
    op.add_column("materials", sa.Column("open_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("materials", "open_at")
