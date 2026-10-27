# app/models/student.py
# Model untuk tabel siswa

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.database import Base

class Student(Base):
    __tablename__ = "students"
    # Nama tabel: students

    id = Column(Integer, primary_key=True, index=True)
    # ID unik internal untuk siswa

    name = Column(String, nullable=False)
    # Nama lengkap siswa

    nipd = Column(String, unique=True, nullable=True)
    # NIPD (Nomor Induk Peserta Didik)

    pin_hash = Column(String, nullable=False)
    # PIN 4 digit siswa yang sudah di-hash

    is_active = Column(Boolean, default=True)
    # Status siswa

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())