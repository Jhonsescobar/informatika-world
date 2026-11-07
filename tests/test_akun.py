# tests/test_akun.py
# Reset PIN siswa & ganti password guru lewat web, termasuk efeknya ke sesi login lama.

import re

from conftest import klien
from tests import data_uji


def pin_dari(html: str) -> list[str]:
    return re.findall(r'<span class="pin">(\d{4})</span>', html)


def test_reset_pin_satu_siswa(guru, data, masuk_siswa):
    sid = data["siswa"]["Ani"]
    lama = masuk_siswa(sid)                       # sedang login dengan PIN lama
    r = guru.post(f"/teacher/students/{sid}/reset-pin")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    [pin] = pin_dari(r.text)
    assert "PIN lama sudah tidak berlaku" in r.text
    # sesi lama otomatis keluar, PIN lama ditolak, PIN baru diterima
    assert "/login" in lama.get("/student/dashboard").headers["location"]
    r = klien().post("/auth/student/verify", data={"student_id": str(sid), "pin": data_uji.PIN})
    assert "error=pin" in r.headers["location"]
    masuk_siswa(sid, pin)


def test_reset_pin_membuka_kunci_salah_pin(guru, data, masuk_siswa):
    sid = data["siswa"]["Budi"]
    c = klien()
    for _ in range(5):
        c.post("/auth/student/verify", data={"student_id": str(sid), "pin": "0000"})
    [pin] = pin_dari(guru.post(f"/teacher/students/{sid}/reset-pin").text)
    masuk_siswa(sid, pin)


def test_reset_pin_massal(guru, data, masuk_siswa):
    ids = [data["siswa"]["Ani"], data["siswa"]["Dodi"]]
    r = guru.post("/teacher/students/bulk", data={"action": "reset_pin", "student_ids": [str(i) for i in ids],
                                                  "kembali": "/teacher/students"})
    pins = pin_dari(r.text)
    assert len(pins) == 2
    # urut nama: Ani, Dodi
    masuk_siswa(ids[0], pins[0])
    masuk_siswa(ids[1], pins[1])


def test_reset_pin_siswa_tidak_ada(guru):
    assert guru.post("/teacher/students/999999/reset-pin").status_code == 303


def test_tambah_siswa_pin_harus_angka(guru, db):
    from app.models.student import Student
    awal = db.query(Student).count()
    for pin in ("", "12", "abcd", "1234567"):
        r = guru.post("/teacher/students/create", data={"name": "Baru", "pin": pin})
        assert "pin_salah" in r.headers["location"]
    guru.post("/teacher/students/create", data={"name": "Baru", "pin": "2468"})
    assert db.query(Student).count() == awal + 1


def ganti(c, lama, baru, ulang=None):
    return c.post("/teacher/account/password", data={"lama": lama, "baru": baru, "ulang": ulang or baru}).headers["location"]


def test_ganti_password_validasi(guru):
    assert ganti(guru, "salah", "SandiBaru#2026").endswith("pesan=lama")
    assert ganti(guru, data_uji.PASSWORD_GURU, "SandiBaru#2026", "beda").endswith("pesan=beda")
    assert ganti(guru, data_uji.PASSWORD_GURU, "pendek").endswith("pesan=lemah")
    assert ganti(guru, data_uji.PASSWORD_GURU, "password").endswith("pesan=lemah")
    assert ganti(guru, data_uji.PASSWORD_GURU, data_uji.PASSWORD_GURU).endswith("pesan=lemah")


def test_ganti_password_berhasil_dan_perangkat_lain_keluar(guru, data):
    perangkat_lain = klien()
    perangkat_lain.post("/auth/teacher/login", data={"email": data_uji.EMAIL_GURU, "password": data_uji.PASSWORD_GURU})
    assert perangkat_lain.get("/teacher/grades").status_code == 200

    assert ganti(guru, data_uji.PASSWORD_GURU, "SandiBaru#2026").endswith("pesan=ok")
    assert guru.get("/teacher/grades").status_code == 200                 # perangkat ini tetap masuk
    assert perangkat_lain.get("/teacher/grades").status_code in (303, 307)  # perangkat lain keluar

    c = klien()
    assert "error=salah" in c.post("/auth/teacher/login", data={"email": data_uji.EMAIL_GURU, "password": data_uji.PASSWORD_GURU}).headers["location"]
    assert c.post("/auth/teacher/login", data={"email": data_uji.EMAIL_GURU, "password": "SandiBaru#2026"}).headers["location"] == "/teacher/dashboard"


def test_ganti_password_dibatasi_saat_menebak(guru):
    for _ in range(5):
        ganti(guru, "tebakan", "SandiBaru#2026")
    assert ganti(guru, data_uji.PASSWORD_GURU, "SandiBaru#2026").endswith("pesan=terkunci")
