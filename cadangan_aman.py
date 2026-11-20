# cadangan_aman.py
# Enkripsi cadangan sebelum disalin ke folder awan (Google Drive / OneDrive).
#
# Cara kerja (kunci publik): laptop hanya menyimpan KUNCI PUBLIK (cadangan_publik.pem). Dengan itu laptop
# bisa mengunci cadangan, tapi TIDAK bisa membukanya. Yang bisa membuka hanya pemegang KUNCI PRIBADI
# (disimpan di luar laptop, dilindungi frasa sandi). Jadi walau laptop atau akun Drive dibobol, isi cadangan aman.
#
# Format berkas .enc:  IWENC1\n | panjang kunci terbungkus (2 byte) | kunci AES terbungkus RSA-OAEP | nonce 12 byte | AES-256-GCM
# Setiap berkas memakai kunci AES acak sendiri. GCM juga mendeteksi berkas yang diubah/rusak.

import getpass
import hashlib
import os
import secrets
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

AWAL = b"IWENC1\n"
BATAS_UKURAN = 500 * 1024 * 1024        # seluruh berkas dibaca ke memori; cadangan sekolah jauh di bawah ini
FOLDER_PROYEK = Path(__file__).resolve().parent
BERKAS_PUBLIK = FOLDER_PROYEK / "cadangan_publik.pem"
MIN_FRASA = 10


class GalatEnkripsi(Exception):
    """Pesan sudah berbahasa Indonesia dan aman ditampilkan apa adanya."""


def _oaep():
    return padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)


def buat_pasangan_kunci(frasa: str) -> tuple[bytes, bytes]:
    """(publik_pem, pribadi_pem_terenkripsi_frasa)."""
    if len(frasa) < MIN_FRASA:
        raise GalatEnkripsi(f"Frasa sandi minimal {MIN_FRASA} karakter.")
    pribadi = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    pem_pribadi = pribadi.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                        serialization.BestAvailableEncryption(frasa.encode()))
    pem_publik = pribadi.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    return pem_publik, pem_pribadi


def sidik_kunci(pem_publik: bytes) -> str:
    """Sidik jari singkat untuk dicatat, supaya tahu pasangan kunci mana yang dipakai."""
    der = serialization.load_pem_public_key(pem_publik).public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    h = hashlib.sha256(der).hexdigest()[:16].upper()
    return "-".join(h[i:i + 4] for i in range(0, 16, 4))


def lokasi_kunci_publik() -> Path:
    return Path(os.getenv("BACKUP_PUBLIC_KEY", "").strip() or BERKAS_PUBLIK)


def muat_kunci_publik() -> bytes | None:
    """Isi kunci publik, atau None bila belum dibuat."""
    p = lokasi_kunci_publik()
    return p.read_bytes() if p.is_file() else None


def enkripsi_berkas(sumber: Path, tujuan: Path, pem_publik: bytes) -> None:
    """Tulis sumber terenkripsi ke tujuan. Ditulis ke berkas sementara lalu diganti sekaligus,
    jadi tidak pernah ada berkas .enc setengah jadi."""
    if sumber.stat().st_size > BATAS_UKURAN:
        raise GalatEnkripsi(f"{sumber.name} terlalu besar untuk dienkripsi ({sumber.stat().st_size // 2**20} MB).")
    try:
        publik = serialization.load_pem_public_key(pem_publik)
    except ValueError as e:
        raise GalatEnkripsi("Kunci publik rusak. Buat ulang dengan: python buat_kunci_cadangan.py") from e
    kunci_aes, nonce = AESGCM.generate_key(256), secrets.token_bytes(12)
    terbungkus = publik.encrypt(kunci_aes, _oaep())
    isi = AESGCM(kunci_aes).encrypt(nonce, sumber.read_bytes(), AWAL)
    sementara = tujuan.with_name(tujuan.name + ".tmp")
    try:
        sementara.write_bytes(AWAL + len(terbungkus).to_bytes(2, "big") + terbungkus + nonce + isi)
        os.replace(sementara, tujuan)
    finally:
        sementara.unlink(missing_ok=True)


def dekripsi_berkas(sumber: Path, tujuan: Path, pem_pribadi: bytes, frasa: str) -> None:
    data = sumber.read_bytes()
    if not data.startswith(AWAL) or len(data) < len(AWAL) + 2 + 12 + 16:
        raise GalatEnkripsi(f"{sumber.name} bukan cadangan terenkripsi buatan aplikasi ini.")
    try:
        pribadi = serialization.load_pem_private_key(pem_pribadi, password=frasa.encode())
    except (ValueError, TypeError) as e:
        raise GalatEnkripsi("Frasa sandi salah, atau berkas kunci pribadi rusak.") from e
    n = int.from_bytes(data[len(AWAL):len(AWAL) + 2], "big")
    a = len(AWAL) + 2
    terbungkus, nonce, isi = data[a:a + n], data[a + n:a + n + 12], data[a + n + 12:]
    try:
        kunci_aes = pribadi.decrypt(terbungkus, _oaep())
        asli = AESGCM(kunci_aes).decrypt(nonce, isi, AWAL)
    except (ValueError, InvalidTag) as e:
        raise GalatEnkripsi("Cadangan tidak bisa dibuka: kunci pribadi bukan pasangannya, atau berkas rusak/diubah.") from e
    sementara = tujuan.with_name(tujuan.name + ".tmp")
    try:
        sementara.write_bytes(asli)
        os.replace(sementara, tujuan)
    finally:
        sementara.unlink(missing_ok=True)


def dekripsi_interaktif(sumber: Path, tujuan: Path) -> None:
    """Minta lokasi kunci pribadi dan frasa sandi di layar (frasa tidak tampil, tidak disimpan)."""
    lokasi = input("Lokasi berkas kunci pribadi (.pem): ").strip().strip('"')
    if not lokasi or not Path(lokasi).is_file():
        raise GalatEnkripsi("Berkas kunci pribadi tidak ditemukan.")
    frasa = getpass.getpass("Frasa sandi kunci (tidak tampil saat diketik): ")
    dekripsi_berkas(sumber, tujuan, Path(lokasi).read_bytes(), frasa)
