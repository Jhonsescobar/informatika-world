# app/models/user.py
# Model untuk tabel pengguna (Guru/Admin)

from sqlalchemy import Column, Integer, String, Boolean, DateTime
# Mengimpor tipe data kolom dari SQLAlchemy

from sqlalchemy.sql import func
# Mengimpor fungsi SQL bawaan seperti func.now() untuk timestamp otomatis

from app.database import Base
# Mengimpor kelas Base dari database.py agar tabel ini terdaftar di SQLAlchemy

class User(Base):
    # Membuat kelas User yang mewarisi Base
    __tablename__ = "users"
    # Nama tabel yang akan dibuat di PostgreSQL

    id = Column(Integer, primary_key=True, index=True)
    # Kolom id: Integer, Primary Key (unik), dan diberi index agar pencarian cepat

    email = Column(String, unique=True, index=True, nullable=False)
    # Kolom email: String, Unik (tidak boleh sama), di-index, tidak boleh kosong (nullable=False)

    full_name = Column(String, nullable=False)
    # Kolom nama lengkap guru

    hashed_password = Column(String, nullable=False)
    # Kolom password yang sudah di-hash (dienkripsi). TIDAK PERNAH simpan password mentah!

    is_active = Column(Boolean, default=True)
    # Kolom status aktif. Defaultnya True (aktif)

    role = Column(String, default="teacher")
    # Kolom peran: "teacher" atau "admin". Defaultnya guru

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # Kolom waktu pembuatan data. Otomatis terisi waktu saat data pertama kali dibuat

    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # Kolom waktu update. Otomatis terisi waktu saat data diubah