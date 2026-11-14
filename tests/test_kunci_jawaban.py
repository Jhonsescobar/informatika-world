# tests/test_kunci_jawaban.py
# Jawaban pilihan ganda terkunci 1 menit setelah pertama dipilih (anti menyalin jawaban teman belakangan).

import json

from sqlalchemy import text

from app.models.exam import ExamEvent, ExamSession
from tests.data_uji import buat_ujian


def mulai(c, exam_id):
    return int(c.post("/student/exam/start", data={"exam_id": str(exam_id)}).headers["location"].rsplit("/", 1)[1])


def pilih(c, sesi, soal, opsi):
    r = c.post(f"/student/exam/events/{sesi}", content=json.dumps([{"k": "pilih", "q": soal, "o": opsi}]),
               headers={"content-type": "application/json"})
    return r.json()


def mundurkan_log(db, sesi, detik):
    """Seolah pilihan dibuat `detik` yang lalu."""
    db.execute(text("UPDATE exam_events SET created_at = created_at - make_interval(secs => :d) WHERE session_id = :s"),
               {"d": detik, "s": sesi})
    db.commit()


def test_ganti_jawaban_sebelum_1_menit_boleh(db, data, masuk_siswa):
    e = buat_ujian(db, data, "A")
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = mulai(ani, e)
    s0 = data["soal"][0]
    pilih(ani, sesi, s0["id"], s0["salah"])
    mundurkan_log(db, sesi, 30)                        # 30 detik kemudian: masih boleh diganti
    assert pilih(ani, sesi, s0["id"], s0["benar"])["terkunci"] == []
    jawab = {f"question_{s['id']}": str(s["benar"]) for s in data["soal"]}
    ani.post(f"/student/exam/submit/{sesi}", data=jawab)
    db.expire_all()
    assert db.get(ExamSession, sesi).score == 100


def test_setelah_1_menit_jawaban_terkunci_di_server(db, data, masuk_siswa):
    e = buat_ujian(db, data, "A")
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = mulai(ani, e)
    s0 = data["soal"][0]
    pilih(ani, sesi, s0["id"], s0["salah"])
    mundurkan_log(db, sesi, 70)                        # lewat 1 menit (+ toleransi 5 dtk)
    # mencoba mengganti lewat log (misalnya setelah melihat jawaban teman): ditolak, tidak dicatat
    assert pilih(ani, sesi, s0["id"], s0["benar"])["terkunci"] == [s0["id"]]
    assert db.query(ExamEvent).filter_by(session_id=sesi, kind="pilih").count() == 1
    # mencoba mengganti lewat form kiriman akhir (JavaScript dimatikan / diakali): tetap jawaban terkunci
    jawab = {f"question_{s['id']}": str(s["benar"]) for s in data["soal"]}
    ani.post(f"/student/exam/submit/{sesi}", data=jawab)
    db.expire_all()
    assert db.get(ExamSession, sesi).score == 75          # soal 1 tetap salah
    catatan = db.query(ExamEvent).filter_by(session_id=sesi, kind="kunci").one()
    assert "1 jawaban diganti setelah terkunci" in catatan.detail


def test_muat_ulang_halaman_tetap_terkunci(db, data, masuk_siswa):
    e = buat_ujian(db, data, "A")
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = mulai(ani, e)
    s0, s1 = data["soal"][:2]
    pilih(ani, sesi, s0["id"], s0["salah"])
    mundurkan_log(db, sesi, 70)
    pilih(ani, sesi, s1["id"], s1["benar"])            # soal 2 baru dipilih: belum terkunci
    html = ani.get(f"/student/exam/take/{sesi}").text
    blok0 = html.split(f'data-soal="{s0["id"]}"')[1].split("</fieldset>")[0]
    blok1 = html.split(f'data-soal="{s1["id"]}"')[1].split("</fieldset>")[0]
    assert 'data-terkunci="1"' in blok0 and blok0.count(" disabled") == 3 and f'value="{s0["salah"]}" required data-q="{s0["id"]}" checked' in blok0
    assert "data-kunci-sisa=" in blok1 and " disabled" not in blok1
    sisa = int(blok1.split('data-kunci-sisa="')[1].split('"')[0])
    assert 50 <= sisa <= 60


def test_soal_belum_dijawab_tidak_terkunci(db, data, masuk_siswa):
    e = buat_ujian(db, data, "A")
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = mulai(ani, e)
    html = ani.get(f"/student/exam/take/{sesi}").text
    assert 'data-terkunci="1"' not in html and 'data-kunci-sisa="' not in html
    assert "TERKUNCI 1 menit setelah kamu memilihnya" in html


def test_waktu_habis_dinilai_dengan_jawaban_terkunci(guru, db, data, masuk_siswa):
    e = buat_ujian(db, data, "A")
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = mulai(ani, e)
    s0 = data["soal"][0]
    pilih(ani, sesi, s0["id"], s0["benar"])
    mundurkan_log(db, sesi, 70)
    # catatan sesudah terkunci yang dipaksa masuk ke database tetap tidak berlaku
    db.execute(text("INSERT INTO exam_events (session_id, kind, question_id, option_id) VALUES (:s, 'pilih', :q, :o)"),
               {"s": sesi, "q": s0["id"], "o": s0["salah"]})
    db.execute(text("UPDATE exam_sessions SET expires_at = now() - interval '10 minutes' WHERE id = :s"), {"s": sesi})
    db.commit()
    guru.get(f"/teacher/exams/{e}/results")
    db.expire_all()
    assert db.get(ExamSession, sesi).score == 25


def test_log_guru_menampilkan_percobaan_ganti(guru, db, data, masuk_siswa):
    e = buat_ujian(db, data, "A")
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = mulai(ani, e)
    s0 = data["soal"][0]
    pilih(ani, sesi, s0["id"], s0["salah"])
    mundurkan_log(db, sesi, 70)
    ani.post(f"/student/exam/submit/{sesi}", data={f"question_{s['id']}": str(s["benar"]) for s in data["soal"]})
    assert "Mengganti jawaban yang sudah terkunci" in guru.get(f"/teacher/exams/{e}/sessions/{sesi}").text
