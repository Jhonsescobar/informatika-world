# app/services/penilaian.py
# Menghitung skor sesi ujian (pilihan ganda + esai) dan menyimpan nilai tertinggi siswa.

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from app.models.exam import Exam, ExamSession, ExamAnswer, ExamEvent
from app.models.question import Question, QuestionOption

# Jawaban yang dikirim sampai 2 menit setelah waktu habis masih diterima (jaringan lambat)
TOLERANSI_KIRIM = timedelta(minutes=2)


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


def nilai_sesi(db: Session, sesi: ExamSession, exam: Exam, pilihan: dict, esai: dict) -> tuple[int, int]:
    """Nilai jawaban satu sesi dan simpan ExamAnswer. pilihan = {id_soal: id_opsi}, esai = {id_soal: teks}.
    Hanya soal milik sesi ini yang dihitung, dan opsi harus milik soalnya. Mengembalikan (skor, jumlah salah)."""
    from app.services.esai import nilai_esai
    ids = id_soal_sesi(db, sesi, exam)
    soal = {q.id: q for q in db.query(Question).filter(Question.id.in_(ids))} if ids else {}
    opsi = {o.id: o for o in db.query(QuestionOption).filter(QuestionOption.question_id.in_(list(soal)))} if soal else {}
    total, salah = 0.0, len(soal)
    for qid, teks in esai.items():
        q = soal.get(qid)
        if not q or q.question_type != "esai":
            continue
        teks = (teks or "").strip()[:5000]
        hasil = nilai_esai(teks, q.answer_key, q.keywords)
        poin = round((q.points or 0) * hasil["persen"], 1)
        total += poin
        if hasil["persen"] >= 1:
            salah -= 1
        db.add(ExamAnswer(session_id=sesi.id, question_id=qid, answer_text=teks,
                          similarity=hasil["kemiripan"], auto_points=poin, is_correct=hasil["persen"] >= 1))
    for qid, oid in pilihan.items():
        q, o = soal.get(qid), opsi.get(oid)
        if not q or q.question_type == "esai" or not o or o.question_id != qid:
            continue
        if o.is_correct:
            total += q.points or 0
            salah -= 1
        db.add(ExamAnswer(session_id=sesi.id, question_id=qid, selected_option_id=oid, is_correct=o.is_correct))
    sesi.score = int(round(total))
    return sesi.score, salah


def selesaikan_dari_log(db: Session, sesi: ExamSession, exam: Exam | None = None) -> None:
    """Waktu habis tanpa jawaban terkirim (HP mati, sinyal putus, tab ditutup):
    nilai diambil dari jawaban terakhir yang tersimpan berkala di log, sampai batas waktu + toleransi.
    Dulu sesi seperti ini tidak punya nilai sama sekali."""
    if sesi.status != "active":
        return
    exam = exam or db.query(Exam).filter(Exam.id == sesi.exam_id).first()
    batas = sesi.expires_at + TOLERANSI_KIRIM
    pilihan, esai = {}, {}
    for e in (db.query(ExamEvent).filter(ExamEvent.session_id == sesi.id, ExamEvent.kind.in_(["pilih", "esai"]))
              .order_by(ExamEvent.id)):
        if e.created_at and e.created_at > batas:
            continue
        if e.kind == "pilih" and e.option_id:
            pilihan[e.question_id] = e.option_id
        elif e.kind == "esai":
            esai[e.question_id] = e.detail or ""
    nilai_sesi(db, sesi, exam, pilihan, esai)
    sesi.status = "expired"
    sesi.submitted_at = sesi.submitted_at or datetime.now(timezone.utc)
    db.add(ExamEvent(session_id=sesi.id, kind="kirim", detail="dari log (waktu habis)"))


def tutup_sesi_lewat(db: Session, exam_ids: list[int] | None = None) -> int:
    """Selesaikan semua sesi yang waktunya sudah lewat tapi masih 'active' (siswa tidak kembali).
    Dipanggil saat guru membuka hasil/rekap, supaya nilainya ikut terhitung."""
    q = db.query(ExamSession).filter(ExamSession.status == "active",
                                     ExamSession.expires_at < datetime.now(timezone.utc) - TOLERANSI_KIRIM)
    if exam_ids is not None:
        q = q.filter(ExamSession.exam_id.in_(exam_ids))
    jumlah = 0
    for sesi in q.with_for_update(skip_locked=True).all():
        selesaikan_dari_log(db, sesi)
        jumlah += 1
    if jumlah:
        db.commit()
    return jumlah
