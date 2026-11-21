# app/services/watermark.py
# Watermark nama + jam di layar ujian/materi. Dipakai supaya foto layar dari HP lain bisa dilacak ke pemilik akun.
# Kekuatan dipilih guru per ujian. Hasil uji: 7% hilang pada foto berkontras tinggi, 12% mulai pecah,
# 18% masih terbaca dan tetap nyaman bagi siswa. Karena itu bawaan 16%.

from datetime import datetime

TINGKAT = {0: "Mati", 8: "Samar", 16: "Sedang", 22: "Jelas"}
BAWAAN = 16
BAWAAN_MATERI = 8                      # materi tidak punya pengaturan; cukup tipis supaya nyaman dibaca lama


def persen_sah(teks, bawaan=None):
    """Angka persen yang diizinkan, atau `bawaan` bila isian kosong/tidak dikenal."""
    try:
        n = int(str(teks).strip())
    except (TypeError, ValueError):
        return bawaan
    return n if n in TINGKAT else bawaan


def jam_watermark() -> dict:
    """Konteks jam untuk templat: teks awal + jam server (epoch ms, selisih zona menit) agar jam di layar
    terus berjalan dari jam server, bukan jam HP siswa yang bisa diubah."""
    sekarang = datetime.now().astimezone()
    return {
        "sekarang": sekarang.strftime("%d/%m/%Y %H:%M"),
        "wm_epoch": int(sekarang.timestamp() * 1000),
        "wm_offset": int(sekarang.utcoffset().total_seconds() // 60),
    }
