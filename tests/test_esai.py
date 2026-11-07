# tests/test_esai.py
# Penilaian esai otomatis (tanpa AI) dan celah-celahnya.

import pytest

from app.models.exam import ExamAnswer
from app.services.esai import kata_dasar, nilai_esai
from tests.data_uji import buat_ujian

KUNCI = "Layar sentuh adalah layar yang dapat menerima input dari sentuhan jari"
KATA_KUNCI = "layar, sentuh/raba, input/masukan, jari"


@pytest.mark.parametrize("kata,dasar", [("disentuh", "sentuh"), ("menyentuh", "sentuh"), ("menggunakan", "guna"),
                                        ("memakai", "pakai"), ("menulis", "tulis"), ("sentuh", "sentuh")])
def test_kata_dasar(kata, dasar):
    assert kata_dasar(kata) == dasar


def test_kalimat_lengkap_nilai_penuh():
    r = nilai_esai("Layar sentuh yaitu layar yang menerima masukan dari sentuhan jari", KUNCI, KATA_KUNCI)
    assert r["persen"] == 1.0 and not r["perlu_cek"]


def test_salah_ketik_kecil_tetap_cocok():
    r = nilai_esai("layar sentuh adalah layar yang menrima inptu dari sentuhan jarii", KUNCI, KATA_KUNCI)
    assert r["persen"] == 1.0


def test_jawaban_sebagian_dapat_sebagian():
    r = nilai_esai("layar yang disentuh", KUNCI, KATA_KUNCI)
    assert 0 < r["persen"] < 1 and "jari" in r["kurang"]


def test_jawaban_salah_atau_kosong_nol():
    assert nilai_esai("monitor untuk menonton", KUNCI, KATA_KUNCI)["persen"] == 0
    assert nilai_esai("", KUNCI, KATA_KUNCI)["persen"] == 0
    assert nilai_esai("yang dan di ke", KUNCI, KATA_KUNCI)["persen"] == 0


@pytest.mark.parametrize("jawaban", ["layar sentuh jari input", "layar, sentuh, input, jari", "jari input layar sentuh raba masukan"])
def test_daftar_kata_kunci_dibatasi_dan_ditandai(jawaban):
    r = nilai_esai(jawaban, KUNCI, KATA_KUNCI)
    assert r["persen"] <= 0.5 and r["dibatasi"] and r["perlu_cek"]


def test_kalimat_pendek_tanpa_kata_sambung_hanya_ditandai():
    r = nilai_esai("layar sentuh menerima masukan jari", KUNCI, KATA_KUNCI)
    assert r["persen"] == 1.0 and r["perlu_cek"] and not r["dibatasi"]


def test_menebar_banyak_kata_ditandai():
    tebar = "layar sentuh input jari " + " ".join(f"kata{i} yang" for i in range(40))
    assert nilai_esai(tebar, KUNCI, KATA_KUNCI)["perlu_cek"]


def test_beberapa_kunci_diambil_yang_paling_mirip():
    kunci = "Router menghubungkan jaringan\nAlat penghubung antar jaringan komputer"
    assert nilai_esai("alat yang menjadi penghubung antar jaringan komputer", kunci)["persen"] == 1.0


def test_esai_lewat_ujian_dan_koreksi_guru(guru, db, data, masuk_siswa):
    e = buat_ujian(db, data, "Esai", bank=data["bank_esai"])
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = int(ani.post("/student/exam/start", data={"exam_id": str(e)}).headers["location"].rsplit("/", 1)[1])
    ani.post(f"/student/exam/submit/{sesi}", data={f"essay_{data['esai']}": "layar, sentuh, input, jari"})
    jawab = db.query(ExamAnswer).filter_by(session_id=sesi).one()
    assert jawab.auto_points == 5.0
    html = guru.get(f"/teacher/exams/{e}/sessions/{sesi}").text
    assert "Perlu dicek" in html and "dibatasi 50%" in html
    guru.post(f"/teacher/answers/{jawab.id}/score", data={"points": "10"})
    db.expire_all()
    from app.models.exam import ExamSession
    assert db.get(ExamSession, sesi).score == 10
