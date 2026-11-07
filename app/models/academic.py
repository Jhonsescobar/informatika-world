# app/models/academic.py
# Model untuk struktur akademik sekolah

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class AcademicYear(Base):
    __tablename__ = "academic_years"
    # Tabel tahun ajaran (contoh: 2024/2025)

    id = Column(Integer, primary_key=True, index=True)
    year_name = Column(String, unique=True, nullable=False)
    is_active = Column(Integer, default=1)

class SchoolClass(Base):
    __tablename__ = "classes"
    # Tabel tingkat kelas (VII, VIII, IX)

    id = Column(Integer, primary_key=True, index=True)
    class_name = Column(String, unique=True, nullable=False)

class Rombel(Base):
    __tablename__ = "rombels"
    # Tabel Rombongan Belajar (VII.1, VII.2, dst)

    id = Column(Integer, primary_key=True, index=True)
    rombel_name = Column(String, nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)

class Enrollment(Base):
    __tablename__ = "enrollments"
    # Tabel PENTING: Mencatat siswa masuk rombel mana di tahun ajaran mana

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    academic_year_id = Column(Integer, ForeignKey("academic_years.id"), nullable=False)
    rombel_id = Column(Integer, ForeignKey("rombels.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship untuk akses data terkait
    student = relationship("Student", back_populates="enrollments")
    rombel = relationship("Rombel")