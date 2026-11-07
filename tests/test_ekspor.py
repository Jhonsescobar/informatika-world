# tests/test_ekspor.py
# Ekspor Excel: bisa dibuka, angkanya sama dengan rekap, dan aman dari rumus jahat.

import io

import openpyxl

from app.models.student import Student
from tests.data_uji import buat_ujian, kerjakan

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def buka(r):
    assert r.status_code == 200 and r.headers["content-type"] == XLSX
    return openpyxl.load_workbook(io.BytesIO(r.content))


def semua_nilai(ws):
    return [c.value for row in ws.iter_rows() for c in row if c.value is not None]


def test_ekspor_rekap_kelas(guru, db, data, masuk_siswa):
    a = buat_ujian(db, data, "A")
    kerjakan(masuk_siswa(data["siswa"]["Ani"]), a, data, 3)
    r = guru.get("/teacher/grades/class/VII/export")
    assert 'filename="rekap_nilai_kelas_VII_' in r.headers["content-disposition"]
    ws = buka(r).active
    isi = semua_nilai(ws)
    assert "Ani" in isi and 75 in isi or 75.0 in isi


def test_ekspor_semua_kelas_tiga_lembar(guru):
    wb = buka(guru.get("/teacher/grades/export"))
    assert wb.sheetnames == ["Kelas VII", "Kelas VIII", "Kelas IX"]


def test_ekspor_hasil_ujian(guru, db, data, masuk_siswa):
    a = buat_ujian(db, data, "Ujian: Bab 1 / \"Jaringan\"")
    kerjakan(masuk_siswa(data["siswa"]["Budi"]), a, data, 4)
    r = guru.get(f"/teacher/exams/{a}/results/export")
    nama = r.headers["content-disposition"]
    assert '"' not in nama.split('filename="', 1)[1][:-1] and "/" not in nama   # nama file disaring
    isi = semua_nilai(buka(r).active)
    assert "Budi" in isi


def test_nama_berawalan_rumus_tidak_dijalankan_excel(guru, db, data, masuk_siswa):
    s = db.get(Student, data["siswa"]["Ani"])
    s.name = '=HYPERLINK("http://contoh.invalid","klik")'
    db.commit()
    a = buat_ujian(db, data, "A")
    kerjakan(masuk_siswa(data["siswa"]["Ani"]), a, data, 2)
    for url in ("/teacher/grades/class/VII/export", f"/teacher/exams/{a}/results/export"):
        isi = semua_nilai(buka(guru.get(url)).active)
        assert not any(isinstance(v, str) and v.startswith("=") for v in isi), url
        assert any(isinstance(v, str) and v.startswith("'=HYPERLINK") for v in isi), url


def test_ekspor_wajib_login(client):
    assert client.get("/teacher/grades/export").status_code in (303, 307)
    assert client.get("/teacher/exams/1/results/export").status_code in (303, 307)
