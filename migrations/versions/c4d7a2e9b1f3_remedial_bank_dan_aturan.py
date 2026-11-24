"""Bank soal remedial dan aturan saran nilai akhir per ujian

Revision ID: c4d7a2e9b1f3
Revises: f2a8c6d4e1b9
Create Date: 2026-11-24
"""
from alembic import op
import sqlalchemy as sa

revision = "c4d7a2e9b1f3"
down_revision = "f2a8c6d4e1b9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("exams", sa.Column("remedial_bank_id", sa.Integer(), sa.ForeignKey("question_banks.id"), nullable=True))
    # Ujian yang sudah ada: "tinggi" = remedial ikut nilai tertinggi, persis perilaku sebelum fitur ini (angka rekap tidak berubah).
    # Ujian baru memakai bawaan aplikasi ("saran"), jadi default sisi database dilepas setelah isian lama terisi.
    op.add_column("exams", sa.Column("remedial_aturan", sa.String(), nullable=False, server_default="tinggi"))
    op.alter_column("exams", "remedial_aturan", server_default=None)


def downgrade():
    op.drop_column("exams", "remedial_aturan")
    op.drop_column("exams", "remedial_bank_id")
