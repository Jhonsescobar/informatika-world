# Panduan Kerja Proyek Informatika World

LMS Informatika SMP: FastAPI + SQLAlchemy 2 + PostgreSQL + Jinja2 + Tailwind (CDN).
Dijalankan di Windows (PowerShell, `venv`). Guru login email/password, siswa login nama + PIN.

## Struktur penting

- `app/models/` — model SQLAlchemy. `__init__.py` WAJIB mengimpor semua modul model.
- `app/routers/` — `auth.py`, `teacher.py` (prefix `/teacher`), `student.py` (prefix `/student`)
- `app/templates/` — Jinja2 (`Environment` manual, autoescape mati: hati-hati menyisipkan data ke JS)
- `migrations/` — Alembic. Ubah struktur tabel = buat migrasi baru
- `app/templates/layouts/` — `base.html` (head, font, 3D), `auth.html`, `teacher.html` (sidebar), `student.html` (dock bawah), `icons.html` (macro `icon()` dan `brand()`)
- `app/static/css/iw.css` — semua warna di variabel `:root`; komponen: `.panel`, `.btn-*`, `.input`, `.chip`, `.table`, `.row`, `.stat`, `.notice`
- `app/static/js/iw-scene.js` — latar 3D Three.js 0.160.0; `data-variant="globe"` (guru/login) atau `"stream"` (siswa)

## Aturan tampilan

- Halaman baru WAJIB `{% extends "layouts/teacher.html" %}` / `student.html` / `auth.html`, set `active` (guru) di atas
- Font: **Raleway Bold** (judul, `--font-display`) + **Montserrat** (isi, label, angka, `--font-body`). Hanya dua font.
  Raleway memakai angka gaya lama: `body` sudah `lining-nums`; kolom angka pakai `tabular-nums`
- Tanpa emoji di judul/tombol, tanpa em dash, copy pendek dan spesifik (lihat skill anti-ai-slop)
- Nama dari database yang masuk atribut HTML atau JS pakai `|e`
- Jangan ubah `action`, `method`, atau `name` form saat merombak tampilan
- Script di root (`seed_rombel.py`, `ganti_tahun_ajaran.py`) dijalankan `python <nama>.py` dari root

## Fakta skema yang sering salah ditebak

- `AcademicYear.is_active` bertipe **Integer** (1/0), bukan Boolean
- `Rombel.class_id` wajib (FK ke `classes` / model `SchoolClass`)
- `Enrollment.academic_year_id` wajib; siswa masuk rombel = baris `Enrollment`
- ID rombel di database TIDAK urut 1–9; jangan pernah menulis ID manual di template

## Cara verifikasi sebelum menyerahkan kode

1. Baca model asli dulu, jangan menebak nama kelas/kolom.
2. Jalankan script **persis seperti user**: proses Python baru, `python nama_script.py`,
   terhadap database uji yang dibangun di proses terpisah. Menjalankan lewat `runpy`/import
   di proses yang sudah memuat semua model bisa menyembunyikan error.
3. Uji tiap modul model diimpor sendirian: `python -c "import app.models.<modul>; from sqlalchemy.orm import configure_mappers; configure_mappers()"`.
4. `pytest` dengan database yang BERISI data, bukan hanya database kosong.
5. Halaman yang diubah: buka dengan Playwright, cek error JS dan perilakunya.
   Untuk perombakan tampilan: bandingkan form versi lama vs baru (action/method/name) di setiap halaman,
   uji di PostgreSQL + psycopg2 (sama dengan laptop), 3 ukuran layar, dan tanpa scroll menyamping.
6. Ikuti akhir baris file asli (kebanyakan CRLF).

## Catatan error yang pernah terjadi

| Error | Penyebab | Pencegahan |
|---|---|---|
| `ModuleNotFoundError: app.models.rombel` | Menebak lokasi model | Baca `app/models/` dulu |
| `NotNullViolation class_id` | Rombel dibuat tanpa tingkat; versi baru script tidak tersalin ke disk | Cek file di disk, bukan percakapan |
| `class_id` kosong di `app/seed.py` | Memakai `kelas.id` sebelum `db.flush()` | `db.flush()` sebelum memakai id baris baru |
| `is_active=True` ke kolom Integer | Asumsi tipe kolom | Cek tipe kolom di model |
| `expression 'Student' failed to locate a name` | Script hanya mengimpor `academic.py`; `relationship("Student")` butuh model Student terdaftar | `app/models/__init__.py` mengimpor semua model; uji di proses baru |
| Bulk import tidak memasukkan siswa ke rombel | Form mengirim `rombel_id`, route mengabaikannya | Cocokkan field form dengan yang dibaca route |
| Route ganda di `teacher.py` | Kode ditempel ulang | Cek route ganda via `app.openapi()` |
| `integer = character varying` di login PIN (hanya dengan driver psycopg 3) | `student_id` dari form berupa teks dibandingkan dengan kolom Integer | Selalu `int()` nilai form sebelum query |
| Menghapus siswa gagal `NotNullViolation student_id` | ORM mencoba mengosongkan FK anak | Hapus anak dulu (jawaban → sesi → nilai → achievement → enrollment) dalam satu transaksi |
| Partikel 3D jadi gumpalan putih | `gl_PointSize` terlalu besar + blending aditif | Ukuran titik 2–6 px; cek screenshot, bukan hanya "tidak error" |
| Scroll menyamping di HP | Grid `1fr` melebar mengikuti isi | `minmax(0, 1fr)` dan `min-width: 0` |

## Git

- Commit dijalankan user dari PowerShell (kredensial GitHub ada di sana).
- Jangan menjalankan git yang menulis dari sesi jarak jauh: menyisakan `.git/index.lock`.
- Progres dan keputusan dicatat di `PROGRES.md`.
