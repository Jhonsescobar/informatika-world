# Kesempatan melanjutkan ujian setelah terkirim otomatis (guru yang memutuskan).

from datetime import datetime, timedelta, timezone

from app.models.exam import ExamAnswer, ExamEvent, ExamSession, ExamViolation
from app.models.student import Student
from app.services.kesempatan import bisa_dilanjutkan, henti_terakhir, info_henti, menit_sah
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
    assert html.count('/lanjut"') == 1 and f"sessions/{sesi_a}/lanjut" in html and f"sessions/{sesi_b}/lanjut" not in html
    r = ani.post(f"/teacher/exams/{a}/sessions/{sesi_a}/lanjut", follow_redirects=False)
    assert r.status_code in (303, 307, 403)
    db.expire_all()
    assert db.get(ExamSession, sesi_a).status == "completed"                # siswa tidak bisa membuka sendiri


def test_henti_terakhir_tanpa_sesi():
    assert henti_terakhir(None, []) == {}


# ---------- sesi terputus: siswa menghilang sampai waktu habis (jaringan putus, layar padam) ----------

def _hilang(guru, db, data, masuk_siswa, nama="Ani", keluar=10, jawab=2, last_seen=None, judul="UH"):
    """Siswa mulai, menjawab `jawab` soal, lalu menghilang di menit `keluar` dari 30 menit. Waktu sudah lama habis.
    Halaman hasil guru dibuka untuk menutup sesinya dari log. Mengembalikan (klien siswa, ujian, sesi)."""
    c = masuk_siswa(data["siswa"][nama])
    a = buat_ujian(db, data, judul)
    sesi = _mulai(c, a)
    for s in data["soal"][:jawab]:
        c.post(f"/student/exam/events/{sesi}", json=[{"k": "pilih", "q": s["id"], "o": s["benar"]}])
    mulai = datetime.now(timezone.utc) - timedelta(minutes=120)
    obj = db.get(ExamSession, sesi)
    obj.started_at, obj.expires_at = mulai, mulai + timedelta(minutes=30)
    db.query(ExamEvent).filter(ExamEvent.session_id == sesi).update({ExamEvent.created_at: mulai + timedelta(minutes=keluar)})
    db.query(Student).filter(Student.id == data["siswa"][nama]).update({Student.last_seen: last_seen(mulai) if last_seen else None})
    db.commit()
    assert guru.get(f"/teacher/exams/{a}/results").status_code == 200        # menutup sesi dari log
    db.expire_all()
    assert db.get(ExamSession, sesi).status == "expired"
    return c, a, sesi


def test_sesi_terputus_menampilkan_menit_keluar_dan_saran(guru, db, data, masuk_siswa):
    c, a, sesi = _hilang(guru, db, data, masuk_siswa, keluar=10)
    h = info_henti(db, db.get(ExamSession, sesi))
    assert h.jenis == "terputus" and h.terpakai_menit == 10 and h.durasi_menit == 30 and h.saran_menit == 20
    html = guru.get(f"/teacher/exams/{a}/results").text
    assert "1 siswa terhenti sebelum waktu habis" in html and "keluar menit 10, saran sisa 20" in html
    assert "Keluar menit 10/30" in html and "Terputus (jaringan atau layar padam)" in html
    assert f'sessions/{sesi}/lanjut' in html and 'name="menit" value="20"' in html


def test_guru_menentukan_menit_bukan_saran_dan_jawaban_tetap(guru, db, data, masuk_siswa):
    c, a, sesi = _hilang(guru, db, data, masuk_siswa, keluar=10, jawab=2)
    r = guru.post(f"/teacher/exams/{a}/sessions/{sesi}/lanjut", data={"menit": "7"})
    assert r.headers["location"].endswith("pesan=lanjut")
    db.expire_all()
    s = db.get(ExamSession, sesi)
    assert s.status == "active" and s.score is None and s.submitted_at is None
    sisa = s.expires_at - datetime.now(timezone.utc)
    assert timedelta(minutes=6, seconds=50) < sisa <= timedelta(minutes=7)               # 7 menit, bukan saran 20
    assert db.query(ExamEvent).filter(ExamEvent.session_id == sesi, ExamEvent.kind == "kesempatan",
                                      ExamEvent.detail.like("%terputus%7 menit%")).count() == 1
    # siswa melanjutkan di sesi yang sama; dua jawaban dari log kembali, lalu dikirim dengan nilai benar
    assert c.post("/student/exam/start", data={"exam_id": str(a)}).headers["location"] == f"/student/exam/take/{sesi}"
    assert c.get(f"/student/exam/take/{sesi}").status_code == 200
    c.post(f"/student/exam/submit/{sesi}", data={f"question_{x['id']}": str(x["benar"]) for x in data["soal"][:2]})
    db.expire_all()
    assert db.get(ExamSession, sesi).score == 50 and db.get(ExamSession, sesi).status == "completed"
    assert not bisa_dilanjutkan(db, db.get(ExamSession, sesi))                           # sudah kirim sendiri: tombol hilang


def test_menit_boleh_lebih_besar_dari_saran_dan_kosong_memakai_saran(guru, db, data, masuk_siswa):
    c, a, sesi = _hilang(guru, db, data, masuk_siswa, keluar=25)                         # saran 5 menit
    assert info_henti(db, db.get(ExamSession, sesi)).saran_menit == 5
    guru.post(f"/teacher/exams/{a}/sessions/{sesi}/lanjut", data={"menit": "15"})
    db.expire_all()
    assert timedelta(minutes=14) < db.get(ExamSession, sesi).expires_at - datetime.now(timezone.utc) <= timedelta(minutes=15)
    c2, a2, sesi2 = _hilang(guru, db, data, masuk_siswa, nama="Budi", keluar=29, judul="UH 2")   # saran 1 menit
    guru.post(f"/teacher/exams/{a2}/sessions/{sesi2}/lanjut", data={"menit": ""})
    db.expire_all()
    assert db.get(ExamSession, sesi2).expires_at - datetime.now(timezone.utc) > timedelta(minutes=2, seconds=50)   # minimal 3 menit


def test_menit_tidak_valid_ditolak_tanpa_mengubah_apa_pun(guru, db, data, masuk_siswa):
    c, a, sesi = _hilang(guru, db, data, masuk_siswa, keluar=10)
    for nilai in ("0", "181", "-5", "5.5", "abc", "1e2"):
        r = guru.post(f"/teacher/exams/{a}/sessions/{sesi}/lanjut", data={"menit": nilai})
        assert r.headers["location"].endswith("pesan=lanjut_menit"), nilai
    db.expire_all()
    assert db.get(ExamSession, sesi).status == "expired"
    assert menit_sah("") is None and menit_sah(None) is None and menit_sah(" 12 ") == 12 and menit_sah("180") == 180
    assert "Menit tidak valid" in guru.get(f"/teacher/exams/{a}/results?pesan=lanjut_menit").text


def test_waktu_memang_habis_bukan_terputus(guru, db, data, masuk_siswa):
    c, a, sesi = _hilang(guru, db, data, masuk_siswa, keluar=30)                         # aktif sampai detik terakhir
    assert info_henti(db, db.get(ExamSession, sesi)) is None
    html = guru.get(f"/teacher/exams/{a}/results").text
    assert "terhenti sebelum waktu habis" not in html and "/lanjut" not in html
    r = guru.post(f"/teacher/exams/{a}/sessions/{sesi}/lanjut", data={"menit": "5"})
    assert r.headers["location"].endswith("pesan=lanjut_gagal")


def test_sinyal_hadir_dipakai_tapi_hanya_selama_waktu_ujian(guru, db, data, masuk_siswa):
    # jawaban terakhir menit 3, tetapi sinyal hadir terakhir menit 12: siswa terlihat sampai menit 12
    c, a, sesi = _hilang(guru, db, data, masuk_siswa, keluar=3, last_seen=lambda m: m + timedelta(minutes=12))
    assert info_henti(db, db.get(ExamSession, sesi)).terpakai_menit == 12
    # siswa baru membuka beranda SETELAH waktu habis: tidak boleh dianggap aktif sampai akhir
    c2, a2, sesi2 = _hilang(guru, db, data, masuk_siswa, nama="Budi", keluar=3, judul="UH 2",
                            last_seen=lambda m: m + timedelta(minutes=90))
    assert info_henti(db, db.get(ExamSession, sesi2)).terpakai_menit == 3


def test_terputus_lagi_setelah_dibuka_dihitung_dari_saat_dibuka(guru, db, data, masuk_siswa):
    c, a, sesi = _hilang(guru, db, data, masuk_siswa, keluar=10)
    guru.post(f"/teacher/exams/{a}/sessions/{sesi}/lanjut", data={"menit": "10"})
    # siswa tidak pernah kembali: waktu 10 menit itu lewat tanpa aktivitas
    s = db.get(ExamSession, sesi)
    dibuka = datetime.now(timezone.utc) - timedelta(minutes=60)
    s.expires_at = dibuka + timedelta(minutes=10)
    db.query(ExamEvent).filter(ExamEvent.session_id == sesi, ExamEvent.kind == "kesempatan").update({ExamEvent.created_at: dibuka})
    db.commit()
    guru.get(f"/teacher/exams/{a}/results")
    db.expire_all()
    s = db.get(ExamSession, sesi)
    assert s.status == "expired"
    h = info_henti(db, s)
    assert h and h.saran_menit == 10 and h.terpakai_menit == 20                          # utuh 10 menit yang diberi, tak terpakai


def test_sesi_otomatis_yang_sudah_dikirim_sendiri_setelah_dibuka_tidak_bisa_lagi(guru, db, data, masuk_siswa):
    ani = masuk_siswa(data["siswa"]["Ani"])
    a = buat_ujian(db, data, "UH")
    sesi = _mulai(ani, a)
    _kirim_otomatis(ani, sesi, data)
    guru.post(f"/teacher/exams/{a}/sessions/{sesi}/lanjut")
    ani.post(f"/student/exam/submit/{sesi}", data={f"question_{data['soal'][0]['id']}": str(data["soal"][0]["benar"])})   # kirim sendiri
    db.expire_all()
    assert not bisa_dilanjutkan(db, db.get(ExamSession, sesi))
    assert "/lanjut" not in guru.get(f"/teacher/exams/{a}/results").text


def test_kesempatan_terputus_dicatat_di_catatan_aksi(guru, db, data, masuk_siswa):
    from app.models.aksi_guru import AksiGuru
    c, a, sesi = _hilang(guru, db, data, masuk_siswa, keluar=10)
    guru.post(f"/teacher/exams/{a}/sessions/{sesi}/lanjut", data={"menit": "12"})
    c = db.query(AksiGuru).filter(AksiGuru.aksi == "Beri kesempatan").one()
    assert "terputus" in c.rincian and "menit 10 dari 30" in c.rincian and "diberi 12 menit (saran 20)" in c.rincian
