# tests/test_keamanan.py
# Upaya penyalahgunaan yang harus selalu ditolak.

from app.models.exam import ExamSession
from tests import data_uji
from tests.data_uji import buat_ujian, kerjakan
from conftest import klien


def test_halaman_guru_wajib_login(client):
    for url in ("/teacher/materials", "/teacher/grades", "/teacher/grades/export", "/teacher/account", "/teacher/students"):
        r = client.get(url)
        assert r.status_code in (303, 307) and "/login" in r.headers["location"], url


def test_siswa_tidak_bisa_membuka_halaman_guru(masuk_siswa, data):
    ani = masuk_siswa(data["siswa"]["Ani"])
    assert ani.get("/teacher/grades").status_code == 403
    assert ani.post("/teacher/students/1/reset-pin").status_code == 403
    assert ani.get("/teacher/grades/export").status_code == 403


def test_dokumentasi_api_dimatikan(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_login_guru_dikunci_setelah_5x_salah(client):
    for _ in range(5):
        client.post("/auth/teacher/login", data={"email": data_uji.EMAIL_GURU, "password": "salah"})
    r = client.post("/auth/teacher/login", data={"email": data_uji.EMAIL_GURU, "password": data_uji.PASSWORD_GURU})
    assert "error=terkunci" in r.headers["location"]


def test_pin_siswa_dikunci_setelah_5x_salah(client, data):
    sid = data["siswa"]["Ani"]
    for _ in range(5):
        client.post("/auth/student/verify", data={"student_id": str(sid), "pin": "0000"})
    r = client.post("/auth/student/verify", data={"student_id": str(sid), "pin": data_uji.PIN})
    assert "error=terkunci" in r.headers["location"]


def test_siswa_nonaktif_tidak_bisa_login_dan_yang_login_terlempar(client, guru, data, masuk_siswa):
    r = client.post("/auth/student/verify", data={"student_id": str(data["nonaktif"]), "pin": data_uji.PIN})
    assert r.headers["location"] == "/login/siswa"
    ani = masuk_siswa(data["siswa"]["Ani"])
    guru.post(f"/teacher/students/{data['siswa']['Ani']}/toggle-active")
    assert "/login" in ani.get("/student/dashboard").headers["location"]


def test_pencarian_nama_minimal_3_huruf(client):
    assert client.get("/auth/student/search?name=an").json() == []
    assert isinstance(client.get("/auth/student/search?name=ani").json(), list)


def test_siswa_tidak_bisa_mengirim_sesi_milik_teman(db, data, masuk_siswa):
    a = buat_ujian(db, data, "A")
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = int(ani.post("/student/exam/start", data={"exam_id": str(a)}).headers["location"].rsplit("/", 1)[1])
    budi = masuk_siswa(data["siswa"]["Budi"])
    jawaban = {f"question_{s['id']}": str(s["salah"]) for s in data["soal"]}
    assert budi.post(f"/student/exam/submit/{sesi}", data=jawaban).headers["location"] == "/student/dashboard"
    assert budi.get(f"/student/exam/result/{sesi}").headers["location"] == "/student/dashboard"
    db.expire_all()
    assert db.get(ExamSession, sesi).status == "active"


def test_skor_dihitung_server_dan_tidak_bisa_dikirim_ulang(db, data, masuk_siswa):
    a = buat_ujian(db, data, "A")
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = kerjakan(ani, a, data, 2)
    db.expire_all()
    assert db.get(ExamSession, sesi).score == 50
    # kirim ulang semua benar + opsi dari soal lain: tidak mengubah skor
    curang = {f"question_{s['id']}": str(s["benar"]) for s in data["soal"]}
    curang["score"] = "100"
    ani.post(f"/student/exam/submit/{sesi}", data=curang)
    db.expire_all()
    assert db.get(ExamSession, sesi).score == 50
    # mulai lagi tanpa izin remedial: diarahkan ke hasil, tidak ada sesi baru
    r = ani.post("/student/exam/start", data={"exam_id": str(a)})
    assert r.headers["location"] == f"/student/exam/result/{sesi}"


def test_ujian_beda_tingkat_tidak_bisa_dimulai(db, data, masuk_siswa):
    a = buat_ujian(db, data, "Khusus VIII", kelas="VIII")
    ani = masuk_siswa(data["siswa"]["Ani"])
    assert ani.post("/student/exam/start", data={"exam_id": str(a)}).headers["location"] == "/student/dashboard"


def test_remedial_guru_tidak_bisa_dipakai_dua_kali(guru, db, data, masuk_siswa):
    a = buat_ujian(db, data, "A")
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = kerjakan(ani, a, data, 1)
    guru.post(f"/teacher/exams/{a}/sessions/{sesi}/remedial")
    guru.post(f"/teacher/exams/{a}/sessions/{sesi}/remedial")     # klik ganda: tetap satu izin
    kerjakan(ani, a, data, 2)
    r = ani.post("/student/exam/start", data={"exam_id": str(a)})
    assert "/student/exam/result/" in r.headers["location"]
    assert db.query(ExamSession).filter_by(exam_id=a, student_id=data["siswa"]["Ani"]).count() == 2


def test_logout_menghapus_akses(guru):
    guru.post("/logout")
    assert guru.get("/teacher/grades").status_code in (303, 307)


def test_halaman_galat_tidak_membocorkan_kode(guru):
    r = guru.get("/teacher/exams/999999/results")
    assert r.status_code in (200, 303) and "Traceback" not in r.text


def test_token_palsu_ditolak(client):
    client.cookies.set("access_token", "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIiwicm9sZSI6InRlYWNoZXIifQ.palsu")
    assert client.get("/teacher/grades").status_code in (303, 307)


def test_klien_baru_tanpa_cookie():
    assert klien().get("/student/dashboard").status_code in (303, 307)


def test_header_keamanan(guru):
    r = guru.get("/teacher/grades")
    assert r.headers["x-frame-options"] == "DENY" and r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "no-store"
