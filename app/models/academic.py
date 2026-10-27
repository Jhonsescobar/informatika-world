# app/models/academic.py
# Model untuk struktur akademik sekolah

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
# ForeignKey: Digunakan untuk membuat relasi antar tabel

from sqlalchemy.sql import func
from app.database import Base

class AcademicYear(Base):
    __tablename__ = "academic_years"
    # Tabel tahun ajaran (contoh: 2024/2025)

    id = Column(Integer, primary_key=True, index=True)
    year_name = Column(String, unique=True, nullable=False)
    # Contoh isi: "2024/2025". Unik, tidak boleh sama

    is_active = Column(Integer, default=1)
    # 1 jika aktif, 0 jika tidak. Hanya 1 tahun ajaran yang aktif

class SchoolClass(Base):
    __tablename__ = "classes"
    # Tabel tingkat kelas (VII, VIII, IX)

    id = Column(Integer, primary_key=True, index=True)
    class_name = Column(String, unique=True, nullable=False)
    # Contoh isi: "VII", "VIII", "IX"

class Rombel(Base):
    __tablename__ = "rombels"
    # Tabel Rombongan Belajar (VII-A, VII-B)

    id = Column(Integer, primary_key=True, index=True)
    rombel_name = Column(String, nullable=False)
    # Contoh isi: "VII-A"

    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    # Relasi ke tabel classes. VII-A pasti milik kelas VII

class Enrollment(Base):
    __tablename__ = "enrollments"
    # Tabel PENTING: Mencatat siswa masuk rombel mana di tahun ajaran mana
    # Ini memungkinkan siswa pindah kelas setiap tahun tanpa menghapus data lama

    id = Column(Integer, primary_key=True, index=True)

    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    # Relasi ke siswa

    academic_year_id = Column(Integer, ForeignKey("academic_years.id"), nullable=False)
    # Relasi ke tahun ajaran

    rombel_id = Column(Integer, ForeignKey("rombels.id"), nullable=False)
    # Relasi ke rombel

    created_at = Column(DateTime(timezone=True), server_default=func.now())