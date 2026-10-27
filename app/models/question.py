# app/models/question.py
# Model untuk Bank Soal, Soal, dan Opsi Jawaban

from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey, DateTime
from sqlalchemy.sql import func
from app.database import Base

class QuestionBank(Base):
    __tablename__ = "question_banks"
    # Wadah/kelompok soal (contoh: "Bank Soal CPU Kelas VII")

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    # Nama bank soal
    
    class_target = Column(String, nullable=False)
    # Target kelas (VII, VIII, IX)
    
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # Guru pembuat
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Question(Base):
    __tablename__ = "questions"
    # Soal individual di dalam bank soal

    id = Column(Integer, primary_key=True, index=True)
    bank_id = Column(Integer, ForeignKey("question_banks.id"), nullable=False)
    # Terikat ke bank soal mana
    
    text = Column(Text, nullable=False)
    # Teks soal itu sendiri
    
    points = Column(Integer, default=1)
    # Poin/nilai soal ini (default 1)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class QuestionOption(Base):
    __tablename__ = "question_options"
    # Opsi/jawaban pilihan ganda (A, B, C, D)

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    # Terikat ke soal mana
    
    text = Column(String, nullable=False)
    # Teks opsi (contoh: "Central Processing Unit")
    
    is_correct = Column(Boolean, default=False)
    # APakah ini jawaban benar? (Ini jauh lebih aman daripada menyimpan "A" atau "B")