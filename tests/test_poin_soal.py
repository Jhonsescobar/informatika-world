# tests/test_poin_soal.py
# Poin per soal: bisa diubah guru (selama bank belum dipakai), tervalidasi, dan benar-benar menentukan nilai.

from app.models.exam import ExamSession
from app.models.question import Question, QuestionOption
from tests.data_uji import buat_ujian


def test_poin_menentukan_nilai(guru, db, data, masuk_siswa):
    s = data["soal"]
    for i, p in enumerate((10, 10, 10, 70)):
        assert guru.post(f"/teacher/questions/{s[i]['id']}/points", data={"points": str(p)}).status_code == 303
    e = buat_ujian(db, data, "Berbobot")
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = int(ani.post("/student/exam/start", data={"exam_id": str(e)}).headers["location"].rsplit("/", 1)[1])
    # hanya soal 4 (70 poin) yang benar
    jawab = {f"question_{q['id']}": str(q["benar"] if i == 3 else q["salah"]) for i, q in enumerate(s)}
    ani.post(f"/student/exam/submit/{sesi}", data=jawab)
    db.expire_all()
    assert db.get(ExamSession, sesi).score == 70


def test_siswa_melihat_poin_tiap_soal(db, data, masuk_siswa):
    e = buat_ujian(db, data, "Lihat")
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = int(ani.post("/student/exam/start", data={"exam_id": str(e)}).headers["location"].rsplit("/", 1)[1])
    assert ani.get(f"/student/exam/take/{sesi}").text.count("· 25 poin") == 4


def test_halaman_bank_menampilkan_total_dan_isian_poin(guru, data):
    html = guru.get(f"/teacher/question-banks/{data['bank']}").text
    assert "Total <strong class=\"text-white\">100 poin</strong> dari 4 soal" in html
    assert html.count('action="/teacher/questions/') >= 4 and 'name="points" value="25"' in html


def test_poin_di_luar_batas_ditolak(guru, db, data):
    q = data["soal"][0]["id"]
    for salah in ("0", "101", "-5", "abc", "", "2.5"):
        r = guru.post(f"/teacher/questions/{q}/points", data={"points": salah})
        assert "pesan=poin_salah" in r.headers["location"], salah
    db.expire_all()
    assert db.get(Question, q).points == 25


def test_poin_terkunci_setelah_bank_dipakai(guru, db, data, masuk_siswa):
    e = buat_ujian(db, data, "Dipakai")
    ani = masuk_siswa(data["siswa"]["Ani"])
    ani.post("/student/exam/start", data={"exam_id": str(e)})
    q = data["soal"][0]["id"]
    r = guru.post(f"/teacher/questions/{q}/points", data={"points": "90"})
    assert "pesan=poin_terkunci" in r.headers["location"]
    db.expire_all()
    assert db.get(Question, q).points == 25
    html = guru.get(f"/teacher/question-banks/{data['bank']}").text
    assert "/points" not in html and "Poin terkunci karena bank sudah dipakai ujian" in html


def test_siswa_tidak_bisa_mengubah_poin(db, data, masuk_siswa):
    ani = masuk_siswa(data["siswa"]["Ani"])
    q = data["soal"][0]["id"]
    ani.post(f"/teacher/questions/{q}/points", data={"points": "100"})
    db.expire_all()
    assert db.get(Question, q).points == 25


def _soal_baru(guru, data, **isi):
    dasar = {"bank_id": str(data["bank"]), "question_type": "pg", "question_text": "Soal baru", "points": "5"}
    dasar.update(isi)
    return guru.post("/teacher/questions/create", data=dasar)


def test_soal_pg_tanpa_kunci_valid_ditolak(guru, db, data):
    n = db.query(Question).count()
    # kunci menunjuk opsi kosong (HTML required diakali)
    r = _soal_baru(guru, data, option_A="satu", option_B="dua", correct_key="D")
    assert "pesan=isian_pg" in r.headers["location"]
    # hanya satu opsi
    r = _soal_baru(guru, data, option_A="satu", correct_key="A")
    assert "pesan=isian_pg" in r.headers["location"]
    # tanpa kunci sama sekali
    r = _soal_baru(guru, data, option_A="satu", option_B="dua")
    assert "pesan=isian_pg" in r.headers["location"]
    assert db.query(Question).count() == n


def test_soal_esai_tanpa_kunci_ditolak(guru, db, data):
    n = db.query(Question).count()
    r = _soal_baru(guru, data, question_type="esai", answer_key="   ")
    assert "pesan=isian_esai" in r.headers["location"]
    assert db.query(Question).count() == n


def test_soal_pg_valid_tersimpan_dengan_poin_dan_satu_kunci(guru, db, data):
    _soal_baru(guru, data, option_A="satu", option_B="dua", option_C="tiga", correct_key="C", points="999")
    q = db.query(Question).order_by(Question.id.desc()).first()
    assert q.text == "Soal baru" and q.points == 100          # dibatasi ke 100
    ops = db.query(QuestionOption).filter_by(question_id=q.id).order_by(QuestionOption.id).all()
    assert [o.text for o in ops] == ["satu", "dua", "tiga"] and [o.is_correct for o in ops] == [False, False, True]
