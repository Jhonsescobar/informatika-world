# tests/test_kkm.py
# KKM bertingkat: KKM tahun ajaran, KKM komponen, dan KKM ujian (penanda tuntas saja).

import io
import re

from openpyxl import load_workbook

from app.models.academic import AcademicYear
from app.models.exam import Exam
from app.models.grade import ScoreComponent
from app.services.rekap import rekap_kelas
from tests.data_uji import buat_ujian, kerjakan


def komponen(db, data, nama="Formatif", bobot=100, kkm=None):
    k = ScoreComponent(name=nama, weight=bobot, class_target="VII", teacher_id=data["guru"], kkm=kkm)
    db.add(k)
    db.commit()
    return k.id


def baris(db, nama):
    return next(b for b in rekap_kelas(db, "VII")["baris"] if b["siswa"].name == nama)


def test_kkm_tahun_ajaran_default_75(db, data):
    assert db.get(AcademicYear, data["tahun"]).kkm == 75


def test_nilai_tepat_di_kkm_tuntas_dan_di_bawahnya_belum(db, data, masuk_siswa):
    e = buat_ujian(db, data)
    kerjakan(masuk_siswa(data["siswa"]["Ani"]), e, data, 3)     # 75
    kerjakan(masuk_siswa(data["siswa"]["Budi"]), e, data, 2)    # 50
    assert baris(db, "Ani")["tuntas"] is True and baris(db, "Ani")["akhir"] == 75.0
    assert baris(db, "Budi")["tuntas"] is False


def test_kkm_ujian_hanya_penanda_tidak_mengubah_nilai_akhir(db, data, masuk_siswa):
    e = buat_ujian(db, data, kkm=90)
    kerjakan(masuk_siswa(data["siswa"]["Ani"]), e, data, 3)     # 75
    b = baris(db, "Ani")
    assert b["akhir"] == 75.0 and b["tuntas"] is True            # nilai akhir tetap pakai KKM tahun ajaran
    assert b["tuntas_ujian"][e] is False                         # tapi ujian ini belum tuntas (KKM 90)


def test_kkm_komponen_dipakai_bila_ujian_kosong(db, data, masuk_siswa):
    k = komponen(db, data, kkm=80)
    e = buat_ujian(db, data, komponen=k)
    kerjakan(masuk_siswa(data["siswa"]["Ani"]), e, data, 3)     # 75 < 80
    kerjakan(masuk_siswa(data["siswa"]["Budi"]), e, data, 4)    # 100
    assert baris(db, "Ani")["tuntas_komponen"][k] is False and baris(db, "Ani")["tuntas_ujian"][e] is False
    assert baris(db, "Budi")["tuntas_komponen"][k] is True and baris(db, "Budi")["tuntas_ujian"][e] is True


def test_kkm_ujian_mengalahkan_kkm_komponen(db, data, masuk_siswa):
    k = komponen(db, data, kkm=80)
    e = buat_ujian(db, data, komponen=k, kkm=70)
    kerjakan(masuk_siswa(data["siswa"]["Ani"]), e, data, 3)     # 75: tuntas menurut KKM ujian 70
    assert baris(db, "Ani")["tuntas_ujian"][e] is True
    assert baris(db, "Ani")["tuntas_komponen"][k] is False       # komponen tetap memakai KKM 80


def test_kkm_komponen_kosong_ikut_tahun_ajaran(db, data, masuk_siswa):
    k = komponen(db, data, kkm=None)
    e = buat_ujian(db, data, komponen=k)
    kerjakan(masuk_siswa(data["siswa"]["Ani"]), e, data, 3)     # 75 = KKM tahun ajaran
    assert baris(db, "Ani")["tuntas_komponen"][k] is True


def test_ubah_kkm_tahun_ajaran_langsung_berlaku(db, data, masuk_siswa):
    e = buat_ujian(db, data)
    kerjakan(masuk_siswa(data["siswa"]["Budi"]), e, data, 2)    # 50
    assert baris(db, "Budi")["tuntas"] is False
    db.get(AcademicYear, data["tahun"]).kkm = 50
    db.commit()
    assert baris(db, "Budi")["tuntas"] is True


def test_batas_remedial_tetap_60_walau_kkm_ujian_tinggi(db, data, masuk_siswa):
    e = buat_ujian(db, data, kkm=90)
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi_ani = kerjakan(ani, e, data, 3)                        # 75: belum tuntas, tapi di atas 60
    html_ani = ani.get(f"/student/exam/result/{sesi_ani}").text
    assert "Belum tuntas" in html_ani and "Ajukan remedial" not in html_ani
    budi = masuk_siswa(data["siswa"]["Budi"])
    sesi_budi = kerjakan(budi, e, data, 2)                      # 50: boleh remedial
    assert "Ajukan remedial" in budi.get(f"/student/exam/result/{sesi_budi}").text


def test_siswa_hanya_melihat_tuntas_tanpa_angka_kkm(db, data, masuk_siswa):
    e = buat_ujian(db, data, kkm=90)
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = kerjakan(ani, e, data, 3)
    html = ani.get(f"/student/exam/result/{sesi}").text
    assert "score-no" in html and "KKM" not in html and "90" not in html.split("Skor kamu")[0]


def test_guru_melihat_status_dan_kkm_ujian(db, data, masuk_siswa, guru):
    e = buat_ujian(db, data, kkm=70)
    kerjakan(masuk_siswa(data["siswa"]["Ani"]), e, data, 3)     # 75 ≥ 70
    kerjakan(masuk_siswa(data["siswa"]["Budi"]), e, data, 2)    # 50 < 70
    html = guru.get(f"/teacher/exams/{e}/results").text
    assert "KKM ujian ini 70" in html
    assert re.search(r'chip-teal"[^>]*>75%', html)          # 75 ≥ 70: hijau
    assert re.search(r'chip-danger"[^>]*>50%', html)         # 50 < 70: merah
    assert ">Belum tuntas<" not in html and ">Tuntas<" not in html   # tanpa tulisan status, warna saja


def test_validasi_kkm_ujian_di_server(db, data, guru):
    e = buat_ujian(db, data)
    for salah in ("101", "-1", "abc", "70.5"):
        r = guru.post(f"/teacher/exams/{e}/kkm", data={"kkm": salah})
        assert "error=kkm" in r.headers["location"], salah
    db.expire_all()
    assert db.get(Exam, e).kkm is None
    guru.post(f"/teacher/exams/{e}/kkm", data={"kkm": "80"})
    db.expire_all()
    assert db.get(Exam, e).kkm == 80
    guru.post(f"/teacher/exams/{e}/kkm", data={"kkm": ""})      # kosong = ikut komponen
    db.expire_all()
    assert db.get(Exam, e).kkm is None


def test_validasi_kkm_komponen_di_server(db, data, guru):
    for salah in ("150", "-5", "x"):
        r = guru.post("/teacher/grades/components/create", data={"name": "UAS", "class_target": "VII", "weight": "40", "kkm": salah})
        assert "error=kkm" in r.headers["location"], salah
    assert db.query(ScoreComponent).filter_by(name="UAS").count() == 0
    guru.post("/teacher/grades/components/create", data={"name": "UAS", "class_target": "VII", "weight": "40", "kkm": "70"})
    assert db.query(ScoreComponent).filter_by(name="UAS").one().kkm == 70
    k = db.query(ScoreComponent).filter_by(name="UAS").one().id
    guru.post(f"/teacher/grades/components/{k}/kkm", data={"kkm": "200"})
    db.expire_all()
    assert db.get(ScoreComponent, k).kkm == 70
    guru.post(f"/teacher/grades/components/{k}/kkm", data={"kkm": ""})
    db.expire_all()
    assert db.get(ScoreComponent, k).kkm is None


def test_form_buat_ujian_menyimpan_kkm(db, data, guru):
    guru.post("/teacher/exams/create", data={"bank_id": str(data["bank"]), "duration_minutes": "20", "title": "KKM 85",
                                             "class_target": "VII", "kkm": "85"})
    assert db.query(Exam).filter_by(title="KKM 85").one().kkm == 85
    r = guru.post("/teacher/exams/create", data={"bank_id": str(data["bank"]), "duration_minutes": "20", "title": "Salah",
                                                 "class_target": "VII", "kkm": "999"})
    assert "error=kkm" in r.headers["location"]
    assert db.query(Exam).filter_by(title="Salah").count() == 0


def test_ekspor_nilai_mencantumkan_kkm(db, data, guru):
    k = komponen(db, data, kkm=80)
    buat_ujian(db, data, komponen=k)
    isi = guru.get("/teacher/grades/export?kelas=VII").content
    lembar = load_workbook(io.BytesIO(isi)).worksheets[0]
    assert "KKM akhir 75" in lembar["A2"].value
    assert any("KKM 80" in str(sel.value) for sel in lembar[5])
