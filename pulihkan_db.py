# pulihkan_db.py
# Memulihkan database dari cadangan di folder backups/ (buatan backup_db.py / ONLINE.bat).
#
#     python pulihkan_db.py                       pilih dari cadangan di folder backups/
#     python pulihkan_db.py "<berkas>.dump"       pulihkan dari berkas tertentu
#     python pulihkan_db.py "<berkas>.dump.enc"   salinan terenkripsi dari Drive (butuh kunci pribadi + frasa sandi)
#
# PERHATIAN: isi database sekarang DIGANTI dengan isi cadangan yang dipilih.
# Sebelum memulihkan, script ini otomatis membuat cadangan keadaan sekarang dulu (backups/pengaman_*.dump),
# jadi kalau salah pilih masih bisa dikembalikan. Matikan web (ONLINE.bat) sebelum menjalankan.

import subprocess
import sys
import tempfile
from pathlib import Path

from backup_db import FOLDER, backup_db, cari_program, koneksi_pg
from cadangan_aman import GalatEnkripsi, dekripsi_interaktif
from datetime import datetime


def berkas_dari_argumen(arg: str, folder_sementara: Path) -> Path | None:
    """Berkas cadangan yang bisa dipakai pg_restore. Yang .enc dibuka dulu ke folder sementara."""
    sumber = Path(arg.strip('"'))
    if not sumber.is_file():
        print(f"Berkas tidak ditemukan: {sumber}")
        return None
    if sumber.suffix != ".enc":
        return sumber
    hasil = folder_sementara / sumber.name[: -len(".enc")]
    try:
        dekripsi_interaktif(sumber, hasil)
    except GalatEnkripsi as e:
        print(e)
        return None
    return hasil


def pilih_dari_folder() -> Path | None:
    daftar = sorted(FOLDER.glob("informatika_*.dump"), reverse=True)[:15]
    if not daftar:
        print("Belum ada cadangan di folder backups/.")
        return None
    print("Cadangan tersedia (terbaru di atas):")
    for i, f in enumerate(daftar, 1):
        try:
            label = datetime.strptime(f.stem.split("_", 1)[1], "%Y%m%d_%H%M%S").strftime("%d-%m-%Y %H:%M:%S")
        except ValueError:
            label = f.name
        print(f"  {i:>2}. {label}   ({f.stat().st_size // 1024} KB)")
    pilih = input("Pilih nomor cadangan: ").strip()
    if not pilih.isdigit() or not 1 <= int(pilih) <= len(daftar):
        print("Nomor tidak valid. Tidak ada yang diubah.")
        return None
    return daftar[int(pilih) - 1]


def main() -> int:
    with tempfile.TemporaryDirectory() as sementara:     # hasil dekripsi tidak tertinggal di disk
        berkas = berkas_dari_argumen(sys.argv[1], Path(sementara)) if len(sys.argv) > 1 else pilih_dari_folder()
        if berkas is None:
            return 1
        return pulihkan(berkas)


def pulihkan(berkas: Path) -> int:
    print(f"\nIsi database sekarang akan DIGANTI dengan {berkas.name}.")
    if input('Ketik PULIHKAN untuk melanjutkan: ').strip() != "PULIHKAN":
        print("Dibatalkan. Tidak ada yang diubah.")
        return 1

    pg_restore = cari_program("pg_restore")
    if not pg_restore:
        print("pg_restore tidak ditemukan. Pastikan PostgreSQL terpasang.")
        return 1
    print("\nMenyimpan keadaan sekarang dulu (jaga-jaga) ...")
    if not backup_db(datetime.now().strftime("%Y%m%d_%H%M%S"), awalan="pengaman"):
        print("Cadangan pengaman gagal dibuat, pemulihan dibatalkan.")
        return 1
    args, env, nama_db = koneksi_pg()
    proses = subprocess.run([pg_restore, *args, "-d", nama_db, "--clean", "--if-exists", "--no-owner",
                             "--single-transaction", str(berkas)], env=env, capture_output=True, text=True)
    if proses.returncode != 0:
        print("Pemulihan GAGAL, database tidak berubah:\n", proses.stderr.strip()[:500])
        return 1
    print("Database berhasil dipulihkan. Jalankan lagi ONLINE.bat.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
