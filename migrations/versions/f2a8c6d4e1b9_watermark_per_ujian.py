"""Kekuatan watermark per ujian

Revision ID: f2a8c6d4e1b9
Revises: b9e4d7a1c2f6
Create Date: 2026-11-21
"""
from alembic import op
import sqlalchemy as sa

revision = "f2a8c6d4e1b9"
down_revision = "b9e4d7a1c2f6"
branch_labels = None
depends_on = None


def upgrade():
    # Ujian yang sudah ada ikut kekuatan bawaan 16% (sebelumnya tetap 7% yang hilang pada foto berkontras tinggi)
    op.add_column("exams", sa.Column("watermark_persen", sa.Integer(), nullable=False, server_default="16"))


def downgrade():
    op.drop_column("exams", "watermark_persen")
