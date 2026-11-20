# Wajib ganti sandi bawaan + catatan aksi guru.

from app.models.aksi_guru import AksiGuru
from app.models.exam import ExamAnswer
from app.models.user import User
from app.utils.security import hash_password
from tests import data_uji
from tests.data_uji import buat_ujian
from tests.test_kesempatan import _kirim_otomatis, _mulai


def _tandai_wajib(db, nilai=True):
    db.query(User).update({User.must_change_password: nilai})
    db.commit()


def _catatan(db):
    db.expire_all()
    return db.query(AksiGuru).order_by(AksiGuru.id).all()


# ---------- wajib ganti sandi ----------

def test_sandi_bawaan_mengunci_semua_menu_kecuali_akun(guru, db):
    _tandai_wajib(db)
    for alamat in ("/teacher/materials", "/teacher/students", "/teacher/exams", "/teacher/account/catatan"):
        r = guru.get(alamat)
        assert r.status_code == 303 and r.headers["location"] == "/teacher/account?pesan=wajib", alamat
    r = guru.post("/teacher/students/bulk-create", data={"names_text": "Zed"})      # POST pun tertahan, tidak ada yang dibuat
    assert r.status_code == 303 and r.headers["location"] == "/teacher/account?pesan=wajib"
    halaman = guru.get("/teacher/account")
    assert halaman.status_code == 200 and "Ganti password dulu sebelum lanjut" in halaman.text


def test_ganti_sandi_membuka_kunci_dan_menolak_sandi_bawaan(guru, db):
    _tandai_wajib(db)
    lama = data_uji.PASSWORD_GURU
    r = guru.post("/teacher/account/password", data={"lama": lama, "baru": "guru123", "ulang": "guru123"})
    assert r.headers["location"].endswith("pesan=lemah")                              # sandi bawaan ditolak sebagai sandi baru
    r = guru.post("/teacher/account/password", data={"lama": lama, "baru": "SandiBaru-2026", "ulang": "SandiBaru-2026"})
    assert r.headers["location"].endswith("pesan=ok")
    db.expire_all()
    assert db.query(User).first().must_change_password is False
    assert guru.get("/teacher/materials").status_code == 200                          # menu terbuka lagi (karcis baru terpasang)
    assert "Ganti password dulu" not in guru.get("/teacher/account").text
    ada = [c for c in _catatan(db) if c.aksi == "Ganti sandi"]
    assert len(ada) == 1 and ada[0].kategori == "Akun" and "SandiBaru" not in (ada[0].rincian + ada[0].sasaran)


def test_sandi_salah_saat_wajib_tetap_menampilkan_banner_dan_pesan(guru, db):
    _tandai_wajib(db)
    r = guru.post("/teacher/account/password", data={"lama": "salah-salah", "baru": "SandiBaru-2026", "ulang": "SandiBaru-2026"})
    assert r.headers["location"].endswith("pesan=lama")
    html = guru.get("/teacher/account?pesan=lama").text
    assert "Ganti password dulu sebelum lanjut" in html and "Password lama salah" in html


def test_akun_yang_sudah_ganti_sandi_tidak_terganggu(guru, db):
    assert db.query(User).first().must_change_password is False
    assert guru.get("/teacher/materials").status_code == 200


def test_siswa_tidak_terpengaruh_penguncian_guru(db, data, masuk_siswa):
    _tandai_wajib(db)
    assert masuk_siswa(data["siswa"]["Ani"]).get("/student/dashboard").status_code == 200


# ---------- catatan aksi ----------

def test_reset_pin_dicatat_tanpa_pin(guru, db, data):
    r = guru.post(f"/teacher/students/{data['siswa']['Ani']}/reset-pin")
    pin = [p for p in r.text.split() if p.isdigit() and len(p) == 4]
    ada = [c for c in _catatan(db) if c.aksi == "Reset PIN"]
    assert len(ada) == 1 and ada[0].kategori == "Siswa" and ada[0].rincian == "Ani" and ada[0].user_id
    assert not any(p in ada[0].rincian + ada[0].sasaran for p in pin if p != "2026")


def test_hapus_siswa_dicatat_dengan_nama(guru, db, data):
    ids = f"{data['siswa']['Ani']},{data['siswa']['Budi']}"
    guru.post("/teacher/students/delete", data={"ids": ids, "confirm_text": "HAPUS"})
    ada = [c for c in _catatan(db) if c.aksi == "Hapus siswa"]
    assert len(ada) == 1 and ada[0].sasaran == "2 siswa" and ada[0].rincian == "Ani, Budi"
    # salah ketik konfirmasi: tidak ada yang terhapus, tidak ada catatan
    guru.post("/teacher/students/delete", data={"ids": str(data["siswa"]["Citra"]), "confirm_text": "hapus saja"})
    assert len([c for c in _catatan(db) if c.aksi == "Hapus siswa"]) == 1


def test_nonaktif_dan_pindah_rombel_dicatat(guru, db, data):
    guru.post("/teacher/students/bulk", data={"student_ids": [str(data["siswa"]["Ani"])], "action": "deactivate"})
    guru.post(f"/teacher/students/{data['siswa']['Ani']}/toggle-active")
    aksi = [c.aksi for c in _catatan(db)]
    assert aksi == ["Nonaktifkan siswa", "Aktifkan siswa"]


def test_ubah_poin_esai_hanya_dicatat_bila_berubah(guru, db, data, masuk_siswa):
    a = buat_ujian(db, data, "UH esai")
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = _mulai(ani, a)
    _kirim_otomatis(ani, sesi, data)
    jawab = db.query(ExamAnswer).filter(ExamAnswer.session_id == sesi).first()
    guru.post(f"/teacher/answers/{jawab.id}/score", data={"points": ""})              # tidak berubah (tetap otomatis)
    assert not [c for c in _catatan(db) if c.aksi == "Ubah poin esai"]
    guru.post(f"/teacher/answers/{jawab.id}/score", data={"points": "0"})
    ada = [c for c in _catatan(db) if c.aksi == "Ubah poin esai"]
    assert len(ada) == 1 and ada[0].kategori == "Nilai" and "Ani" in ada[0].sasaran and "→ 0" in ada[0].rincian


def test_beri_kesempatan_dan_remedial_dicatat(guru, db, data, masuk_siswa):
    a = buat_ujian(db, data, "UH")
    ani = masuk_siswa(data["siswa"]["Ani"])
    sesi = _mulai(ani, a)
    _kirim_otomatis(ani, sesi, data)
    guru.post(f"/teacher/exams/{a}/sessions/{sesi}/lanjut")
    assert [c.aksi for c in _catatan(db)] == ["Beri kesempatan"]
    # aksi yang gagal (sesi sudah aktif lagi) tidak ikut tercatat
    guru.post(f"/teacher/exams/{a}/sessions/{sesi}/lanjut")
    assert len(_catatan(db)) == 1
    ani.post(f"/student/exam/submit/{sesi}", data={f"question_{x['id']}": str(x["benar"]) for x in data["soal"][:1]})
    guru.post(f"/teacher/exams/{a}/sessions/{sesi}/remedial")
    assert [c.aksi for c in _catatan(db)] == ["Beri kesempatan", "Beri remedial"]


def test_kkm_dan_hapus_ujian_dicatat(guru, db, data):
    a = buat_ujian(db, data, "UH hapus")
    guru.post(f"/teacher/exams/{a}/kkm", data={"kkm": "80"})
    guru.post(f"/teacher/exams/{a}/kkm", data={"kkm": "80"})                          # sama: tidak dicatat dua kali
    guru.post(f"/teacher/exams/{a}/delete")
    assert [c.aksi for c in _catatan(db)] == ["Ubah KKM ujian", "Hapus ujian"]


def test_halaman_catatan_saring_dan_hanya_guru(guru, db, data, client, masuk_siswa):
    guru.post(f"/teacher/students/{data['siswa']['Ani']}/reset-pin")
    a = buat_ujian(db, data, "UH")
    guru.post(f"/teacher/exams/{a}/delete")
    semua = guru.get("/teacher/account/catatan").text
    assert "Reset PIN" in semua and "Hapus ujian" in semua and "2 catatan" in semua
    siswa = guru.get("/teacher/account/catatan?kategori=Siswa").text
    assert "Reset PIN" in siswa and "Hapus ujian" not in siswa
    assert "2 catatan" in guru.get("/teacher/account/catatan?kategori=ngawur").text      # kategori tak dikenal = semua
    assert "Belum ada catatan" in guru.get("/teacher/account/catatan?kategori=Akun").text
    assert guru.get("/teacher/account/catatan?hal=abc").status_code == 200
    assert client.get("/teacher/account/catatan").status_code in (303, 307)
    assert masuk_siswa(data["siswa"]["Budi"]).get("/teacher/account/catatan").status_code == 403


def test_nama_di_catatan_tidak_menyisipkan_html(guru, db, data):
    guru.post("/teacher/students/create", data={"name": "<script>x()</script>", "pin": "4321"})
    html = guru.get("/teacher/account/catatan").text
    assert "<script>x()</script>" not in html and "&lt;script&gt;" in html
