# app/models/exam.py
# Model untuk tabel Ujian/Formatif

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.sql import func
from app.database import Base

class Exam(Base):
    __tablename__ = "exams"
    # Tabel untuk menyimpan konfigurasi ujian

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    # Judul ujian (contoh: "Formatif 1 - CPU & RAM")
    
    bank_id = Column(Integer, ForeignKey("question_banks.id"), nullable=False)
    # Bank soal mana yang dipakai untuk ujian ini
    
    class_target = Column(String, nullable=False)
    # Kelas mana yang boleh mengerjakan ujian ini (VII, VIII, IX)
    
    duration_minutes = Column(Integer, nullable=False)
    # Durasi ujian dalam menit (contoh: 15)
    
    randomize_questions = Column(Boolean, default=False)
    # Fitur anti-cheat: Acak urutan soal untuk setiap siswa?
    
    randomize_options = Column(Boolean, default=False)
    # Fitur anti-cheat: Acak urutan opsi A/B/C/D untuk setiap siswa?
    
    is_published = Column(Boolean, default=False)
    # Status ujian: False = Draf (belum bisa dikerjakan), True = Published (siswa bisa kerjakan)
    
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # Guru pembuat ujian
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # app/models/exam.py (Tambahkan di bawah class Exam)

class ExamSession(Base):
    __tablename__ = "exam_sessions"
    # Catatan sesi ujian seorang siswa

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    # Waktu mulai (otomatis terisi saat data dibuat)
    
    expires_at = Column(DateTime(timezone=True), nullable=False)
    # Batas waktu (waktu mulai + durasi ujian). Server akan membandingkan ini
    
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    # Waktu siswa mengirim jawaban (klik selesai)
    
    score = Column(Integer, nullable=True)
    # Nilai akhir (dihitung di backend)
    
    status = Column(String, default="active")
    # Status: "active" (sedang dikerjakan), "completed" (sudah submit), "expired" (waktu habis)

class ExamAnswer(Base):
    __tablename__ = "exam_answers"
    # Jawaban siswa untuk setiap soal

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("exam_sessions.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    
    selected_option_id = Column(Integer, ForeignKey("question_options.id"), nullable=True)
    # Opsi mana yang dipilih siswa (berdasarkan ID, BUKAN huruf A/B/C/D)
    
    is_correct = Column(Boolean, default=False)
    # Apakah jawaban ini benar? (Dievaluasi saat submit)