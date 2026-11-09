# tests/test_impor_soal.py
# Impor soal dari JSON hasil AI: perbaikan otomatis, kesalahan per nomor, simpan, dan keamanan tampilan.

import json

from app.models.question import Question, QuestionOption
from app.services.impor_soal import CONTOH, periksa, rapikan
from app.services.teks import format_soal
from tests.data_uji import buat_ujian, kerjakan

BERSIH = json.dumps(CONTOH, ensure_ascii=False)


def test_contoh_bawaan_lolos_tanpa_galat():
    h = periksa(BERSIH)
    assert h["galat"] == [] and len(h["soal"]) == 3 and h["topik"]
    assert h["soal"][1]["kode"].startswith("angka = 7") and h["soal"][1]["benar"] == 1


def test_pagar_kode_teks_pembuka_dan_koma_sisa_dirapikan():
    kotor = 'Tentu! Berikut soalnya:\n```json\n{"soal": [{"tipe": "pg", "pertanyaan": "1+1?", "opsi": ["1", "2",], "jawaban": "B",},]}\n```\nSemoga membantu.'
    h = periksa(kotor)
    assert h["galat"] == [] and h["soal"][0]["benar"] == 1
    assert any("Pagar" in p for p in h["perbaikan"]) and any("Koma" in p for p in h["perbaikan"])


def test_kutip_melengkung_dirapikan_termasuk_di_dalam_teks():
    kotor = '{“soal”: [{“tipe”: “pg”, “pertanyaan”: “Apa arti “input”?”, “opsi”: [“masukan”, “keluaran”], “jawaban”: “A”}]}'
    t, perbaikan = rapikan(kotor)
    assert json.loads(t)["soal"][0]["pertanyaan"] == 'Apa arti "input"?'
    assert periksa(kotor)["galat"] == []


def test_kesalahan_ditunjukkan_per_nomor():
    data = {"soal": [
        {"tipe": "pg", "pertanyaan": "Benar", "opsi": ["a", "b", "c", "d"], "jawaban": "C"},
        {"tipe": "pg", "pertanyaan": "", "opsi": ["a"], "jawaban": "E"},
        {"tipe": "esai", "pertanyaan": "Jelaskan", "kunci": ""},
        {"tipe": "isian", "pertanyaan": "x"},
        {"tipe": "pg", "pertanyaan": "Kembar", "opsi": ["sama", "Sama", "c"], "jawaban": "A", "poin": 500},
    ]}
    g = periksa(json.dumps(data))["galat"]
    assert len(g) == 4
    assert g[0].startswith("Soal 2:") and "pertanyaan kosong" in g[0] and "opsi harus 2–5" in g[0]
    assert g[1].startswith("Soal 3:") and "kunci jawaban esai kosong" in g[1]
    assert g[2].startswith("Soal 4:") and "tidak dikenal" in g[2]
    assert g[3].startswith("Soal 5:") and "opsi kembar" in g[3] and "poin" in g[3]


def test_json_rusak_diberi_baris_dan_kolom():
    g = periksa('{"soal": [\n {"tipe": "pg" "pertanyaan": "x"}\n]}')["galat"]
    assert len(g) == 1 and "baris 2" in g[0] and "kurang tanda koma" in g[0]


def test_variasi_jawaban_dari_ai_diterima():
    for jawaban in ("b", "B.", "B. Dua", "Dua", 2):
        s = {"soal": [{"pertanyaan": "1+1?", "opsi": ["A. Satu", "B. Dua", "C. Tiga"], "jawaban": jawaban}]}
        h = periksa(json.dumps(s))
        assert h["galat"] == [] and h["soal"][0]["benar"] == 1 and h["soal"][0]["opsi"][1] == "Dua", jawaban


def test_batas_jumlah_soal():
    banyak = {"soal": [{"pertanyaan": f"s{i}", "opsi": ["a", "b"], "jawaban": "A"} for i in range(101)]}
    assert "Maksimal 100" in periksa(json.dumps(banyak))["galat"][0]


def test_tampilan_soal_aman_dan_kode_rapi():
    html = str(format_soal('Apa hasil `x < 5`?\n\n```python\nif x < 5:\n    print("<b>hai</b>")\n```'))
    assert "<b>hai</b>" not in html and "&lt;b&gt;hai&lt;/b&gt;" in html
    assert '<pre class="kode-blok"' in html and "    print(" in html
    assert '<code class="kode-sebaris">x &lt; 5</code>' in html
    assert "<script>" not in str(format_soal("<script>alert(1)</script>"))


def test_periksa_tidak_menyimpan_lalu_simpan(guru, db, data):
    url = f"/teacher/question-banks/{data['bank']}/import"
    awal = db.query(Question).count()
    r = guru.post(url, data={"aksi": "periksa", "teks": BERSIH})
    assert r.status_code == 200 and "Pratinjau impor" in r.text and "Simpan 3 soal" in r.text
    assert db.query(Question).count() == awal
    r = guru.post(url, data={"aksi": "simpan", "teks": BERSIH})
    assert "pesan=impor&n=3&lewat=0" in r.headers["location"]
    q = db.query(Question).filter(Question.text.like("Apa keluaran program%")).one()
    assert "```python\nangka = 7" in q.text and q.points == 2
    assert [o.is_correct for o in db.query(QuestionOption).filter_by(question_id=q.id).order_by(QuestionOption.id)] == [False, True, False, False]
    esai = db.query(Question).filter_by(question_type="esai", bank_id=data["bank"]).one()
    assert esai.keywords.startswith("ulang/perulangan")
    # tempel dua kali: tidak ada soal kembar
    r = guru.post(url, data={"aksi": "simpan", "teks": BERSIH})
    assert "n=0&lewat=3" in r.headers["location"]
    assert db.query(Question).count() == awal + 3


def test_simpan_ditolak_bila_masih_ada_galat(guru, db, data):
    awal = db.query(Question).count()
    rusak = json.dumps({"soal": [{"pertanyaan": "ok", "opsi": ["a", "b"], "jawaban": "A"},
                                 {"pertanyaan": "rusak", "opsi": ["a"], "jawaban": "A"}]})
    r = guru.post(f"/teacher/question-banks/{data['bank']}/import", data={"aksi": "simpan", "teks": rusak})
    assert r.status_code == 200 and "Soal 2:" in r.text and "Belum disimpan" in r.text
    assert db.query(Question).count() == awal


def test_xss_dari_teks_ai_tidak_jalan(guru, db, data, masuk_siswa):
    jahat = json.dumps({"soal": [{"pertanyaan": "<img src=x onerror=alert(1)>Soal", "opsi": ["<script>alert(2)</script>", "b"], "jawaban": "A"}]})
    r = guru.post(f"/teacher/question-banks/{data['bank']}/import", data={"aksi": "periksa", "teks": jahat})
    assert "<img src=x" not in r.text and "<script>alert(2)" not in r.text
    guru.post(f"/teacher/question-banks/{data['bank']}/import", data={"aksi": "simpan", "teks": jahat})
    assert "<img src=x" not in guru.get(f"/teacher/question-banks/{data['bank']}").text
    e = buat_ujian(db, data, "A")
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = ani.post("/student/exam/start", data={"exam_id": str(e)}).headers["location"]
    html = ani.get(sesi).text
    assert "<img src=x" not in html and "<script>alert(2)" not in html and "&lt;img src=x" in html


def test_hapus_soal_dan_kunci_setelah_dipakai(guru, db, data, masuk_siswa):
    q = db.query(Question).filter_by(bank_id=data["bank_esai"]).first()
    r = guru.post(f"/teacher/questions/{q.id}/delete")
    assert "pesan=hapus" in r.headers["location"]
    # bank PG dipakai ujian yang sudah dikerjakan -> soal terkunci
    e = buat_ujian(db, data, "A")
    kerjakan(masuk_siswa(data["siswa"]["Ani"]), e, data, 2)
    q = db.query(Question).filter_by(bank_id=data["bank"]).first()
    assert "pesan=terkunci" in guru.post(f"/teacher/questions/{q.id}/delete").headers["location"]
    assert db.query(Question).filter_by(id=q.id).count() == 1


def test_soal_manual_dengan_kode(guru, db, data):
    guru.post("/teacher/questions/create", data={"bank_id": data["bank_esai"], "question_type": "pg",
              "question_text": "Keluaran?", "code": "print(1 < 2)", "option_A": "True", "option_B": "False",
              "option_C": "1", "option_D": "2", "correct_key": "A", "points": "1"})
    q = db.query(Question).filter_by(text="Keluaran?\n\n```python\nprint(1 < 2)\n```").one()
    assert [o.is_correct for o in db.query(QuestionOption).filter_by(question_id=q.id).order_by(QuestionOption.id)] == [True, False, False, False]
    html = guru.get(f"/teacher/question-banks/{data['bank_esai']}").text
    assert "print(1 &lt; 2)" in html and ">True</span>" in html     # opsi PG benar-benar tampil di bank
    assert guru.post("/teacher/questions/create", data={"bank_id": "999999", "question_text": "x"}).headers["location"] == "/teacher/question-banks"


def test_kutip_escape_yang_ikut_melengkung():
    kotor = '{“soal”: [{“pertanyaan”: “x”, “kode”: “print(\\“kecil\\”)”, “opsi”: [“a”, “b”], “jawaban”: “A”}]}'
    h = periksa(kotor)
    assert h["galat"] == [] and h["soal"][0]["kode"] == 'print("kecil")'
