# app/services/materi.py
# Materi untuk siswa: kapan tampil, dan cara menampilkan isinya dengan aman.

import re
from datetime import datetime, timezone
from html import escape

from markupsafe import Markup


def sekarang():
    return datetime.now(timezone.utc)


def status_materi(m, kini=None) -> str:
    """tertutup | terjadwal | terbuka | lewat"""
    kini = kini or sekarang()
    if not m.is_published:
        return "tertutup"
    if m.open_at and m.open_at > kini:
        return "terjadwal"
    if m.close_at and m.close_at <= kini:
        return "lewat"
    return "terbuka"


def baca_waktu(teks: str):
    """Isian datetime-local ('2026-11-09T13:30') = jam di laptop server (WIB). Kosong/salah -> None."""
    teks = (teks or "").strip()
    if not teks:
        return None
    try:
        return datetime.strptime(teks[:16], "%Y-%m-%dT%H:%M").astimezone()
    except ValueError:
        return None


# ---------- isi materi ----------
_TAG_HTML = re.compile(r"<\s*(!doctype|html|head|body|div|section|article|style|script|table|p|h[1-6]|ul|ol|button|canvas|svg|iframe|main)\b", re.I)


def isi_html(teks: str) -> bool:
    """Isi berupa HTML (misalnya media ajar interaktif buatan AI)."""
    return bool(_TAG_HTML.search(teks or ""))


def _sebaris(t: str) -> str:
    t = escape(t)
    t = re.sub(r"`([^`\n]+)`", r'<code class="kode-sebaris">\1</code>', t)
    t = re.sub(r"\*\*([^*\n]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", t)
    # tautan hanya http(s): javascript: dan sejenisnya tidak pernah jadi tautan
    t = re.sub(r"\[([^\]\n]+)\]\((https?://[^\s)]+)\)",
               r'<a href="\2" target="_blank" rel="noopener noreferrer nofollow">\1</a>', t)
    return t


def format_materi(teks) -> Markup:
    """Teks biasa dengan format ringan: # judul, - daftar, 1. daftar, **tebal**, `kode`, ```blok kode```, [tautan](https://...).
    Semua HTML di-escape: isi tidak bisa menyisipkan skrip."""
    baris = (teks or "").replace("\r\n", "\n").split("\n")
    out, para, daftar, i = [], [], None, 0

    def tutup_para():
        if para:
            out.append("<p>" + "<br>".join(_sebaris(x) for x in para) + "</p>")
            para.clear()

    def tutup_daftar():
        nonlocal daftar
        if daftar:
            out.append(f"<{daftar[0]}>" + "".join(f"<li>{_sebaris(x)}</li>" for x in daftar[1]) + f"</{daftar[0]}>")
            daftar = None

    while i < len(baris):
        b = baris[i]
        if b.strip().startswith("```"):
            tutup_para(); tutup_daftar()
            kode = []
            i += 1
            while i < len(baris) and not baris[i].strip().startswith("```"):
                kode.append(baris[i]); i += 1
            out.append(f'<pre class="kode-blok" translate="no"><code>{escape(chr(10).join(kode))}</code></pre>')
            i += 1
            continue
        m = re.match(r"^(#{1,3})\s+(.*)", b)
        if m:
            tutup_para(); tutup_daftar()
            tingkat = {1: "h2", 2: "h3", 3: "h4"}[len(m.group(1))]
            out.append(f"<{tingkat}>{_sebaris(m.group(2))}</{tingkat}>")
        elif re.match(r"^\s*[-*•]\s+", b):
            tutup_para()
            if not daftar or daftar[0] != "ul":
                tutup_daftar(); daftar = ("ul", [])
            daftar[1].append(re.sub(r"^\s*[-*•]\s+", "", b))
        elif re.match(r"^\s*\d+[.)]\s+", b):
            tutup_para()
            if not daftar or daftar[0] != "ol":
                tutup_daftar(); daftar = ("ol", [])
            daftar[1].append(re.sub(r"^\s*\d+[.)]\s+", "", b))
        elif not b.strip():
            tutup_para(); tutup_daftar()
        else:
            tutup_daftar()
            para.append(b)
        i += 1
    tutup_para(); tutup_daftar()
    return Markup("".join(out))


# Disisipkan ke dalam materi HTML yang tampil di iframe ber-sandbox:
# teks tidak bisa diseleksi/disalin/dicetak, dan tinggi iframe mengikuti isi.
_SISIPAN_KEPALA = ("<meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
                   "<style>html,body{-webkit-user-select:none;user-select:none;-webkit-touch-callout:none}"
                   "@media print{body{display:none!important}}</style>")
_SISIPAN_AKHIR = ("<script>(function(){['copy','cut','contextmenu','dragstart','selectstart'].forEach(function(e){"
                  "document.addEventListener(e,function(x){var t=x.target;if(t&&t.closest&&t.closest('input,textarea'))return;x.preventDefault();});});"
                  # tinggi = bawah elemen terakhir (bukan scrollHeight: itu ikut tinggi kotak dan terus membesar)
                  "var akhir=0;function tinggi(){var b=document.body,h=0;if(!b)return 0;for(var i=0;i<b.children.length;i++){var c=b.children[i];"
                  "if(c.tagName==='SCRIPT'||c.tagName==='STYLE')continue;var r=c.getBoundingClientRect();if(r.height>0)h=Math.max(h,r.bottom+window.scrollY);}"
                  "var g=getComputedStyle(b);return Math.ceil(h+parseFloat(g.marginBottom||0)+parseFloat(g.paddingBottom||0));}"
                  "function lapor(){var h=tinggi();if(h>0){akhir=h;try{parent.postMessage({iwTinggi:h},'*');}catch(e){}}}"
                  "window.addEventListener('load',lapor);setInterval(lapor,800);"
                  "if(window.ResizeObserver){new ResizeObserver(lapor).observe(document.documentElement);}})();</script>")


def dokumen_iframe(teks: str) -> str:
    """Isi HTML guru + sisipan pengaman, untuk atribut srcdoc (di-escape di template)."""
    t = teks or ""
    if re.search(r"<head[^>]*>", t, re.I):
        t = re.sub(r"(<head[^>]*>)", lambda m: m.group(1) + _SISIPAN_KEPALA, t, count=1, flags=re.I)
    elif re.search(r"<html[^>]*>", t, re.I):
        t = re.sub(r"(<html[^>]*>)", lambda m: m.group(1) + "<head>" + _SISIPAN_KEPALA + "</head>", t, count=1, flags=re.I)
    else:
        t = "<!doctype html><html><head>" + _SISIPAN_KEPALA + "</head><body>" + t + "</body></html>"
    if re.search(r"</body>", t, re.I):
        t = re.sub(r"(</body>)", lambda m: _SISIPAN_AKHIR + m.group(1), t, count=1, flags=re.I)
    else:
        t += _SISIPAN_AKHIR
    return t
