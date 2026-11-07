# tests/test_nilai.py
# Logika nilai: komponen & bobot, nilai tertinggi, tahun ajaran, urutan, peringkat siswa.

from app.models.exam import Exam
from app.models.grade import ScoreComponent
from app.services.rekap import rekap_kelas, urutkan
from tests.data_uji import buat_ujian, kerjakan


def komponen(db, data, nama, bobot, kelas="VII"):
    k = ScoreComponent(name=nama, weight=bobot, class_target=kelas, teacher_id=data["guru"])
    db.add(k)
    db.commit()
    return k.id


def akhir(db, nama, kelas="VII"):
    return {b["siswa"].name: b["akhir"] for b in rekap_kelas(db, kelas)["baris"]}[nama]


def test_bobot_per_kelas_tidak_boleh_lebih_100(guru, db):
    guru.post("/teacher/grades/components/create", data={"name": "Formatif", "class_target": "VII", "weight": "70"})
    r = guru.post("/teacher/grades/components/create", data={"name": "Sumatif", "class_target": "VII", "weight": "40"})
    assert "error=bobot" in r.headers["location"] and "sisa=30" in r.headers["location"]
    assert "Sisa bobot yang masih bisa dipakai: 30%" in guru.get(r.headers["location"]).text
    # kelas lain punya jatah 100% sendiri
    guru.post("/teacher/grades/components/create", data={"name": "Sumatif", "class_target": "VIII", "weight": "40"})
    assert db.query(ScoreComponent).count() == 2


def test_isian_komponen_aneh_ditolak(guru, db):
    for isian in ({"name": "", "class_target": "VII", "weight": "20"},
                  {"name": "X", "class_target": "X", "weight": "20"},
                  {"name": "X", "class_target": "VII", "weight": "0"},
                  {"name": "X", "class_target": "VII", "weight": "abc"},
                  {"name": "X", "class_target": "VII", "weight": "-5"}):
        r = guru.post("/teacher/grades/components/create", data=isian)
        assert "error=isian" in r.headers["location"], isian
    assert db.query(ScoreComponent).count() == 0


def test_ujian_tidak_bisa_masuk_komponen_kelas_lain(guru, db, data):
    k8 = komponen(db, data, "Sumatif VIII", 50, kelas="VIII")
    r = guru.post("/teacher/exams/create", data={"title": "Ujian VII", "bank_id": data["bank"], "class_target": "VII",
                                                 "duration_minutes": "30", "component_id": str(k8)})
    assert "error=komponen" in r.headers["location"]
    assert db.query(Exam).count() == 0


def test_ujian_baru_tercatat_di_tahun_aktif_dan_komponen(guru, db, data):
    k = komponen(db, data, "Formatif", 40)
    guru.post("/teacher/exams/create", data={"title": "F1", "bank_id": data["bank"], "class_target": "VII",
                                             "duration_minutes": "30", "component_id": str(k)})
    e = db.query(Exam).one()
    assert e.component_id == k and e.academic_year_id == data["tahun"] and not e.is_published


def test_nilai_akhir_berbobot(db, data, masuk_siswa):
    kf = komponen(db, data, "Formatif", 40)
    ks = komponen(db, data, "Sumatif", 60)
    f1 = buat_ujian(db, data, "F1", komponen=kf)
    f2 = buat_ujian(db, data, "F2", komponen=kf)
    s1 = buat_ujian(db, data, "S1", komponen=ks)
    ani = masuk_siswa(data["siswa"]["Ani"])
    kerjakan(ani, f1, data, 4)   # 100
    kerjakan(ani, f2, data, 2)   # 50  -> formatif 75
    kerjakan(ani, s1, data, 3)   # 75  -> sumatif 75
    assert akhir(db, "Ani") == 75.0
    # Budi hanya mengerjakan F1 (100): F2 & S1 dihitung 0 -> formatif 50, sumatif 0 -> 20
    kerjakan(masuk_siswa(data["siswa"]["Budi"]), f1, data, 4)
    assert akhir(db, "Budi") == 20.0
    baris = {b["siswa"].name: b for b in rekap_kelas(db, "VII")["baris"]}
    assert baris["Budi"]["belum"] == 2 and not baris["Budi"]["tuntas"] and baris["Ani"]["tuntas"]   # 75 = KKM: tuntas


def test_bobot_belum_100_tetap_skala_0_100(db, data, masuk_siswa):
    kf = komponen(db, data, "Formatif", 30)
    f1 = buat_ujian(db, data, "F1", komponen=kf)
    kerjakan(masuk_siswa(data["siswa"]["Ani"]), f1, data, 4)
    rekap = rekap_kelas(db, "VII")
    assert rekap["total_bobot"] == 30
    assert akhir(db, "Ani") == 100.0     # bukan 30: dibagi total bobot yang terpakai


def test_tanpa_komponen_pakai_rata_rata_ujian(db, data, masuk_siswa):
    a = buat_ujian(db, data, "A")
    b = buat_ujian(db, data, "B")
    ani = masuk_siswa(data["siswa"]["Ani"])
    kerjakan(ani, a, data, 4)
    kerjakan(ani, b, data, 1)
    assert not rekap_kelas(db, "VII")["pakai_bobot"]
    assert akhir(db, "Ani") == 62.5


def test_ujian_draf_tanpa_sesi_dan_tahun_lama_tidak_dihitung(db, data, masuk_siswa):
    a = buat_ujian(db, data, "A")
    buat_ujian(db, data, "Draf", terbit=False)
    buat_ujian(db, data, "Tahun lalu", tahun=data["tahun_lama"])
    kerjakan(masuk_siswa(data["siswa"]["Ani"]), a, data, 4)
    rekap = rekap_kelas(db, "VII")
    assert [e.title for e in rekap["ujian"]] == ["A"]
    assert akhir(db, "Ani") == 100.0


def test_remedial_memakai_nilai_tertinggi(guru, db, data, masuk_siswa):
    a = buat_ujian(db, data, "A")
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = kerjakan(ani, a, data, 1)                    # 25
    guru.post(f"/teacher/exams/{a}/sessions/{sesi}/remedial")
    kerjakan(ani, a, data, 3)                            # 75
    assert akhir(db, "Ani") == 75.0
    guru.post(f"/teacher/exams/{a}/sessions/{sesi}/remedial")
    kerjakan(ani, a, data, 2)                            # 50: nilai tidak turun
    assert akhir(db, "Ani") == 75.0


def test_hapus_komponen_tidak_menghapus_ujian(guru, db, data):
    k = komponen(db, data, "Formatif", 40)
    e = buat_ujian(db, data, "F1", komponen=k)
    guru.post(f"/teacher/grades/components/{k}/delete")
    db.expire_all()
    ujian = db.get(Exam, e)
    assert ujian is not None and ujian.component_id is None


def test_urutan_dan_saring_rombel(guru, db, data, masuk_siswa):
    a = buat_ujian(db, data, "A")
    for nama, benar in (("Ani", 2), ("Budi", 4), ("Dodi", 3)):
        kerjakan(masuk_siswa(data["siswa"][nama]), a, data, benar)
    baris = rekap_kelas(db, "VII")["baris"]
    assert [b["siswa"].name for b in urutkan(baris, "nilai")][:3] == ["Budi", "Dodi", "Ani"]
    assert [b["siswa"].name for b in urutkan(baris, "az")] == ["Ani", "Budi", "Citra", "Dodi", "Eka", "Gilang Nonaktif"]
    assert [b["siswa"].name for b in urutkan(baris, "za")][0] == "Gilang Nonaktif"

    html = guru.get("/teacher/grades/class/VII?urut=nilai").text
    assert html.index("Budi") < html.index("Dodi") < html.index("Ani")
    html = guru.get(f"/teacher/grades/class/VII?urut=az&rombel={data['rombel']['VII.2']}").text
    assert "Dodi" in html and "Budi" not in html
    # parameter aneh tidak membuat error
    assert guru.get("/teacher/grades/class/VII?urut=<script>&rombel=abc").status_code == 200
    assert guru.get("/teacher/grades/class/XII").status_code == 303


def test_peringkat_siswa_sama_dengan_rekap_guru(db, data, masuk_siswa):
    kf = komponen(db, data, "Formatif", 100)
    a = buat_ujian(db, data, "A", komponen=kf)
    kerjakan(masuk_siswa(data["siswa"]["Budi"]), a, data, 4)
    ani = masuk_siswa(data["siswa"]["Ani"])
    kerjakan(ani, a, data, 3)
    html = ani.get("/student/leaderboard").text
    assert html.index("Budi") < html.index("Ani")
    assert "100.0" in html and "75.0" in html
    assert "Fajar" not in html          # beda tingkat tidak ikut peringkat kelas VII


def test_hasil_ujian_guru_urut_dan_tombol_remedial(guru, db, data, masuk_siswa):
    a = buat_ujian(db, data, "A")
    kerjakan(masuk_siswa(data["siswa"]["Ani"]), a, data, 1)    # 25: boleh remedial
    kerjakan(masuk_siswa(data["siswa"]["Budi"]), a, data, 4)   # 100
    html = guru.get(f"/teacher/exams/{a}/results").text
    assert html.index("Budi") < html.index("Ani")
    assert html.count('/remedial" method="POST"') == 1
    html = guru.get(f"/teacher/exams/{a}/results?urut=az").text
    assert html.index("Ani") < html.index("Budi")


def test_pindah_komponen_ujian_lama(guru, db, data):
    k7 = komponen(db, data, "Formatif", 40)
    k8 = komponen(db, data, "Sumatif VIII", 60, kelas="VIII")
    e = buat_ujian(db, data, "Ujian lama")
    guru.post(f"/teacher/exams/{e}/component", data={"component_id": str(k7)})
    db.expire_all()
    assert db.get(Exam, e).component_id == k7
    r = guru.post(f"/teacher/exams/{e}/component", data={"component_id": str(k8)})
    assert "error=komponen" in r.headers["location"]
    guru.post(f"/teacher/exams/{e}/component", data={"component_id": ""})
    db.expire_all()
    assert db.get(Exam, e).component_id is None
