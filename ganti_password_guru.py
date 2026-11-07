# ganti_password_guru.py
# Mengganti password akun guru. Password diketik saat script berjalan (tidak terlihat
# di layar dan tidak disimpan di file mana pun).
#
#     python ganti_password_guru.py

import getpass
import sys

from app.database import SessionLocal
from app.models.user import User
from app.utils.security import hash_password, verify_password

MIN_PANJANG = 8


def main():
    db = SessionLocal()
    try:
        guru = db.query(User).filter(User.role == "teacher").order_by(User.id).all()
        if not guru:
            print("Belum ada akun guru di database.")
            return 1
        print("Akun guru:")
        for i, g in enumerate(guru, 1):
            print(f"  {i}. {g.email}")
        pilih = input(f"Pilih nomor akun [1]: ").strip() or "1"
        if not pilih.isdigit() or not 1 <= int(pilih) <= len(guru):
            print("Nomor tidak valid. Tidak ada yang diubah.")
            return 1
        akun = guru[int(pilih) - 1]

        baru = getpass.getpass("Password baru (tidak tampil saat diketik): ")
        if len(baru) < MIN_PANJANG:
            print(f"Password minimal {MIN_PANJANG} karakter. Tidak ada yang diubah.")
            return 1
        if baru.lower() in ("guru123", "password", "12345678", "informatika"):
            print("Password terlalu mudah ditebak. Tidak ada yang diubah.")
            return 1
        if getpass.getpass("Ulangi password baru: ") != baru:
            print("Kedua password tidak sama. Tidak ada yang diubah.")
            return 1

        akun.hashed_password = hash_password(baru)
        db.commit()
        if not verify_password(baru, akun.hashed_password):
            print("Gagal memverifikasi password baru.")
            return 1
        print(f"Password {akun.email} berhasil diganti. Login berikutnya pakai password baru.")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
