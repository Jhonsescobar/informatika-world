# app/services/teks.py
# Menampilkan teks soal/opsi dengan aman.
# Template memakai autoescape mati, jadi teks soal (termasuk hasil AI) WAJIB lewat filter "soal":
#   - semua HTML di-escape: kode seperti `if x < 5` atau print("<b>") tampil apa adanya, bukan jadi HTML
#   - blok ```python ... ``` -> kotak kode (indentasi terjaga)
#   - `kode pendek` -> kode sebaris
#   - baris baru dipertahankan

import re
from html import escape
from pathlib import Path

from markupsafe import Markup

_BLOK = re.compile(r"```[a-zA-Z0-9_+-]*[ \t]*\n?(.*?)```", re.S)
_SEBARIS = re.compile(r"`([^`\n]+)`")


def _sebaris(teks: str) -> str:
    aman = escape(teks)
    aman = _SEBARIS.sub(lambda m: f'<code class="kode-sebaris">{m.group(1)}</code>', aman)
    return aman.replace("\n", "<br>")


def format_soal(teks) -> Markup:
    teks = (teks or "").replace("\r\n", "\n")
    bagian, akhir = [], 0
    for m in _BLOK.finditer(teks):
        sebelum = teks[akhir:m.start()].strip("\n")
        if sebelum:
            bagian.append(f"<span class=\"teks-soal\">{_sebaris(sebelum)}</span>")
        kode = m.group(1).strip("\n")
        bagian.append(f'<pre class="kode-blok" translate="no"><code>{escape(kode)}</code></pre>')
        akhir = m.end()
    sisa = teks[akhir:].strip("\n")
    if sisa:
        bagian.append(f"<span class=\"teks-soal\">{_sebaris(sisa)}</span>")
    return Markup("".join(bagian))


_STATIC = Path(__file__).resolve().parent.parent / "static"


def aset(jalur: str) -> str:
    """/static/... + ?v=<waktu file diubah>: HP siswa selalu mengambil versi terbaru setelah pembaruan,
    tidak memakai salinan lama di cache (misalnya iw-guard.js versi sebelum anti-tempel)."""
    try:
        versi = int((_STATIC / jalur).stat().st_mtime)
    except OSError:
        versi = 0
    return f"/static/{jalur}?v={versi}"


def grup_kunci(teks) -> list[str]:
    """Cara sistem membaca kata kunci esai, untuk ditampilkan ke guru (tiap item = 1 kata kunci wajib)."""
    from app.services.esai import baca_kata_kunci, label_grup
    return [label_grup(g) for g in baca_kata_kunci(teks or "")]


def pasang(env):
    """Daftarkan filter & fungsi bantu ke Environment Jinja milik router."""
    env.filters["soal"] = format_soal
    env.filters["grup_kunci"] = grup_kunci
    from app.services.materi import format_materi, isi_html, dokumen_iframe
    env.filters["format_materi"] = format_materi
    env.filters["isi_html"] = isi_html
    env.filters["dokumen_iframe"] = dokumen_iframe
    env.globals["aset"] = aset
