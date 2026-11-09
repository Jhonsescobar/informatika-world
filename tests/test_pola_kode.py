# tests/test_pola_kode.py
# Pola kode yang pernah membuat server macet total saat 30 siswa login bersamaan (simulasi 9 Nov 2026):
# route `async def` memakai `db`, lalu `await` (form / thread) tanpa melepas koneksi dulu.
# Koneksi yang dipegang sambil menunggu menghabiskan pool, dan jalur utama server ikut berhenti.

import re
from pathlib import Path

POLA_DB = re.compile(r"\bdb\.(query|get|add|execute)|\b(halaman_bank|reset_pin_siswa|bank_terkunci|tutup_sesi_lewat|rekap_kelas)\(")


def test_tidak_ada_await_saat_memegang_koneksi_database():
    temuan = []
    for f in Path("app/routers").glob("*.py"):
        baris = f.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
        i = 0
        while i < len(baris):
            m = re.match(r"\s*async def (\w+)\(", baris[i])
            if not m:
                i += 1
                continue
            j, isi = i + 1, []
            while j < len(baris) and not re.match(r"^(@router|async def|def |[A-Za-z_])", baris[j]):
                isi.append((j + 1, baris[j]))
                j += 1
            pertama = next((n for n, l in isi if POLA_DB.search(l)), None)
            if pertama:
                lepas = [n for n, l in isi if "db.rollback()" in l or "db.commit()" in l]
                for n, l in isi:
                    if n > pertama and "await " in l and not any(pertama < r < n for r in lepas):
                        temuan.append(f"{f.name}:{n} {m.group(1)}: {l.strip()[:60]}")
            i = j
    assert not temuan, "await setelah memakai db tanpa melepas koneksi:\n" + "\n".join(temuan)
