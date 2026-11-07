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
| Rombel / penempatan siswa | ✅ saat bulk import | ✅ | ❌ pindah rombel | ✅ keluarkan dari rombel |
| Tahun ajaran / tingkat | lewat script | — | `ganti_tahun_ajaran.py` | ❌ |

## Tahap 3 — Rapikan Git (7 Nov 2026)

- [x] `.gitattributes` ditambahkan (akhir baris seragam di semua komputer)
- [x] `.gitignore`: `cloudflared.exe`/`*.exe`, `_to_delete/`, `.pytest_cache/`
- [x] Commit per kelompok perubahan & push ke GitHub (`fc54f9a..b816e56`)

## Tahap 3b — Fitur rombel & tahun ajaran (7 Nov 2026)

- [x] Bug: Bulk Import mengabaikan pilihan "Rombel Tujuan" (siswa tidak masuk rombel). Sekarang langsung terdaftar
- [x] Bug: dropdown rombel memakai ID tulisan tangan (1–9) yang tidak cocok dengan database. Sekarang diambil dari database
- [x] Fitur baru: tombol **✕ Keluarkan** di Kelola Siswa (hapus keanggotaan rombel saja; akun & nilai tetap)
- [x] Script `ganti_tahun_ajaran.py`: 2026/2027 jadi aktif, keanggotaan rombel ikut pindah
- [x] Diuji: bulk import ke rombel, bulk import tanpa rombel, keluarkan siswa, ganti tahun 2x (tidak dobel), leaderboard 200
- [x] Fix error `expression 'Student' failed to locate a name` saat menjalankan `ganti_tahun_ajaran.py`: `app/models/__init__.py` kini mendaftarkan semua model
- [x] Pelajaran error dicatat di `CLAUDE.md` (cara verifikasi + tabel error)
- [x] Pencarian nama login siswa kembali minimal 3 huruf, hanya siswa aktif; tes `test_student_search_too_short` lulus lagi
- [ ] Jalankan `python ganti_tahun_ajaran.py` di laptop (PostgreSQL)
- [ ] Commit & push

## Tahap 4 — Perapihan struktur folder (berikutnya)

- [ ] Template lama yang tidak dipakai lagi: `teacher/login.html`, `student/login.html`, `teacher/dashboard.html`
- [ ] Folder kosong `app/templates/components/`
- [ ] Script lepas `app/add_student.py`, `app/add_achievements.py`, `seed_rombel.py`: satukan ke folder `scripts/`
- [ ] `teacher.py` (±500 baris) dipecah per fitur
- [ ] Hapus isi `_to_delete/` setelah dicek

## Keputusan yang menunggu Anda

- [x] Rombel lama **VII-A**: dikosongkan manual lewat tombol Keluarkan (rombelnya sendiri dihapus di Tahap 4)
- [x] Tahun ajaran → 2026/2027
- [x] Pencarian nama login: minimal 3 huruf, siswa aktif saja
- [ ] Sistem pindah rombel: pindah massal (B) + naik kelas otomatis (C) — menunggu konfirmasi rancangan
