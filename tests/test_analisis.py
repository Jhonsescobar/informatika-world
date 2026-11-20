# Uji analisis butir soal, daftar remedial, grafik perkembangan siswa, dan rapor.

from datetime import datetime, timezone

from sqlalchemy import func

from app.models.exam import Exam, ExamAnswer, ExamSession, RemedialRequest
from app.models.question import Question, QuestionOption
from app.services.analisis import LABEL, analisis_butir, tentukan_label
from app.services.perkembangan import arah, bentuk_grafik, pesan_semangat, riwayat_siswa
from app.services.remedial import daftar_remedial
from tests.data_uji import buat_ujian, kerjakan


# ---------- label butir (murni, tanpa database) ----------

def test_label_butir_prioritas():
    assert tentukan_label(3, 0.5, 0.5, 0, False) == "kurang"                 # terlalu sedikit siswa
    assert tentukan_label(20, 0.5, -0.3, 0.2, False) == "periksa"            # pembeda negatif mengalahkan yang lain
    assert tentukan_label(20, 0.2, 0.3, 0.5, True) == "menjebak"             # pengecoh dominan, walau sulit
    assert tentukan_label(20, 0.2, 0.3, 0.1, False) == "sulit"
    assert tentukan_label(20, 0.95, 0.1, 0, False) == "mudah"
    assert tentukan_label(20, 0.6, 0.05, 0.1, False) == "lemah"
    assert tentukan_label(20, 0.6, 0.4, 0.1, False) == "baik"
    assert tentukan_label(20, 0.6, None, 0.1, False) == "baik"               # esai: tanpa pembeda
    assert set(LABEL) >= {"periksa", "menjebak", "sulit", "mudah", "lemah", "baik", "kurang"}


def test_arah_tren():
    assert arah(None) == "baru" and arah(10) == "naik" and arah(-10) == "turun" and arah(1.5) == "tetap"


# ---------- analisis butir dari data nyata ----------

def test_analisis_butir_hanya_menghitung_ujian_itu(db, data, masuk_siswa):
    a = buat_ujian(db, data, "A")
    b = buat_ujian(db, data, "B")                       # bank yang sama; jawabannya tidak boleh bercampur
    kerjakan(masuk_siswa(data["siswa"]["Ani"]), a, data, 4)
    kerjakan(masuk_siswa(data["siswa"]["Budi"]), b, data, 0)
    hasil = analisis_butir(db, db.get(Exam, a))
    assert hasil["siswa"] == 1 and hasil["rata"] == 100.0
    assert all(x["p"] == 100 for x in hasil["butir"])
    assert analisis_butir(db, db.get(Exam, b))["rata"] == 0.0


def test_analisis_butir_tanpa_sesi_kosong(db, data):
    assert analisis_butir(db, db.get(Exam, buat_ujian(db, data, "Kosong"))) is None


def test_halaman_analisis_guru(guru, db, data, masuk_siswa):
    a = buat_ujian(db, data, "A")
    kerjakan(masuk_siswa(data["siswa"]["Ani"]), a, data, 3)
    html = guru.get(f"/teacher/exams/{a}/analytics").text
    assert "Analisis butir soal" in html and "menjawab benar" in html
    assert guru.get("/teacher/exams/99999/analytics", follow_redirects=False).status_code == 303
    belum = buat_ujian(db, data, "Belum")
    assert "Belum ada data" in guru.get(f"/teacher/exams/{belum}/analytics").text


# ---------- remedial ----------

def test_daftar_remedial_dan_beri_sekaligus(guru, db, data, masuk_siswa):
    a = buat_ujian(db, data, "A")
    kerjakan(masuk_siswa(data["siswa"]["Ani"]), a, data, 1)      # 25%: perlu
    kerjakan(masuk_siswa(data["siswa"]["Budi"]), a, data, 4)     # 100%: aman
    daftar = daftar_remedial(db, db.get(Exam, a))
    assert [x["siswa"].name for x in daftar["perlu"]] == ["Ani"]
    assert daftar["perlu"][0]["status"] is None
    assert "Perlu remedial" in guru.get(f"/teacher/exams/{a}/results").text
    r = guru.post(f"/teacher/exams/{a}/remedial-semua", follow_redirects=False)
    assert "pesan=remedial&n=1" in r.headers["location"]
    guru.post(f"/teacher/exams/{a}/remedial-semua")              # diulang: tidak membuat data ganda
    db.expire_all()
    assert db.query(RemedialRequest).filter(RemedialRequest.exam_id == a, RemedialRequest.status == "approved").count() == 1
    assert daftar_remedial(db, db.get(Exam, a))["perlu"][0]["status"] == "approved"


def test_unduh_daftar_remedial(guru, db, data, masuk_siswa):
    from io import BytesIO
    from openpyxl import load_workbook
    a = buat_ujian(db, data, "A")
    kerjakan(masuk_siswa(data["siswa"]["Ani"]), a, data, 1)
    r = guru.get(f"/teacher/exams/{a}/remedial/export")
    assert r.status_code == 200 and "spreadsheetml" in r.headers["content-type"]
    wb = load_workbook(BytesIO(r.content))
    assert wb.sheetnames == ["Perlu remedial", "Belum mengerjakan"]
    assert wb["Perlu remedial"]["B5"].value == "Ani"


# ---------- perkembangan siswa ----------

def test_riwayat_siswa_naik_dan_grafik(db, data, masuk_siswa):
    ani = masuk_siswa(data["siswa"]["Ani"])
    a, b = buat_ujian(db, data, "Awal"), buat_ujian(db, data, "Lanjut")
    kerjakan(ani, a, data, 1)       # 25
    kerjakan(ani, b, data, 3)       # 75
    r = riwayat_siswa(db, data["siswa"]["Ani"])
    assert [t["judul"] for t in r["titik"]] == ["Awal", "Lanjut"]
    assert r["tren"] == "naik" and r["selisih"] == 50.0 and r["rata"] == 50.0 and r["terbaik"] == 75.0
    g = bentuk_grafik(r["titik"])
    assert len(g["titik"]) == 2 and g["garis"].startswith("M") and g["area"].endswith("Z")
    assert all(g["atas"] <= t["y"] <= g["bawah"] for t in g["titik"])


def test_grafik_satu_titik_dan_pesan():
    g = bentuk_grafik([{"nilai": 80, "kkm": 75, "tuntas": True, "judul": "A", "rombel": None}])
    assert g["garis"] == "" and g["area"] == "" and len(g["titik"]) == 1
    assert "Naik 10" in pesan_semangat("naik", 10, True)[0]
    assert "Turun" in pesan_semangat("turun", -5, False)[0]


def test_halaman_progres_siswa_dan_guru(guru, db, data, masuk_siswa):
    ani = masuk_siswa(data["siswa"]["Ani"])
    assert "Belum ada nilai" in ani.get("/student/progress").text
    kerjakan(ani, buat_ujian(db, data, "Awal"), data, 1)
    kerjakan(ani, buat_ujian(db, data, "Lanjut"), data, 4)
    html = ani.get("/student/progress").text
    assert "<svg" in html and "Naik 75 poin" in html
    assert "Nilai ujian terakhirmu" in ani.get("/student/dashboard").text
    tampil_guru = guru.get(f"/teacher/students/{data['siswa']['Ani']}/progress").text
    assert "<svg" in tampil_guru and "Rata-rata rombel" in tampil_guru
    assert guru.get("/teacher/students/99999/progress", follow_redirects=False).status_code == 303


def test_siswa_tidak_melihat_progres_orang_lain(masuk_siswa, data):
    # halaman siswa hanya memakai id dari token, tidak ada parameter id yang bisa diganti
    ani = masuk_siswa(data["siswa"]["Ani"])
    assert ani.get(f"/student/progress?student_id={data['siswa']['Budi']}").status_code == 200
    assert "Budi" not in ani.get(f"/student/progress?student_id={data['siswa']['Budi']}").text


# ---------- rapor ----------

def test_rapor_cetak(guru, db, data, masuk_siswa):
    kerjakan(masuk_siswa(data["siswa"]["Ani"]), buat_ujian(db, data, "UH 1"), data, 4)
    html = guru.get("/teacher/grades/class/VII/rapor").text
    assert "RAPOR INFORMATIKA" in html and "Ani" in html and "UH 1" in html
    satu = guru.get(f"/teacher/grades/class/VII/rapor?siswa={data['siswa']['Ani']}").text
    assert satu.count('class="halaman"') == 1 and "Budi" not in satu
    assert guru.get("/teacher/grades/class/XII/rapor", follow_redirects=False).status_code == 303
    assert "<script>alert" not in guru.get("/teacher/grades/class/VII/rapor?rombel=<script>alert(1)</script>").text


# ---------- hasil ujian dikelompokkan per rombel ----------

def test_hasil_ujian_dipisah_per_rombel(guru, db, data, masuk_siswa):
    a = buat_ujian(db, data, "UH rombel")
    kerjakan(masuk_siswa(data["siswa"]["Ani"]), a, data, 4)      # VII.1
    kerjakan(masuk_siswa(data["siswa"]["Dodi"]), a, data, 1)     # VII.2
    html = guru.get(f"/teacher/exams/{a}/results").text
    bagian = html.split('aria-label="Hasil rombel')[1:]
    assert len(bagian) == 2 and bagian[0].startswith(" VII.1") and bagian[1].startswith(" VII.2")
    assert "Ani" in bagian[0] and "Dodi" not in bagian[0]
    assert "Dodi" in bagian[1] and "Ani" not in bagian[1]
    assert 'href="#rombel-VII-2"' in html and 'id="rombel-VII-2"' in html
    assert "Tuntas 1/1" in bagian[0] and "Tuntas 0/1" in bagian[1]


def test_panel_rombel_bisa_dilipat_dan_rombel_pertama_terbuka(guru, db, data, masuk_siswa):
    a = buat_ujian(db, data, "UH lipat")
    kerjakan(masuk_siswa(data["siswa"]["Ani"]), a, data, 4)
    kerjakan(masuk_siswa(data["siswa"]["Dodi"]), a, data, 1)
    html = guru.get(f"/teacher/exams/{a}/results").text
    assert html.count('<details class="panel panel-tight rombel"') == 2
    assert 'id="rombel-VII-1" aria-label="Hasil rombel VII.1" open' in html
    assert 'id="rombel-VII-2" aria-label="Hasil rombel VII.2">' in html           # rombel kedua tertutup
    assert 'data-lipat="buka"' in html and 'data-lipat="tutup"' in html
    satu = guru.get(f"/teacher/exams/{buat_ujian(db, data, 'Kosong')}/results").text
    assert "Belum ada yang mengerjakan" in satu and 'data-lipat="buka"' not in satu
