# app/models/achievement.py
# Model untuk Sistem Achievement (Lencana/Gamifikasi)

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func
from app.database import Base

class Achievement(Base):
    __tablename__ = "achievements"
    # Tabel definisi lencana yang ada di sistem

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    # Nama lencana (contoh: "Computer Explorer")
    
    description = Column(String, nullable=False)
    # Syarat mendapatkannya (contoh: "Menyelesaikan ujian pertama")
    
    icon = Column(String, nullable=False)
    # Emoji ikon lencana (contoh: "🚀")
    
    condition_type = Column(String, nullable=False)
    # Tipe kondisi trigger (contoh: "FIRST_EXAM", "PERFECT_SCORE")

class StudentAchievement(Base):
    __tablename__ = "student_achievements"
    # Tabel catatan lencana yang sudah didapat siswa

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    # Siswa penerima
    
    achievement_id = Column(Integer, ForeignKey("achievements.id"), nullable=False)
    # Lencana apa yang didapat
    
    awarded_at = Column(DateTime(timezone=True), server_default=func.now())
    # Waktu lencana diberikan