# Batas keluar layar ditegakkan di SERVER, bukan hanya oleh skrip di perangkat siswa.

from datetime import datetime, timedelta, timezone

from app.models.exam import ExamSession, ExamViolation
from app.services.kesempatan import bisa_dilanjutkan
from tests.data_uji import buat_ujian


def _mulai(c, exam_id):
    r = c.post("/student/exam/start", data={"exam_id": str(exam_id)})
    return int(r.headers["location"].rsplit("/", 1)[1])


def _keluar(db, sesi, n, mulai):
    for i in range(n):
        db.add(ExamViolation(session_id=sesi, kind="keluar_layar_penuh", created_at=mulai + timedelta(seconds=10 * i)))
    db.commit()


def test_esai_berulang_dalam_tiga_detik_dihitung_satu(db, data, masuk_siswa):
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = _mulai(ani, buat_ujian(db, data, "UH"))
    for _ in range(5):                                     # Esc ditekan berulang-ulang sangat cepat
        r = ani.post(f"/student/exam/violation/{sesi}", data={"kind": "keluar_layar_penuh"}).json()
    assert r["count"] == 1 and r["active"] is True


def test_server_menutup_sesi_setelah_tenggang_bila_skrip_siswa_dilewati(db, data, masuk_siswa):
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = _mulai(ani, buat_ujian(db, data, "UH"))
    s0 = data["soal"][0]
    ani.post(f"/student/exam/events/{sesi}", json=[{"k": "pilih", "q": s0["id"], "o": s0["benar"]}])
    _keluar(db, sesi, 3, datetime.now(timezone.utc) - timedelta(minutes=2))      # tiga kali keluar, sudah lewat tenggang
    # siswa memblokir skrip kirim otomatis lalu mencoba terus mengerjakan: simpan jawaban ditolak dan sesi ditutup
    r = ani.post(f"/student/exam/events/{sesi}", json=[{"k": "pilih", "q": s0["id"], "o": s0["benar"]}]).json()
    assert r["ok"] is False and r.get("selesai") is True
    db.expire_all()
    s = db.get(ExamSession, sesi)
    assert s.status == "completed" and s.score is not None
    assert bisa_dilanjutkan(db, s)                         # guru tetap bisa memberi kesempatan


def test_muat_ulang_halaman_tidak_membuka_ujian_setelah_batas(db, data, masuk_siswa):
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = _mulai(ani, buat_ujian(db, data, "UH"))
    _keluar(db, sesi, 3, datetime.now(timezone.utc) - timedelta(seconds=5))      # masih dalam tenggang
    r = ani.get(f"/student/exam/take/{sesi}", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/student/exam/result/{sesi}"
    db.expire_all()
    assert db.get(ExamSession, sesi).status == "completed"


def test_kiriman_otomatis_dalam_tenggang_memakai_jawaban_form(db, data, masuk_siswa):
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = _mulai(ani, buat_ujian(db, data, "UH"))
    _keluar(db, sesi, 3, datetime.now(timezone.utc) - timedelta(seconds=3))
    jawab = {f"question_{s['id']}": str(s["benar"]) for s in data["soal"][:2]}
    ani.post(f"/student/exam/submit/{sesi}", data=dict(jawab, otomatis="1"))
    db.expire_all()
    assert db.get(ExamSession, sesi).score == 50           # dua dari empat soal dari isi form, bukan dari log kosong


def test_kiriman_setelah_tenggang_tidak_dipakai(db, data, masuk_siswa):
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = _mulai(ani, buat_ujian(db, data, "UH"))
    _keluar(db, sesi, 3, datetime.now(timezone.utc) - timedelta(minutes=3))
    jawab = {f"question_{s['id']}": str(s["benar"]) for s in data["soal"]}
    ani.post(f"/student/exam/submit/{sesi}", data=jawab)
    db.expire_all()
    s = db.get(ExamSession, sesi)
    assert s.status == "completed" and (s.score or 0) == 0   # jawaban dari form (semua benar) diabaikan; log kosong
