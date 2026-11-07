# app/services/rekap.py
# SATU-SATUNYA tempat perhitungan nilai. Dipakai rekap guru, peringkat siswa, dan ekspor Excel,
# supaya angka di semua tempat selalu sama.
#
# Aturan:
#   nilai ujian    = persen TERTINGGI siswa di ujian itu (remedial tidak menurunkan nilai)
#   nilai komponen = rata-rata nilai ujian yang masuk komponen itu (belum mengerjakan = 0)
#   nilai akhir    = Σ(nilai komponen × bobot) / Σ bobot   -> selalu skala 0–100
#   tanpa komponen = rata-rata semua ujian (supaya peringkat tetap jalan sebelum bobot diatur)
# Hanya ujian tahun ajaran aktif yang terbit / sudah pernah dikerjakan yang dihitung.

from collections import defaultdict
from sqlalchemy.orm import Session

from app.models.academic import AcademicYear, Enrollment, Rombel, SchoolClass
from app.models.exam import Exam, ExamSession
from app.models.grade import ScoreComponent
from app.models.question import Question
from app.models.student import Student

KKM = 75             # batas tuntas nilai akhir
BATAS_REMEDIAL = 60  # nilai ujian di bawah ini boleh remedial


def tahun_aktif(db: Session):
    return db.query(AcademicYear).filter(AcademicYear.is_active == 1).order_by(AcademicYear.id.desc()).first()


def persen_terbaik(db: Session, exam_ids: list[int], student_ids: list[int] | None = None) -> dict:
    """{(student_id, exam_id): persen tertinggi 0-100} dari sesi yang sudah selesai."""
    if not exam_ids:
        return {}
    exams = {e.id: e for e in db.query(Exam).filter(Exam.id.in_(exam_ids))}
    poin = {q.id: q.points or 0 for q in db.query(Question.id, Question.points)
            .filter(Question.bank_id.in_({e.bank_id for e in exams.values()}))}
    poin_bank = defaultdict(int)
    for q in db.query(Question.id, Question.bank_id, Question.points).filter(Question.bank_id.in_({e.bank_id for e in exams.values()})):
        poin_bank[q.bank_id] += q.points or 0

    q = db.query(ExamSession).filter(ExamSession.exam_id.in_(exam_ids), ExamSession.status != "active",
                                     ExamSession.score != None)
    if student_ids is not None:
        q = q.filter(ExamSession.student_id.in_(student_ids))
    hasil = {}
    for s in q:
        if s.question_ids:
            maks = sum(poin.get(int(x), 0) for x in s.question_ids.split(",") if x.strip().isdigit())
        else:
            maks = poin_bank[exams[s.exam_id].bank_id]
        persen = round(s.score * 100 / maks, 1) if maks else 0.0
        kunci = (s.student_id, s.exam_id)
        hasil[kunci] = max(hasil.get(kunci, 0.0), min(persen, 100.0))
    return hasil


def ujian_dihitung(db: Session, kelas: str, tahun):
    """Ujian tingkat ini di tahun ajaran aktif yang terbit atau sudah pernah dikerjakan."""
    q = db.query(Exam).filter(Exam.class_target == kelas)
    if tahun:
        q = q.filter((Exam.academic_year_id == tahun.id) | (Exam.academic_year_id == None))
    pernah = {x[0] for x in db.query(ExamSession.exam_id).distinct()}
    return [e for e in q.order_by(Exam.id) if e.is_published or e.id in pernah]


def siswa_kelas(db: Session, kelas: str, tahun, rombel_id: int | None = None):
    """[(Student, nama rombel)] di tingkat ini pada tahun ajaran aktif."""
    q = (db.query(Student, Rombel.rombel_name, Rombel.id)
         .join(Enrollment, Enrollment.student_id == Student.id)
         .join(Rombel, Rombel.id == Enrollment.rombel_id)
         .join(SchoolClass, SchoolClass.id == Rombel.class_id)
         .filter(SchoolClass.class_name == kelas))
    if tahun:
        q = q.filter(Enrollment.academic_year_id == tahun.id)
    if rombel_id:
        q = q.filter(Rombel.id == rombel_id)
    lihat = {}
    for s, nama_rombel, rid in q.order_by(Student.name):
        lihat.setdefault(s.id, (s, nama_rombel, rid))
    return list(lihat.values())


def rekap_kelas(db: Session, kelas: str, rombel_id: int | None = None) -> dict:
    tahun = tahun_aktif(db)
    komponen = db.query(ScoreComponent).filter(ScoreComponent.class_target == kelas).order_by(ScoreComponent.id).all()
    ujian = ujian_dihitung(db, kelas, tahun)
    murid = siswa_kelas(db, kelas, tahun, rombel_id)
    terbaik = persen_terbaik(db, [e.id for e in ujian], [s.id for s, _, _ in murid])

    per_komponen = {k.id: [e for e in ujian if e.component_id == k.id] for k in komponen}
    lepas = [e for e in ujian if e.component_id not in per_komponen]
    total_bobot = sum(k.weight for k in komponen if per_komponen[k.id])

    baris = []
    for s, nama_rombel, rid in murid:
        nilai_ujian = {e.id: terbaik.get((s.id, e.id)) for e in ujian}
        nilai_komp, belum = {}, 0
        for k in komponen:
            daftar = per_komponen[k.id]
            if not daftar:
                nilai_komp[k.id] = None
                continue
            belum += sum(1 for e in daftar if nilai_ujian[e.id] is None)
            nilai_komp[k.id] = round(sum(nilai_ujian[e.id] or 0 for e in daftar) / len(daftar), 1)
        if total_bobot:
            akhir = round(sum((nilai_komp[k.id] or 0) * k.weight for k in komponen if per_komponen[k.id]) / total_bobot, 1)
        elif ujian:
            akhir = round(sum(v or 0 for v in nilai_ujian.values()) / len(ujian), 1)
            belum = sum(1 for v in nilai_ujian.values() if v is None)
        else:
            akhir = None
        baris.append({"siswa": s, "rombel": nama_rombel, "rombel_id": rid, "ujian": nilai_ujian,
                      "komponen": nilai_komp, "akhir": akhir, "belum": belum,
                      "tuntas": akhir is not None and akhir >= KKM})

    bobot_semua = sum(k.weight for k in komponen)
    return {"kelas": kelas, "tahun": tahun, "komponen": komponen, "per_komponen": per_komponen, "ujian": ujian,
            "lepas": lepas, "baris": baris, "total_bobot": total_bobot, "bobot_semua": bobot_semua,
            "pakai_bobot": bool(total_bobot)}


def urutkan(baris: list, urut: str) -> list:
    """urut: nilai (tertinggi dulu, default) | rendah | az | za"""
    nama = lambda r: r["siswa"].name.lower()
    if urut == "az":
        return sorted(baris, key=nama)
    if urut == "za":
        return sorted(baris, key=nama, reverse=True)
    if urut == "rendah":
        return sorted(baris, key=lambda r: (r["akhir"] if r["akhir"] is not None else -1, nama(r)))
    return sorted(baris, key=lambda r: (-(r["akhir"] if r["akhir"] is not None else -1), nama(r)))
