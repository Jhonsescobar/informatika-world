# Progres Perapihan — Informatika World

Ceklis ini diperbarui setiap selesai satu langkah. `[x]` = selesai, `[ ]` = belum.

## Tahap 1 — Perbaikan seed rombel (7 Nov 2026)

- [x] Akar error `NotNullViolation class_id` ditemukan: file di disk masih versi 2
- [x] `seed_rombel.py` ditulis ulang (±80 baris, memakai model asli `SchoolClass`, `AcademicYear`, `Rombel`, `Enrollment`)
- [x] Bug `is_active=True` di versi 3 dihindari (kolomnya Integer, diisi `1`)
- [x] `app/seed.py`: tambah `db.flush()` agar `class_id` rombel terisi saat setup dari database kosong
- [x] Dijalankan di PostgreSQL: 9 rombel dibuat, 33 siswa masuk VII.1

## Tahap 2 — Audit CRUD & sinkronisasi (7 Nov 2026)

- [x] Semua route guru dilindungi `require_teacher`, semua route siswa dilindungi `require_student`
- [x] Semua template yang dipanggil router ada; semua link/form di template punya route
- [x] Route ganda di `teacher.py` dihapus (`GET /teacher/students` dan `POST /teacher/students/bulk-create` tertulis 2x) + `import random` ganda
- [x] Uji otomatis: `pytest` 4/4 lulus; 9 halaman guru & siswa + bulk-create siswa membalas 200
- [x] Model tidak mengubah struktur tabel (hanya menambah `relationship`), jadi migrasi Alembic tidak perlu ditambah

### Matriks CRUD

| Fitur | Create | Read | Update | Delete |
|---|---|---|---|---|
| Materi | ✅ | ✅ | ❌ | ✅ |
| Bank soal | ✅ | ✅ | ❌ | ✅ (ikut hapus soal, ujian, sesi, jawaban) |
| Soal | ✅ | ✅ (di detail bank) | ❌ | ❌ |
| Ujian | ✅ | ✅ + hasil + analitik | publish/unpublish saja | ✅ |
| Komponen nilai | ✅ | ✅ + rekap per tingkat | ❌ | ✅ |
| Nilai | otomatis dari ujian | ✅ | ❌ input manual | ❌ |
| Siswa | ✅ massal + PIN | ✅ | ❌ (nama/NIPD/reset PIN) | nonaktifkan saja |
| Rombel / penempatan siswa | lewat `seed_rombel.py` | ✅ (leaderboard) | ❌ pindah rombel | ❌ |
| Tahun ajaran / tingkat | lewat seed | — | ❌ | ❌ |

## Tahap 3 — Rapikan Git (7 Nov 2026)

- [x] `.gitattributes` ditambahkan (akhir baris seragam di semua komputer)
- [x] `.gitignore`: `cloudflared.exe`/`*.exe`, `_to_delete/`, `.pytest_cache/`
- [ ] Commit per kelompok perubahan & push ke GitHub (dijalankan dari PowerShell)

## Tahap 4 — Perapihan struktur folder (berikutnya)

- [ ] Template lama yang tidak dipakai lagi: `teacher/login.html`, `student/login.html`, `teacher/dashboard.html`
- [ ] Folder kosong `app/templates/components/`
- [ ] Script lepas `app/add_student.py`, `app/add_achievements.py`, `seed_rombel.py`: satukan ke folder `scripts/`
- [ ] `teacher.py` (±500 baris) dipecah per fitur
- [ ] Hapus isi `_to_delete/` setelah dicek

## Keputusan yang menunggu Anda

- [ ] Rombel lama **VII-A** (1 siswa) dari seed awal: hapus, atau pindahkan siswanya ke VII.1?
- [ ] Tahun ajaran aktif masih **2024/2025**: ganti ke 2026/2027?
- [ ] Fitur CRUD mana yang paling dibutuhkan dulu (lihat ❌ di matriks)
