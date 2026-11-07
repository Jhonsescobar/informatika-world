# backup_db.py
# Cadangan database + rekap nilai Excel, gratis dan tanpa layanan luar.
#
#     python backup_db.py            -> cadangan lengkap (dipanggil otomatis oleh ONLINE.bat)
#
# Hasil di folder backups/ (tidak ikut ke GitHub karena berisi data siswa):
#   informatika_YYYYMMDD_HHMMSS.dump   cadangan utuh, bisa dipulihkan dengan pulihkan_db.py
#   nilai_YYYYMMDD_HHMMSS.xlsx         rekap nilai semua kelas, langsung bisa dibuka di Excel
# Disimpan 30 cadangan terbaru; yang lebih lama dihapus otomatis.
#
# Agar cadangan juga ada di luar laptop, isi BACKUP_COPY_DIR di file .env dengan folder yang
# tersinkron ke awan, misalnya folder Google Drive / OneDrive:
#   BACKUP_COPY_DIR=G:\My Drive\Backup Informatika

import glob
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url

FOLDER = Path(__file__).resolve().parent / "backups"
SIMPAN = 30


def cari_program(nama: str) -> str | None:
    """pg_dump / pg_restore: dari PATH, atau versi terbaru di folder instalasi PostgreSQL Windows."""
    ada = shutil.which(nama)
    if ada:
        return ada
    calon = glob.glob(f"C:/Program Files/PostgreSQL/*/bin/{nama}.exe")
    calon.sort(key=lambda p: int(Path(p).parent.parent.name) if Path(p).parent.parent.name.isdigit() else 0)
    return calon[-1] if calon else None


def koneksi_pg() -> tuple[list[str], dict, str]:
    """Argumen koneksi untuk pg_dump/pg_restore dari DATABASE_URL. Password lewat env, bukan argumen."""
    load_dotenv()
    url = make_url(os.environ["DATABASE_URL"])
    args = ["-h", url.host or "localhost", "-p", str(url.port or 5432), "-U", url.username or "postgres"]
    env = dict(os.environ)
    if url.password:
        env["PGPASSWORD"] = url.password
    return args, env, url.database


def rapikan(pola: str):
    lama = sorted(FOLDER.glob(pola))[:-SIMPAN]
    for f in lama:
        try:
            f.unlink()
        except OSError:
            pass


def salin_ke_awan(berkas: list[Path]):
    tujuan = os.getenv("BACKUP_COPY_DIR", "").strip()
    if not tujuan:
        return
    try:
        Path(tujuan).mkdir(parents=True, exist_ok=True)
        for f in berkas:
            shutil.copy2(f, Path(tujuan) / f.name)
        print(f"  disalin juga ke {tujuan}")
    except OSError as e:
        print(f"  ! gagal menyalin ke {tujuan}: {e}")


def backup_db(stempel: str, awalan: str = "informatika") -> Path | None:
    pg_dump = cari_program("pg_dump")
    if not pg_dump:
        print("  ! pg_dump tidak ditemukan. Pastikan PostgreSQL terpasang (C:\\Program Files\\PostgreSQL).")
        return None
    args, env, nama_db = koneksi_pg()
    hasil = FOLDER / f"{awalan}_{stempel}.dump"
    proses = subprocess.run([pg_dump, *args, "-Fc", "--no-owner", "-f", str(hasil), nama_db],
                            env=env, capture_output=True, text=True)
    if proses.returncode != 0:
        print("  ! pg_dump gagal:", proses.stderr.strip()[:300])
        hasil.unlink(missing_ok=True)
        return None
    print(f"  database   -> backups/{hasil.name} ({hasil.stat().st_size // 1024} KB)")
    return hasil


def backup_excel(stempel: str) -> Path | None:
    try:
        from app.database import SessionLocal
        from app.services.rekap import rekap_kelas, urutkan
        from app.services.excel import buku_rekap
    except Exception as e:  # noqa: BLE001 - cadangan database tetap jalan walau Excel gagal
        print("  ! rekap Excel dilewati:", e)
        return None
    db = SessionLocal()
    try:
        semua = []
        for kelas in ("VII", "VIII", "IX"):
            rekap = rekap_kelas(db, kelas)
            rekap["baris"] = urutkan(rekap["baris"], "az")
            semua.append(rekap)
        hasil = FOLDER / f"nilai_{stempel}.xlsx"
        hasil.write_bytes(buku_rekap(semua))
        print(f"  rekap nilai -> backups/{hasil.name}")
        return hasil
    except Exception as e:  # noqa: BLE001
        print("  ! rekap Excel gagal:", e)
        return None
    finally:
        db.close()


def main() -> int:
    FOLDER.mkdir(exist_ok=True)
    stempel = datetime.now().strftime("%Y%m%d_%H%M%S")
    print("Membuat cadangan ...")
    dibuat = [f for f in (backup_db(stempel), backup_excel(stempel)) if f]
    rapikan("informatika_*.dump")
    rapikan("nilai_*.xlsx")
    rapikan("pengaman_*.dump")
    salin_ke_awan(dibuat)
    if not any(f.suffix == ".dump" for f in dibuat):
        print("Cadangan database GAGAL. Web tetap bisa dipakai, tapi perbaiki sebelum ujian penting.")
        return 1
    print("Cadangan selesai.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
