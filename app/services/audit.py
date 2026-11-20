# app/services/audit.py
# Catatan aksi guru. catat() hanya menambah baris ke sesi database; pemanggil yang commit,
# jadi catatan dan aksinya tersimpan bersama (atau batal bersama).
# JANGAN pernah mengisi rincian dengan PIN atau password.

from sqlalchemy.orm import Session

from app.models.aksi_guru import AksiGuru
from app.models.user import User

KATEGORI = ("Siswa", "Nilai", "Ujian", "Akun")
PER_HALAMAN = 50


def _potong(teks, panjang: int) -> str:
    teks = " ".join(str(teks or "").split())
    return teks if len(teks) <= panjang else teks[: panjang - 1] + "…"


def daftar_nama(nama: list[str], batas: int = 8) -> str:
    """'Ani, Budi, Cici' atau 'Ani, Budi, ... (+5 lagi)' agar rincian tetap pendek."""
    tampil = ", ".join(nama[:batas])
    return tampil + (f" (+{len(nama) - batas} lagi)" if len(nama) > batas else "")


def catat(db: Session, user, kategori: str, aksi: str, sasaran: str = "", rincian: str = "") -> None:
    assert kategori in KATEGORI, kategori
    uid = None
    try:
        uid = int((user or {}).get("sub"))
    except (TypeError, ValueError):
        pass
    db.add(AksiGuru(user_id=uid, kategori=kategori, aksi=_potong(aksi, 60),
                    sasaran=_potong(sasaran, 200), rincian=_potong(rincian, 400)))


def baca(db: Session, kategori: str | None = None, halaman: int = 1) -> dict:
    """Satu halaman catatan, terbaru di atas. kategori tak dikenal = semua."""
    q = db.query(AksiGuru, User.full_name).outerjoin(User, User.id == AksiGuru.user_id)
    if kategori in KATEGORI:
        q = q.filter(AksiGuru.kategori == kategori)
    else:
        kategori = None
    total = q.count()
    halaman = max(1, halaman)
    baris = (q.order_by(AksiGuru.waktu.desc(), AksiGuru.id.desc())
             .offset((halaman - 1) * PER_HALAMAN).limit(PER_HALAMAN).all())
    return {"baris": [{"catatan": a, "oleh": nama or "(akun dihapus)"} for a, nama in baris],
            "kategori": kategori, "halaman": halaman, "total": total,
            "ada_lanjut": halaman * PER_HALAMAN < total}
