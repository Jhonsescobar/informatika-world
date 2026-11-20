# Kesempatan melanjutkan ujian setelah terkirim otomatis (guru yang memutuskan).

from datetime import datetime, timedelta, timezone

from app.models.exam import ExamAnswer, ExamEvent, ExamSession, ExamViolation
from app.services.kesempatan import bisa_dilanjutkan, sesi_otomatis
from tests.data_uji import buat_ujian


def _mulai(c, exam_id):
    r = c.post("/student/exam/start", data={"exam_id": str(exam_id)})
    return int(r.headers["location"].rsplit("/", 1)[1])


def _kirim_otomatis(c, sesi, data, jumlah=2):
    """Siswa memilih `jumlah` jawaban benar, lalu halaman mengirim otomatis (tiga kali keluar layar)."""
    jawab = {f"question_{s['id']}": str(s["benar"]) for s in data["soal"][:jumlah]}
    for s in data["soal"][:jumlah]:                      # jawaban juga tersimpan berkala di log
        c.post(f"/student/exam/events/{sesi}", json=[{"k": "pilih", "q": s["id"], "o": s["benar"]}])
    r = c.post(f"/student/exam/submit/{sesi}", data=dict(jawab, otomatis="1"))
    assert r.headers["location"] == f"/student/exam/result/{sesi}"


def test_guru_membuka_lagi_sesi_kirim_otomatis(guru, db, data, masuk_siswa):
    ani = masuk_siswa(data["siswa"]["Ani"])
    a = buat_ujian(db, data, "UH")
    sesi = _mulai(ani, a)
    _kirim_otomatis(ani, sesi, data)
    db.expire_all()
    s = db.get(ExamSession, sesi)
    assert s.status == "completed" and bisa_dilanjutkan(db, s)

    r = guru.post(f"/teacher/exams/{a}/sessions/{sesi}/lanjut", follow_redirects=False)
    assert r.headers["location"].endswith("pesan=lanjut")
    db.expire_all()
    s = db.get(ExamSession, sesi)
    assert s.status == "active" and s.submitted_at is None and s.score is None
    assert s.expires_at > datetime.now(timezone.utc) + timedelta(minutes=2)
    assert db.query(ExamAnswer).filter(ExamAnswer.session_id == sesi).count() == 0       # tidak ganda saat kirim lagi
    assert db.query(ExamEvent).filter(ExamEvent.session_id == sesi, ExamEvent.kind == "kesempatan").count() == 1

    # siswa melanjutkan di sesi yang sama, jawabannya tetap
    r = ani.post("/student/exam/start", data={"exam_id": str(a)}, follow_redirects=False)
    assert r.headers["location"] == f"/student/exam/take/{sesi}"
    assert ani.get(f"/student/exam/take/{sesi}").status_code == 200
    r = ani.post(f"/student/exam/submit/{sesi}", data={f"question_{x['id']}": str(x["benar"]) for x in data["soal"][:2]})
    assert r.headers["location"] == f"/student/exam/result/{sesi}"
    db.expire_all()
    assert db.query(ExamAnswer).filter(ExamAnswer.session_id == sesi).count() == 2
    assert db.get(ExamSession, sesi).score == 50                                          # 2 dari 4 soal benar


def test_hitungan_pelanggaran_mulai_dari_nol_setelah_kesempatan(guru, db, data, masuk_siswa):
    ani = masuk_siswa(data["siswa"]["Ani"])
    a = buat_ujian(db, data, "UH")
    sesi = _mulai(ani, a)
    lama = datetime.now(timezone.utc) - timedelta(minutes=5)
    for i in range(3):
        db.add(ExamViolation(session_id=sesi, kind="pindah_tab", created_at=lama + timedelta(seconds=10 * i)))
    db.commit()
    _kirim_otomatis(ani, sesi, data, 1)
    guru.post(f"/teacher/exams/{a}/sessions/{sesi}/lanjut")
    r = ani.post(f"/student/exam/violation/{sesi}", data={"kind": "pindah_tab"}).json()
    assert r["count"] == 1 and r["limit"] == 3                                            # bukan 4
    db.expire_all()
    assert db.query(ExamViolation).filter(ExamViolation.session_id == sesi).count() == 4  # catatan lama tetap untuk guru


def test_kesempatan_hanya_untuk_kirim_otomatis(guru, db, data, masuk_siswa):
    ani = masuk_siswa(data["siswa"]["Ani"])
    a = buat_ujian(db, data, "UH")
    sesi = _mulai(ani, a)
    ani.post(f"/student/exam/submit/{sesi}", data={f"question_{data['soal'][0]['id']}": str(data["soal"][0]["benar"])})   # kirim sendiri
    db.expire_all()
    assert not bisa_dilanjutkan(db, db.get(ExamSession, sesi))
    r = guru.post(f"/teacher/exams/{a}/sessions/{sesi}/lanjut", follow_redirects=False)
    assert r.headers["location"].endswith("pesan=lanjut_gagal")
    db.expire_all()
    assert db.get(ExamSession, sesi).status == "completed"


def test_tidak_bisa_setelah_waktu_habis_atau_ada_sesi_baru(guru, db, data, masuk_siswa):
    ani = masuk_siswa(data["siswa"]["Ani"])
    a = buat_ujian(db, data, "UH")
    sesi = _mulai(ani, a)
    _kirim_otomatis(ani, sesi, data)
    s = db.get(ExamSession, sesi)
    s.expires_at = s.submitted_at                         # dikirim tepat saat waktu habis
    db.commit()
    assert not bisa_dilanjutkan(db, db.get(ExamSession, sesi))
    s.expires_at = s.submitted_at + timedelta(minutes=10)
    db.add(ExamSession(student_id=s.student_id, exam_id=a, status="active", expires_at=datetime.now(timezone.utc) + timedelta(minutes=5)))
    db.commit()
    assert not bisa_dilanjutkan(db, db.get(ExamSession, sesi))             # sudah ada sesi yang lebih baru


def test_tombol_hanya_muncul_untuk_sesi_otomatis_dan_hanya_guru(guru, db, data, masuk_siswa):
    ani, budi = masuk_siswa(data["siswa"]["Ani"]), masuk_siswa(data["siswa"]["Budi"])
    a = buat_ujian(db, data, "UH")
    sesi_a = _mulai(ani, a)
    _kirim_otomatis(ani, sesi_a, data)
    sesi_b = _mulai(budi, a)
    budi.post(f"/student/exam/submit/{sesi_b}", data={})
    html = guru.get(f"/teacher/exams/{a}/results").text
    assert html.count("Beri kesempatan") == 1 and f"sessions/{sesi_a}/lanjut" in html
    r = ani.post(f"/teacher/exams/{a}/sessions/{sesi_a}/lanjut", follow_redirects=False)
    assert r.status_code in (303, 307, 403)
    db.expire_all()
    assert db.get(ExamSession, sesi_a).status == "completed"                # siswa tidak bisa membuka sendiri


def test_sesi_otomatis_membaca_log():
    assert sesi_otomatis(None, []) == set()
