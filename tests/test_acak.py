# tests/test_acak.py
# Urutan soal dan opsi diacak per akun siswa, tetap sama saat halaman dimuat ulang.

import re

from app.models.exam import Exam, ExamSession
from app.models.question import Question, QuestionBank, QuestionOption
from tests.data_uji import buat_ujian


def bank_besar(db, data, jumlah=15):
    b = QuestionBank(title="Bank 15", class_target="VII", teacher_id=data["guru"])
    db.add(b)
    db.flush()
    for i in range(jumlah):
        q = Question(bank_id=b.id, text=f"Pertanyaan nomor {i + 1}", points=10, question_type="pg")
        db.add(q)
        db.flush()
        db.add_all([QuestionOption(question_id=q.id, text=f"Jawab {i + 1}-{h}", is_correct=(h == "A")) for h in "ABCD"])
    db.commit()
    return b.id


def mulai(c, exam_id):
    return int(c.post("/student/exam/start", data={"exam_id": str(exam_id)}).headers["location"].rsplit("/", 1)[1])


def urutan(html):
    """(urutan soal, urutan opsi per soal) seperti yang tampil di layar siswa."""
    soal = re.findall(r"Pertanyaan nomor (\d+)", html)
    opsi = re.findall(r"Jawab (\d+-[A-D])", html)
    return soal, opsi


def test_form_ujian_baru_mengacak_secara_bawaan(guru):
    html = guru.get("/teacher/exams").text
    assert 'name="randomize_questions" checked' in html and 'name="randomize_options" checked' in html


def test_tiap_akun_dapat_urutan_berbeda_dan_stabil(db, data, masuk_siswa):
    e = buat_ujian(db, data, "Acak", bank=bank_besar(db, data), randomize_questions=True, randomize_options=True)
    hasil = {}
    for nama in ("Ani", "Budi", "Citra"):
        c = masuk_siswa(data["siswa"][nama])
        sesi = mulai(c, e)
        pertama = urutan(c.get(f"/student/exam/take/{sesi}").text)
        kedua = urutan(c.get(f"/student/exam/take/{sesi}").text)      # muat ulang
        assert pertama == kedua, "urutan berubah saat halaman dimuat ulang"
        assert len(pertama[0]) == 15 and sorted(pertama[0], key=int) == [str(i) for i in range(1, 16)]
        hasil[nama] = pertama
    soal = [tuple(h[0]) for h in hasil.values()]
    opsi = [tuple(h[1]) for h in hasil.values()]
    assert len(set(soal)) == 3, "dua siswa mendapat urutan soal yang sama"
    # opsi dibandingkan per soal (bukan per urutan tampil) supaya yang diuji memang pengacakan opsi
    per_soal = [tuple(sorted(o, key=lambda x: int(x.split("-")[0]))) for o in opsi]
    assert per_soal[0] != per_soal[1] or per_soal[1] != per_soal[2]
    assert any(o != tuple(sorted(o)) for o in opsi)


def test_tanpa_acak_urutan_bank(db, data, masuk_siswa):
    e = buat_ujian(db, data, "Urut", bank=bank_besar(db, data), randomize_questions=False, randomize_options=False)
    c = masuk_siswa(data["siswa"]["Ani"])
    soal, opsi = urutan(c.get(f"/student/exam/take/{mulai(c, e)}").text)
    assert soal == [str(i) for i in range(1, 16)]
    assert opsi[:4] == ["1-A", "1-B", "1-C", "1-D"]


def test_guru_bisa_mengubah_acak_ujian_lama(guru, db, data):
    e = buat_ujian(db, data, "Lama", randomize_questions=False, randomize_options=False)
    guru.post(f"/teacher/exams/{e}/acak", data={"jenis": "soal"})
    guru.post(f"/teacher/exams/{e}/acak", data={"jenis": "opsi"})
    db.expire_all()
    ujian = db.get(Exam, e)
    assert ujian.randomize_questions and ujian.randomize_options
    assert "Soal diacak" in guru.get("/teacher/exams").text
    guru.post(f"/teacher/exams/{e}/acak", data={"jenis": "aneh"})       # isian tak dikenal diabaikan
    db.expire_all()
    assert db.get(Exam, e).randomize_questions


def test_acak_opsi_ditolak_saat_ada_yang_mengerjakan(guru, db, data, masuk_siswa):
    e = buat_ujian(db, data, "Berjalan", randomize_options=False)
    ani = masuk_siswa(data["siswa"]["Ani"])
    mulai(ani, e)
    r = guru.post(f"/teacher/exams/{e}/acak", data={"jenis": "opsi"})
    assert "error=opsi_aktif" in r.headers["location"]
    db.expire_all()
    assert not db.get(Exam, e).randomize_options
    assert "huruf A–D di layar mereka tidak berpindah" in guru.get(r.headers["location"]).text


def test_ubah_acak_soal_tidak_mengubah_sesi_berjalan(guru, db, data, masuk_siswa):
    e = buat_ujian(db, data, "Berjalan", bank=bank_besar(db, data), randomize_questions=True)
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = mulai(ani, e)
    sebelum = urutan(ani.get(f"/student/exam/take/{sesi}").text)[0]
    guru.post(f"/teacher/exams/{e}/acak", data={"jenis": "soal"})
    assert urutan(ani.get(f"/student/exam/take/{sesi}").text)[0] == sebelum


def test_siswa_tidak_bisa_mengubah_acak(db, data, masuk_siswa):
    e = buat_ujian(db, data, "X", randomize_questions=False)
    ani = masuk_siswa(data["siswa"]["Ani"])
    ani.post(f"/teacher/exams/{e}/acak", data={"jenis": "soal"})
    db.expire_all()
    assert not db.get(Exam, e).randomize_questions
