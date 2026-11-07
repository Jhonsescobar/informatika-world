# app/models/material.py
# Model untuk tabel materi pembelajaran

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean, false
# Text: Tipe data untuk teks panjang (isi materi)

from sqlalchemy.sql import func
from app.database import Base

class Material(Base):
    __tablename__ = "materials"
    # Nama tabel

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    # Judul materi (contoh: "CPU & RAM")
    
    description = Column(String, nullable=True)
    # Deskripsi singkat
    
    content = Column(Text, nullable=True)
    # Isi materi lengkap (bisa teks panjang, nanti bisa HTML)
    
    class_target = Column(String, nullable=False)
    # Target kelas (contoh: "VII", "VIII", "IX")
    
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # Siapa guru yang membuat materi ini
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Materi tampil di sisi siswa sebagai kisi-kisi hanya bila dibuka guru,
    # dan otomatis tertutup setelah close_at (kosong = terbuka sampai ditutup manual)
    is_published = Column(Boolean, nullable=False, default=False, server_default=false())
    close_at = Column(DateTime(timezone=True), nullable=True)