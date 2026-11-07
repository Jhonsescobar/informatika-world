# app/services/penilaian.py
# Menghitung skor sesi ujian (pilihan ganda + esai) dan menyimpan nilai tertinggi siswa.

from sqlalchemy.orm import Session
from app.models.exam import Exam, ExamSession, ExamAnswer
from app.models.question import Question
from app.models.grade import ScoreComponent, Score


def id_soal_sesi(db: Session, sesi: ExamSession, exam: Exam) -> list[int]:
    """Soal yang didapat siswa di sesi ini (urut tampil). Sesi lama tanpa daftar = semua soal bank."""
    if sesi.question_ids:
        return [int(x) for x in sesi.question_ids.split(",") if x.strip().isdigit()]
    return [q.id for q in db.query(Question.id).filter(Question.bank_id == exam.bank_id).order_by(Question.id)]


def total_poin_sesi(db: Session, sesi: ExamSession, exam: Exam) -> int:
    ids = id_soal_sesi(db, sesi, exam)
    return sum(q.points or 0 for q in db.query(Question).filter(Question.id.in_(ids))) if ids else 0


def poin_jawaban(jawaban: ExamAnswer, soal: Question) -> float:
    if soal.question_type == "esai":
        if jawaban.manual_points is not None:
            return jawaban.manual_points
        return jawaban.auto_points or 0.0
    return float(soal.points or 0) if jawaban.is_correct else 0.0


def hitung_ulang_skor(db: Session, sesi: ExamSession) -> int:
    """Jumlahkan ulang poin semua jawaban sesi (dipakai setelah guru mengoreksi esai)."""
    total = 0.0
    for jawaban, soal in (db.query(ExamAnswer, Question).join(Question, Question.id == ExamAnswer.question_id)
                          .filter(ExamAnswer.session_id == sesi.id)):
        total += poin_jawaban(jawaban, soal)
    sesi.score = int(round(total))
    return sesi.score


def simpan_nilai_tertinggi(db: Session, exam: Exam, student_id: int) -> None:
    """Komponen nilai ujian = skor tertinggi siswa dari semua sesinya (termasuk remedial)."""
    terbaik = max((s.score or 0 for s in db.query(ExamSession).filter(
        ExamSession.exam_id == exam.id, ExamSession.student_id == student_id, ExamSession.score != None)), default=0)
    komponen = db.query(ScoreComponent).filter(ScoreComponent.name == exam.title).first()
    if not komponen:
        return
    nilai = db.query(Score).filter(Score.student_id == student_id, Score.component_id == komponen.id).first()
    if nilai:
        nilai.score_value = terbaik
    else:
        db.add(Score(student_id=student_id, component_id=komponen.id, score_value=terbaik))
