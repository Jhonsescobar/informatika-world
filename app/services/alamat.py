# app/services/alamat.py
# Alamat web untuk siswa (dipakai halaman QR guru).
#
# Sumber utama: logs/alamat.json yang ditulis online.ps1 setiap kali alamat diketahui
# (tunnel Cloudflare menyala, alamat tunnel berganti, atau web dinyalakan ulang), dan dihapus
# saat sesi dimatikan. Isinya divalidasi ketat: QR hanya boleh mengarah ke alamat tunnel
# trycloudflare atau IP jaringan lokal, bukan ke situs lain.

import json
import re
import time
from datetime import datetime
from pathlib import Path

import segno

FILE_ALAMAT = Path(__file__).resolve().parents[2] / "logs" / "alamat.json"
MULAI_PROSES = time.time()

POLA_TUNNEL = re.compile(r"^https://[a-z0-9-]+\.trycloudflare\.com/login$")
POLA_LOKAL = re.compile(r"^http://(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3}):(\d{2,5})/login$")
POLA_HOST = re.compile(r"^(https?)://([a-z0-9.-]+)(:\d{2,5})?/$")


def alamat_sah(url) -> bool:
    if not isinstance(url, str) or len(url) > 200:
        return False
    if POLA_TUNNEL.match(url):
        return not url.startswith("https://api.")
    m = POLA_LOKAL.match(url)
    if not m:
        return False
    *oktet, port = (int(x) for x in m.groups())
    return all(o <= 255 for o in oktet) and oktet[0] not in (0, 127) and 1 <= port <= 65535


def baca_file(path: Path = None) -> dict | None:
    """Isi alamat.json yang sah, atau None. File yang lebih tua dari proses web ini dianggap sisa
    sesi lama (jendela ONLINE.bat ditutup dengan X), karena online.ps1 selalu menulis ulang
    file setelah web menyala."""
    path = path or FILE_ALAMAT
    try:
        if path.stat().st_mtime < MULAI_PROSES - 2:
            return None
        isi = json.loads(path.read_text(encoding="utf-8-sig"))     # PowerShell menulis UTF-8 dengan BOM
    except (OSError, ValueError):
        return None
    if not isinstance(isi, dict) or not alamat_sah(isi.get("url")):
        return None
    lain = [u for u in (isi.get("lain") or []) if alamat_sah(u) and u != isi["url"]][:3] \
        if isinstance(isi.get("lain"), list) else []
    return {"url": isi["url"], "mode": "internet" if POLA_TUNNEL.match(isi["url"]) else "lokal", "lain": lain,
            "waktu": datetime.fromtimestamp(path.stat().st_mtime).strftime("%H:%M")}


def dari_permintaan(base_url: str) -> dict | None:
    """Cadangan bila file tidak ada: guru membuka web lewat alamat yang juga bisa dibuka siswa
    (bukan localhost). Host tetap divalidasi supaya QR tidak mengarah ke tempat aneh."""
    m = POLA_HOST.match(base_url or "")
    if not m or m.group(2) in ("localhost", "127.0.0.1", "testserver"):
        return None
    url = base_url + "login"
    if not alamat_sah(url):
        return None
    return {"url": url, "mode": "internet" if url.startswith("https://") else "lokal", "lain": [], "waktu": None}


def alamat_siswa(base_url: str) -> dict | None:
    return baca_file() or dari_permintaan(base_url)


def svg_qr(url: str) -> str:
    # latar putih + tepi 4 modul: syarat agar kamera HP mudah membaca, juga di tema gelap & proyektor
    return segno.make(url, error="m").svg_inline(scale=10, border=4, dark="#000000", light="#ffffff",
                                                   omitsize=True)
