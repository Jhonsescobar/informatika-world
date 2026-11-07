# Progres Informatika World

Status per 7 November 2026. `[x]` selesai, `[ ]` belum. Urutan roadmap = urutan prioritas.

## Sudah selesai

### Fondasi & data
- [x] Struktur akademik: tahun ajaran (2026/2027 aktif), tingkat VII–IX, 9 rombel VII.1–IX.3
- [x] `seed_rombel.py` dan `ganti_tahun_ajaran.py` (aman dijalankan berulang)
- [x] `app/models/__init__.py` mendaftarkan semua model (mencegah error relasi saat menjalankan script)
- [x] Git rapi: `.gitattributes`, `.gitignore`, riwayat commit per fitur

### Fitur guru
- [x] Materi: tambah, lihat, hapus
- [x] Bank soal & soal pilihan ganda: tambah, lihat, hapus bank (ikut menghapus soal, ujian, dan jawaban)
- [x] Ujian: buat, terbitkan / tarik, hasil per siswa, analitik 3 soal tersulit, hapus
- [x] Komponen nilai & bobot per tingkat, rekap nilai akhir per tingkat
- [x] Siswa: tambah massal + PIN otomatis langsung ke rombel, cetak PIN
- [x] Saring per rombel, cari nama, centang / pilih semua
- [x] Aksi massal: pindah rombel, nonaktifkan, aktifkan, keluarkan dari rombel, hapus permanen
- [x] Hapus permanen (satu atau banyak): rincian data yang ikut terhapus, konfirmasi ketik HAPUS, satu transaksi
- [x] Kisi-kisi: materi dibuka/ditutup guru per materi, batas waktu baca opsional
- [x] Remedial: siswa dengan nilai < 60% mengajukan, guru menyetujui/menolak, izin sekali pakai, nilai tertinggi dipakai
- [x] Hasil ujian menampilkan nama siswa, persen, percobaan remedial, dan jumlah pelanggaran
- [x] Soal esai: kunci jawaban (boleh beberapa), kata kunci wajib + sinonim, poin
- [x] Penilaian esai otomatis (kata dasar, salah ketik, sinonim, kata kunci) + koreksi guru per jawaban
- [x] Soal acak per siswa: "soal per siswa" diambil acak dari bank, tetap sama saat halaman dimuat ulang
- [x] Detail sesi: jawaban per soal, kapan dijawab, berapa kali ganti, linimasa klik/tap + pelanggaran

### Fitur siswa
- [x] Login 2 langkah: cari nama (minimal 3 huruf, siswa aktif saja) lalu PIN
- [x] Hanya melihat dan bisa memulai ujian untuk tingkat rombelnya
- [x] Kisi-kisi untuk tingkatnya: tidak bisa diseleksi, disalin, dicetak; isi tertutup saat meninggalkan halaman; watermark nama + waktu
- [x] Beranda ujian, mengerjakan ujian dengan timer, hasil per soal, peringkat rombel & angkatan, lencana
- [x] Satu ujian dikerjakan sekali; ujian yang selesai tampil "Selesai"; jawaban terkirim otomatis saat waktu habis
- [x] Jawaban PG & esai tersimpan berkala: tidak hilang bila halaman tidak sengaja dimuat ulang

### Anti-cheat ujian
- [x] Layar pembuka + layar penuh; tombol kembali browser dikunci
- [x] Pindah tab / aplikasi / keluar layar penuh tercatat di server; peringatan 1–2, kirim otomatis pada ke-3
- [x] Salin, tempel (termasuk ke kotak esai), klik kanan, seret, cetak, F12 / Ctrl+Shift+I / Ctrl+U diblokir dan tercatat
- [x] PrintScreen: isi langsung ditutup, papan klip dikosongkan, tercatat
- [x] Watermark nama siswa + waktu di seluruh layar ujian
- [x] Batas: screenshot bawaan HP, rekam layar sistem operasi, dan foto dari HP lain TIDAK bisa diblokir oleh web

### Tampilan
- [x] Sistem desain bersama (3 layout, `iw.css`), font Raleway Bold + Montserrat
- [x] Latar 3D Three.js (globe guru, aliran data siswa), redup di HP, diam bila "kurangi gerak"
- [x] Responsif laptop / tablet / HP tanpa scroll menyamping

### Keamanan (diuji dengan skrip serangan di server lokal)
- [x] Password guru & PIN siswa di-hash Argon2; cookie login HttpOnly + SameSite=Lax, Secure otomatis di HTTPS
- [x] Semua halaman guru/siswa dicek peran; akun dihapus/nonaktif langsung keluar walau token masih berlaku
- [x] Tombol Keluar (sebelumnya tidak ada logout)
- [x] Batas 5x salah login per 10 menit (PIN siswa dan password guru)
- [x] Siswa hanya bisa membuka dan mengirim sesi ujian miliknya sendiri
- [x] Skor dihitung server dari soal di bank ujian itu saja; opsi harus milik soalnya (sebelumnya nilai penuh bisa dipalsukan)
- [x] Jawaban tidak bisa dikirim ulang; batas waktu ditegakkan server (toleransi 2 menit)
- [x] Halaman error umum; detail teknis hanya di log server (sebelumnya traceback tampil ke siswa)
- [x] `/docs`, `/redoc`, `/openapi.json` dimatikan
- [x] Login PIN tidak lagi bergantung pada driver database (konversi `student_id` ke angka)

## Roadmap: perlu, belum dikerjakan

### Prioritas tinggi (keamanan & data)
- [ ] **Ganti password guru default** `guru123` dan buat halaman ganti password
- [ ] **Pastikan `SECRET_KEY` di `.env` panjang dan acak** (`python -c "import secrets; print(secrets.token_urlsafe(48))"`)
- [ ] **Backup database terjadwal** (`pg_dump` harian ke folder lain / cloud). Saat ini belum ada backup sama sekali
- [ ] **Ekspor nilai ke Excel/CSV** per kelas, sebelum menghapus siswa atau akhir semester
- [ ] **Jinja autoescape** belum aktif di 3 router: teks yang diketik guru (judul, nama siswa) dirender sebagai HTML
- [ ] **Header keamanan** (CSP, X-Content-Type-Options, frame-ancestors) lewat middleware
- [ ] **Reset PIN siswa** satu per satu (sekarang hanya saat akun dibuat)

### Prioritas sedang (logika yang perlu diputuskan)
- [ ] **Isi bank soal minimal 2x jumlah soal per siswa** supaya kombinasi soal benar-benar beragam
- [ ] **Esai: daftar kata kunci tanpa kalimat bisa dapat nilai penuh** — guru tetap cek jawaban di halaman detail
- [ ] **Mode ujian pengawas**: guru melihat siapa sedang mengerjakan dan pelanggarannya secara langsung
- [ ] **Komponen nilai otomatis**: setiap ujian membuat komponen bernama judul ujian dengan bobot 100%, sehingga total bobot per tingkat lewat dari 100%. Saran: guru memilih komponen tujuan saat membuat ujian
- [ ] **Leaderboard & rekap belum menyaring tahun ajaran aktif** (wajib sebelum fitur naik kelas)
- [ ] **Edit** materi, soal, ujian, dan data siswa (nama/NIPD)

### Fitur berikutnya
- [ ] Naik kelas otomatis di akhir tahun ajaran (dengan pratinjau)
- [ ] Hapus rombel kosong (misalnya VII-A dari data awal)

### Kerapian & operasional
- [ ] Pindahkan script lepas (`seed_rombel.py`, `ganti_tahun_ajaran.py`, `app/add_*.py`) ke folder `scripts/`
- [ ] Pecah `teacher.py` (±600 baris) per fitur
- [ ] Simpan three.js dan CSS Tailwind di `app/static` agar web tetap jalan tanpa internet (Tailwind CDN tidak disarankan untuk produksi)
- [ ] Tes otomatis untuk alur ujian & keamanan (sekarang 4 tes dasar)
- [ ] Hapus isi `_to_delete/` dan folder kosong `app/templates/components/`
