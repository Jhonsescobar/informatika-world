# app/routers/teacher/umum.py
# Bagian bersama semua halaman guru: lokasi template, kelas aktif, dan beberapa fungsi kecil yang dipakai lebih dari satu fitur.

import re
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import Response
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session

from app.models.academic import AcademicYear
from app.services.teks import pasang as _pasang_filter

BASE_DIR = Path(__file__).resolve().parent.parent.parent      # folder app/
templates_env = Environment(loader=FileSystemLoader(BASE_DIR / "templates"))


# --- Kelas aktif: satu pilihan di sidebar yang berlaku untuk semua menu guru (disimpan di cookie) ---
KELAS_PILIHAN = ("VII", "VIII", "IX")
KELAS_AWAL = "VIII"          # sebelum guru memilih


def kelas_aktif(request) -> str:
    kelas = request.cookies.get("iw_kelas")
    return kelas if kelas in KELAS_PILIHAN else KELAS_AWAL


templates_env.globals["kelas_aktif"] = kelas_aktif
templates_env.globals["kelas_pilihan"] = KELAS_PILIHAN
_pasang_filter(templates_env)   # filter |soal: teks soal aman + blok kode


def baca_kkm(teks):
    """KKM dari isian form: kosong = None (ikut default), angka 0–100 = sah, selain itu = ValueError."""
    teks = (teks or "").strip()
    if teks == "":
        return None
    if not teks.isdigit() or not 0 <= int(teks) <= 100:
        raise ValueError("kkm")
    return int(teks)


TINGKAT = ("VII", "VIII", "IX")


URUTAN = {"nilai": "Nilai tertinggi", "rendah": "Nilai terendah", "az": "Nama A–Z", "za": "Nama Z–A"}


def unduh_xlsx(isi: bytes, nama: str):
    # nama file hanya huruf/angka/strip supaya header tidak bisa disisipi
    aman = re.sub(r"[^A-Za-z0-9_-]+", "_", nama)[:80] or "nilai"
    return Response(content=isi, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{aman}.xlsx"', "Cache-Control": "no-store"})


def tahun_ajaran_aktif(db: Session):
    # Tahun ajaran yang sedang aktif (is_active = 1); dipakai saat siswa dimasukkan ke rombel
    tahun = db.query(AcademicYear).filter(AcademicYear.is_active == 1).order_by(AcademicYear.id.desc()).first()
    if tahun is None:
        raise HTTPException(status_code=400, detail="Belum ada tahun ajaran aktif. Jalankan: python ganti_tahun_ajaran.py")
    return tahun


def baca_ids(teks: str) -> list[int]:
    return sorted({int(x) for x in (teks or "").split(",") if x.strip().isdigit()})
