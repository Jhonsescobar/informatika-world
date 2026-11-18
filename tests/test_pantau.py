# Pantau guru: sinyal online dari siswa, batas 2 menit, sesi ujian aktif, dan akses per peran.

from datetime import datetime, timedelta, timezone

from app.models.exam import ExamSession, ExamViolation
from app.models.student import Student
from app.services.pantau import BATAS_ONLINE, pantau_data
from tests.data_uji import buat_ujian


def _sinyal(db, student_id, waktu):
    db.query(Student).filter(Student.id == student_id).update({Student.last_seen: waktu})
    db.commit()


def test_ping_hanya_mencatat_siswa_yang_login(masuk_siswa, db, data):
    ani = masuk_siswa(data["siswa"]["Ani"])
    assert ani.post("/student/ping").status_code == 200
    db.expire_all()
    terbaru = db.get(Student, data["siswa"]["Ani"]).last_seen
    assert terbaru is not None and datetime.now(timezone.utc) - terbaru.replace(tzinfo=timezone.utc) < timedelta(minutes=1)
    assert db.get(Student, data["siswa"]["Budi"]).last_seen is None


def test_ping_tanpa_login_ditolak(client):
    r = client.post("/student/ping", follow_redirects=False)
    assert r.status_code in (303, 307, 401, 403)


def test_online_hanya_dalam_batas_dua_menit(db, data):
    sekarang = datetime.now(timezone.utc)
    _sinyal(db, data["siswa"]["Ani"], sekarang - timedelta(seconds=30))
    _sinyal(db, data["siswa"]["Budi"], sekarang - BATAS_ONLINE - timedelta(seconds=30))
    hasil = pantau_data(db, "VII", sekarang)
    nama = [x["nama"] for x in hasil["online"]]
    assert "Ani" in nama and "Budi" not in nama
    assert hasil["ringkas"]["online"] == len(hasil["online"])


def test_sedang_ujian_menampilkan_progres_dan_pelanggaran(db, data, masuk_siswa):
    ujian = buat_ujian(db, data, "Sedang jalan")
    sekarang = datetime.now(timezone.utc)
    sesi = ExamSession(student_id=data["siswa"]["Ani"], exam_id=ujian, status="active",
                       expires_at=sekarang + timedelta(minutes=20))
    db.add(sesi); db.flush()
    db.add(ExamViolation(session_id=sesi.id, kind="pindah tab")); db.commit()
    hasil = pantau_data(db, "VII", sekarang)
    baris = next(x for x in hasil["ujian"] if x["nama"] == "Ani")
    assert baris["ujian"] == "Sedang jalan" and baris["pelanggaran"] == 1 and baris["total"] > 0
    assert hasil["ringkas"]["pelanggaran"] >= 1


def test_sesi_lewat_waktu_tidak_dianggap_sedang_ujian(db, data):
    ujian = buat_ujian(db, data, "Sudah habis")
    sekarang = datetime.now(timezone.utc)
    db.add(ExamSession(student_id=data["siswa"]["Citra"], exam_id=ujian, status="active",
                       expires_at=sekarang - timedelta(minutes=5)))
    db.commit()
    assert all(x["nama"] != "Citra" for x in pantau_data(db, "VII", sekarang)["ujian"])


def test_guru_melihat_halaman_dan_data(guru, db, data, masuk_siswa):
    guru.cookies.set("iw_kelas", "VII")
    masuk_siswa(data["siswa"]["Ani"]).post("/student/ping")
    html = guru.get("/teacher/students/pantau").text
    assert "Siapa yang" in html and "daftar-online" in html
    j = guru.get("/teacher/students/pantau/data")
    assert j.status_code == 200 and j.headers["cache-control"] == "no-store"
    assert "Ani" in [x["nama"] for x in j.json()["online"]]


def test_siswa_tidak_bisa_membuka_pantau(masuk_siswa, data):
    ani = masuk_siswa(data["siswa"]["Ani"])
    for url in ("/teacher/students/pantau", "/teacher/students/pantau/data"):
        r = ani.get(url, follow_redirects=False)
        assert r.status_code in (303, 307, 403)
        assert "Online di aplikasi" not in r.text and "Ani" not in r.text


def test_tombol_pantau_ada_di_daftar_siswa(guru):
    assert 'href="/teacher/students/pantau"' in guru.get("/teacher/students").text
