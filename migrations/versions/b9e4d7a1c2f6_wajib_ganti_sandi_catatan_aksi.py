"""Wajib ganti sandi bawaan + catatan aksi guru

Revision ID: b9e4d7a1c2f6
Revises: a7c3e91f2b40
Create Date: 2026-11-20
"""
from alembic import op
import sqlalchemy as sa

revision = "b9e4d7a1c2f6"
down_revision = "a7c3e91f2b40"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()))
    # Akun yang SAAT INI masih memakai sandi bawaan ditandai wajib ganti; yang sudah diganti tidak terganggu.
    from app.utils.security import SANDI_BAWAAN, verify_password
    sambungan = op.get_bind()
    for uid, hash_ in sambungan.execute(sa.text("SELECT id, hashed_password FROM users")).fetchall():
        try:
            bawaan = verify_password(SANDI_BAWAAN, hash_)
        except Exception:  # hash tak dikenal: jangan kunci akun
            bawaan = False
        if bawaan:
            sambungan.execute(sa.text("UPDATE users SET must_change_password = true WHERE id = :i"), {"i": uid})

    op.create_table(
        "aksi_guru",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("waktu", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kategori", sa.String(20), nullable=False),
        sa.Column("aksi", sa.String(60), nullable=False),
        sa.Column("sasaran", sa.String(200), nullable=False, server_default=""),
        sa.Column("rincian", sa.String(400), nullable=False, server_default=""),
    )
    op.create_index("ix_aksi_guru_waktu", "aksi_guru", ["waktu"])
    op.create_index("ix_aksi_guru_kategori", "aksi_guru", ["kategori"])


def downgrade():
    op.drop_table("aksi_guru")
    op.drop_column("users", "must_change_password")
