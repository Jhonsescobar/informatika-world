# pulihkan_db.py
# Memulihkan database dari cadangan di folder backups/ (buatan backup_db.py / ONLINE.bat).
#
#     python pulihkan_db.py
#
# PERHATIAN: isi database sekarang DIGANTI dengan isi cadangan yang dipilih.
# Sebelum memulihkan, script ini otomatis membuat cadangan keadaan sekarang dulu (backups/pengaman_*.dump),
# jadi kalau salah pilih masih bisa dikembalikan. Matikan web (ONLINE.bat) sebelum menjalankan.

import subprocess
import sys

from backup_db import FOLDER, backup_db, cari_program, koneksi_pg
from datetime import datetime


def main() -> int:
    daftar = sorted(FOLDER.glob("informatika_*.dump"), reverse=True)[:15]
    if not daftar:
        print("Belum ada cadangan di folder backups/.")
        return 1
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
        return 1
    berkas = daftar[int(pilih) - 1]
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
