# buat_kunci_cadangan.py
# Membuat pasangan kunci untuk mengenkripsi cadangan yang disalin ke Google Drive / OneDrive. Cukup SEKALI.
#
#     python buat_kunci_cadangan.py
#
# Hasil:
#   cadangan_publik.pem          tetap di folder proyek (aman; hanya bisa MENGUNCI cadangan)
#   KUNCI_PRIBADI_cadangan.pem   WAJIB dipindah ke luar laptop (flashdisk / penyimpan sandi) lalu dihapus dari laptop.
#                                Hanya ini yang bisa MEMBUKA cadangan. Tanpanya cadangan di awan tidak bisa dibaca siapa pun.
# Frasa sandi dipilih sendiri, tidak disimpan di mana pun. Catat frasa dan lokasi berkas pribadi di tempat terpisah.

import getpass
import sys
from pathlib import Path

from cadangan_aman import (BERKAS_PUBLIK, MIN_FRASA, GalatEnkripsi, buat_pasangan_kunci, dekripsi_berkas,
                           enkripsi_berkas, sidik_kunci)

BERKAS_PRIBADI = Path("KUNCI_PRIBADI_cadangan.pem")


def uji_pasangan(pem_publik: bytes, pem_pribadi: bytes, frasa: str) -> None:
    """Kunci dikunci lalu dibuka lagi: memastikan frasa yang diketik benar-benar bisa dipakai nanti."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        a, b, c = Path(d, "a"), Path(d, "a.enc"), Path(d, "c")
        a.write_bytes(b"uji-kunci-cadangan")
        enkripsi_berkas(a, b, pem_publik)
        dekripsi_berkas(b, c, pem_pribadi, frasa)
        if c.read_bytes() != a.read_bytes():
            raise GalatEnkripsi("Uji kunci gagal. Tidak ada yang disimpan.")


def main() -> int:
    if BERKAS_PUBLIK.exists():
        print(f"{BERKAS_PUBLIK.name} sudah ada. Membuat kunci baru membuat cadangan baru memakai kunci yang berbeda,")
        print("dan kunci pribadi LAMA tetap diperlukan untuk membuka cadangan lama.")
        if input("Ketik GANTI untuk tetap membuat kunci baru: ").strip() != "GANTI":
            print("Dibatalkan. Tidak ada yang diubah.")
            return 1
    if BERKAS_PRIBADI.exists():
        print(f"{BERKAS_PRIBADI.name} sudah ada di folder ini. Pindahkan atau ganti namanya dulu. Tidak ada yang diubah.")
        return 1
    print(f"Pilih frasa sandi (minimal {MIN_FRASA} karakter). Frasa ini TIDAK bisa dipulihkan bila lupa.")
    frasa = getpass.getpass("Frasa sandi: ")
    if len(frasa) < MIN_FRASA:
        print(f"Frasa minimal {MIN_FRASA} karakter. Tidak ada yang diubah.")
        return 1
    if getpass.getpass("Ulangi frasa sandi: ") != frasa:
        print("Kedua isian tidak sama. Tidak ada yang diubah.")
        return 1
    print("Membuat kunci (beberapa detik) ...")
    try:
        publik, pribadi = buat_pasangan_kunci(frasa)
        uji_pasangan(publik, pribadi, frasa)
    except GalatEnkripsi as e:
        print(e)
        return 1
    BERKAS_PUBLIK.write_bytes(publik)
    BERKAS_PRIBADI.write_bytes(pribadi)
    print()
    print(f"Selesai. Sidik jari kunci: {sidik_kunci(publik)}   (catat, untuk mengenali pasangan kunci ini)")
    print(f"  {BERKAS_PUBLIK.name}  -> tetap di sini")
    print(f"  {BERKAS_PRIBADI.name} -> PINDAHKAN ke flashdisk / penyimpan sandi, LALU HAPUS dari laptop ini.")
    print("Mulai sekarang cadangan yang disalin ke awan otomatis terenkripsi (berakhiran .enc).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
