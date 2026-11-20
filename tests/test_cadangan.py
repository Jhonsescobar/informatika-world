# Cadangan terenkripsi untuk folder awan + uji pemulihan.

import pytest

import backup_db
import cadangan_aman as ca
import uji_pemulihan
from app.database import engine

FRASA = "frasa-uji-yang-panjang"


@pytest.fixture(scope="module")
def kunci():
    return ca.buat_pasangan_kunci(FRASA)          # RSA-4096: dibuat sekali untuk seluruh berkas uji


@pytest.fixture
def terlihat_awan(tmp_path, monkeypatch, kunci):
    """BACKUP_COPY_DIR + kunci publik terpasang; mengembalikan folder awan."""
    awan = tmp_path / "awan"
    monkeypatch.setenv("BACKUP_COPY_DIR", str(awan))
    pub = tmp_path / "publik.pem"
    pub.write_bytes(kunci[0])
    monkeypatch.setenv("BACKUP_PUBLIC_KEY", str(pub))
    return awan


# ---------- enkripsi ----------

def test_enkripsi_lalu_dekripsi_mengembalikan_isi_asli(tmp_path, kunci):
    asli = tmp_path / "data.dump"
    asli.write_bytes(b"data siswa rahasia " * 1000)
    enc, hasil = tmp_path / "data.dump.enc", tmp_path / "pulih"
    ca.enkripsi_berkas(asli, enc, kunci[0])
    assert b"rahasia" not in enc.read_bytes() and enc.read_bytes().startswith(ca.AWAL)
    ca.dekripsi_berkas(enc, hasil, kunci[1], FRASA)
    assert hasil.read_bytes() == asli.read_bytes()
    assert not list(tmp_path.glob("*.tmp"))                       # tidak ada sisa berkas sementara


def test_dua_enkripsi_isi_sama_hasilnya_berbeda(tmp_path, kunci):
    asli = tmp_path / "a"
    asli.write_bytes(b"sama")
    ca.enkripsi_berkas(asli, tmp_path / "1", kunci[0])
    ca.enkripsi_berkas(asli, tmp_path / "2", kunci[0])
    assert (tmp_path / "1").read_bytes() != (tmp_path / "2").read_bytes()


def test_frasa_salah_kunci_lain_dan_berkas_diubah_ditolak(tmp_path, kunci):
    asli = tmp_path / "a"
    asli.write_bytes(b"isi")
    enc = tmp_path / "a.enc"
    ca.enkripsi_berkas(asli, enc, kunci[0])
    with pytest.raises(ca.GalatEnkripsi, match="Frasa sandi salah"):
        ca.dekripsi_berkas(enc, tmp_path / "x", kunci[1], "frasa-yang-salah-sekali")
    lain = ca.buat_pasangan_kunci("frasa-kunci-lain-lagi")
    with pytest.raises(ca.GalatEnkripsi, match="bukan pasangannya"):
        ca.dekripsi_berkas(enc, tmp_path / "x", lain[1], "frasa-kunci-lain-lagi")
    data = bytearray(enc.read_bytes())
    data[-5] ^= 0xFF                                               # satu byte berubah
    enc.write_bytes(bytes(data))
    with pytest.raises(ca.GalatEnkripsi, match="rusak/diubah"):
        ca.dekripsi_berkas(enc, tmp_path / "x", kunci[1], FRASA)
    assert not (tmp_path / "x").exists()                           # tidak ada hasil setengah jadi


def test_berkas_biasa_bukan_cadangan_terenkripsi(tmp_path, kunci):
    polos = tmp_path / "polos.enc"
    polos.write_bytes(b"ini bukan cadangan" * 5)
    with pytest.raises(ca.GalatEnkripsi, match="bukan cadangan terenkripsi"):
        ca.dekripsi_berkas(polos, tmp_path / "x", kunci[1], FRASA)


def test_frasa_pendek_ditolak():
    with pytest.raises(ca.GalatEnkripsi):
        ca.buat_pasangan_kunci("pendek")


def test_sidik_kunci_stabil(kunci):
    assert ca.sidik_kunci(kunci[0]) == ca.sidik_kunci(kunci[0]) and len(ca.sidik_kunci(kunci[0])) == 19


# ---------- salinan ke awan ----------

def _berkas(tmp_path, *nama):
    hasil = []
    for n in nama:
        f = tmp_path / n
        f.write_bytes(b"isi " + n.encode())
        hasil.append(f)
    return hasil


def test_tanpa_kunci_tidak_ada_data_polos_ke_awan(tmp_path, monkeypatch, capsys):
    awan = tmp_path / "awan"
    monkeypatch.setenv("BACKUP_COPY_DIR", str(awan))
    monkeypatch.setenv("BACKUP_PUBLIC_KEY", str(tmp_path / "tidak-ada.pem"))
    assert backup_db.salin_ke_awan(_berkas(tmp_path, "informatika_20260101_000000.dump")) is False
    assert not awan.exists() or not list(awan.iterdir())
    assert "buat_kunci_cadangan" in capsys.readouterr().out


def test_salinan_awan_terenkripsi_dan_bisa_dibuka(tmp_path, terlihat_awan, kunci):
    sumber = _berkas(tmp_path, "informatika_20260101_000000.dump", "nilai_20260101_000000.xlsx")
    assert backup_db.salin_ke_awan(sumber) is True
    assert sorted(f.name for f in terlihat_awan.iterdir()) == [
        "informatika_20260101_000000.dump.enc", "nilai_20260101_000000.xlsx.enc"]
    ca.dekripsi_berkas(terlihat_awan / "nilai_20260101_000000.xlsx.enc", tmp_path / "buka", kunci[1], FRASA)
    assert (tmp_path / "buka").read_bytes() == sumber[1].read_bytes()


def test_awan_hanya_menyimpan_30_terbaru_dan_peringatkan_salinan_polos(tmp_path, terlihat_awan, capsys, monkeypatch):
    terlihat_awan.mkdir()
    for i in range(33):
        (terlihat_awan / f"informatika_202601{i:02d}_000000.dump.enc").write_bytes(b"x")
    (terlihat_awan / "informatika_20250101_000000.dump").write_bytes(b"polos")      # sisa sebelum ada enkripsi
    (terlihat_awan / "catatan-saya.txt").write_bytes(b"jangan disentuh")
    backup_db.salin_ke_awan(_berkas(tmp_path, "informatika_20260301_000000.dump"))
    enc = sorted(terlihat_awan.glob("informatika_*.dump.enc"))
    assert len(enc) == backup_db.SIMPAN and enc[-1].name == "informatika_20260301_000000.dump.enc"
    assert (terlihat_awan / "catatan-saya.txt").exists() and (terlihat_awan / "informatika_20250101_000000.dump").exists()
    assert "belum terenkripsi" in capsys.readouterr().out


def test_folder_awan_tak_bisa_dibuat_tidak_menggagalkan_cadangan(tmp_path, monkeypatch, kunci, capsys):
    pub = tmp_path / "publik.pem"
    pub.write_bytes(kunci[0])
    monkeypatch.setenv("BACKUP_PUBLIC_KEY", str(pub))
    terhalang = tmp_path / "berkas-biasa"
    terhalang.write_text("bukan folder")
    monkeypatch.setenv("BACKUP_COPY_DIR", str(terhalang / "sub"))
    assert backup_db.salin_ke_awan(_berkas(tmp_path, "informatika_20260101_000000.dump")) is False
    assert "gagal menyalin" in capsys.readouterr().out


def test_tanpa_tujuan_awan_tidak_ada_yang_terjadi(tmp_path, monkeypatch):
    monkeypatch.delenv("BACKUP_COPY_DIR", raising=False)
    assert backup_db.salin_ke_awan(_berkas(tmp_path, "informatika_20260101_000000.dump")) is True


# ---------- cadangan nyata + uji pemulihan ----------

def test_cadangan_database_nyata_bisa_dipulihkan_ke_database_sementara(tmp_path, monkeypatch, data):
    monkeypatch.setattr(backup_db, "FOLDER", tmp_path)
    dump = backup_db.backup_db("20260101_000000")
    assert dump and dump.exists() and backup_db.dump_terbaca(dump)
    h = uji_pemulihan.uji(dump)
    assert h["ok"], h["pesan"]
    assert h["tabel"]["users"] == (1, 1)
    assert h["tabel"]["students"][0] == h["tabel"]["students"][1] > 0          # isi cadangan = isi database sekarang
    # database sementara sudah dibuang, database asli utuh
    with engine.connect() as c:
        nama = [r[0] for r in c.exec_driver_sql("SELECT datname FROM pg_database")]
    assert not any(n.endswith(uji_pemulihan.AKHIRAN) for n in nama)


def test_berkas_dump_rusak_gagal_diuji_dan_tidak_meninggalkan_database_sementara(tmp_path):
    rusak = tmp_path / "rusak.dump"
    rusak.write_bytes(b"bukan dump postgres")
    h = uji_pemulihan.uji(rusak)
    assert h["ok"] is False and "GAGAL" in h["pesan"]
    with engine.connect() as c:
        assert not [r for r in c.exec_driver_sql("SELECT datname FROM pg_database") if r[0].endswith(uji_pemulihan.AKHIRAN)]


def test_dump_terpotong_dibuang_saat_cadangan(tmp_path, monkeypatch):
    monkeypatch.setattr(backup_db, "FOLDER", tmp_path)
    monkeypatch.setattr(backup_db, "dump_terbaca", lambda _: False)
    assert backup_db.backup_db("20260101_000001") is None
    assert not list(tmp_path.glob("*.dump"))
