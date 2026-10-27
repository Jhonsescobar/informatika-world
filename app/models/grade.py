# app/models/grade.py
# Model untuk Sistem Nilai Akademik

from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.sql import func
from app.database import Base

class ScoreComponent(Base):
    __tablename__ = "score_components"
    # Tabel untuk menampung komponen penilaian (Formatif, UAS, Project, dll)

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    # Nama komponen (contoh: "Formatif 1")
    
    weight = Column(Integer, nullable=False)
    # Bobot komponen dalam persentase (contoh: 15 untuk 15%)
    
    class_target = Column(String, nullable=False)
    # Kelas target (VII, VIII, IX)
    
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # Guru pembuat
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Score(Base):
    __tablename__ = "scores"
    # Tabel untuk menyimpan nilai siswa per komponen

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    # Siswa yang dinilai
    
    component_id = Column(Integer, ForeignKey("score_components.id"), nullable=False)
    # Komponen nilainya apa (relasi ke ScoreComponent)
    
    score_value = Column(Integer, nullable=False)
    # Nilai siswa (0-100)