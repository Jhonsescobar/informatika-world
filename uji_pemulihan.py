# uji_pemulihan.py
# Membuktikan cadangan benar-benar bisa dipulihkan, TANPA menyentuh database asli.
#
#     python uji_pemulihan.py                       uji cadangan terbaru di folder backups/
#     python uji_pemulihan.py "<berkas>.dump"       uji berkas tertentu
#     python uji_pemulihan.py "<berkas>.dump.enc"   uji salinan terenkripsi dari Drive (butuh kunci pribadi + frasa sandi)
#
# Cadangan dipulihkan ke database sementara "<nama db>_uji_pulih", isi tabelnya dihitung dan dibandingkan
# dengan database sekarang, lalu database sementara itu dihapus. Disarankan dijalankan sebulan sekali
# dan setelah mengganti kunci enkripsi.

import subprocess
import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from backup_db import FOLDER, cari_program, koneksi_pg
from cadangan_aman import GalatEnkripsi, dekripsi_interaktif

AKHIRAN = "_uji_pulih"


def _url_db(nama: str):
    import os
    return make_url(os.environ["DATABASE_URL"]).set(database=nama)


def hitung_baris(url) -> dict[str, int]:
    mesin = create_engine(url)
    try:
        with mesin.connect() as c:
            tabel = sorted(t for t in inspect(c).get_table_names() if t != "alembic_version")
            return {t: c.execute(text(f'SELECT count(*) FROM "{t}"')).scalar() for t in tabel}
    finally:
        mesin.dispose()


def uji(berkas: Path) -> dict:
    """Pulihkan `berkas` ke database sementara. Mengembalikan {"ok", "pesan", "tabel": {nama: (cadangan, sekarang)}}."""
    pg_restore = cari_program("pg_restore")
    if not pg_restore:
        return {"ok": False, "pesan": "pg_restore tidak ditemukan. Pastikan PostgreSQL terpasang.", "tabel": {}}
    args, env, nama_db = koneksi_pg()
    sementara = nama_db + AKHIRAN
    assert sementara != nama_db and sementara.endswith(AKHIRAN)      # pagar: tidak mungkin menyentuh database asli
    admin = create_engine(_url_db("postgres"), isolation_level="AUTOCOMMIT")
    url_sementara = _url_db(sementara)
    try:
        with admin.connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{sementara}" WITH (FORCE)'))
            c.execute(text(f'CREATE DATABASE "{sementara}"'))
        proses = subprocess.run([pg_restore, *args, "-d", sementara, "--no-owner", "--exit-on-error", str(berkas)],
                                env=env, capture_output=True, text=True)
        if proses.returncode != 0:
            return {"ok": False, "pesan": "Pemulihan GAGAL: " + proses.stderr.strip()[:400], "tabel": {}}
        hasil = hitung_baris(url_sementara)
        sekarang = hitung_baris(_url_db(nama_db))
        tabel = {t: (n, sekarang.get(t)) for t, n in hasil.items()}
        with create_engine(url_sementara).connect() as c:
            versi = c.execute(text("SELECT count(*) FROM alembic_version")).scalar()
        if not hasil.get("users"):
            return {"ok": False, "pesan": "Pulih, tetapi tabel users kosong: cadangan ini tidak berisi akun guru.", "tabel": tabel}
        if not versi:
            return {"ok": False, "pesan": "Pulih, tetapi versi skema (alembic_version) tidak ada.", "tabel": tabel}
        return {"ok": True, "pesan": "Cadangan bisa dipulihkan dengan baik.", "tabel": tabel}
    finally:
        try:
            with admin.connect() as c:
                c.execute(text(f'DROP DATABASE IF EXISTS "{sementara}" WITH (FORCE)'))
        finally:
            admin.dispose()


def main() -> int:
    with tempfile.TemporaryDirectory() as folder_sementara:
        if len(sys.argv) > 1:
            sumber = Path(sys.argv[1].strip('"'))
            if not sumber.is_file():
                print(f"Berkas tidak ditemukan: {sumber}")
                return 1
        else:
            daftar = sorted(FOLDER.glob("informatika_*.dump"))
            if not daftar:
                print("Belum ada cadangan di folder backups/.")
                return 1
            sumber = daftar[-1]
        berkas = sumber
        if sumber.suffix == ".enc":
            berkas = Path(folder_sementara) / sumber.name[: -len(".enc")]
            try:
                dekripsi_interaktif(sumber, berkas)
            except GalatEnkripsi as e:
                print(e)
                return 1
        print(f"Menguji {sumber.name} ...")
        h = uji(berkas)
    if h["tabel"]:
        print(f"\n  {'tabel':<24}{'cadangan':>10}{'sekarang':>10}")
        for t, (a, b) in h["tabel"].items():
            tanda = "  <- cadangan lebih lama dari data sekarang" if b is not None and a < b else ""
            print(f"  {t:<24}{a:>10}{(b if b is not None else '-'):>10}{tanda}")
    print("\n" + ("LULUS: " if h["ok"] else "GAGAL: ") + h["pesan"])
    print("Database asli tidak diubah.")
    return 0 if h["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
