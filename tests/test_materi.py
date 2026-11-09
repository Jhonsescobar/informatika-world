# tests/test_materi.py
# Materi: buka/tutup/jadwal, edit, pratinjau, tampilan aman untuk siswa.

from datetime import datetime, timedelta

from app.models.material import Material
from app.services.materi import dokumen_iframe, format_materi, isi_html


def buat(db, data, **lain):
    m = Material(title=lain.pop("title", "Bab 1"), class_target=lain.pop("class_target", "VII"), description="",
                 content=lain.pop("content", "isi"), teacher_id=data["guru"], **lain)
    db.add(m)
    db.commit()
    return m.id


def waktu(menit: int) -> str:
    return (datetime.now() + timedelta(minutes=menit)).strftime("%Y-%m-%dT%H:%M")


def test_buka_tanpa_tanggal_langsung_terlihat_siswa(guru, db, data, masuk_siswa):
    mid = buat(db, data)
    r = guru.post(f"/teacher/materials/{mid}/visibility", data={"action": "open", "open_at": "", "close_at": ""})
    assert r.headers["location"].endswith("pesan=dibuka")
    assert "Materi dibuka untuk siswa" in guru.get(r.headers["location"]).text
    ani = masuk_siswa(data["siswa"]["Ani"])
    assert "Bab 1" in ani.get("/student/materials").text
    assert ani.get(f"/student/materials/{mid}").status_code == 200
    assert "1 materi" in ani.get("/student/dashboard").text          # pemberitahuan di beranda


def test_tanggal_tutup_yang_sudah_lewat_ditolak_dengan_pesan(guru, db, data):
    mid = buat(db, data)
    r = guru.post(f"/teacher/materials/{mid}/visibility", data={"action": "open", "close_at": waktu(-5)})
    assert r.headers["location"].endswith("pesan=lewat")
    assert "Batas tutup harus di masa depan" in guru.get(r.headers["location"]).text
    db.expire_all()
    assert not db.get(Material, mid).is_published


def test_tutup_sebelum_mulai_ditolak(guru, db, data):
    mid = buat(db, data)
    r = guru.post(f"/teacher/materials/{mid}/visibility", data={"action": "open", "open_at": waktu(60), "close_at": waktu(30)})
    assert r.headers["location"].endswith("pesan=urutan")


def test_jadwal_mulai_tampil(guru, db, data, masuk_siswa):
    mid = buat(db, data)
    r = guru.post(f"/teacher/materials/{mid}/visibility", data={"action": "open", "open_at": waktu(60), "close_at": waktu(120)})
    assert r.headers["location"].endswith("pesan=terjadwal")
    assert "Tampil mulai" in guru.get("/teacher/materials").text
    ani = masuk_siswa(data["siswa"]["Ani"])
    assert ani.get(f"/student/materials/{mid}").status_code == 303     # belum waktunya
    db.expire_all()
    m = db.get(Material, mid)
    m.open_at = m.open_at - timedelta(hours=2)
    db.commit()
    assert ani.get(f"/student/materials/{mid}").status_code == 200     # sudah waktunya
    guru.post(f"/teacher/materials/{mid}/visibility", data={"action": "close"})
    assert ani.get(f"/student/materials/{mid}").status_code == 303


def test_materi_lewat_bisa_dibuka_lagi(guru, db, data, masuk_siswa):
    from datetime import timezone
    mid = buat(db, data, is_published=True, close_at=datetime.now(timezone.utc) - timedelta(hours=1))
    assert "Sudah ditutup otomatis" in guru.get("/teacher/materials").text
    guru.post(f"/teacher/materials/{mid}/visibility", data={"action": "open", "close_at": ""})
    assert masuk_siswa(data["siswa"]["Ani"]).get(f"/student/materials/{mid}").status_code == 200


def test_edit_dan_pratinjau(guru, db, data):
    mid = buat(db, data)
    guru.post(f"/teacher/materials/{mid}/edit", data={"title": "Bab 1 revisi", "class_target": "VIII", "description": "d",
                                                     "content": "# Judul\n- poin"})
    db.expire_all()
    m = db.get(Material, mid)
    assert m.title == "Bab 1 revisi" and m.class_target == "VIII"
    html = guru.get(f"/teacher/materials/{mid}").text
    assert "Bab 1 revisi" in html and "Tampilan ini sama dengan yang dilihat siswa" in html
    assert "pesan=isian" in guru.post(f"/teacher/materials/{mid}/edit", data={"title": "", "class_target": "X"}).headers["location"]


def test_siswa_tidak_bisa_mengakses_halaman_guru_materi(db, data, masuk_siswa):
    mid = buat(db, data)
    ani = masuk_siswa(data["siswa"]["Ani"])
    assert ani.get(f"/teacher/materials/{mid}").status_code == 403
    assert ani.post(f"/teacher/materials/{mid}/visibility", data={"action": "open"}).status_code == 403


def test_format_teks_aman():
    html = str(format_materi("# Bab\n- satu **tebal**\n- dua `x<1`\n\n[buka](https://contoh.id) [jahat](javascript:alert(1))\n<script>alert(1)</script>"))
    assert "<h2>Bab</h2>" in html and "<li>satu <strong>tebal</strong></li>" in html
    assert '<code class="kode-sebaris">x&lt;1</code>' in html
    assert 'href="https://contoh.id"' in html
    assert "<script>" not in html and 'href="javascript' not in html


def test_html_interaktif_tampil_di_iframe_bersandbox(guru, db, data, masuk_siswa):
    konten = "<!DOCTYPE html><html><head><title>W</title></head><body><button onclick=\"alert(1)\">Linux</button><script>document.cookie</script></body></html>"
    assert isi_html(konten) and not isi_html("teks biasa dengan x < 5")
    doc = dokumen_iframe(konten)
    assert doc.index("user-select:none") < doc.index("<title>") and "iwTinggi" in doc
    mid = buat(db, data, content=konten)
    guru.post(f"/teacher/materials/{mid}/visibility", data={"action": "open"})
    html = masuk_siswa(data["siswa"]["Ani"]).get(f"/student/materials/{mid}").text
    assert 'sandbox="allow-scripts"' in html and "allow-same-origin" not in html
    assert "<button onclick" not in html.split("srcdoc=")[0]                # tidak dijalankan di halaman utama
    assert "srcdoc=\"&lt;!DOCTYPE html&gt;" in html                          # isi hanya hidup di dalam iframe
