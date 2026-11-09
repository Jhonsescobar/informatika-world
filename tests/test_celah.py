# tests/test_celah.py
# Celah hasil audit 9 Nov 2026: balapan klik ganda, waktu habis tanpa terkirim, pencarian nama, kunci login.

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app as aplikasi
from app.models.exam import ExamAnswer, ExamSession
from app.utils.ratelimit import ip_klien
from tests import data_uji
from tests.data_uji import buat_ujian


def mulai(c, exam_id):
    return int(c.post("/student/exam/start", data={"exam_id": str(exam_id)}).headers["location"].rsplit("/", 1)[1])


def klien_dari(ip):
    return TestClient(aplikasi, follow_redirects=False, client=(ip, 50000))


def test_klik_mulai_bersamaan_hanya_satu_sesi(db, data, masuk_siswa):
    e = buat_ujian(db, data, "A", question_count=2)
    ani = masuk_siswa(data["siswa"]["Ani"])
    with ThreadPoolExecutor(6) as ex:
        hasil = list(ex.map(lambda _: ani.post("/student/exam/start", data={"exam_id": str(e)}).headers["location"], range(6)))
    assert db.query(ExamSession).filter_by(exam_id=e, student_id=data["siswa"]["Ani"]).count() == 1
    assert len(set(hasil)) == 1


def test_klik_kirim_bersamaan_tidak_ganda(db, data, masuk_siswa):
    e = buat_ujian(db, data, "A")
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = mulai(ani, e)
    jawaban = {f"question_{s['id']}": str(s["benar"]) for s in data["soal"]}
    with ThreadPoolExecutor(5) as ex:
        list(ex.map(lambda _: ani.post(f"/student/exam/submit/{sesi}", data=jawaban), range(5)))
    assert db.query(ExamAnswer).filter_by(session_id=sesi).count() == 4
    db.expire_all()
    assert db.get(ExamSession, sesi).score == 100


def kirim_log(c, sesi, kejadian):
    return c.post(f"/student/exam/events/{sesi}", content=json.dumps(kejadian), headers={"content-type": "application/json"}).json()


def mundurkan(db, sesi, menit):
    db.execute(text("UPDATE exam_sessions SET started_at = started_at - make_interval(mins => :m), "
                    "expires_at = expires_at - make_interval(mins => :m) WHERE id = :s"), {"m": menit, "s": sesi})
    # jawaban di log memang terjadi selama ujian, jadi ikut dimundurkan
    db.execute(text("UPDATE exam_events SET created_at = created_at - make_interval(mins => :m) WHERE session_id = :s"),
               {"m": menit, "s": sesi})
    db.commit()


def test_waktu_habis_tanpa_terkirim_dinilai_dari_log(guru, db, data, masuk_siswa):
    e = buat_ujian(db, data, "A")
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = mulai(ani, e)
    s0, s1, s2 = data["soal"][:3]
    kirim_log(ani, sesi, [{"k": "pilih", "q": s0["id"], "o": s0["benar"]}, {"k": "pilih", "q": s1["id"], "o": s1["benar"]},
                          {"k": "pilih", "q": s2["id"], "o": s2["salah"]}])
    mundurkan(db, sesi, 60)                       # HP mati, siswa tidak kembali; waktu sudah lewat
    assert kirim_log(ani, sesi, [{"k": "pilih", "q": s2["id"], "o": s2["benar"]}]) == {"ok": False}   # log lewat waktu ditolak
    html = guru.get(f"/teacher/exams/{e}/results").text   # guru membuka hasil -> sesi diselesaikan dari log
    db.expire_all()
    s = db.get(ExamSession, sesi)
    assert s.status == "expired" and s.score == 50
    assert "dari log" in guru.get(f"/teacher/exams/{e}/sessions/{sesi}").text
    assert "50" in ani.get(f"/student/exam/result/{sesi}").text


def test_kirim_terlambat_memakai_log_bukan_isi_form(db, data, masuk_siswa):
    e = buat_ujian(db, data, "A")
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = mulai(ani, e)
    s0 = data["soal"][0]
    kirim_log(ani, sesi, [{"k": "pilih", "q": s0["id"], "o": s0["benar"]}])
    mundurkan(db, sesi, 60)
    semua_benar = {f"question_{s['id']}": str(s["benar"]) for s in data["soal"]}
    ani.post(f"/student/exam/submit/{sesi}", data=semua_benar)          # dikirim jauh setelah waktu habis
    db.expire_all()
    assert db.get(ExamSession, sesi).score == 25


def test_sesi_lewat_ikut_rekap_nilai(guru, db, data, masuk_siswa):
    from app.services.rekap import rekap_kelas
    e = buat_ujian(db, data, "A")
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = mulai(ani, e)
    s0, s1 = data["soal"][:2]
    kirim_log(ani, sesi, [{"k": "pilih", "q": s0["id"], "o": s0["benar"]}, {"k": "pilih", "q": s1["id"], "o": s1["benar"]}])
    mundurkan(db, sesi, 60)
    baris = {b["siswa"].name: b for b in rekap_kelas(db, "VII")["baris"]}
    assert baris["Ani"]["akhir"] == 50.0


def test_pencarian_nama_wildcard_dan_dibatasi(client):
    assert client.get("/auth/student/search?name=%25%25%25").json() == []
    assert client.get("/auth/student/search?name=___").json() == []
    assert client.get("/auth/student/search?name=a%25i").json() == []      # % bukan lagi pengganti huruf apa pun
    from app.routers.auth import BATAS_CARI_PER_MENIT
    from app.utils import ratelimit
    c = klien_dari("10.0.0.21")
    # satu kelas (40 siswa x 10 ketikan) di belakang satu alamat masih bisa mencari
    for _ in range(400):
        assert ratelimit.boleh("cari:10.0.0.21", BATAS_CARI_PER_MENIT, 60)
    for _ in range(BATAS_CARI_PER_MENIT - 400):
        c.get("/auth/student/search?name=ani")
    assert c.get("/auth/student/search?name=ani").json() == []             # melewati batas per menit
    assert klien_dari("10.0.0.22").get("/auth/student/search?name=ani").json() != []


def test_orang_lain_tidak_bisa_mengunci_login_guru(data):
    penyerang = klien_dari("10.0.0.66")
    for _ in range(6):
        penyerang.post("/auth/teacher/login", data={"email": data_uji.EMAIL_GURU, "password": "salah"})
    assert "terkunci" in penyerang.post("/auth/teacher/login", data={"email": data_uji.EMAIL_GURU,
                                                                     "password": data_uji.PASSWORD_GURU}).headers["location"]
    guru = klien_dari("10.0.0.5")
    assert guru.post("/auth/teacher/login", data={"email": data_uji.EMAIL_GURU,
                                                  "password": data_uji.PASSWORD_GURU}).headers["location"] == "/teacher/dashboard"


def test_satu_perangkat_menebak_pin_banyak_siswa_dikunci(data):
    from app.routers.auth import BATAS_PIN_SALAH_PER_PERANGKAT
    from app.utils import ratelimit
    c = klien_dari("10.0.0.77")
    ids = list(data["siswa"].values())
    for _ in range(BATAS_PIN_SALAH_PER_PERANGKAT - 6):
        ratelimit.catat_gagal("pin-ip:10.0.0.77")
    for i in range(6):
        c.post("/auth/student/verify", data={"student_id": str(ids[i % len(ids)]), "pin": f"{i:04d}"})
    r = c.post("/auth/student/verify", data={"student_id": str(data["siswa"]["Fajar"]), "pin": data_uji.PIN})
    assert "terkunci" in r.headers["location"]


def test_alamat_asli_lewat_tunnel_hanya_dipercaya_dari_laptop():
    lewat_tunnel = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"), headers={"cf-connecting-ip": "36.1.2.3"})
    dari_wifi = SimpleNamespace(client=SimpleNamespace(host="192.168.1.20"), headers={"cf-connecting-ip": "1.1.1.1"})
    assert ip_klien(lewat_tunnel) == "36.1.2.3" and ip_klien(dari_wifi) == "192.168.1.20"


def test_log_dan_pelanggaran_tidak_bisa_membanjiri_database(db, data, masuk_siswa):
    from app.models.exam import ExamEvent, ExamViolation
    from app.routers import student as rs
    e = buat_ujian(db, data, "Esai", bank=data["bank_esai"])
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = mulai(ani, e)
    teks = "x" * 5000
    for _ in range(15):                          # 15 x 30 kiriman (masing-masing < batas 200 KB)
        kirim_log(ani, sesi, [{"k": "esai", "q": data["esai"], "d": teks}] * 30)
    assert db.query(ExamEvent).filter_by(session_id=sesi, kind="esai").count() == rs.MAKS_ESAI_SESI
    db.execute(text("INSERT INTO exam_violations (session_id, kind) SELECT :s, 'salin' FROM generate_series(1, :n)"),
               {"s": sesi, "n": rs.MAKS_PELANGGARAN_DICATAT})
    db.commit()
    ani.post(f"/student/exam/violation/{sesi}", data={"kind": "salin"})
    assert db.query(ExamViolation).filter_by(session_id=sesi).count() == rs.MAKS_PELANGGARAN_DICATAT
