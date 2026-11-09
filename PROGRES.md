# Progres Informatika World

Status per 9 November 2026. `[x]` selesai, `[ ]` belum. Urutan roadmap = urutan prioritas.

## Sudah selesai

### Fondasi & data
- [x] Struktur akademik: tahun ajaran (2026/2027 aktif), tingkat VII–IX, 9 rombel VII.1–IX.3
- [x] `seed_rombel.py` dan `ganti_tahun_ajaran.py` (aman dijalankan berulang)
- [x] `app/models/__init__.py` mendaftarkan semua model (mencegah error relasi saat menjalankan script)
- [x] Git rapi: `.gitattributes`, `.gitignore`, riwayat commit per fitur

### Fitur guru
- [x] Materi: tambah, **edit**, **pratinjau** (sama dengan layar siswa), hapus
- [x] Materi bisa berformat (judul, daftar, tebal, kode, tautan) atau HTML interaktif buatan AI (tampil di kotak aman ber-sandbox)
- [x] Buka materi untuk siswa: "Mulai tampil" & "Tutup otomatis" berlabel jelas, tanggal yang sudah lewat ditolak dengan pesan
  (dulu isian tanpa label, tanggal lewat diterima diam-diam -> materi langsung "Batas waktu lewat")
- [x] Bank soal & soal pilihan ganda: tambah, lihat, hapus bank (ikut menghapus soal, ujian, dan jawaban)
- [x] Bank soal 2 mode: **Manual** atau **Tempel dari AI** (prompt siap salin, JSON dirapikan otomatis, kesalahan per nomor, pratinjau sebelum simpan, soal kembar dilewati, maks 100 soal sekali impor)
- [x] Soal boleh berisi potongan kode Python (blok kode rapi di layar siswa, aman dari HTML/skrip)
- [x] Hapus satu soal (terkunci bila ujian dari bank itu sudah pernah dikerjakan)
- [x] Perbaikan: opsi PG di halaman bank soal sebelumnya tidak tampil
- [x] Ujian: buat, terbitkan / tarik, hasil per siswa, analitik 3 soal tersulit, hapus
- [x] Komponen nilai & bobot per tingkat (total ≤ 100% divalidasi); ujian dipilihkan komponen saat dibuat
- [x] Rekap nilai akhir per tingkat: hanya tahun ajaran aktif, nilai tertinggi tiap ujian, urut nilai / A–Z / Z–A, saring rombel
- [x] Ekspor Excel: rekap per kelas, semua kelas, dan hasil per ujian
- [x] Hasil ujian: urut nilai / nama, tombol **Beri remedial** untuk nilai < 60%
- [x] Reset PIN satu siswa atau massal (PIN lama & sesi login lama langsung tidak berlaku)
- [x] Halaman **Akun**: ganti password lewat web (perangkat lain otomatis keluar)
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
- [x] Menu **Materi** di sisi siswa + pemberitahuan materi baru di beranda; tidak bisa diseleksi, disalin, dicetak; isi tertutup saat meninggalkan halaman; watermark nama + waktu
- [x] Beranda ujian, mengerjakan ujian dengan timer, hasil per soal, peringkat rombel & angkatan, lencana
- [x] Satu ujian dikerjakan sekali; ujian yang selesai tampil "Selesai"; jawaban terkirim otomatis saat waktu habis
- [x] Jawaban PG & esai tersimpan berkala: tidak hilang bila halaman tidak sengaja dimuat ulang

### Anti-cheat ujian
- [x] Layar pembuka + layar penuh; tombol kembali browser dikunci
- [x] Pindah tab / aplikasi / keluar layar penuh tercatat di server; peringatan 1–2, kirim otomatis pada ke-3
- [x] Perbaikan: satu kali keluar dari layar penuh dulu terhitung 2 kejadian (ujian berhenti di keluar ke-2). Kini catatan dalam 3 detik = 1 kejadian, di browser dan di server
- [x] Salin, tempel (termasuk ke kotak esai), klik kanan, seret, cetak, F12 / Ctrl+Shift+I / Ctrl+U diblokir dan tercatat
- [x] Tempel dari papan klip HP diblokir: tombol papan klip di keyboard (Gboard/SwiftKey/Samsung), menu tekan-lama, komposisi keyboard, seret-lepas. Teks > 20 huruf yang masuk sekaligus dibatalkan; papan klip dikosongkan saat kotak jawaban disentuh. Batas: riwayat papan klip keyboard tidak bisa dihapus web, dan dikte suara kalimat panjang ikut tertahan
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
- [x] Ganti password / reset PIN membatalkan semua token lama; masa login 4 jam (ujian panjang tidak terputus)
- [x] PIN dibuat dengan `secrets` (bukan `random`); PIN manual wajib 4–6 angka
- [x] Header keamanan (nosniff, anti-frame, no-store di halaman guru/siswa); app menolak jalan bila `SECRET_KEY` pendek
- [x] Ekspor Excel aman dari rumus jahat (nama diawali `=`, `+`, `-`, `@`)
- [x] Login PIN tidak lagi bergantung pada driver database (konversi `student_id` ke angka)

## Roadmap: perlu, belum dikerjakan

### Prioritas tinggi (keamanan & data)
- [x] Script `ganti_password_guru.py` (password diketik saat berjalan, tidak disimpan di file)
- [ ] Jalankan `python ganti_password_guru.py` di laptop sebelum web dionlinekan
- [x] Halaman ganti password di web
- [x] `SECRET_KEY` di laptop sudah 42 karakter; app kini menolak kunci pendek
- [x] Cadangan otomatis sebelum & sesudah sesi (`backup_db.py`, 30 terakhir, opsional salin ke Google Drive) + `pulihkan_db.py`
- [x] Ekspor nilai ke Excel
- [ ] **Jinja autoescape** belum aktif di 3 router: teks yang diketik guru (judul, nama siswa) dirender sebagai HTML
- [x] Header keamanan dasar (CSP belum: banyak script inline)
- [x] Audit 9 Nov: klik Mulai/Kirim bersamaan tidak membuat sesi/jawaban ganda (kunci baris database)
- [x] Waktu habis tanpa terkirim (HP mati, sinyal putus): dinilai dari jawaban yang tersimpan berkala; log setelah waktu habis ditolak
- [x] Pencarian nama siswa: tanda % dan _ tidak lagi menampilkan semua nama, dibatasi per perangkat
- [x] Login guru dikunci per email + perangkat (orang lain tidak bisa mengunci guru); PIN dibatasi juga per perangkat
- [x] Log esai & catatan pelanggaran dibatasi per sesi (tidak bisa membanjiri database)
- [x] **Server macet total saat 15+ siswa login bersamaan** (ditemukan di simulasi): koneksi database dipegang sambil menunggu; diperbaiki + uji pola kode
- [x] Reset PIN siswa

### Prioritas sedang (logika yang perlu diputuskan)
- [ ] **Isi bank soal minimal 2x jumlah soal per siswa** supaya kombinasi soal benar-benar beragam
- [x] Esai: deretan kata kunci dibatasi 50% dan ditandai "Perlu dicek"
- [x] Esai: jawaban di luar topik (misalnya surat panjang) bernilai 0 dan ditandai; tanpa kata kunci cocok = kemiripan 0
- [x] Esai: kata kunci dibaca sebagai frasa (semua katanya harus ada); tafsiran kata kunci ditampilkan di bank soal
- [x] Tombol **Hitung ulang esai** di hasil ujian (koreksi manual guru tidak berubah)
- [ ] **Mode ujian pengawas**: guru melihat siapa sedang mengerjakan dan pelanggarannya secara langsung
- [x] Logika nilai dirombak: guru memilih komponen tujuan saat membuat ujian
- [x] Peringkat & rekap hanya tahun ajaran aktif
- [ ] **Edit** materi, soal, ujian, dan data siswa (nama/NIPD)

- [x] Komponen ujian bisa diganti langsung dari daftar Ujian (untuk ujian lama yang "tanpa komponen")
- [ ] Siswa nonaktif masih tampil di rekap & peringkat (sengaja: nilainya tetap tercatat)

- [x] Simulasi kelas mode lokal: 30 HP, 2 gelombang x 15 bersamaan, semua data masuk, Excel & cadangan berhasil
- [x] Uji beban server: 30 siswa + guru bersamaan selesai 6,9 detik tanpa gagal

### Fitur berikutnya
- [ ] Naik kelas otomatis di akhir tahun ajaran (dengan pratinjau)
- [ ] Hapus rombel kosong (misalnya VII-A dari data awal)

### Kerapian & operasional
- [x] `ONLINE.bat`: mode internet (Cloudflare) atau jaringan lokal, cadangan otomatis, cegah laptop tidur, nyalakan ulang otomatis
- [x] `PANDUAN_ONLINE.md`
- [ ] Uji `ONLINE.bat` pertama kali di laptop (belum bisa diuji di luar Windows)
- [ ] Pindahkan script lepas (`seed_rombel.py`, `ganti_tahun_ajaran.py`, `app/add_*.py`) ke folder `scripts/`
- [ ] Pecah `teacher.py` (±600 baris) per fitur
- [x] three.js, Tailwind (build), dan font disimpan di `app/static`: web jalan tanpa internet
- [x] 114 uji otomatis (`python -m pytest -q`): nilai, keamanan, akun, ekspor, esai, fitur kelas
- [ ] Hapus isi `_to_delete/` dan folder kosong `app/templates/components/`
