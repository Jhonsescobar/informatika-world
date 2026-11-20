# app/services/kesempatan.py
# Kesempatan melanjutkan ujian: guru membuka kembali sesi yang berhenti sebelum waktunya habis.
# Dua sebab yang dikenali sistem:
#   - "otomatis": terkirim otomatis karena pelanggaran (layar keluar berkali-kali)
#   - "terputus": siswa menghilang (jaringan putus, HP mati, layar padam) sampai waktu habis, lalu sesi ditutup dari log
#
# Guru menentukan berapa menit yang diberikan; sistem hanya MENYARANKAN: sisa waktu saat siswa terakhir terlihat
# (mis. keluar di menit 10 dari 15 = saran 5 menit). Guru bebas menaikkan atau menurunkan.
#
#   - sesi kembali "active", nilai dikosongkan (dihitung ulang saat siswa mengirim lagi)
#   - ExamAnswer lama dihapus agar tidak ganda; jawaban dipulihkan dari log seperti saat halaman dimuat ulang
#   - hitungan pelanggaran mulai dari nol: hanya pelanggaran SETELAH kesempatan yang dihitung menuju kirim otomatis
#     (catatan pelanggaran lama tetap tersimpan untuk guru)

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.exam import Exam, ExamAnswer, ExamEvent, ExamSession, ExamViolation
from app.models.student import Student

OTOMATIS = "otomatis"
TERPUTUS = "terputus"
DETAIL_TERPUTUS = "dari log (waktu habis)"      # ditulis selesaikan_dari_log di services/penilaian.py

MIN_SISA = timedelta(minutes=3)       # saran minimal bila guru tidak mengisi menit
MIN_SISA_SESI = timedelta(minutes=1)  # berhenti kurang dari ini dari batas waktu = waktunya memang habis, bukan terhenti
MENIT_MIN, MENIT_MAKS = 1, 180        # batas isian guru


@dataclass(frozen=True)
class Henti:
    jenis: str               # OTOMATIS / TERPUTUS
    terakhir_aktif: datetime
    sisa: timedelta          # sisa waktu saat siswa terakhir terlihat = saran untuk guru
    terpakai_menit: int      # "keluar di menit ke-N"
    durasi_menit: int

    @property
    def saran_menit(self) -> int:
        return max(1, int(round(self.sisa.total_seconds() / 60)))


def _aware(w):
    return w if w is None or w.tzinfo else w.replace(tzinfo=timezone.utc)


def henti_terakhir(db: Session, session_ids: list[int]) -> dict[int, tuple[str, str | None]]:
    """Per sesi: (jenis, detail) dari event 'kirim' atau 'kesempatan' yang PALING AKHIR.
    Kesempatan yang lebih baru dari kiriman terakhir berarti sesi itu sedang dilanjutkan, bukan terhenti."""
    if not session_ids:
        return {}
    hasil = {}
    for sid, kind, detail in (db.query(ExamEvent.session_id, ExamEvent.kind, ExamEvent.detail)
                              .filter(ExamEvent.session_id.in_(session_ids), ExamEvent.kind.in_(["kirim", "kesempatan"]))
                              .order_by(ExamEvent.id)):
        hasil[sid] = (kind, detail)
    return hasil


def terakhir_aktif(db: Session, sesi: ExamSession) -> datetime:
    """Kapan siswa terakhir terlihat di sesi ini: jawaban/aktivitas terakhir, pelanggaran terakhir, sinyal 'hadir'
    (selama masih dalam waktu ujian), dan saat kesempatan dibuka. Tidak pernah melewati batas waktu."""
    awal = _aware(sesi.started_at) or _aware(sesi.expires_at)
    batas = _aware(sesi.expires_at)
    kandidat = [awal]
    for q in (db.query(func.max(ExamEvent.created_at)).filter(ExamEvent.session_id == sesi.id, ExamEvent.kind.notin_(["kirim", "kesempatan"])),
              db.query(func.max(ExamEvent.created_at)).filter(ExamEvent.session_id == sesi.id, ExamEvent.kind == "kesempatan"),
              db.query(func.max(ExamViolation.created_at)).filter(ExamViolation.session_id == sesi.id)):
        w = _aware(q.scalar())
        if w:
            kandidat.append(w)
    terlihat = _aware(db.query(Student.last_seen).filter(Student.id == sesi.student_id).scalar())
    if terlihat and awal <= terlihat <= batas:      # sesudah waktu habis = siswa kembali ke beranda, bukan sedang ujian
        kandidat.append(terlihat)
    return min(max(kandidat), batas)


def info_henti(db: Session, sesi: ExamSession, terakhir: dict | None = None) -> Henti | None:
    """Data henti bila sesi ini boleh dibuka lagi oleh guru; None bila tidak (selesai sendiri, waktu memang habis,
    sedang berjalan, atau siswa sudah membuka sesi yang lebih baru)."""
    if sesi.status == "active":
        return None
    kind, detail = (terakhir if terakhir is not None else henti_terakhir(db, [sesi.id])).get(sesi.id, (None, None))
    if kind != "kirim":
        return None
    if detail == "otomatis":
        jenis, aktif = OTOMATIS, _aware(sesi.submitted_at)
    elif detail == DETAIL_TERPUTUS:
        jenis, aktif = TERPUTUS, terakhir_aktif(db, sesi)
    else:
        return None
    if aktif is None or not sesi.expires_at:
        return None
    sisa = _aware(sesi.expires_at) - aktif
    if sisa < MIN_SISA_SESI:
        return None
    if db.query(ExamSession.id).filter(ExamSession.student_id == sesi.student_id, ExamSession.exam_id == sesi.exam_id,
                                       ExamSession.id > sesi.id).first():
        return None
    durasi = db.query(Exam.duration_minutes).filter(Exam.id == sesi.exam_id).scalar() or 0
    terpakai = max(0, min(durasi, int(round(durasi - sisa.total_seconds() / 60))))
    return Henti(jenis, aktif, sisa, terpakai, durasi)


def bisa_dilanjutkan(db: Session, sesi: ExamSession, terakhir: dict | None = None) -> bool:
    return info_henti(db, sesi, terakhir) is not None


def menit_sah(teks) -> int | None | bool:
    """Isian menit dari guru: kosong -> None (pakai saran); angka 1..180 -> int; selain itu False."""
    teks = (str(teks) if teks is not None else "").strip()
    if teks == "":
        return None
    if not teks.isdigit() or not MENIT_MIN <= int(teks) <= MENIT_MAKS:
        return False
    return int(teks)


def beri_kesempatan(db: Session, sesi: ExamSession, menit: int | None = None) -> Henti | None:
    """Buka kembali sesi dengan `menit` menit (None = saran sistem, minimal 3 menit).
    Mengembalikan data henti (untuk dicatat), atau None bila tidak memenuhi syarat (tidak ada yang diubah)."""
    info = info_henti(db, sesi)
    if info is None or (menit is not None and not MENIT_MIN <= menit <= MENIT_MAKS):
        return None
    sisa = timedelta(minutes=menit) if menit is not None else max(info.sisa, MIN_SISA)
    db.query(ExamAnswer).filter(ExamAnswer.session_id == sesi.id).delete(synchronize_session=False)
    sesi.status, sesi.submitted_at, sesi.score = "active", None, None
    sesi.expires_at = datetime.now(timezone.utc) + sisa
    db.add(ExamEvent(session_id=sesi.id, kind="kesempatan",
                     detail=f"guru membuka lagi ({info.jenis}), diberi {int(sisa.total_seconds() // 60)} menit"))
    return info


def batas_hitung_pelanggaran(db: Session, session_id: int):
    """Waktu kesempatan terakhir (pelanggaran sebelum ini tidak dihitung menuju kirim otomatis); None bila belum pernah."""
    return db.query(ExamEvent.created_at).filter(ExamEvent.session_id == session_id, ExamEvent.kind == "kesempatan") \
        .order_by(ExamEvent.id.desc()).limit(1).scalar()
