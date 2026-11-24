# tests/test_remedial_bank.py
# Remedial dengan bank soal berbeda dan saran nilai akhir. Nilai awal (sesi pertama) tetap di rekap;
# sesi berikutnya = remedial, dihitung menurut aturan tiap ujian.

import io

from openpyxl import load_workbook

from app.models.aksi_guru import AksiGuru
from app.models.exam import Exam, ExamSession
from app.models.question import Question, QuestionBank, QuestionOption
from app.services.nilai_remedial import ATURAN, aturan_sah, nilai_dipakai, saran_akhir
from app.services.perkembangan import riwayat_siswa
from app.services.rekap import awal_dan_remedial, rekap_kelas
from tests.data_uji import buat_ujian, kerjakan


def baris(db, nama="Ani"):
    return next(b for b in rekap_kelas(db, "VII")["baris"] if b["siswa"].name == nama)


def bank_remedial(db, data, jumlah=2, poin=10, kelas="VII", judul="Bank remedial"):
    b = QuestionBank(title=judul, class_target=kelas, teacher_id=data["guru"])
    db.add(b)
    db.flush()
    for i in range(jumlah):
        q = Question(bank_id=b.id, text=f"Soal remedial {i + 1}", points=poin, question_type="pg")
        db.add(q)
        db.flush()
        db.add_all([QuestionOption(question_id=q.id, text=f"R{i + 1}{h}", is_correct=(h == "A")) for h in "ABCD"])
    db.commit()
    return b.id


def kerjakan_remedial(c, db, exam_id, benar_semua=True) -> int:
    """Siswa memulai ujian (remedial yang sudah disetujui) dan mengirim: semua benar, atau semua salah."""
    r = c.post("/student/exam/start", data={"exam_id": str(exam_id)})
    assert "/student/exam/take/" in r.headers["location"], r.headers["location"]
    sesi = int(r.headers["location"].rsplit("/", 1)[1])
    s = db.get(ExamSession, sesi)
    form = {}
    for qid in (int(x) for x in s.question_ids.split(",")):
        opsi = db.query(QuestionOption).filter(QuestionOption.question_id == qid).order_by(QuestionOption.id).all()
        form[f"question_{qid}"] = str((next(o for o in opsi if o.is_correct) if benar_semua else next(o for o in opsi if not o.is_correct)).id)
    assert c.post(f"/student/exam/submit/{sesi}", data=form).status_code == 303
    return sesi


def awal_lalu_remedial(guru, db, data, masuk_siswa, exam_id, benar_awal=2, benar_rem=4):
    """Ani: nilai awal 50 (2 dari 4), lalu remedial dengan soal yang sama (4 dari 4 = 100)."""
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = kerjakan(ani, exam_id, data, benar_awal)
    guru.post(f"/teacher/exams/{exam_id}/sessions/{sesi}/remedial")
    kerjakan(ani, exam_id, data, benar_rem)
    return ani, sesi


# ---- aturan murni -------------------------------------------------------------------------
def test_contoh_67_dan_89():
    assert saran_akhir("kkm", 67, 89, 75) == 75
    assert saran_akhir("rata", 67, 89, 75) == 78
    assert saran_akhir("tinggi", 67, 89, 75) == 89
    assert nilai_dipakai("saran", 67, 89, 75) == 67


def test_saran_tidak_pernah_di_bawah_nilai_awal():
    for aturan in ("kkm", "rata", "tinggi"):
        assert saran_akhir(aturan, 80, 50, 75) == 80, aturan
        assert saran_akhir(aturan, 40, None, 75) == 40, aturan


def test_remedial_di_bawah_kkm_dipakai_apa_adanya():
    assert saran_akhir("kkm", 40, 60, 75) == 60
    assert saran_akhir("rata", 40, 61, 75) == 50.5


def test_awal_sudah_di_atas_kkm_tidak_berubah():
    assert saran_akhir("kkm", 80, 100, 75) == 80


def test_aturan_sah():
    assert aturan_sah("kkm") == "kkm" and aturan_sah(" rata ") == "rata"
    assert aturan_sah("ngawur") is None and aturan_sah(None, "saran") == "saran" and aturan_sah("") is None
    assert set(ATURAN) == {"saran", "kkm", "rata", "tinggi"}


# ---- rekap ---------------------------------------------------------------------------------
def test_ujian_baru_bawaannya_hanya_saran(guru, db, data):
    guru.post("/teacher/kelas", data={"kelas": "VII"})
    guru.post("/teacher/exams/create", data={"title": "Baru", "bank_id": str(data["bank"]), "class_target": "VII",
                                             "duration_minutes": "20"})
    assert db.query(Exam).filter(Exam.title == "Baru").one().remedial_aturan == "saran"


def test_hanya_saran_rekap_tetap_nilai_awal(guru, db, data, masuk_siswa):
    e = buat_ujian(db, data, "A", kkm=75)
    awal_lalu_remedial(guru, db, data, masuk_siswa, e)
    b = baris(db)
    assert b["awal"][e] == 50 and b["remedial"][e] == 100
    assert b["ujian"][e] == 50 and b["akhir"] == 50, "rekap harus tetap nilai awal"
    assert b["saran"][e] == 75, "saran memakai rumus dibatasi KKM"


def test_aturan_dibatasi_kkm_dipakai_di_rekap(guru, db, data, masuk_siswa):
    e = buat_ujian(db, data, "A", kkm=75, remedial_aturan="kkm")
    awal_lalu_remedial(guru, db, data, masuk_siswa, e)
    b = baris(db)
    assert b["ujian"][e] == 75 and b["akhir"] == 75 and b["awal"][e] == 50


def test_aturan_rata_dan_tertinggi(guru, db, data, masuk_siswa):
    e1 = buat_ujian(db, data, "Rata", remedial_aturan="rata")
    e2 = buat_ujian(db, data, "Tinggi", remedial_aturan="tinggi")
    for e in (e1, e2):
        awal_lalu_remedial(guru, db, data, masuk_siswa, e)
    b = baris(db)
    assert b["ujian"][e1] == 75 and b["ujian"][e2] == 100


def test_tanpa_remedial_tidak_ada_saran(guru, db, data, masuk_siswa):
    e = buat_ujian(db, data, "A")
    kerjakan(masuk_siswa(data["siswa"]["Ani"]), e, data, 3)
    b = baris(db)
    assert b["ujian"][e] == 75 and b["remedial"][e] is None and b["saran"][e] is None


def test_remedial_lebih_rendah_tidak_menurunkan(guru, db, data, masuk_siswa):
    e = buat_ujian(db, data, "A", remedial_aturan="tinggi")
    awal_lalu_remedial(guru, db, data, masuk_siswa, e, benar_awal=3, benar_rem=1)
    assert baris(db)["ujian"][e] == 75


# ---- bank soal remedial --------------------------------------------------------------------
def test_remedial_memakai_bank_lain_dan_nilainya_benar(guru, db, data, masuk_siswa):
    rem = bank_remedial(db, data, jumlah=2, poin=10)
    e = buat_ujian(db, data, "A", kkm=75, remedial_aturan="tinggi", remedial_bank_id=rem)
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = kerjakan(ani, e, data, 2)
    guru.post(f"/teacher/exams/{e}/sessions/{sesi}/remedial")
    baru = kerjakan_remedial(ani, db, e, benar_semua=True)

    ids = [int(x) for x in db.get(ExamSession, baru).question_ids.split(",")]
    assert {q.bank_id for q in db.query(Question).filter(Question.id.in_(ids))} == {rem}, "remedial harus dari bank remedial"
    ar = awal_dan_remedial(db, [e])
    assert ar[(data["siswa"]["Ani"], e)] == (50.0, 100.0), "persen remedial dihitung dari poin bank remedial, bukan bank ujian"
    assert baris(db)["ujian"][e] == 100


def test_sesi_pertama_tetap_dari_bank_ujian(guru, db, data, masuk_siswa):
    rem = bank_remedial(db, data)
    e = buat_ujian(db, data, "A", remedial_bank_id=rem)
    sesi = kerjakan(masuk_siswa(data["siswa"]["Ani"]), e, data, 3)
    ids = [int(x) for x in db.get(ExamSession, sesi).question_ids.split(",")]
    assert {q.bank_id for q in db.query(Question).filter(Question.id.in_(ids))} == {data["bank"]}


def test_tanpa_bank_remedial_soal_sama(guru, db, data, masuk_siswa):
    e = buat_ujian(db, data, "A")
    ani, sesi = awal_lalu_remedial(guru, db, data, masuk_siswa, e)
    sesi_rem = db.query(ExamSession).filter(ExamSession.exam_id == e).order_by(ExamSession.id.desc()).first()
    ids = [int(x) for x in sesi_rem.question_ids.split(",")]
    assert {q.bank_id for q in db.query(Question).filter(Question.id.in_(ids))} == {data["bank"]}


def test_nilai_remedial_tetap_benar_walau_bank_remedial_diganti_sebelum_dipakai(guru, db, data, masuk_siswa):
    r1, r2 = bank_remedial(db, data, judul="R1"), bank_remedial(db, data, jumlah=5, poin=4, judul="R2")
    e = buat_ujian(db, data, "A", remedial_aturan="tinggi", remedial_bank_id=r1)
    guru.post(f"/teacher/exams/{e}/remedial-pengaturan", data={"bank": str(r2), "aturan": "tinggi"})
    db.expire_all()
    assert db.get(Exam, e).remedial_bank_id == r2


# ---- pengaturan oleh guru ------------------------------------------------------------------
def test_guru_mengatur_remedial_dan_tercatat(guru, db, data):
    rem = bank_remedial(db, data)
    e = buat_ujian(db, data, "A")
    r = guru.post(f"/teacher/exams/{e}/remedial-pengaturan", data={"bank": str(rem), "aturan": "kkm"})
    assert r.headers["location"].endswith("pesan=remedial")
    db.expire_all()
    x = db.get(Exam, e)
    assert (x.remedial_bank_id, x.remedial_aturan) == (rem, "kkm")
    cat = db.query(AksiGuru).filter(AksiGuru.aksi == "Ubah pengaturan remedial").all()
    assert len(cat) == 1 and "Dibatasi KKM" in cat[0].rincian
    guru.post(f"/teacher/exams/{e}/remedial-pengaturan", data={"bank": str(rem), "aturan": "kkm"})   # sama: tidak dicatat ulang
    assert db.query(AksiGuru).filter(AksiGuru.aksi == "Ubah pengaturan remedial").count() == 1


def test_pengaturan_tidak_valid_ditolak(guru, db, data):
    kosong = bank_remedial(db, data, jumlah=0, judul="Kosong")
    kelas_lain = bank_remedial(db, data, kelas="VIII", judul="Kelas VIII")
    e = buat_ujian(db, data, "A")
    kasus = [{"bank": str(kosong), "aturan": "kkm"}, {"bank": str(kelas_lain), "aturan": "kkm"},
             {"bank": str(data["bank"]), "aturan": "kkm"}, {"bank": "99999", "aturan": "kkm"},
             {"bank": "abc", "aturan": "kkm"}, {"bank": "", "aturan": "ngawur"}, {"bank": "", "aturan": ""}]
    for k in kasus:
        assert "error=remedial" in guru.post(f"/teacher/exams/{e}/remedial-pengaturan", data=k).headers["location"], k
    db.expire_all()
    x = db.get(Exam, e)
    assert (x.remedial_bank_id, x.remedial_aturan) == (None, "saran")


def test_bank_remedial_terkunci_setelah_dipakai(guru, db, data, masuk_siswa):
    r1, r2 = bank_remedial(db, data, judul="R1"), bank_remedial(db, data, judul="R2")
    e = buat_ujian(db, data, "A", remedial_bank_id=r1)
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = kerjakan(ani, e, data, 1)
    guru.post(f"/teacher/exams/{e}/sessions/{sesi}/remedial")
    kerjakan_remedial(ani, db, e)
    r = guru.post(f"/teacher/exams/{e}/remedial-pengaturan", data={"bank": str(r2), "aturan": "kkm"})
    assert "error=remedial_terkunci" in r.headers["location"]
    db.expire_all()
    assert db.get(Exam, e).remedial_bank_id == r1
    # aturan nilai tetap boleh diganti
    guru.post(f"/teacher/exams/{e}/remedial-pengaturan", data={"bank": str(r1), "aturan": "rata"})
    db.expire_all()
    assert db.get(Exam, e).remedial_aturan == "rata"


def test_bank_remedial_tidak_bisa_dihapus_selama_dipakai(guru, db, data):
    rem = bank_remedial(db, data)
    buat_ujian(db, data, "A", remedial_bank_id=rem)
    r = guru.post(f"/teacher/question-banks/{rem}/delete")
    assert "pesan=bank_remedial" in r.headers["location"]
    db.expire_all()
    assert db.get(QuestionBank, rem) is not None
    assert "dipakai sebagai soal remedial" in guru.get(r.headers["location"]).text


def test_soal_bank_remedial_terkunci_setelah_remedial_dimulai(guru, db, data, masuk_siswa):
    from app.routers.teacher.bank_soal import bank_terkunci
    rem = bank_remedial(db, data)
    e = buat_ujian(db, data, "A", remedial_bank_id=rem)
    assert not bank_terkunci(db, rem)
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = kerjakan(ani, e, data, 1)
    assert not bank_terkunci(db, rem), "sesi awal memakai bank ujian, bukan bank remedial"
    guru.post(f"/teacher/exams/{e}/sessions/{sesi}/remedial")
    kerjakan_remedial(ani, db, e)
    assert bank_terkunci(db, rem)


# ---- tampilan dan ekspor -------------------------------------------------------------------
def test_halaman_nilai_menampilkan_kolom_remedial(guru, db, data, masuk_siswa):
    guru.post("/teacher/kelas", data={"kelas": "VII"})
    e = buat_ujian(db, data, "Formatif Remed", kkm=75)
    assert ">Remedial<" not in guru.get("/teacher/grades/class/VII").text
    awal_lalu_remedial(guru, db, data, masuk_siswa, e)
    html = guru.get("/teacher/grades/class/VII").text
    assert ">Remedial<" in html and "saran 75" in html and "50" in html


def test_halaman_ujian_memuat_pengaturan_remedial(guru, db, data):
    guru.post("/teacher/kelas", data={"kelas": "VII"})
    rem = bank_remedial(db, data, judul="Bank Khusus")
    buat_ujian(db, data, "A", remedial_bank_id=rem, remedial_aturan="kkm")
    html = guru.get("/teacher/exams").text
    assert "remedial-pengaturan" in html and "Bank Khusus" in html and "Dibatasi KKM" in html and "Sama dengan ujian ini" in html


def test_excel_punya_lembar_remedial_hanya_bila_ada(guru, db, data, masuk_siswa):
    e = buat_ujian(db, data, "A", kkm=75)
    kerjakan(masuk_siswa(data["siswa"]["Budi"]), e, data, 3)
    r = guru.get("/teacher/grades/class/VII/export")
    assert "Remedial VII" not in load_workbook(io.BytesIO(r.content)).sheetnames
    awal_lalu_remedial(guru, db, data, masuk_siswa, e)
    wb = load_workbook(io.BytesIO(guru.get("/teacher/grades/class/VII/export").content))
    assert "Remedial VII" in wb.sheetnames
    ws = wb["Remedial VII"]
    isi = [[c.value for c in row] for row in ws.iter_rows(min_row=5)]
    assert isi == [["Ani", "VII.1", "A", 50.0, 100.0, 75, "Dibatasi KKM", "Tidak (hanya saran)", 50.0]]


def test_perkembangan_siswa_mengikuti_aturan(guru, db, data, masuk_siswa):
    e1 = buat_ujian(db, data, "Saran", kkm=75)
    awal_lalu_remedial(guru, db, data, masuk_siswa, e1)
    p = riwayat_siswa(db, data["siswa"]["Ani"])
    assert [t["nilai"] for t in p["titik"]] == [50.0]
    db.get(Exam, e1).remedial_aturan = "tinggi"
    db.commit()
    assert [t["nilai"] for t in riwayat_siswa(db, data["siswa"]["Ani"])["titik"]] == [100.0]


def test_analisis_butir_hanya_percobaan_pertama(guru, db, data, masuk_siswa):
    from app.services.analisis import analisis_butir, sesi_terbaik
    rem = bank_remedial(db, data)
    e = buat_ujian(db, data, "A", remedial_bank_id=rem)
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = kerjakan(ani, e, data, 1)
    guru.post(f"/teacher/exams/{e}/sessions/{sesi}/remedial")
    kerjakan_remedial(ani, db, e)
    assert [s.id for s in sesi_terbaik(db, e)] == [sesi]
    assert analisis_butir(db, db.get(Exam, e)) is not None


def test_halaman_hasil_tetap_terbuka_dengan_sesi_remedial_bank_lain(guru, db, data, masuk_siswa):
    rem = bank_remedial(db, data)
    e = buat_ujian(db, data, "A", remedial_bank_id=rem)
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = kerjakan(ani, e, data, 1)
    guru.post(f"/teacher/exams/{e}/sessions/{sesi}/remedial")
    baru = kerjakan_remedial(ani, db, e)
    assert guru.get(f"/teacher/exams/{e}/results").status_code == 200
    assert guru.get(f"/teacher/exams/{e}/sessions/{baru}").status_code == 200
    assert guru.get(f"/teacher/exams/{e}/analytics").status_code == 200
