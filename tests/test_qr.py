# tests/test_qr.py
# Halaman QR guru: QR mengarah ke alamat web untuk siswa, hanya alamat yang sah, file sisa sesi lama diabaikan.

import io
import json
import time

import pytest

import app.services.alamat as alamat


@pytest.fixture
def file_alamat(tmp_path, monkeypatch):
    f = tmp_path / "alamat.json"
    monkeypatch.setattr(alamat, "FILE_ALAMAT", f)
    monkeypatch.setattr(alamat, "MULAI_PROSES", time.time() - 60)
    return f


def tulis(f, isi, bom=True):
    teks = json.dumps(isi)
    f.write_bytes(("﻿" + teks if bom else teks).encode("utf-8"))   # PowerShell 5 menulis dengan BOM


def pindai(url):
    """Membaca QR yang dibuat untuk url dengan pembaca QR sungguhan (OpenCV)."""
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    import segno
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="png", scale=10, border=4)
    img = cv2.imdecode(np.frombuffer(buf.getvalue(), np.uint8), cv2.IMREAD_GRAYSCALE)
    teks, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
    return teks


def test_qr_mode_internet(guru, file_alamat):
    tulis(file_alamat, {"url": "https://kata-acak.trycloudflare.com/login", "lain": [], "waktu": "x"})
    html = guru.get("/teacher/qr").text
    assert "<svg" in html and "https://kata-acak.trycloudflare.com/login" in html
    assert "Online lewat internet" in html and "Alamat dibuat pukul" in html
    assert alamat.svg_qr("https://kata-acak.trycloudflare.com/login") in html
    assert pindai("https://kata-acak.trycloudflare.com/login") == "https://kata-acak.trycloudflare.com/login"


def test_qr_mode_lokal_dengan_alamat_cadangan(guru, file_alamat):
    tulis(file_alamat, {"url": "http://192.168.43.10:8000/login", "lain": ["http://10.0.0.7:8000/login", "https://jahat.com/x"]}, bom=False)
    html = guru.get("/teacher/qr").text
    assert "Jaringan lokal" in html and "WiFi/hotspot yang sama" in html
    assert "http://10.0.0.7:8000/login" in html and "jahat.com" not in html
    assert pindai("http://192.168.43.10:8000/login") == "http://192.168.43.10:8000/login"


def test_tanpa_alamat_tidak_ada_qr(guru, file_alamat):
    html = guru.get("/teacher/qr").text
    assert "class=\"segno\"" not in html and "Web belum online untuk siswa" in html
    assert guru.get("/teacher/qr/status").json() == {"url": None}


@pytest.mark.parametrize("url", [
    "https://phising.com/login", "https://api.trycloudflare.com/login", "http://127.0.0.1:8000/login",
    "https://a.trycloudflare.com/login?next=//jahat.com", "javascript:alert(1)", "http://300.1.1.1:8000/login",
    "https://a.trycloudflare.com.jahat.com/login",
])
def test_alamat_tidak_sah_ditolak(guru, file_alamat, url):
    tulis(file_alamat, {"url": url})
    html = guru.get("/teacher/qr").text
    assert "Web belum online untuk siswa" in html and url not in html.split("<script>")[0]


def test_file_rusak_diabaikan(guru, file_alamat):
    file_alamat.write_text("{bukan json", encoding="utf-8")
    assert "Web belum online untuk siswa" in guru.get("/teacher/qr").text
    tulis(file_alamat, ["https://a.trycloudflare.com/login"])
    assert "Web belum online untuk siswa" in guru.get("/teacher/qr").text


def test_file_sisa_sesi_lama_diabaikan(guru, file_alamat, monkeypatch):
    tulis(file_alamat, {"url": "https://tunnel-lama.trycloudflare.com/login"})
    monkeypatch.setattr(alamat, "MULAI_PROSES", time.time() + 60)     # web dinyalakan setelah file ditulis
    assert "tunnel-lama" not in guru.get("/teacher/qr").text


def test_status_berganti_saat_alamat_berganti(guru, file_alamat):
    tulis(file_alamat, {"url": "https://satu.trycloudflare.com/login"})
    assert guru.get("/teacher/qr/status").json()["url"] == "https://satu.trycloudflare.com/login"
    tulis(file_alamat, {"url": "https://dua.trycloudflare.com/login"})
    assert guru.get("/teacher/qr/status").json()["url"] == "https://dua.trycloudflare.com/login"


def test_cadangan_dari_alamat_yang_dibuka_guru(file_alamat):
    assert alamat.dari_permintaan("http://192.168.1.20:8000/")["url"] == "http://192.168.1.20:8000/login"
    for b in ("http://localhost:8000/", "http://127.0.0.1:8000/", "http://evil.com/", "http://testserver/"):
        assert alamat.dari_permintaan(b) is None


def test_hanya_guru(masuk_siswa, data, client, file_alamat):
    tulis(file_alamat, {"url": "https://a.trycloudflare.com/login"})
    ani = masuk_siswa(data["siswa"]["Ani"])
    assert ani.get("/teacher/qr").status_code == 403
    assert ani.get("/teacher/qr/status").status_code == 403
    r = client.get("/teacher/qr", follow_redirects=False)
    assert r.status_code in (303, 307) and "/login" in r.headers["location"]


def test_menu_qr_di_sidebar_guru(guru):
    assert 'href="/teacher/qr"' in guru.get("/teacher/exams").text
