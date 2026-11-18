"""KKM bertingkat: KKM tahun ajaran, KKM komponen, KKM ujian

Revision ID: e5a1c9d3b7f2
Revises: d4f1b8c2a913
Create Date: 2026-11-16
"""
from alembic import op
import sqlalchemy as sa

revision = "e5a1c9d3b7f2"
down_revision = "d4f1b8c2a913"
branch_labels = None
depends_on = None


def upgrade():
    # KKM akhir tahun ajaran: tahun lama otomatis 75 (sama seperti sebelumnya)
    op.add_column("academic_years", sa.Column("kkm", sa.Integer(), nullable=False, server_default="75"))
    # Kosong = pakai KKM default (komponen: ikut tahun ajaran; ujian: ikut komponen)
    op.add_column("score_components", sa.Column("kkm", sa.Integer(), nullable=True))
    op.add_column("exams", sa.Column("kkm", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("exams", "kkm")
    op.drop_column("score_components", "kkm")
    op.drop_column("academic_years", "kkm")
