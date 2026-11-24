# tests/test_rekap_terbit.py
# Rekap nilai hanya memuat ujian yang terbit. Ujian draf atau yang ditarik, walau sudah ada hasilnya, tidak ikut,
# tetapi guru diberi tahu dan nilainya kembali ikut begitu diterbitkan.

from app.models.exam import Exam
from app.services.rekap import rekap_kelas, ujian_tak_ikut, tahun_aktif
from tests.data_uji import buat_ujian, kerjakan


def judul(db):
    return [e.title for e in rekap_kelas(db, "VII")["ujian"]]


def test_ujian_draf_tanpa_hasil_tidak_ikut(db, data):
    buat_ujian(db, data, "Terbit")
    buat_ujian(db, data, "Draf", terbit=False)
    assert judul(db) == ["Terbit"]


def test_ujian_ditarik_setelah_dikerjakan_tidak_ikut_tapi_dicatat(db, data, masuk_siswa):
    a = buat_ujian(db, data, "Formatif 1")
    b = buat_ujian(db, data, "Formatif 2")
    c = buat_ujian(db, data, "Formatif 3")
    for e in (a, b, c):
        kerjakan(masuk_siswa(data["siswa"]["Ani"]), e, data, 4)
    kerjakan(masuk_siswa(data["siswa"]["Budi"]), c, data, 2)
    db.get(Exam, c).is_published = False
    db.commit()

    r = rekap_kelas(db, "VII")
    assert [e.title for e in r["ujian"]] == ["Formatif 1", "Formatif 2"]
    assert all(c not in b["ujian"] for b in r["baris"])
    assert [(x["ujian"].title, x["siswa"]) for x in r["tak_ikut"]] == [("Formatif 3", 2)]


def test_diterbitkan_lagi_nilainya_kembali(db, data, masuk_siswa):
    e = buat_ujian(db, data, "Sempat ditarik")
    kerjakan(masuk_siswa(data["siswa"]["Ani"]), e, data, 4)
    db.get(Exam, e).is_published = False
    db.commit()
    assert judul(db) == []
    db.get(Exam, e).is_published = True
    db.commit()
    r = rekap_kelas(db, "VII")
    assert judul(db) == ["Sempat ditarik"] and r["tak_ikut"] == []
    ani = next(b for b in r["baris"] if b["siswa"].name == "Ani")
    assert ani["ujian"][e] == 100.0


def test_draf_tanpa_hasil_tidak_dicatat_sebagai_tak_ikut(db, data):
    buat_ujian(db, data, "Draf kosong", terbit=False)
    assert ujian_tak_ikut(db, "VII", tahun_aktif(db)) == []


def test_halaman_nilai_menampilkan_catatan(guru, db, data, masuk_siswa):
    guru.post("/teacher/kelas", data={"kelas": "VII"})
    e = buat_ujian(db, data, "Formatif Bayangan")
    kerjakan(masuk_siswa(data["siswa"]["Ani"]), e, data, 4)
    db.get(Exam, e).is_published = False
    db.commit()
    html = guru.get("/teacher/grades/class/VII").text
    assert "belum terbit dan tidak ikut rekap" in html and "Formatif Bayangan" in html and "1 siswa sudah mengerjakan" in html
