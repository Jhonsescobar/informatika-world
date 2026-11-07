# tests/test_fitur.py
# Fitur kelas sehari-hari: rombel massal, hapus siswa, remedial siswa, kisi-kisi, anti-cheat, log aktivitas.

import json

from app.models.academic import Enrollment
from app.models.exam import ExamEvent, ExamSession, ExamViolation, RemedialRequest
from app.models.material import Material
from app.models.student import Student
from tests.data_uji import buat_ujian, kerjakan


def test_pindah_rombel_massal_tanpa_ganda(guru, db, data):
    ids = [data["siswa"]["Ani"], data["siswa"]["Budi"]]
    r = guru.post("/teacher/students/bulk", data={"action": "move", "rombel_id": str(data["rombel"]["VIII.1"]),
                                                  "student_ids": [str(i) for i in ids], "kembali": "/teacher/students"})
    assert "pesan=pindah&n=2" in r.headers["location"]
    for sid in ids:
        assert [e.rombel_id for e in db.query(Enrollment).filter_by(student_id=sid)] == [data["rombel"]["VIII.1"]]
    r = guru.post("/teacher/students/bulk", data={"action": "move", "rombel_id": str(data["rombel"]["VII.1"]),
                                                  "student_ids": [str(ids[0])], "kembali": "https://situs-lain.example"})
    assert r.headers["location"].startswith("/teacher/students")


def test_hapus_siswa_harus_konfirmasi(guru, db, data, masuk_siswa):
    sid = data["siswa"]["Eka"]
    kerjakan(masuk_siswa(sid), buat_ujian(db, data, "A"), data, 2)
    r = guru.post("/teacher/students/bulk", data={"action": "delete", "student_ids": [str(sid)], "kembali": "/teacher/students"})
    assert "/teacher/students/delete?ids=" in r.headers["location"]
    guru.post("/teacher/students/delete", data={"ids": str(sid), "confirm_text": "hapuss"})
    assert db.get(Student, sid) is not None
    guru.post("/teacher/students/delete", data={"ids": str(sid), "confirm_text": "HAPUS"})
    db.expire_all()
    assert db.get(Student, sid) is None
    assert db.query(ExamSession).filter_by(student_id=sid).count() == 0


def test_remedial_diajukan_siswa_lalu_disetujui(guru, db, data, masuk_siswa):
    a = buat_ujian(db, data, "A")
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = kerjakan(ani, a, data, 0)
    assert "Ajukan remedial" in ani.get(f"/student/exam/result/{sesi}").text
    ani.post(f"/student/exam/remedial/{sesi}")
    ani.post(f"/student/exam/remedial/{sesi}")
    req = db.query(RemedialRequest).filter_by(session_id=sesi).one()      # klik ganda: tetap satu
    ani.post(f"/teacher/remedial/{req.id}/approve")                       # siswa tidak bisa menyetujui sendiri
    db.expire_all()
    assert db.get(RemedialRequest, req.id).status == "pending"
    guru.post(f"/teacher/remedial/{req.id}/approve")
    sesi2 = kerjakan(ani, a, data, 4)
    assert sesi2 != sesi
    assert "Ajukan remedial" not in ani.get(f"/student/exam/result/{sesi2}").text


def test_nilai_lulus_tidak_bisa_minta_remedial(db, data, masuk_siswa):
    a = buat_ujian(db, data, "A")
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = kerjakan(ani, a, data, 3)          # 75%
    ani.post(f"/student/exam/remedial/{sesi}")
    assert db.query(RemedialRequest).count() == 0


def test_kisi_kisi_per_tingkat_dan_batas_waktu(guru, db, data, masuk_siswa):
    m7 = Material(title="Kisi VII", class_target="VII", description="", content="isi", teacher_id=data["guru"])
    m8 = Material(title="Kisi VIII", class_target="VIII", description="", content="isi", teacher_id=data["guru"])
    db.add_all([m7, m8])
    db.commit()
    ani = masuk_siswa(data["siswa"]["Ani"])
    assert ani.get(f"/student/materials/{m7.id}").status_code == 303        # belum dibuka guru
    for m in (m7, m8):
        guru.post(f"/teacher/materials/{m.id}/visibility", data={"action": "open", "close_at": ""})
    daftar = ani.get("/student/materials").text
    assert "Kisi VII" in daftar and "Kisi VIII" not in daftar
    assert ani.get(f"/student/materials/{m8.id}").status_code == 303        # beda tingkat lewat URL
    baca = ani.get(f"/student/materials/{m7.id}").text
    assert "iw-guard.js" in baca and 'class="watermark"' in baca
    guru.post(f"/teacher/materials/{m7.id}/visibility", data={"action": "open", "close_at": "2020-01-01T08:00"})
    assert ani.get(f"/student/materials/{m7.id}").status_code == 303        # batas waktu lewat


def test_pelanggaran_dihitung_server(db, data, masuk_siswa):
    a = buat_ujian(db, data, "A")
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = int(ani.post("/student/exam/start", data={"exam_id": str(a)}).headers["location"].rsplit("/", 1)[1])
    hitung = [ani.post(f"/student/exam/violation/{sesi}", data={"kind": "pindah_tab"}).json()["count"] for _ in range(3)]
    assert hitung == [1, 2, 3]
    masuk_siswa(data["siswa"]["Budi"]).post(f"/student/exam/violation/{sesi}", data={"kind": "pindah_tab"})
    ani.post(f"/student/exam/violation/{sesi}", data={"kind": "<script>alert(1)</script>"})
    jenis = [v.kind for v in db.query(ExamViolation).filter_by(session_id=sesi).order_by(ExamViolation.id)]
    assert len(jenis) == 4 and jenis[-1] == "lainnya"


def test_log_aktivitas_hanya_soal_milik_sesi(db, data, masuk_siswa):
    a = buat_ujian(db, data, "A")
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = int(ani.post("/student/exam/start", data={"exam_id": str(a)}).headers["location"].rsplit("/", 1)[1])
    s0 = data["soal"][0]
    kirim = [{"k": "pilih", "q": s0["id"], "o": s0["benar"]},
             {"k": "pilih", "q": 999999, "o": 1},                                # soal bukan milik sesi
             {"k": "pilih", "q": s0["id"], "o": data["soal"][1]["benar"]}]       # opsi milik soal lain
    r = ani.post(f"/student/exam/events/{sesi}", content=json.dumps(kirim),
                 headers={"content-type": "application/json"})
    assert r.json() == {"ok": True, "saved": 1}
    pilih = db.query(ExamEvent).filter_by(session_id=sesi, kind="pilih").all()
    assert len(pilih) == 1
    budi = masuk_siswa(data["siswa"]["Budi"])
    budi.post(f"/student/exam/events/{sesi}", content=json.dumps(kirim[:1]),
              headers={"content-type": "application/json"})
    assert db.query(ExamEvent).filter_by(session_id=sesi, kind="pilih").count() == 1


def test_ujian_draf_dan_tingkat_lain_tidak_tampil(db, data, masuk_siswa):
    buat_ujian(db, data, "Ujian Draf VII", terbit=False)
    buat_ujian(db, data, "Ujian Kelas VIII", kelas="VIII")
    buat_ujian(db, data, "Ujian Terbit VII")
    html = masuk_siswa(data["siswa"]["Ani"]).get("/student/dashboard").text
    assert "Ujian Terbit VII" in html and "Ujian Draf VII" not in html and "Ujian Kelas VIII" not in html
