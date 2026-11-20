# app/services/kesempatan.py
# Kesempatan melanjutkan ujian: guru membuka kembali sesi yang terkirim otomatis karena pelanggaran
# (misalnya jaringan putus atau layar tak sengaja keluar). Jawaban siswa tetap, waktu memakai sisa waktunya.
#
#   - sesi kembali "active", nilai dikosongkan (dihitung ulang saat siswa mengirim lagi)
#   - ExamAnswer lama dihapus agar tidak ganda; jawaban dipulihkan dari log seperti saat halaman dimuat ulang
#   - hitungan pelanggaran mulai dari nol: hanya pelanggaran SETELAH kesempatan yang dihitung menuju kirim otomatis
#     (catatan pelanggaran lama tetap tersimpan untuk guru)

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.exam import ExamAnswer, ExamEvent, ExamSession

MIN_SISA = timedelta(minutes=3)       # siswa selalu mendapat waktu cukup untuk melanjutkan
MIN_SISA_SESI = timedelta(minutes=1)  # sesi yang terkirim kurang dari ini dari batas waktu dianggap habis waktu, bukan terhenti


def _aware(w):
    return w if w is None or w.tzinfo else w.replace(tzinfo=timezone.utc)


def sesi_otomatis(db: Session, session_ids: list[int]) -> set[int]:
    """Id sesi yang terkirim otomatis (bukan klik Kirim oleh siswa)."""
    if not session_ids:
        return set()
    return {sid for (sid,) in db.query(ExamEvent.session_id).filter(
        ExamEvent.session_id.in_(session_ids), ExamEvent.kind == "kirim", ExamEvent.detail == "otomatis")}


def sisa_waktu(sesi: ExamSession) -> timedelta:
    if not sesi.submitted_at or not sesi.expires_at:
        return timedelta(0)
    return _aware(sesi.expires_at) - _aware(sesi.submitted_at)


def bisa_dilanjutkan(db: Session, sesi: ExamSession, otomatis: set[int] | None = None) -> bool:
    """Sesi selesai karena kirim otomatis, masih ada sisa waktu, dan siswa belum membuka sesi yang lebih baru."""
    if sesi.status == "active" or sisa_waktu(sesi) < MIN_SISA_SESI:
        return False
    ada = otomatis if otomatis is not None else sesi_otomatis(db, [sesi.id])
    if sesi.id not in ada:
        return False
    lebih_baru = db.query(ExamSession.id).filter(ExamSession.student_id == sesi.student_id,
                                                 ExamSession.exam_id == sesi.exam_id, ExamSession.id > sesi.id).first()
    return lebih_baru is None


def beri_kesempatan(db: Session, sesi: ExamSession) -> bool:
    """Buka kembali sesi. False bila tidak memenuhi syarat (tidak ada yang diubah)."""
    if not bisa_dilanjutkan(db, sesi):
        return False
    sisa = max(sisa_waktu(sesi), MIN_SISA)
    sekarang = datetime.now(timezone.utc)
    db.query(ExamAnswer).filter(ExamAnswer.session_id == sesi.id).delete(synchronize_session=False)
    sesi.status, sesi.submitted_at, sesi.score = "active", None, None
    sesi.expires_at = sekarang + sisa
    db.add(ExamEvent(session_id=sesi.id, kind="kesempatan", detail=f"guru membuka lagi, sisa {int(sisa.total_seconds() // 60)} menit"))
    return True


def batas_hitung_pelanggaran(db: Session, session_id: int):
    """Waktu kesempatan terakhir (pelanggaran sebelum ini tidak dihitung menuju kirim otomatis); None bila belum pernah."""
    return db.query(ExamEvent.created_at).filter(ExamEvent.session_id == session_id, ExamEvent.kind == "kesempatan") \
        .order_by(ExamEvent.id.desc()).limit(1).scalar()
