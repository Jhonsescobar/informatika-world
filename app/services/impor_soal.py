# app/services/impor_soal.py
# Impor soal dari teks JSON hasil AI (ChatGPT, Gemini, Claude, ...).
#
# Alur: guru menempel teks -> rapikan() memperbaiki kesalahan format yang umum ->
# periksa() mengecek setiap soal dan melaporkan kesalahan PER NOMOR -> guru melihat pratinjau ->
# simpan hanya bila tidak ada kesalahan. Server selalu memeriksa ulang saat menyimpan.
#
# Format (lihat juga CONTOH di bawah):
#   {"soal": [ {"tipe": "pg", "pertanyaan": "...", "kode": "...", "opsi": ["..", ".."], "jawaban": "B", "poin": 1},
#              {"tipe": "esai", "pertanyaan": "...", "kunci": "...", "kata_kunci": "a/b, c", "poin": 5} ]}
# Daftar soal tanpa {"soal": ...} juga diterima.

import json
import re

MAKS_SOAL = 100
MAKS_TEKS = 4000
MAKS_OPSI_TEKS = 500
HURUF = "ABCDE"

CONTOH = {
    "topik": "Algoritma dan Pemrograman Python",
    "soal": [
        {"tipe": "pg", "pertanyaan": "Urutan langkah yang logis untuk menyelesaikan masalah disebut ...",
         "opsi": ["Algoritma", "Variabel", "Perangkat keras", "Sistem operasi"], "jawaban": "A", "poin": 1},
        {"tipe": "pg", "pertanyaan": "Apa keluaran program berikut?",
         "kode": "angka = 7\nif angka % 2 == 0:\n    print(\"genap\")\nelse:\n    print(\"ganjil\")",
         "opsi": ["genap", "ganjil", "7", "Error"], "jawaban": "B", "poin": 2},
        {"tipe": "esai", "pertanyaan": "Jelaskan fungsi perulangan `for` dalam Python!",
         "kunci": "Perulangan for digunakan untuk mengulang perintah sebanyak jumlah tertentu atau untuk setiap item dalam daftar",
         "kata_kunci": "ulang/perulangan, jumlah/banyak/setiap", "poin": 5},
    ],
}


def rapikan(teks: str) -> tuple[str, list[str]]:
    """Memperbaiki kesalahan format yang sering muncul dari AI. Mengembalikan (teks baru, daftar perbaikan)."""
    perbaikan = []
    t = (teks or "").strip().lstrip("﻿")
    # pagar kode ```json ... ```
    pagar = re.search(r"```(?:json|JSON)?\s*\n?(.*?)```", t, re.S)
    if pagar:
        t = pagar.group(1).strip()
        perbaikan.append("Pagar kode ``` dibuang")
    # kalimat pembuka/penutup dari AI di luar JSON
    awal = min([i for i in (t.find("{"), t.find("[")) if i >= 0], default=-1)
    akhir = max(t.rfind("}"), t.rfind("]"))
    if awal > 0 or (akhir >= 0 and akhir < len(t) - 1):
        if awal >= 0 and akhir > awal:
            t = t[awal:akhir + 1]
            perbaikan.append("Teks di luar JSON dibuang")
    # kutip melengkung -> kutip biasa (di luar string: struktur; di dalam string: jadi \")
    if re.search("[“”‘’]", t):
        t = _kutip_lurus(t)
        perbaikan.append("Kutip melengkung diganti kutip biasa")
    # koma sisa sebelum } atau ]
    baru = re.sub(r",(\s*[}\]])", r"\1", t)
    if baru != t:
        t = baru
        perbaikan.append("Koma sisa sebelum } atau ] dibuang")
    # kutip ganda di dalam teks yang tidak di-escape, misalnya kode print("Halo") di isian "kode",
    # atau baris baru mentah di dalam teks. Hanya dicoba bila JSON memang belum bisa dibaca.
    try:
        json.loads(t)
    except json.JSONDecodeError:
        baru, n_kutip, n_baris = _rapikan_isi_teks(t)
        if baru != t:
            try:
                json.loads(baru)
                t = baru
                if n_kutip:
                    perbaikan.append(f'{n_kutip} tanda kutip di dalam teks (misalnya print("...")) di-escape')
                if n_baris:
                    perbaikan.append("Baris baru di dalam teks diubah menjadi \\n")
            except json.JSONDecodeError:
                pass        # tidak berhasil: laporkan galat asli, bukan hasil tebakan
    return t, perbaikan


def _lewati_spasi(t: str, i: int) -> int:
    while i < len(t) and t[i] in " \t\r\n":
        i += 1
    return i


def _kutip_penutup(t: str, i: int) -> bool:
    """Apakah tanda " di posisi i menutup teks JSON? Ya bila sesudahnya struktur JSON: : , } ] atau akhir.
    Untuk koma, dicek lebih jauh: sesudah koma harus ada } ] atau teks JSON berikutnya yang diikuti : , } ]
    (supaya print("a", "b") di dalam kode tidak dianggap penutup)."""
    j = _lewati_spasi(t, i + 1)
    if j >= len(t) or t[j] in ":}]":
        return True
    if t[j] != ",":
        return False
    k = _lewati_spasi(t, j + 1)
    if k >= len(t) or t[k] in "}]":
        return True
    if t[k] != '"':
        return k < len(t) and (t[k].isdigit() or t[k] in "-{[tfn")   # angka / objek / true / false / null
    m = k + 1
    while m < len(t) and t[m] != '"':
        m += 2 if t[m] == "\\" else 1
    n = _lewati_spasi(t, m + 1)
    return n >= len(t) or t[n] in ":,}]"


def _rapikan_isi_teks(t: str) -> tuple[str, int, int]:
    hasil, dalam, i, n_kutip, n_baris = [], False, 0, 0, 0
    while i < len(t):
        c = t[i]
        if dalam and c == "\\" and i + 1 < len(t):
            hasil.append(t[i:i + 2]); i += 2; continue
        if c == '"':
            if not dalam:
                dalam = True; hasil.append(c)
            elif _kutip_penutup(t, i):
                dalam = False; hasil.append(c)
            else:
                hasil.append('\\"'); n_kutip += 1
        elif dalam and c in "\n\r\t":
            if c == "\n":
                hasil.append("\\n"); n_baris += 1
            elif c == "\t":
                hasil.append("\\t")
        else:
            hasil.append(c)
        i += 1
    return "".join(hasil), n_kutip, n_baris


def _kutip_lurus(t: str) -> str:
    """Kutip melengkung pembuka/penutup string -> ". Kutip melengkung di dalam isi string -> \\" atau '."""
    hasil, dalam, i = [], False, 0
    while i < len(t):
        c = t[i]
        if c == "\\" and dalam and i + 1 < len(t):
            # \“ (kutip escape yang ikut dilengkungkan Word/WhatsApp) -> \"
            hasil.append('\\"' if t[i + 1] in "\u201c\u201d" else t[i:i + 2]); i += 2; continue
        if c == '"':
            dalam = not dalam
            hasil.append(c)
        elif c in "“”":
            if not dalam:
                dalam = True; hasil.append('"')
            else:
                # penutup string bila setelahnya (abaikan spasi) ada : , } ]
                sisa = t[i + 1:].lstrip()
                if not sisa or sisa[0] in ":,}]":
                    dalam = False; hasil.append('"')
                else:
                    hasil.append('\\"')
        elif c in "‘’":
            hasil.append("'")
        else:
            hasil.append(c)
        i += 1
    return "".join(hasil)


def _teks(v) -> str:
    return v.strip() if isinstance(v, str) else ("" if v is None else str(v).strip())


def periksa(teks: str) -> dict:
    """Hasil: {"soal": [...siap simpan...], "galat": ["Soal 3: ..."], "perbaikan": [...], "topik": str}."""
    t, perbaikan = rapikan(teks)
    hasil = {"soal": [], "galat": [], "perbaikan": perbaikan, "topik": ""}
    if not t:
        hasil["galat"].append("Teks kosong. Tempel hasil dari AI dulu.")
        return hasil
    try:
        data = json.loads(t)
    except json.JSONDecodeError as e:
        baris = t.splitlines()[e.lineno - 1] if 0 < e.lineno <= len(t.splitlines()) else ""
        hasil["galat"].append(f"Format JSON rusak di baris {e.lineno}, kolom {e.colno}: {_pesan_json(e.msg)}. "
                              f"Potongan: {baris.strip()[:80]}")
        return hasil

    if isinstance(data, dict):
        hasil["topik"] = _teks(data.get("topik"))[:150]
        daftar = data.get("soal", data.get("questions"))
    else:
        daftar = data
    if not isinstance(daftar, list) or not daftar:
        hasil["galat"].append('Tidak menemukan daftar soal. Bentuknya harus {"soal": [ ... ]}.')
        return hasil
    if len(daftar) > MAKS_SOAL:
        hasil["galat"].append(f"Terlalu banyak: {len(daftar)} soal. Maksimal {MAKS_SOAL} per impor; bagi menjadi beberapa kali.")
        return hasil

    for n, s in enumerate(daftar, 1):
        galat = []
        if not isinstance(s, dict):
            hasil["galat"].append(f"Soal {n}: bukan objek {{...}}.")
            continue
        tipe = _teks(s.get("tipe") or s.get("type") or "pg").lower()
        tipe = {"pilihan ganda": "pg", "pilgan": "pg", "mc": "pg", "essay": "esai", "uraian": "esai"}.get(tipe, tipe)
        pertanyaan = _teks(s.get("pertanyaan") or s.get("soal") or s.get("question"))
        kode = s.get("kode") or s.get("code") or ""
        kode = kode.strip("\n") if isinstance(kode, str) else ""
        try:
            poin = int(s.get("poin", s.get("points", 1)) or 1)
        except (TypeError, ValueError):
            poin, _ = 1, galat.append("poin harus angka")
        if tipe not in ("pg", "esai"):
            galat.append(f'tipe "{tipe}" tidak dikenal (pakai "pg" atau "esai")')
        if not pertanyaan:
            galat.append("pertanyaan kosong")
        if len(pertanyaan) > MAKS_TEKS or len(kode) > MAKS_TEKS:
            galat.append(f"pertanyaan/kode lebih dari {MAKS_TEKS} karakter")
        if not 1 <= poin <= 100:
            galat.append("poin harus 1–100")
        item = {"tipe": tipe, "pertanyaan": pertanyaan, "kode": kode, "poin": poin}

        if tipe == "pg":
            opsi = s.get("opsi") or s.get("options") or []
            if isinstance(opsi, dict):                       # {"A": "...", "B": "..."}
                opsi = [opsi[k] for k in sorted(opsi)]
            opsi = [_teks(o) for o in opsi] if isinstance(opsi, list) else []
            opsi = [re.sub(r"^[A-Ea-e][.)]\s+", "", o) for o in opsi]   # "A. Algoritma" -> "Algoritma"
            if not 2 <= len(opsi) <= 5:
                galat.append(f"opsi harus 2–5, ada {len(opsi)}")
            if any(not o for o in opsi):
                galat.append("ada opsi kosong")
            if any(len(o) > MAKS_OPSI_TEKS for o in opsi):
                galat.append(f"opsi lebih dari {MAKS_OPSI_TEKS} karakter")
            if len({o.lower() for o in opsi}) != len(opsi):
                galat.append("ada opsi kembar")
            benar = _jawaban(s.get("jawaban", s.get("answer")), opsi)
            if benar is None:
                galat.append(f'jawaban "{_teks(s.get("jawaban", s.get("answer")))}" tidak cocok dengan opsi '
                             f'(pakai huruf {HURUF[:max(len(opsi), 2)]})')
            item.update(opsi=opsi, benar=benar)
        elif tipe == "esai":
            kunci = s.get("kunci") or s.get("kunci_jawaban") or s.get("answer_key") or ""
            kunci = "\n".join(_teks(k) for k in kunci) if isinstance(kunci, list) else _teks(kunci)
            kata_kunci = s.get("kata_kunci") or s.get("keywords") or ""
            kata_kunci = ", ".join(_teks(k) for k in kata_kunci) if isinstance(kata_kunci, list) else _teks(kata_kunci)
            if not kunci:
                galat.append("kunci jawaban esai kosong")
            if len(kunci) > MAKS_TEKS or len(kata_kunci) > 500:
                galat.append("kunci/kata kunci terlalu panjang")
            item.update(kunci=kunci, kata_kunci=kata_kunci)

        if galat:
            hasil["galat"].append(f"Soal {n}: " + "; ".join(galat) + ".")
        item["nomor"] = n
        item["galat"] = galat
        hasil["soal"].append(item)
    return hasil


def _jawaban(j, opsi: list[str]):
    """'B' / 'b' / 'B. teks' / 2 (nomor 1-based) / teks opsi -> indeks 0-based, atau None."""
    if isinstance(j, bool):
        return None
    if isinstance(j, int):
        return j - 1 if 1 <= j <= len(opsi) else None
    t = _teks(j)
    m = re.match(r"^([A-Ea-e])(?:[.)]|\s|$)", t)
    if m and len(t) <= 3 or (m and t[1:2] in ".)"):
        i = HURUF.index(m.group(1).upper())
        return i if i < len(opsi) else None
    for i, o in enumerate(opsi):
        if t.lower() == o.lower():
            return i
    return None


def _pesan_json(msg: str) -> str:
    return {
        "Expecting ',' delimiter": "kurang tanda koma",
        "Expecting ':' delimiter": "kurang titik dua",
        "Expecting value": "nilai kosong atau ada karakter aneh",
        "Expecting property name enclosed in double quotes": "nama isian harus dalam kutip ganda",
        "Unterminated string starting at": "kutip tidak ditutup",
        "Extra data": "ada teks tambahan setelah JSON",
        "Invalid control character at": "ada baris baru di dalam teks; ganti dengan \\n",
    }.get(msg, msg)


def gabung_kode(pertanyaan: str, kode: str) -> str:
    """Kode Python disimpan di teks soal sebagai blok ``` agar ditampilkan rapi (lihat services/teks.py)."""
    return pertanyaan if not kode else f"{pertanyaan}\n\n```python\n{kode}\n```"


def prompt_ai(topik: str, kelas: str, jumlah_pg: int, jumlah_esai: int, kesulitan: str) -> str:
    """Prompt siap salin untuk AI. Ditampilkan juga di halaman (dibangun ulang oleh JS saat isian diganti)."""
    contoh = json.dumps(CONTOH, ensure_ascii=False, indent=2)
    return PROMPT.format(topik=topik, kelas=kelas, pg=jumlah_pg, esai=jumlah_esai, kesulitan=kesulitan, contoh=contoh)


PROMPT = """Buatkan soal untuk siswa SMP kelas {kelas}, topik "{topik}".
Jumlah: {pg} soal pilihan ganda dan {esai} soal esai. Tingkat kesulitan: {kesulitan}.

Aturan:
- Bahasa Indonesia yang baku, singkat, dan sesuai usia SMP.
- Pilihan ganda: 4 opsi, tepat satu jawaban benar, opsi pengecoh masuk akal, jangan pakai "semua benar"/"semua salah".
- Sebar letak jawaban benar (A, B, C, D) secara acak dan seimbang.
- Bila soal memakai potongan kode Python, taruh kodenya di isian "kode" (bukan di "pertanyaan"), indentasi 4 spasi,
  baris baru ditulis \\n, dan teks di dalam kode memakai kutip tunggal: print('Halo') (bukan print("Halo")).
- Esai: isi "kunci" dengan jawaban lengkap satu kalimat, dan "kata_kunci" dengan kata atau frasa pendek yang WAJIB ada,
  dipisah koma, sinonim dipisah garis miring (contoh: "cpu/central processing unit, ram, motherboard").
  Jangan menulis kalimat sebagai kata kunci.
- "poin": pilihan ganda 1, esai 5 (boleh diubah sesuai bobot).

Jawab HANYA dengan JSON valid, tanpa penjelasan, persis mengikuti bentuk contoh ini:
{contoh}"""
