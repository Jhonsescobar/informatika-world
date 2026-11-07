# app/models/exam.py
# Model untuk tabel Ujian/Formatif

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, Float
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

    # Jumlah soal per siswa, diambil acak dari bank (kosong = semua soal di bank)
    question_count = Column(Integer, nullable=True)
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

    # Soal yang didapat siswa ini (id dipisah koma, urut tampil); kosong = semua soal bank
    question_ids = Column(Text, nullable=True)
    # Status: "active" (sedang dikerjakan), "completed" (sudah submit), "expired" (waktu habis)

class RemedialRequest(Base):
    __tablename__ = "remedial_requests"
    # Permintaan mengulang ujian dari siswa (nilai < 60%), harus disetujui guru
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    session_id = Column(Integer, ForeignKey("exam_sessions.id"), nullable=False)
    status = Column(String, nullable=False, default="pending")  # pending / approved / rejected / used
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    decided_at = Column(DateTime(timezone=True), nullable=True)


class ExamViolation(Base):
    __tablename__ = "exam_violations"
    # Catatan anti-cheat: siswa pindah tab, keluar layar penuh, mencoba salin/screenshot, dst.
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("exam_sessions.id"), nullable=False, index=True)
    kind = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ExamAnswer(Base):
    __tablename__ = "exam_answers"
    # Jawaban siswa untuk setiap soal

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("exam_sessions.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    
    selected_option_id = Column(Integer, ForeignKey("question_options.id"), nullable=True)
    # Opsi mana yang dipilih siswa (berdasarkan ID, BUKAN huruf A/B/C/D)
    
    is_correct = Column(Boolean, default=False)

    # Khusus esai
    answer_text = Column(Text, nullable=True)       # jawaban siswa
    similarity = Column(Float, nullable=True)       # kemiripan dengan kunci (0-1)
    auto_points = Column(Float, nullable=True)      # poin hasil penilaian otomatis
    manual_points = Column(Float, nullable=True)    # poin koreksi guru (menggantikan otomatis)


class ExamEvent(Base):
    __tablename__ = "exam_events"
    # Log aktivitas siswa selama ujian: soal dilihat, pilih / ganti jawaban, ketik esai, mulai, kirim
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("exam_sessions.id"), nullable=False, index=True)
    kind = Column(String, nullable=False)
    question_id = Column(Integer, nullable=True)
    option_id = Column(Integer, nullable=True)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # Apakah jawaban ini benar? (Dievaluasi saat submit)