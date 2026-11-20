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
# Salinan di awan SELALU dienkripsi (berakhiran .enc) dengan kunci publik: jalankan sekali
#   python buat_kunci_cadangan.py
# Tanpa kunci itu, salinan ke awan dilewati (data siswa tidak pernah dikirim tanpa enkripsi).
# Membuka salinan terenkripsi: python pulihkan_db.py "<berkas>.dump.enc"   (butuh kunci pribadi + frasa sandi)

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


def rapikan_awan(folder: Path):
    """Simpan SIMPAN salinan terenkripsi terbaru per jenis; hanya menyentuh berkas buatan aplikasi ini (*.enc)."""
    for pola in ("informatika_*.dump.enc", "nilai_*.xlsx.enc"):
        for f in sorted(folder.glob(pola))[:-SIMPAN]:
            try:
                f.unlink()
            except OSError:
                pass


def sisa_tanpa_enkripsi(folder: Path) -> list[Path]:
    """Salinan lama (sebelum ada enkripsi) yang masih tergeletak polos di folder awan."""
    return sorted(f for pola in ("informatika_*.dump", "nilai_*.xlsx", "pengaman_*.dump") for f in folder.glob(pola))


def salin_ke_awan(berkas: list[Path]) -> bool:
    """Salin terenkripsi ke BACKUP_COPY_DIR. True bila tidak ada yang perlu disalin atau semuanya berhasil."""
    tujuan = os.getenv("BACKUP_COPY_DIR", "").strip()
    if not tujuan:
        return True
    try:
        from cadangan_aman import GalatEnkripsi, enkripsi_berkas, muat_kunci_publik
    except ImportError:   # cadangan lokal tetap jalan; salinan awan menunggu paketnya terpasang
        print("  ! Salinan ke awan DILEWATI: paket 'cryptography' belum terpasang. Jalankan: pip install -r requirements.txt")
        return False
    kunci = muat_kunci_publik()
    if kunci is None:
        print("  ! Salinan ke awan DILEWATI: belum ada kunci enkripsi (data siswa tidak dikirim tanpa enkripsi).")
        print("    Buat sekali dengan: python buat_kunci_cadangan.py")
        return False
    folder = Path(tujuan)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        for f in berkas:
            enkripsi_berkas(f, folder / (f.name + ".enc"), kunci)
        rapikan_awan(folder)
        print(f"  disalin terenkripsi ke {tujuan}")
        polos = sisa_tanpa_enkripsi(folder)
        if polos:
            print(f"  ! {len(polos)} salinan LAMA di folder itu belum terenkripsi (mis. {polos[0].name}). Hapus manual dari Drive.")
        return True
    except (OSError, GalatEnkripsi) as e:
        print(f"  ! gagal menyalin ke {tujuan}: {e}")
        return False


def dump_terbaca(dump: Path) -> bool:
    """Pemeriksaan cepat: daftar isi dump bisa dibaca pg_restore (berkas terpotong/rusak langsung ketahuan)."""
    pg_restore = cari_program("pg_restore")
    if not pg_restore:
        return True   # tidak bisa memeriksa; jangan menggagalkan cadangan hanya karena itu
    return subprocess.run([pg_restore, "--list", str(dump)], capture_output=True).returncode == 0


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
    if not dump_terbaca(hasil):
        print("  ! cadangan database tidak terbaca (rusak). Dibuang.")
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
    awan_ok = salin_ke_awan(dibuat)
    if not any(f.suffix == ".dump" for f in dibuat):
        print("Cadangan database GAGAL. Web tetap bisa dipakai, tapi perbaiki sebelum ujian penting.")
        return 1
    print("Cadangan selesai." + ("" if awan_ok else " (salinan ke awan belum berhasil, lihat pesan di atas)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
