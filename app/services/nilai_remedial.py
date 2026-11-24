# app/services/nilai_remedial.py
# Aturan saran nilai akhir bila siswa mengikuti remedial. Fungsi murni, tanpa akses database.
#
# Nilai awal = sesi pertama yang selesai (tetap yang paling atas di rekap). Nilai remedial = sesi-sesi berikutnya.
# Contoh nilai awal 67, remedial 89, KKM 75: dibatasi KKM = 75, rata-rata = 78, tertinggi = 89.

ATURAN = {
    "saran": "Hanya saran (atur sendiri di Excel)",
    "kkm": "Dibatasi KKM",
    "rata": "Rata-rata awal dan remedial",
    "tinggi": "Nilai tertinggi",
}
BAWAAN = "saran"           # ujian baru: rekap tetap memakai nilai awal, saran tampil di sampingnya
ATURAN_SARAN = "kkm"       # rumus angka saran bila guru memilih "hanya saran"


def aturan_sah(teks, bawaan=None):
    t = str(teks).strip() if teks is not None else ""
    return t if t in ATURAN else bawaan


def saran_akhir(aturan: str, awal: float, remedial, kkm: float) -> float:
    """Nilai akhir yang disarankan. Tidak pernah di bawah nilai awal."""
    if remedial is None:
        return awal
    if aturan == "rata":
        return max(awal, round((awal + remedial) / 2, 1))
    if aturan == "tinggi":
        return max(awal, remedial)
    return max(awal, min(remedial, kkm))


def nilai_dipakai(aturan: str, awal: float, remedial, kkm: float) -> float:
    """Nilai yang masuk rekap: 'saran' tidak mengubah apa pun (nilai awal), aturan lain memakai hasil saran."""
    if aturan == "saran" or remedial is None:
        return awal
    return saran_akhir(aturan, awal, remedial, kkm)
