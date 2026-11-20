# app/models/aksi_guru.py
# Catatan aksi guru yang berdampak pada data (reset PIN, hapus siswa, ubah nilai, remedial, dll).
# Hanya ditambah, tidak pernah diubah atau dihapus lewat aplikasi.

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.database import Base


class AksiGuru(Base):
    __tablename__ = "aksi_guru"

    id = Column(Integer, primary_key=True)
    waktu = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    kategori = Column(String(20), nullable=False, index=True)   # Siswa / Nilai / Ujian / Akun
    aksi = Column(String(60), nullable=False)
    sasaran = Column(String(200), nullable=False, default="")
    rincian = Column(String(400), nullable=False, default="")
