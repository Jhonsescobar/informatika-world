# app/services/esai.py
# Penilaian otomatis soal esai berbahasa Indonesia, tanpa AI/layanan luar.
#
# Cara kerja:
# 1. Teks dinormalkan: huruf kecil, tanda baca dibuang, kata sambung ("yang", "dan", ...) dibuang.
# 2. Tiap kata diubah ke kata dasar sederhana: "disentuh" -> "sentuh", "menggunakan" -> "guna".
# 3. Kata siswa dicocokkan dengan kata kunci jawaban; salah ketik kecil tetap dianggap cocok.
# 4. Jika guru mengisi KATA KUNCI, nilai terutama dari kata kunci yang tertulis
#    (sinonim dipisah "/": "sentuh/raba"). Jika tidak, dari kata penting di kunci jawaban.
# 5. Kunci jawaban boleh lebih dari satu (satu per baris): diambil yang paling mirip.
#
# 6. Celah "tulis daftar kata kunci saja" ditutup: jawaban 3+ kata tanpa satu pun kata sambung
#    (bukan kalimat) ditandai "perlu dicek"; bila jelas hanya deretan kata kunci, nilainya dibatasi BATAS_DAFTAR. Jawaban yang jauh
#    lebih panjang dari kunci (menebar banyak kata) juga ditandai, tanpa mengurangi nilai.
#
# Hasilnya selalu bisa dikoreksi guru di halaman detail sesi.

import re
from difflib import SequenceMatcher

# Kemiripan >= BATAS_PENUH dianggap jawaban lengkap (nilai penuh)
BATAS_PENUH = 0.8
# Kemiripan < BATAS_NOL dianggap tidak menjawab (nilai 0)
BATAS_NOL = 0.25
# Nilai maksimal untuk jawaban berupa daftar kata (bukan kalimat)
BATAS_DAFTAR = 0.5

KATA_SAMBUNG = set("""
yang dan atau di ke dari pada untuk dengan dalam oleh adalah ialah merupakan yaitu yakni
itu ini tersebut sebuah suatu seorang para sang si dapat bisa dapatkan akan sudah telah
juga pun saja hanya agar supaya karena sebab jika kalau bila ketika saat waktu sehingga
maka lalu kemudian serta bahwa sebagai seperti secara antara tentang terhadap hingga
sampai tidak bukan belum ada kita kami saya kamu anda mereka dia ia nya lah kah tah
apa siapa mana bagaimana mengapa kenapa berapa sangat lebih paling cukup harus
""".split())

# (awalan, panjang minimal sisa kata) — awalan pendek butuh sisa lebih panjang agar "sentuh" tidak jadi "ntuh"
AWALAN = (("menge", 4), ("penge", 4), ("meny", 4), ("peny", 4), ("meng", 4), ("peng", 4),
          ("mem", 4), ("pem", 4), ("men", 4), ("pen", 4), ("ber", 4), ("ter", 4), ("per", 4),
          ("di", 4), ("ke", 5), ("me", 5), ("pe", 5), ("be", 5), ("te", 5), ("se", 5))
AKHIRAN = ("kannya", "annya", "kan", "an", "nya", "lah", "kah", "i")


def kata_dasar(kata: str) -> str:
    """Stemming ringan bahasa Indonesia (cukup untuk mencocokkan jawaban siswa)."""
    w = kata
    for akhir in AKHIRAN:
        # "-i" tidak dibuang setelah vokal: pakai, kedai, santai
        if akhir == "i" and len(w) > 1 and w[-2] in "aiueo":
            continue
        if w.endswith(akhir) and len(w) - len(akhir) >= 4:
            w = w[: -len(akhir)]
            break
    for awal, minimal in AWALAN:
        if w.startswith(awal) and len(w) - len(awal) >= minimal:
            sisa = w[len(awal):]
            # peluluhan: menyentuh -> sentuh, memakai -> pakai, menulis -> tulis, mengetik -> ketik
            if awal in ("meny", "peny"):
                sisa = "s" + sisa
            elif awal in ("mem", "pem") and sisa[0] in "aiueo":
                sisa = "p" + sisa
            elif awal in ("men", "pen") and sisa[0] in "aiueo":
                sisa = "t" + sisa
            elif awal in ("meng", "peng") and sisa[0] in "aiueo" and not sisa.startswith(("ung", "ena", "ana", "ali")):
                sisa = "k" + sisa
            w = sisa
            break
    return w


def kata_penting(teks: str) -> list[tuple[str, str]]:
    """Daftar (kata asli, kata dasar) tanpa kata sambung."""
    kata = re.findall(r"[a-z0-9]+", (teks or "").lower())
    return [(k, kata_dasar(k)) for k in kata if k not in KATA_SAMBUNG and len(k) > 1]


def mirip_kata(a: str, b: str) -> bool:
    """Sama, atau berbeda sedikit (salah ketik / imbuhan tersisa).
    Awalan dianggap cocok hanya bila yang pendek >= 5 huruf dan menutup >= 70% kata yang panjang
    (dulu 4 huruf: "prog" cocok dengan "program", "data" dengan "database")."""
    if a == b:
        return True
    pendek, panjang = sorted((a, b), key=len)
    if len(pendek) >= 5 and panjang.startswith(pendek) and len(pendek) / len(panjang) >= 0.7:
        return True
    return len(a) >= 4 and len(b) >= 4 and SequenceMatcher(None, a, b).ratio() >= 0.8


def ada_di(kata: tuple[str, str], daftar: list[tuple[str, str]]) -> bool:
    # cocok bila bentuk asli ATAU bentuk dasarnya mirip (melindungi dari pemotongan imbuhan yang keliru)
    return any(mirip_kata(x, y) for k in daftar for x in kata for y in k)


# Pemisah antar kata kunci: koma, titik koma, baris baru, atau titik di akhir kalimat
_PEMISAH_GRUP = re.compile(r"[,;\n]|\.(?=\s|$)")


def baca_kata_kunci(teks: str) -> list[list[list[tuple[str, str]]]]:
    """"cpu/central processing unit, ram" -> [ [[cpu], [central, processing, unit]], [[ram]] ].

    Tiap GRUP wajib ada di jawaban. Pilihan dalam grup dipisah "/" (sinonim).
    Tiap pilihan adalah FRASA: semua katanya harus muncul (dulu cukup salah satu kata,
    sehingga kata kunci berupa kalimat bisa dipenuhi oleh satu kata umum seperti "program").
    Grup kembar (misalnya "Cpu, cpu") dihitung sekali."""
    grup, sudah = [], set()
    for bagian in _PEMISAH_GRUP.split(teks or ""):
        pilihan = [kata_penting(alt) for alt in bagian.split("/")]
        pilihan = [p for p in pilihan if p]
        tanda = tuple(sorted(" ".join(k[1] for k in p) for p in pilihan))
        if pilihan and tanda not in sudah:
            sudah.add(tanda)
            grup.append(pilihan)
    return grup


def label_grup(g) -> str:
    return " / ".join(" ".join(k[0] for k in frasa) for frasa in g)


def skor_frasa(frasa, siswa) -> float:
    return sum(1 for k in frasa if ada_di(k, siswa)) / len(frasa)


# Bagian jawaban yang harus relevan dengan kunci. Di bawah ini nilai diturunkan bertahap,
# sehingga teks panjang di luar topik yang kebetulan memuat 1-2 kata kunci tidak mendapat poin.
BATAS_RELEVAN = 0.2


def nilai_esai(jawaban: str, kunci: str, kata_kunci: str = "") -> dict:
    """Bandingkan jawaban siswa dengan kunci guru.

    Kembalian: kemiripan (0-1), persen nilai (0-1), kata yang cocok & yang kurang, tanda perlu dicek.
    """
    siswa = kata_penting(jawaban)
    kosong = {"kemiripan": 0.0, "persen": 0.0, "cocok": [], "kurang": [], "perlu_cek": "", "dibatasi": False, "relevan": 0.0}
    if not siswa:
        return kosong
    semua_kata = re.findall(r"[a-z0-9]+", (jawaban or "").lower())
    # kalimat wajar hampir selalu memuat kata sambung (yang, untuk, dengan, adalah, ...)
    daftar_kata = len(semua_kata) >= 3 and not any(k in KATA_SAMBUNG for k in semua_kata)
    unik = list(dict.fromkeys(siswa))                          # kata siswa tanpa pengulangan

    grup = baca_kata_kunci(kata_kunci)
    baris_kunci = [b for b in (kunci or "").splitlines() if b.strip()] or [""]
    kata_grup = [k for g in grup for frasa in g for k in frasa]
    terbaik = None
    for baris in baris_kunci:
        kunci_kata = list(dict.fromkeys(kata_penting(baris)))   # tanpa duplikat
        if grup:
            # tiap grup: frasa terbaik di antara sinonimnya; frasa sebagian = nilai sebagian
            skor = [max(skor_frasa(f, siswa) for f in g) for g in grup]
            cocok = [label_grup(g) for g, n in zip(grup, skor) if n >= 1]
            kurang = [label_grup(g) for g, n in zip(grup, skor) if n < 1]
            cakupan = sum(skor) / len(grup)
        elif kunci_kata:
            cocok = [k[0] for k in kunci_kata if ada_di(k, siswa)]
            kurang = [k[0] for k in kunci_kata if not ada_di(k, siswa)]
            cakupan = len(cocok) / len(kunci_kata)
        else:
            cocok, kurang, cakupan = [], [], 0.0
        if cakupan == 0:
            # tidak satu pun kata kunci muncul: kemiripan susunan kalimat tidak boleh memberi poin
            kemiripan, urutan = 0.0, 0.0
        else:
            urutan = (SequenceMatcher(None, " ".join(k[1] for k in kunci_kata), " ".join(k[1] for k in siswa)).ratio()
                      if kunci_kata else 0.0)
            kemiripan = 0.8 * cakupan + 0.2 * urutan
        # relevansi: bagian kata siswa yang memang ada di kunci / kata kunci
        acuan = kata_grup + kunci_kata
        relevan = sum(1 for k in unik if ada_di(k, acuan)) / len(unik) if acuan else 0.0
        faktor = min(1.0, relevan / BATAS_RELEVAN)
        kemiripan = round(kemiripan * faktor, 3)
        if terbaik is None or kemiripan > terbaik["kemiripan"]:
            terbaik = {"kemiripan": kemiripan, "cocok": cocok, "kurang": kurang, "relevan": round(relevan, 2), "faktor": faktor}

    k = terbaik["kemiripan"]
    if k >= BATAS_PENUH:
        persen = 1.0
    elif k < BATAS_NOL:
        persen = 0.0
    else:
        persen = round(k / BATAS_PENUH, 2)

    terbaik["perlu_cek"], terbaik["dibatasi"] = "", False
    panjang_kunci = max((len(kata_penting(b)) for b in (kunci or "").splitlines()), default=0)
    if daftar_kata:
        terbaik["perlu_cek"] = "Jawaban berupa daftar kata, bukan kalimat"
        # dibatasi hanya jika jelas daftar: dipisah koma, atau hampir semua katanya kata kunci/kunci
        acuan = kata_grup or [k for b in (kunci or "").splitlines() for k in kata_penting(b)]
        isi_kunci = sum(1 for k in siswa if ada_di(k, acuan)) / len(siswa)
        if ("," in (jawaban or "") or isi_kunci >= 0.9) and persen > BATAS_DAFTAR:
            persen, terbaik["dibatasi"] = BATAS_DAFTAR, True
    elif terbaik["faktor"] < 1:
        terbaik["perlu_cek"] = "Sebagian besar jawaban di luar topik"
    elif panjang_kunci and len(siswa) > max(25, 4 * panjang_kunci):
        terbaik["perlu_cek"] = "Jawaban jauh lebih panjang dari kunci"
    terbaik.pop("faktor", None)
    terbaik["persen"] = persen
    return terbaik
