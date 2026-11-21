# tests/test_watermark.py
# Watermark nama + jam di layar siswa: kekuatan dipilih guru per ujian, jam berjalan dari jam server.

import re

from app.models.aksi_guru import AksiGuru
from app.models.exam import Exam
from app.services.watermark import BAWAAN, TINGKAT, jam_watermark, persen_sah
from tests.data_uji import buat_ujian
from tests.test_acak import mulai


def halaman(c, exam_id):
    return c.get(f"/student/exam/take/{mulai(c, exam_id)}").text


def test_pilihan_dan_bawaan():
    assert persen_sah("16") == 16 and persen_sah(" 22 ") == 22 and persen_sah("0") == 0
    assert persen_sah("50") is None and persen_sah("abc") is None and persen_sah(None) is None
    assert persen_sah("50", BAWAAN) == BAWAAN
    assert BAWAAN in TINGKAT and BAWAAN >= 12, "bawaan harus cukup kuat: 7% hilang pada foto berkontras tinggi"


def test_jam_server_untuk_templat():
    j = jam_watermark()
    assert re.fullmatch(r"\d\d/\d\d/\d{4} \d\d:\d\d", j["sekarang"])
    assert j["wm_epoch"] > 1_700_000_000_000 and -840 <= j["wm_offset"] <= 840


def test_ujian_lama_dan_baru_memakai_bawaan(db, data):
    e = buat_ujian(db, data, "Tanpa isian")
    assert db.get(Exam, e).watermark_persen == BAWAAN


def test_layar_siswa_memuat_watermark_sesuai_pilihan(db, data, masuk_siswa):
    e = buat_ujian(db, data, "Jelas", watermark_persen=22)
    html = halaman(masuk_siswa(data["siswa"]["Ani"]), e)
    m = re.search(r'<div class="watermark"[^>]*style="opacity:0\.22"[^>]*data-epoch="(\d+)" data-offset="-?\d+"', html)
    assert m, "watermark 22% tidak tampil"
    assert html.count("<time>") == 60 and "Ani" in html.split('class="watermark"')[1]


def test_watermark_mati_tidak_dirender(db, data, masuk_siswa):
    e = buat_ujian(db, data, "Mati", watermark_persen=0)
    assert 'class="watermark"' not in halaman(masuk_siswa(data["siswa"]["Ani"]), e)


def test_guru_ubah_kekuatan_dan_tercatat(guru, db, data):
    guru.post("/teacher/kelas", data={"kelas": "VII"})
    e = buat_ujian(db, data, "Ubah")
    assert guru.post(f"/teacher/exams/{e}/watermark", data={"persen": "8"}).status_code == 303
    db.expire_all()
    assert db.get(Exam, e).watermark_persen == 8
    baris = db.query(AksiGuru).filter(AksiGuru.aksi == "Ubah watermark").all()
    assert len(baris) == 1 and "Sedang ke Samar" in baris[0].rincian
    guru.post(f"/teacher/exams/{e}/watermark", data={"persen": "8"})          # sama: tidak dicatat ulang
    assert db.query(AksiGuru).filter(AksiGuru.aksi == "Ubah watermark").count() == 1


def test_isian_tak_dikenal_ditolak(guru, db, data):
    e = buat_ujian(db, data, "Tolak")
    for salah in ("50", "-5", "abc", ""):
        guru.post(f"/teacher/exams/{e}/watermark", data={"persen": salah})
    db.expire_all()
    assert db.get(Exam, e).watermark_persen == BAWAAN


def test_siswa_tidak_bisa_mengubah(db, data, masuk_siswa):
    e = buat_ujian(db, data, "Siswa")
    masuk_siswa(data["siswa"]["Ani"]).post(f"/teacher/exams/{e}/watermark", data={"persen": "0"})
    db.expire_all()
    assert db.get(Exam, e).watermark_persen == BAWAAN


def test_form_dan_daftar_ujian_punya_pilihan(guru, db, data):
    guru.post("/teacher/kelas", data={"kelas": "VII"})
    buat_ujian(db, data, "Daftar")
    html = guru.get("/teacher/exams").text
    assert 'name="watermark_persen"' in html and 'name="persen"' in html
    assert all(f">{nama}</option>" in html for nama in TINGKAT.values())


def test_buat_ujian_menyimpan_pilihan_watermark(guru, db, data):
    guru.post("/teacher/kelas", data={"kelas": "VII"})
    guru.post("/teacher/exams/create", data={"title": "Baru", "bank_id": str(data["bank"]), "class_target": "VII",
                                             "duration_minutes": "20", "watermark_persen": "22"})
    db.expire_all()
    assert db.query(Exam).filter(Exam.title == "Baru").one().watermark_persen == 22

