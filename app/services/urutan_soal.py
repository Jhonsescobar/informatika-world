# app/services/urutan_soal.py
# Menyusun paket soal untuk SATU siswa. Aturan utama: soal diacak hanya di antara jenisnya sendiri.
# Pola jenis per nomor mengikuti bank (mis. nomor 1-15 PG, 16-20 esai) dan tidak berpindah, jadi
# esai tidak naik ke nomor depan dan semua siswa mengerjakan jenis yang sama di nomor yang sama.

import random
from collections import OrderedDict


def jenis_soal(tipe) -> str:
    """Hanya dua jenis: esai, atau pilihan ganda (termasuk soal lama yang jenisnya kosong)."""
    return "esai" if tipe == "esai" else "pg"


def kuota_per_jenis(ukuran: "OrderedDict[str, int]", jumlah: int) -> dict:
    """Berapa soal per jenis bila hanya `jumlah` soal yang diambil: sebanding dengan isi bank,
    sama untuk semua siswa, dan setiap jenis tetap kebagian minimal 1 selama jumlah mencukupi."""
    total = sum(ukuran.values())
    mentah = {j: jumlah * n / total for j, n in ukuran.items()}
    kuota = {j: min(int(m), ukuran[j]) for j, m in mentah.items()}
    urut = sorted(ukuran, key=lambda j: (-(mentah[j] - int(mentah[j])), list(ukuran).index(j)))
    sisa = jumlah - sum(kuota.values())
    while sisa > 0:
        for j in urut:
            if sisa > 0 and kuota[j] < ukuran[j]:
                kuota[j] += 1
                sisa -= 1
    if jumlah >= len(ukuran):
        for j in ukuran:
            if kuota[j] == 0:
                donor = max((x for x in kuota if kuota[x] > 1), key=lambda x: kuota[x], default=None)
                if donor:
                    kuota[donor] -= 1
                    kuota[j] = 1
    return kuota


def susun_soal(soal: list, jumlah, acak: bool, rng=random) -> list[int]:
    """soal: [(id, jenis)] dalam urutan bank. jumlah: batas soal per siswa (kosong = semua).
    Hasil: id soal sesuai urutan tampil siswa itu."""
    soal = sorted(soal, key=lambda s: s[0])
    per_jenis: "OrderedDict[str, list]" = OrderedDict()
    for qid, jenis in soal:
        per_jenis.setdefault(jenis_soal(jenis), []).append(qid)
    pola = [jenis_soal(j) for _, j in soal]
    if jumlah and jumlah < len(soal):
        kuota = kuota_per_jenis(OrderedDict((j, len(v)) for j, v in per_jenis.items()), jumlah)
        dipakai = {j: 0 for j in per_jenis}
        pola_baru = []
        for j in pola:                      # tiap jenis mempertahankan nomor-nomor awalnya
            if dipakai[j] < kuota[j]:
                dipakai[j] += 1
                pola_baru.append(j)
        pola = pola_baru
        pilihan = {j: rng.sample(v, kuota[j]) for j, v in per_jenis.items()}
    else:
        pilihan = {j: list(v) for j, v in per_jenis.items()}
    for j, v in pilihan.items():
        if acak:
            rng.shuffle(v)
        else:
            v.sort()
    antrean = {j: iter(v) for j, v in pilihan.items()}
    return [next(antrean[j]) for j in pola]
