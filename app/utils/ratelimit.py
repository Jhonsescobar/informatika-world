# app/utils/ratelimit.py
# Membatasi percobaan login yang gagal supaya PIN 4 angka tidak bisa ditebak berulang-ulang.
# Disimpan di memori server: hilang saat server restart (cukup untuk 1 proses uvicorn).

import time
from threading import Lock

MAKS_GAGAL = 5            # percobaan salah yang diizinkan
JENDELA_DETIK = 10 * 60   # dihitung dalam 10 menit terakhir

_gagal: dict[str, list[float]] = {}
_kunci = Lock()


def _bersihkan(kunci: str, sekarang: float) -> list[float]:
    daftar = [t for t in _gagal.get(kunci, []) if sekarang - t < JENDELA_DETIK]
    _gagal[kunci] = daftar
    return daftar


def sisa_kunci_detik(kunci: str) -> int:
    """0 jika boleh mencoba; selain itu jumlah detik sampai boleh mencoba lagi."""
    with _kunci:
        sekarang = time.time()
        daftar = _bersihkan(kunci, sekarang)
        if len(daftar) < MAKS_GAGAL:
            return 0
        return int(JENDELA_DETIK - (sekarang - daftar[0])) + 1


def catat_gagal(kunci: str) -> None:
    with _kunci:
        sekarang = time.time()
        _bersihkan(kunci, sekarang).append(sekarang)


def reset(kunci: str) -> None:
    with _kunci:
        _gagal.pop(kunci, None)
