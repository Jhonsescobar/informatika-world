# Penjaga struktur rute guru setelah teacher.py dipecah per fitur.
# tests/rute_guru.json = daftar (metode, alamat) yang harus ada; tidak boleh hilang, bertambah diam-diam, atau tertutup rute lain.

import json
import re
from pathlib import Path

from starlette.routing import Match

from app.main import app
from app.routers.teacher import akun, analisis, bank_soal, hasil, materi, nilai, siswa, ujian

URUTAN_BAGIAN = (akun, materi, bank_soal, ujian, hasil, nilai, siswa, analisis)     # sama dengan app/routers/teacher/__init__.py


def test_daftar_rute_guru_tidak_berubah():
    ada = sorted((m.upper(), p) for p, v in app.openapi()["paths"].items() if p.startswith("/teacher") for m in v)
    seharusnya = sorted(tuple(x) for x in json.loads((Path(__file__).parent / "rute_guru.json").read_text(encoding="utf-8")))
    assert ada == seharusnya, (
        f"hilang: {sorted(set(seharusnya) - set(ada))}  baru: {sorted(set(ada) - set(seharusnya))}. "
        "Bila rute memang sengaja ditambah/dihapus, perbarui tests/rute_guru.json.")


def test_tidak_ada_rute_guru_yang_tertutup_rute_lain():
    """Urutan pendaftaran menentukan pemenang bila dua alamat sama-sama cocok (mis. /students/delete vs /students/{id}).
    Setiap rute, diuji dengan alamat contohnya, harus menang atas rute yang didaftarkan lebih dulu."""
    semua = [r for bagian in URUTAN_BAGIAN for r in bagian.router.routes]
    assert len(semua) >= 60
    tertutup = []
    for r in semua:
        contoh = re.sub(r"\{[^}]+\}", "1", r.path)
        for metode in r.methods - {"HEAD"}:
            scope = {"type": "http", "path": contoh, "method": metode, "root_path": "", "headers": []}
            pemenang = next(x for x in semua if x.matches(scope)[0] == Match.FULL)
            if pemenang.path != r.path:
                tertutup.append((metode, r.path, "tertutup oleh", pemenang.path))
    assert not tertutup, tertutup


def test_setiap_bagian_hanya_berisi_rutenya_sendiri():
    """Satu alamat hanya boleh didaftarkan di satu bagian (tidak ganda antar berkas)."""
    terlihat = {}
    for bagian in URUTAN_BAGIAN:
        for r in bagian.router.routes:
            for m in r.methods - {"HEAD"}:
                kunci = (m, r.path)
                assert kunci not in terlihat, f"{kunci} ganda di {bagian.__name__} dan {terlihat[kunci]}"
                terlihat[kunci] = bagian.__name__
