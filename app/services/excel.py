# app/services/excel.py
# Ekspor nilai ke file Excel (.xlsx) untuk rapor dan arsip.

from io import BytesIO
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.services.rekap import KKM_DEFAULT

JUDUL = Font(bold=True, size=14)
KEPALA = Font(bold=True, color="FFFFFF")
ISI_KEPALA = PatternFill("solid", fgColor="0F766E")
MERAH = Font(color="B91C1C")


def aman(nilai):
    """Cegah 'formula injection': teks yang diawali = + - @ dibaca Excel sebagai rumus."""
    if isinstance(nilai, str) and nilai[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + nilai
    return nilai


def _tabel(ws, baris_awal, kepala, data, lebar=None):
    for i, k in enumerate(kepala, 1):
        sel = ws.cell(row=baris_awal, column=i, value=k)
        sel.font, sel.fill = KEPALA, ISI_KEPALA
        sel.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for r, baris in enumerate(data, baris_awal + 1):
        for c, v in enumerate(baris, 1):
            ws.cell(row=r, column=c, value=aman(v))
    for i, w in enumerate(lebar or [], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = ws.cell(row=baris_awal + 1, column=3)


def lembar_rekap(wb, rekap, judul_lembar=None):
    ws = wb.create_sheet(title=(judul_lembar or f"Kelas {rekap['kelas']}")[:31])
    tahun = rekap["tahun"].year_name if rekap["tahun"] else "-"
    ws["A1"] = f"Rekap Nilai Informatika Kelas {rekap['kelas']}"
    ws["A1"].font = JUDUL
    ws["A2"] = f"Tahun ajaran {tahun} · KKM akhir {rekap.get('kkm_akhir', KKM_DEFAULT)} · diunduh {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    if rekap["pakai_bobot"]:
        ws["A3"] = "Nilai akhir = Σ(nilai komponen × bobot) / Σ bobot. Nilai ujian = persen tertinggi (termasuk remedial)."
    else:
        ws["A3"] = "Belum ada bobot komponen: nilai akhir = rata-rata semua ujian."
    kepala = ["No", "Nama", "Rombel", "NIPD"]
    kolom_k = [k for k in rekap["komponen"] if rekap["per_komponen"][k.id]]
    kepala += [f"{k.name} ({k.weight}%, KKM {rekap['kkm_komponen'][k.id]})" for k in kolom_k]
    kepala += [f"Ujian: {e.title}" for e in rekap["ujian"]]
    kepala += ["Nilai akhir", "Keterangan", "Ujian belum dikerjakan"]
    data = []
    for i, r in enumerate(rekap["baris"], 1):
        data.append([i, r["siswa"].name, r["rombel"], r["siswa"].nipd or ""]
                    + [r["komponen"][k.id] for k in kolom_k]
                    + [r["ujian"][e.id] if r["ujian"][e.id] is not None else "belum" for e in rekap["ujian"]]
                    + [r["akhir"], "Tuntas" if r["tuntas"] else "Belum tuntas", r["belum"]])
    _tabel(ws, 5, kepala, data, [5, 34, 10, 12] + [14] * (len(kepala) - 4))
    kolom_akhir = len(kepala) - 2
    for r in range(6, 6 + len(data)):
        sel = ws.cell(row=r, column=kolom_akhir)
        if isinstance(sel.value, (int, float)) and sel.value < rekap.get("kkm_akhir", KKM_DEFAULT):
            sel.font = MERAH
    # nilai komponen diwarnai sesuai KKM komponennya masing-masing
    for j, k in enumerate(kolom_k):
        for r in range(6, 6 + len(data)):
            sel = ws.cell(row=r, column=5 + j)
            if isinstance(sel.value, (int, float)) and sel.value < rekap["kkm_komponen"][k.id]:
                sel.font = MERAH
    return ws


def buku_rekap(daftar_rekap) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    for rekap in daftar_rekap:
        lembar_rekap(wb, rekap)
    if not wb.sheetnames:
        wb.create_sheet("Kosong")["A1"] = "Belum ada data."
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _nama_lembar(nama, terpakai):
    """Nama lembar Excel: maks 31 huruf, tanpa karakter terlarang, unik."""
    bersih = "".join("-" if c in '[]:*?/\\' else c for c in (nama or "Tanpa rombel")).strip()[:31] or "Tanpa rombel"
    asal, n = bersih, 2
    while bersih.lower() in terpakai:
        bersih = f"{asal[:28]} {n}"
        n += 1
    terpakai.add(bersih.lower())
    return bersih


def _kunci_alami(teks):
    """VIII.2 sebelum VIII.10; 'Tanpa rombel' selalu terakhir."""
    import re
    return (teks == "", [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", teks)])


def buku_ujian(exam, rows, kkm=None) -> bytes:
    """Satu lembar per rombel (hasil kelas dipisah), ditambah lembar Ringkasan di depan."""
    wb = Workbook()
    ringkasan = wb.active
    ringkasan.title = "Ringkasan"
    status = {"completed": "Selesai", "submitted": "Selesai", "expired": "Waktu habis", "active": "Mengerjakan"}
    per_rombel = {}
    for r in rows:
        per_rombel.setdefault(r.get("rombel") or "", []).append(r)
    terpakai = {"ringkasan"}
    ringkasan_data = []
    for rombel in sorted(per_rombel, key=_kunci_alami):
        daftar = sorted(per_rombel[rombel], key=lambda r: (r["siswa"].name.lower(), r["ke"]))
        ws = wb.create_sheet(_nama_lembar(rombel, terpakai))
        ws["A1"] = f"Hasil ujian: {aman(exam.title)} · Rombel {rombel or '(tanpa rombel)'}"
        ws["A1"].font = JUDUL
        ws["A2"] = f"Kelas {exam.class_target} · diunduh {datetime.now().strftime('%d/%m/%Y %H:%M')}" + (f" · KKM {kkm}" if kkm is not None else "")
        data, ada = [], {}
        for i, r in enumerate(daftar, 1):
            sesi = r["sesi"]
            data.append([i, r["siswa"].name, "Remedial " + str(r["ke"] - 1) if r["ke"] > 1 else "Utama",
                         status.get(sesi.status, sesi.status), r["persen"], sesi.score, r["maks"], r["pelanggaran"],
                         sesi.submitted_at.astimezone().strftime("%d/%m/%Y %H:%M") if sesi.submitted_at else ""])
            if r["persen"] is not None:
                ada[r["siswa"].id] = max(ada.get(r["siswa"].id, -1), r["persen"])
        _tabel(ws, 4, ["No", "Nama", "Percobaan", "Status", "Nilai (%)", "Skor", "Skor maks", "Pelanggaran", "Dikirim"],
               data, [5, 34, 12, 13, 10, 8, 10, 12, 18])
        if kkm is not None:
            for baris in range(5, 5 + len(data)):
                sel = ws.cell(row=baris, column=5)
                if isinstance(sel.value, (int, float)) and sel.value < kkm:
                    sel.font = MERAH
        nilai = list(ada.values())
        siswa_unik = {r["siswa"].id for r in daftar}
        ringkasan_data.append([rombel or "(tanpa rombel)", len(siswa_unik), len(nilai),
                               round(sum(nilai) / len(nilai), 1) if nilai else "", max(nilai) if nilai else "", min(nilai) if nilai else "",
                               sum(1 for v in nilai if kkm is not None and v >= kkm) if kkm is not None else ""])
    ringkasan["A1"] = f"Ringkasan hasil: {aman(exam.title)} (Kelas {exam.class_target})"
    ringkasan["A1"].font = JUDUL
    ringkasan["A2"] = f"Diunduh {datetime.now().strftime('%d/%m/%Y %H:%M')}. Nilai tiap siswa = persen tertinggi dari semua percobaannya."
    _tabel(ringkasan, 4, ["Rombel", "Siswa", "Sudah mengerjakan", "Rata-rata (%)", "Tertinggi", "Terendah", "Tuntas"],
           ringkasan_data or [["Belum ada hasil", 0, 0, "", "", "", ""]], [20, 9, 20, 14, 11, 11, 9])
    ringkasan.freeze_panes = None
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def buku_remedial(exam, data: dict) -> bytes:
    """Daftar siswa yang perlu remedial (nilai tertinggi di bawah batas) dan yang belum mengerjakan."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Perlu remedial"
    ws["A1"] = f"Perlu remedial: {exam.title}"
    ws["A1"].font = JUDUL
    ws["A2"] = f"Kelas {exam.class_target} · nilai tertinggi di bawah {data['batas']}% · diunduh {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    status = {"approved": "Izin sudah diberi", "pending": "Menunggu persetujuan", None: "Belum diberi izin"}
    baris = [[i, x["siswa"].name, x["rombel"], x["persen"], status[x["status"]]] for i, x in enumerate(data["perlu"], 1)]
    _tabel(ws, 4, ["No", "Nama", "Rombel", "Nilai tertinggi (%)", "Status remedial"], baris, [5, 34, 10, 20, 24])
    ws2 = wb.create_sheet("Belum mengerjakan")
    ws2["A1"] = f"Belum mengerjakan: {exam.title}"
    ws2["A1"].font = JUDUL
    _tabel(ws2, 3, ["No", "Nama", "Rombel"], [[i, x["siswa"].name, x["rombel"]] for i, x in enumerate(data["belum"], 1)],
           [5, 34, 10])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()

