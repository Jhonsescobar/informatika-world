# app/services/remedial.py
# Siapa yang perlu remedial di satu ujian, dan pemberian izin remedial (satu siswa atau sekaligus).

from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.exam import ExamSession, RemedialRequest
from app.services.rekap import BATAS_REMEDIAL, persen_terbaik, siswa_kelas, tahun_aktif


def beri_remedial(db: Session, exam_id: int, student_id: int, session_id: int) -> None:
    """Izin remedial untuk satu siswa. Permintaan yang sedang menunggu langsung disetujui (tanpa data ganda)."""
    sekarang = datetime.now(timezone.utc)
    ada = db.query(RemedialRequest).filter(RemedialRequest.student_id == student_id, RemedialRequest.exam_id == exam_id,
                                           RemedialRequest.status.in_(["pending", "approved"])).first()
    if ada:
        ada.status, ada.decided_at = "approved", sekarang
    else:
        db.add(RemedialRequest(student_id=student_id, exam_id=exam_id, session_id=session_id, status="approved",
                               decided_at=sekarang))


def daftar_remedial(db: Session, exam) -> dict:
    """{"perlu": siswa dengan nilai tertinggi < batas, "belum": siswa yang belum mengerjakan, "batas": ...}
    Tiap entri "perlu": siswa, rombel, persen, sesi_id (sesi selesai terakhir), status (None/pending/approved)."""
    murid = siswa_kelas(db, exam.class_target, tahun_aktif(db))
    nilai = persen_terbaik(db, [exam.id], [s.id for s, _, _ in murid])
    sesi_terakhir = {}
    for s in (db.query(ExamSession).filter(ExamSession.exam_id == exam.id, ExamSession.status != "active")
              .order_by(ExamSession.id)):
        sesi_terakhir[s.student_id] = s.id
    status = {r.student_id: r.status for r in db.query(RemedialRequest).filter(
        RemedialRequest.exam_id == exam.id, RemedialRequest.status.in_(["pending", "approved"]))}
    perlu, belum = [], []
    for s, rombel, _ in murid:
        persen = nilai.get((s.id, exam.id))
        if persen is None:
            belum.append({"siswa": s, "rombel": rombel})
        elif persen < BATAS_REMEDIAL and s.id in sesi_terakhir:
            perlu.append({"siswa": s, "rombel": rombel, "persen": persen, "sesi_id": sesi_terakhir[s.id],
                          "status": status.get(s.id)})
    perlu.sort(key=lambda x: (x["persen"], x["siswa"].name.lower()))
    return {"perlu": perlu, "belum": belum, "batas": BATAS_REMEDIAL}
