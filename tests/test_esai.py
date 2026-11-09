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


# --- kasus nyata dari uji coba guru (9 Nov 2026) ---
SURAT = ("Assalamualaikum warahmatullahi wabarakatuh. Selamat pagi, Bapak/Ibu Dosen. Mohon maaf mengganggu waktunya. "
         "Perkenalkan, saya mahasiswi baru program RPL Pendidikan Pancasila dan Kewarganegaraan (PPKn). Sebelumnya, saya ingin "
         "menyampaikan permohonan maaf karena belum dapat mengikuti beberapa pertemuan perkuliahan akibat tanggung jawab pekerjaan "
         "saya di lembaga sekolah. Saya menyadari bahwa selama ketidakhadiran tersebut, ada beberapa materi perkuliahan dan "
         "penugasan yang sudah tertinggal.")
K_HW = ("Hardware adalah perangkat keras yang berwujud fisik dan dapat disentuh, sedangkan software adalah perangkat lunak "
        "berupa program/data tak berwujud fisik yang berjalan di dalam komputer.")
KK_HW = ("Hardware adalah perangkat yang bisa dilihat, Hardware adalah perangkat yang bisa disentuh. software adalah program "
         "komputer, software adalah perangkat yang tidak bisa disentuh")
K_CPU, KK_CPU = "CPU (Processor), Motherboard, dan RAM.", "Cpu, cpu. central processing unit, RAM, ram"


def test_teks_tak_relevan_bernilai_nol_dan_ditandai():
    r = nilai_esai(SURAT, K_HW, KK_HW)
    assert r["persen"] == 0 and r["perlu_cek"] == "Sebagian besar jawaban di luar topik"


def test_tanpa_kata_kunci_cocok_kemiripan_nol():
    r = nilai_esai("aha", K_CPU, KK_CPU)
    assert r["persen"] == 0 and r["kemiripan"] == 0


def test_kata_kunci_kalimat_dibaca_sebagai_frasa():
    from app.services.esai import baca_kata_kunci, label_grup
    assert [label_grup(g) for g in baca_kata_kunci(KK_CPU)] == ["cpu", "central processing unit", "ram"]
    assert [label_grup(g) for g in baca_kata_kunci("cpu/central processing unit, ram")] == ["cpu / central processing unit", "ram"]
    # satu kata umum tidak lagi memenuhi kata kunci berupa kalimat
    assert nilai_esai("program", K_HW, KK_HW)["persen"] == 0


def test_jawaban_benar_tetap_dihargai():
    benar = ("Hardware adalah perangkat keras komputer yang berwujud fisik sehingga bisa dilihat dan disentuh, "
             "sedangkan software adalah program komputer yang tidak bisa disentuh.")
    assert nilai_esai(benar, K_HW, KK_HW)["persen"] == 1.0
    assert nilai_esai("Contohnya adalah CPU atau central processing unit, RAM, serta motherboard.", K_CPU, KK_CPU)["persen"] == 1.0
    assert nilai_esai("CPU, RAM, dan motherboard", K_CPU, "cpu/central processing unit, ram, motherboard")["persen"] == 1.0


def test_jawaban_sebagian_dapat_sebagian():
    assert 0 < nilai_esai("CPU", K_CPU, "cpu/central processing unit, ram, motherboard")["persen"] <= 0.5
    assert nilai_esai("Keyboard, mouse, dan monitor", K_CPU, KK_CPU)["persen"] == 0


def test_awalan_pendek_tidak_lagi_dianggap_sama():
    from app.services.esai import mirip_kata
    assert not mirip_kata("data", "database") and not mirip_kata("prog", "program")
    assert mirip_kata("sentuhan", "sentuh") and mirip_kata("menrima", "menerima")


def test_hitung_ulang_esai_memperbaiki_nilai_lama(guru, db, data, masuk_siswa):
    from app.models.exam import ExamSession
    from app.models.question import Question
    q = db.get(Question, data["esai"])
    q.answer_key, q.keywords, q.points = K_HW, KK_HW, 20
    db.commit()
    e = buat_ujian(db, data, "Esai", bank=data["bank_esai"])
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = int(ani.post("/student/exam/start", data={"exam_id": str(e)}).headers["location"].rsplit("/", 1)[1])
    ani.post(f"/student/exam/submit/{sesi}", data={f"essay_{data['esai']}": SURAT})
    jawab = db.query(ExamAnswer).filter_by(session_id=sesi).one()
    jawab.auto_points = 6.8                      # nilai lama dari aturan sebelumnya
    db.get(ExamSession, sesi).score = 7
    db.commit()
    r = guru.post(f"/teacher/exams/{e}/recalc")
    assert "pesan=hitung&n=1" in r.headers["location"]
    db.expire_all()
    assert db.get(ExamAnswer, jawab.id).auto_points == 0 and db.get(ExamSession, sesi).score == 0
    # koreksi manual guru tidak diubah oleh hitung ulang
    guru.post(f"/teacher/answers/{jawab.id}/score", data={"points": "5"})
    guru.post(f"/teacher/exams/{e}/recalc")
    db.expire_all()
    assert db.get(ExamAnswer, jawab.id).manual_points == 5 and db.get(ExamSession, sesi).score == 5
    assert "Hitung ulang esai" in guru.get(f"/teacher/exams/{e}/results").text
