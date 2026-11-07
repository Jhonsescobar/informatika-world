# app/services/excel.py
# Ekspor nilai ke file Excel (.xlsx) untuk rapor dan arsip.

from io import BytesIO
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.services.rekap import KKM

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
    ws["A2"] = f"Tahun ajaran {tahun} · KKM {KKM} · diunduh {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    if rekap["pakai_bobot"]:
        ws["A3"] = "Nilai akhir = Σ(nilai komponen × bobot) / Σ bobot. Nilai ujian = persen tertinggi (termasuk remedial)."
    else:
        ws["A3"] = "Belum ada bobot komponen: nilai akhir = rata-rata semua ujian."
    kepala = ["No", "Nama", "Rombel", "NIPD"]
    kolom_k = [k for k in rekap["komponen"] if rekap["per_komponen"][k.id]]
    kepala += [f"{k.name} ({k.weight}%)" for k in kolom_k]
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
        if isinstance(sel.value, (int, float)) and sel.value < KKM:
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


def buku_ujian(exam, rows) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Hasil ujian"
    ws["A1"] = f"Hasil ujian: {aman(exam.title)} (Kelas {exam.class_target})"
    ws["A1"].font = JUDUL
    ws["A2"] = f"Diunduh {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    status = {"completed": "Selesai", "submitted": "Selesai", "expired": "Waktu habis", "active": "Mengerjakan"}
    data = []
    for i, r in enumerate(rows, 1):
        s = r["sesi"]
        data.append([i, r["siswa"].name, r.get("rombel") or "", "Remedial " + str(r["ke"] - 1) if r["ke"] > 1 else "Utama",
                     status.get(s.status, s.status), r["persen"], s.score, r["maks"], r["pelanggaran"],
                     s.submitted_at.astimezone().strftime("%d/%m/%Y %H:%M") if s.submitted_at else ""])
    _tabel(ws, 4, ["No", "Nama", "Rombel", "Percobaan", "Status", "Nilai (%)", "Skor", "Skor maks", "Pelanggaran", "Dikirim"],
           data, [5, 34, 10, 12, 13, 10, 8, 10, 12, 18])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
