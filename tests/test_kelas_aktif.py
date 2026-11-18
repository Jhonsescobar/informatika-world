# tests/test_kelas_aktif.py
# Kelas aktif di sidebar guru: satu pilihan untuk semua menu, disimpan di cookie.

from app.models.exam import Exam
from app.models.material import Material
from app.models.question import QuestionBank
from tests.data_uji import buat_ujian


def pilih(guru, kelas, kembali="/teacher/exams"):
    return guru.post("/teacher/kelas", data={"kelas": kelas, "kembali": kembali}, follow_redirects=False)


def test_awal_kelas_viii_dan_sidebar_menampilkannya(guru):
    html = guru.get("/teacher/exams").text
    assert 'aria-pressed="true">VIII<' in html and 'name="kelas" value="VII"' in html


def test_pilih_kelas_mengubah_sidebar_dan_cookie(guru):
    r = pilih(guru, "VII")
    assert r.status_code == 303 and r.headers["location"] == "/teacher/exams"
    assert 'aria-pressed="true">VII<' in guru.get("/teacher/exams").text


def test_kelas_tidak_valid_diabaikan(guru):
    pilih(guru, "IX")
    pilih(guru, "XII")
    assert 'aria-pressed="true">IX<' in guru.get("/teacher/exams").text


def test_tujuan_kembali_tidak_boleh_keluar_situs(guru):
    for jahat in ("https://jahat.example", "//jahat.example", "/login", "/teacher/../x\\y"):
        r = pilih(guru, "IX", jahat)
        assert r.headers["location"].startswith("/teacher/") and "jahat" not in r.headers["location"], jahat


def test_halaman_detail_kembali_ke_daftar(guru, db, data):
    e = buat_ujian(db, data)
    r = pilih(guru, "VIII", f"/teacher/exams/{e}/results")
    assert r.headers["location"] == "/teacher/exams"


def test_daftar_ujian_hanya_kelas_aktif(guru, db, data):
    buat_ujian(db, data, "Ujian tujuh", "VII")
    buat_ujian(db, data, "Ujian delapan", "VIII")
    assert "Ujian delapan" in guru.get("/teacher/exams").text and "Ujian tujuh" not in guru.get("/teacher/exams").text
    pilih(guru, "VII")
    html = guru.get("/teacher/exams").text
    assert "Ujian tujuh" in html and "Ujian delapan" not in html


def test_materi_dan_bank_soal_mengikuti_kelas(guru, db, data):
    db.add(Material(title="Materi IX", class_target="IX", teacher_id=data["guru"], content="x"))
    db.add(QuestionBank(title="Bank IX", class_target="IX", teacher_id=data["guru"]))
    db.commit()
    assert "Materi IX" not in guru.get("/teacher/materials").text and "Bank IX" not in guru.get("/teacher/question-banks").text
    pilih(guru, "IX")
    assert "Materi IX" in guru.get("/teacher/materials").text and "Bank IX" in guru.get("/teacher/question-banks").text


def test_form_buat_membawa_kelas_aktif_tanpa_pilihan(guru, db, data):
    pilih(guru, "IX")
    html = guru.get("/teacher/exams").text
    assert 'name="class_target" value="IX"' in html and '<select name="class_target"' not in html
    guru.post("/teacher/question-banks/create", data={"title": "Bank baru", "class_target": "IX"})
    assert db.query(QuestionBank).filter_by(title="Bank baru").one().class_target == "IX"


def test_komponen_nilai_hanya_kelas_aktif(guru, db, data):
    guru.post("/teacher/grades/components/create", data={"name": "Komp delapan", "class_target": "VIII", "weight": "30"})
    guru.post("/teacher/grades/components/create", data={"name": "Komp sembilan", "class_target": "IX", "weight": "30"})
    html = guru.get("/teacher/grades").text
    assert "Komp delapan" in html and "Komp sembilan" not in html
    pilih(guru, "IX")
    html = guru.get("/teacher/grades").text
    assert "Komp sembilan" in html and "Komp delapan" not in html


def test_siswa_hanya_kelas_aktif(guru, data):
    html = guru.get("/teacher/students").text
    assert "Fajar" in html and "Ani" not in html
    pilih(guru, "VII", "/teacher/students")
    html = guru.get("/teacher/students").text
    assert "Ani" in html and "Fajar" not in html
