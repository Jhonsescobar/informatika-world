# tests/test_acak_jenis.py
# Soal diacak hanya di antara jenisnya: PG tetap di nomor PG, esai tetap di nomor esai.

import random
import re
from collections import Counter

from app.models.question import Question, QuestionBank, QuestionOption
from app.services.urutan_soal import kuota_per_jenis, susun_soal
from tests.data_uji import buat_ujian
from tests.test_acak import mulai


def bank_campur(db, data, pg=15, esai=5):
    b = QuestionBank(title="Campur", class_target="VII", teacher_id=data["guru"])
    db.add(b)
    db.flush()
    for i in range(pg):
        q = Question(bank_id=b.id, text=f"Pilgan nomor {i + 1}", points=1, question_type="pg")
        db.add(q)
        db.flush()
        db.add_all([QuestionOption(question_id=q.id, text=f"Opsi {i + 1}-{h}", is_correct=(h == "A")) for h in "ABCD"])
    for i in range(esai):
        db.add(Question(bank_id=b.id, text=f"Uraian nomor {i + 1}", points=5, question_type="esai", answer_key="x"))
    db.commit()
    return b.id


def jenis_tampil(html):
    return re.findall(r"(Pilgan|Uraian) nomor (\d+)", html)


# ---- logika murni --------------------------------------------------------------------------
SOAL = [(i, "pg") for i in range(1, 16)] + [(i, "esai") for i in range(16, 21)]
JENIS = {i: j for i, j in SOAL}


def test_pola_jenis_tetap_dan_semua_soal_ada():
    for seed in range(50):
        hasil = susun_soal(SOAL, None, True, random.Random(seed))
        assert sorted(hasil) == list(range(1, 21))
        assert [JENIS[i] for i in hasil] == ["pg"] * 15 + ["esai"] * 5


def test_acak_hanya_di_dalam_jenis():
    hasil = susun_soal(SOAL, None, True, random.Random(1))
    assert sorted(hasil[:15]) == list(range(1, 16)) and sorted(hasil[15:]) == list(range(16, 21))
    assert hasil != list(range(1, 21))


def test_tanpa_acak_urutan_bank():
    assert susun_soal(SOAL, None, False, random.Random(1)) == list(range(1, 21))
    hasil = susun_soal(SOAL, 10, False, random.Random(1))       # dibatasi: soal terpilih tetap urut nomor bank
    assert hasil == sorted(hasil) and len(hasil) == 10


def test_pola_selang_seling_dipertahankan():
    campur = [(1, "pg"), (2, "esai"), (3, "pg"), (4, "pg"), (5, "esai"), (6, "pg")]
    for seed in range(30):
        hasil = susun_soal(campur, None, True, random.Random(seed))
        assert [dict(campur)[i] for i in hasil] == ["pg", "esai", "pg", "pg", "esai", "pg"]


def test_batas_jumlah_komposisi_sama_untuk_semua_siswa():
    komposisi = set()
    for seed in range(100):
        hasil = susun_soal(SOAL, 10, True, random.Random(seed))
        assert len(hasil) == len(set(hasil)) == 10
        urut = [JENIS[i] for i in hasil]
        assert urut == sorted(urut, key=["pg", "esai"].index)       # esai tetap di belakang
        komposisi.add(tuple(urut))
    assert len(komposisi) == 1 and Counter(next(iter(komposisi))) == {"pg": 8, "esai": 2}


def test_kuota_tiap_jenis_minimal_satu_bila_cukup():
    from collections import OrderedDict
    assert kuota_per_jenis(OrderedDict(pg=40, esai=1), 5) == {"pg": 4, "esai": 1}
    assert kuota_per_jenis(OrderedDict(pg=15, esai=5), 4) == {"pg": 3, "esai": 1}
    assert sum(kuota_per_jenis(OrderedDict(pg=7, esai=3), 9).values()) == 9
    assert kuota_per_jenis(OrderedDict(pg=2, esai=1), 1) in ({"pg": 1, "esai": 0}, {"pg": 0, "esai": 1})


def test_jenis_kosong_dianggap_pg():
    hasil = susun_soal([(1, None), (2, "pg"), (3, "esai")], None, True, random.Random(3))
    assert hasil[2] == 3 and sorted(hasil[:2]) == [1, 2]


# ---- lewat aplikasi ------------------------------------------------------------------------
def test_siswa_esai_tetap_di_belakang_pg_beda_tiap_siswa(db, data, masuk_siswa):
    e = buat_ujian(db, data, "Campur", bank=bank_campur(db, data), randomize_questions=True, randomize_options=True)
    urutan = {}
    for nama in ("Ani", "Budi", "Citra"):
        c = masuk_siswa(data["siswa"][nama])
        sesi = mulai(c, e)
        a = jenis_tampil(c.get(f"/student/exam/take/{sesi}").text)
        assert a == jenis_tampil(c.get(f"/student/exam/take/{sesi}").text), "urutan berubah saat dimuat ulang"
        assert [j for j, _ in a] == ["Pilgan"] * 15 + ["Uraian"] * 5
        assert sorted(int(n) for j, n in a if j == "Pilgan") == list(range(1, 16))
        assert sorted(int(n) for j, n in a if j == "Uraian") == list(range(1, 6))
        urutan[nama] = tuple(a)
    assert len(set(urutan.values())) == 3, "dua siswa mendapat urutan yang sama"


def test_batas_jumlah_lewat_aplikasi_komposisi_sama(db, data, masuk_siswa):
    e = buat_ujian(db, data, "Batas", bank=bank_campur(db, data), randomize_questions=True, question_count=10)
    for nama in ("Ani", "Budi", "Citra"):
        c = masuk_siswa(data["siswa"][nama])
        a = jenis_tampil(c.get(f"/student/exam/take/{mulai(c, e)}").text)
        assert [j for j, _ in a] == ["Pilgan"] * 8 + ["Uraian"] * 2


def test_form_menjelaskan_jenis_tetap_di_tempat(guru):
    assert "jenis soal tetap di nomornya" in guru.get("/teacher/exams").text
