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

- [x] Jawaban PG terkunci 1 menit setelah pertama dipilih (hitung mundur di layar; server menolak penggantian lewat log maupun form; percobaan tercatat di log guru)
- [x] Acak soal & opsi tercentang bawaan untuk ujian baru; bisa dinyalakan/dimatikan pada ujian lama (acak opsi ditolak saat ada siswa sedang mengerjakan)
- [x] Poin soal bisa diubah langsung di bank (1–100, terkunci bila bank sudah dipakai ujian); total poin tampil; soal PG tanpa kunci valid / esai tanpa kunci ditolak server
- [x] Halaman QR Siswa (/teacher/qr) untuk proyektor: alamat dari ONLINE.bat (logs/alamat.json), ikut berganti saat tunnel berganti, alamat divalidasi

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

## KKM bertingkat dan rapi tampilan (migrasi e5a1c9d3b7f2)
- [x] KKM tahun ajaran (default 75), KKM komponen, KKM ujian (penanda tuntas saja, tidak mengubah nilai akhir)
- [x] Urutan: KKM ujian → KKM komponen → KKM tahun ajaran; remedial tetap 60 global
- [x] Siswa melihat "Tuntas" / "Belum tuntas" tanpa angka KKM
- [x] Excel: header KKM akhir, nama kolom komponen memuat KKM, warna merah di bawah KKM
- [x] Uji `tests/test_kkm.py` (14 uji); pytest penuh 179 lulus
- [x] E2E lulus: kunci, poin massal, impor, tempel, esai, baru, rekap
- [ ] `simulasi_kelas.js` belum dijalankan (butuh data demo yang tidak ada di harness reset)
- [ ] Pasang ke laptop (md5 + migrasi)
- [x] Peri di beranda siswa (`js/iw-peri.js`, gaya di `iw.css`): bisa diseret, ketuk = kilau, posisi diingat per tab, tidak ada di halaman ujian, patuh "kurangi gerakan"
- [x] Peri: ketuk 2x = melonjak; ketuk 3x cepat = jongkok, terbang melengkung keluar layar dengan jejak kilau, muncul lagi di tempat acak (patuh "kurangi gerakan"); seretan pendek tidak dihitung ketukan (ambang 8 px)
- [x] Daftar ujian guru dirapikan (chip pengaturan seragam, KKM diklik untuk ubah); tabel hasil: warna merah/hijau menggantikan tulisan "Belum tuntas"
- [x] Kelas aktif di sidebar guru (cookie `iw_kelas`, awal VIII): Materi, Bank soal, Ujian, Nilai, Siswa mengikuti pilihan; form tidak lagi memilih kelas; tujuan pindah rombel tetap lintas kelas

## Ekspor per rombel, keamanan, pemasangan (18 Nov 2026)
- Ekspor hasil ujian: lembar "Ringkasan" + satu lembar per rombel (VIII.1, VIII.2, ...), urut alami.
- Keamanan: tautan halaman PIN siswa bertanda tangan (id berurutan tak bisa dipakai mengintip nama); tolak POST/PUT/PATCH/DELETE bila Origin/Referer dari situs lain; HSTS bila https.
- Pemasangan: ONLINE.bat menjalankan `alembic upgrade head` otomatis dan menunggu port 8000 bebas; UPDATE.bat memasang paket rilis (cadangan, cek SHA-256, migrasi, uji cepat, kembalikan kode lama bila gagal). Paket dibuat dengan `buat_rilis.py`.

## Analisis butir, remedial, grafik, rapor (18 Nov 2026)
- Analisis butir soal (`services/analisis.py`, halaman `/teacher/exams/{id}/analytics`): tingkat kesukaran, daya pembeda, sebaran pilihan, label (periksa kunci, menjebak, terlalu sulit/mudah, pembeda lemah, baik). Hanya jawaban ujian itu, satu sesi terbaik per siswa. Menggantikan analitik lama yang mencampur ujian dengan bank sama.
- Remedial: panel "Perlu remedial" di hasil ujian, tombol beri remedial ke semua, unduh daftar Excel (`services/remedial.py`).
- Grafik perkembangan: siswa `/student/progress` (menu Progres, kartu tren di beranda), guru `/teacher/students/{id}/progress` (dengan garis rata-rata rombel). Bentuk grafik dihitung di `services/perkembangan.py`, digambar SVG di `layouts/grafik.html`.
- Rapor cetak: `/teacher/grades/class/{kelas}/rapor` (?rombel=, ?siswa=), satu halaman A4 per siswa, simpan PDF lewat dialog cetak.
- Rute baru ada di `routers/teacher/analisis.py` (sebelumnya `teacher_analisis.py`). `tingkat_siswa` pindah ke `services/rekap.py`.
- Cadangan ke Google Drive: isi `BACKUP_COPY_DIR` di .env dengan folder Google Drive for Desktop (sudah didukung `backup_db.py`).

## Impor soal: kode terstruktur (18 Nov 2026)
- Isian "bahasa" (python/excel/teks) untuk kode; kode Python diperiksa sintaksnya dengan nomor baris.
- Kode Python yang menempel di satu baris (nama = "A"print(nama)) dipisah otomatis bila hasilnya valid.
- "kode_tidak_valid": true untuk soal yang sengaja berisi kode salah.
- Prompt AI dan contoh: rumus Excel, isian rumpang dengan ___.

## Pantau siswa: online dan sedang ujian (18 Nov 2026)
- Siswa mengirim sinyal tiap 60 detik saat tab terbuka dan aktif (`POST /student/ping`, `static/js/iw-hadir.js`). Kolom `students.last_seen` lewat migrasi `a7c3e91f2b40`.
- Guru: `/teacher/students/pantau` (tombol di Daftar siswa), diperbarui tiap 10 detik dari `/teacher/students/pantau/data`.
- Online = sinyal terakhir dalam 2 menit. Sedang ujian = sesi aktif yang belum lewat batas waktu, dengan progres soal dan pelanggaran.
- Hanya guru yang bisa melihat; siswa diarahkan keluar dari halaman pantau.

## Hasil ujian per rombel (20 Nov 2026)
- Halaman hasil ujian dikelompokkan per rombel (VIII.1, VIII.2, ...): satu panel tiap rombel dengan rata-rata dan jumlah tuntas, tombol loncat antar rombel, urutan alami. Daftar "Perlu remedial" bisa dilipat.

## Kesempatan melanjutkan ujian (20 Nov 2026)
- Guru bisa membuka lagi sesi yang terkirim otomatis (mis. keluar layar tak sengaja): tombol "Beri kesempatan" di hasil ujian. Jawaban tetap, waktu memakai sisa waktu (minimal 3 menit), hitungan pelanggaran mulai dari nol, catatan pelanggaran lama tetap ada. Logika di `services/kesempatan.py`.
- Hanya untuk sesi kirim otomatis yang masih punya sisa waktu dan belum punya sesi lebih baru.

## Keamanan prioritas tinggi (20 Nov 2026)
- Sandi bawaan: kolom `users.must_change_password` (migrasi `b9e4d7a1c2f6`; akun yang saat migrasi masih ber-sandi `guru123` otomatis ditandai). Selama True, `require_teacher` mengalihkan semua alamat guru selain `/teacher/account` dan `/teacher/account/password` ke halaman Akun (303). Daftar sandi terlarang satu sumber: `PASSWORD_UMUM` di `utils/security.py` (termasuk `guru123`).
- Catatan aksi guru: tabel `aksi_guru`, `services/audit.py` (`catat` sebelum `commit`, atomik dengan aksinya), halaman `/teacher/account/catatan` (saring kategori, 50 per halaman, hanya baca). Dicatat: reset PIN, tambah/hapus/aktif/nonaktif/pindah/keluarkan siswa, ubah poin esai, hitung ulang esai, remedial, beri kesempatan, ubah KKM, hapus ujian/bank soal, ganti sandi. PIN dan sandi TIDAK pernah dicatat.
- Cadangan awan terenkripsi: `cadangan_aman.py` (RSA-4096 + AES-256-GCM per berkas; laptop hanya menyimpan kunci publik), `buat_kunci_cadangan.py` (sekali), salinan `.enc` hanya 30 terbaru. Tanpa kunci publik salinan awan dilewati. `pulihkan_db.py` dan `uji_pemulihan.py` menerima berkas `.enc`.
- `uji_pemulihan.py`: pulihkan ke database sementara `<db>_uji_pulih`, bandingkan jumlah baris tiap tabel, lalu dibuang. `backup_db.py` kini membuang dump yang tak terbaca `pg_restore --list`.
- `cryptography` ditambahkan ke requirements.txt (UPDATE.bat memasangnya otomatis).

## Hasil ujian: panel rombel bisa dilipat (20 Nov 2026)
- Tiap rombel jadi satu baris ringkas (jumlah siswa, rata-rata dengan bar, tuntas, pelanggaran); tabel siswa hanya tampil saat dibuka. Rombel pertama terbuka, lainnya tertutup.
- Tombol "Buka semua"/"Tutup semua"; klik chip rombel membuka dan menggulir ke rombel itu (juga lewat alamat `#rombel-VII-2`). Memakai `<details>` bawaan browser, bisa lewat keyboard.
- Ikon baru `chevron-right` di `layouts/icons.html`.

## Kesempatan untuk sesi terputus + teacher.py dipecah (20 Nov 2026)
- Kesempatan kini juga untuk siswa yang menghilang sampai waktu habis (jaringan putus, HP mati, layar padam; sesi ditutup dari log). `services/kesempatan.py`: `info_henti` (jenis `otomatis`/`terputus`, menit keluar, saran sisa), `terakhir_aktif` (aktivitas terakhir, pelanggaran, sinyal hadir selama waktu ujian, atau saat kesempatan dibuka), `menit_sah`. Guru mengisi menit 1-180 (kosong = saran, minimal 3); sistem hanya menyarankan (sisa waktu saat siswa terakhir terlihat). Alasan henti dibaca dari event `kirim`/`kesempatan` TERAKHIR, jadi siswa yang sudah mengirim sendiri sesudah dibuka tidak ditawari lagi.
- Halaman hasil ujian: pemberitahuan "N siswa terhenti sebelum waktu habis" dengan menit keluar dan saran, serta isian menit di kolom Tindakan.
- `routers/teacher.py` (1.300+ baris) dipecah jadi paket `routers/teacher/`: `umum` (template, kelas aktif, fungsi bersama), `akun`, `materi`, `bank_soal`, `ujian`, `hasil`, `nilai`, `siswa`, `analisis`. `__init__.py` menyatukan semuanya di bawah `/teacher`; urutan penyertaan menentukan pencocokan alamat. Kode dipindah mekanis (pohon sintaks tiap fungsi dibandingkan dengan versi lama: identik). `tests/test_rute_guru.py` + `tests/rute_guru.json` menjaga daftar rute dan memastikan tak ada rute yang tertutup rute lain. Bila menambah rute guru, perbarui `rute_guru.json`.

## Acak soal per jenis (21 Nov 2026)
- `services/urutan_soal.py` (`susun_soal`): pengacakan urutan soal hanya di antara jenis yang sama. Pola jenis per nomor mengikuti bank (mis. 1-15 PG, 16-20 esai) dan tidak berpindah, jadi esai tidak naik ke nomor depan; isi tiap nomor beda per siswa. Pola selang-seling juga dipertahankan.
- Bila guru membatasi jumlah soal per siswa, jatah tiap jenis sebanding dengan isi bank dan SAMA untuk semua siswa (mis. 10 dari 15 PG + 5 esai = 8 PG + 2 esai), tiap jenis minimal 1 soal. Dulu pengambilan murni acak sehingga komposisi PG/esai bisa berbeda antar siswa.
- Tanpa acak: urutan bank. Sesi yang sudah berjalan tidak berubah (urutan terkunci di `question_ids`).

## Watermark: kekuatan per ujian, jam berjalan (21 Nov 2026)
- Watermark nama + jam di layar ujian ternyata sudah ada, tetapi kekuatannya tetap 7%. Uji foto simulasi (abu-abu, kontras 1,5x): 7% hilang sepenuhnya, 12% mulai pecah, 18% masih terbaca dan tetap nyaman bagi siswa.
- Kolom `exams.watermark_persen` (migrasi `f2a8c6d4e1b9`, bawaan 16; ujian lama otomatis 16). Pilihan di `services/watermark.py`: Mati 0, Samar 8, Sedang 16, Jelas 22. Guru memilih saat membuat ujian dan bisa mengubah lewat chip "Watermark" di daftar ujian (`POST /teacher/exams/{id}/watermark`, tercatat di Catatan aksi bila berubah). Materi memakai 8% tetap.
- Jam di watermark kini berjalan (diperbarui tiap 15 detik) dari JAM SERVER saat halaman dibuka (`data-epoch`, `data-offset`), bukan jam HP siswa yang bisa diubah. Foto yang diambil menit ke-20 tidak lagi menunjukkan jam awal.
- Batasan jujur: watermark mempersulit dan memudahkan pelacakan, tidak mencegah foto.


## Rekap hanya ujian terbit dan alur remedial per ujian (24 Nov 2026)
- Rekap nilai kelas kini hanya memuat ujian berstatus terbit. Ujian yang ditarik tetapi sudah ada hasilnya tidak dihitung; guru melihat catatan "tak ikut rekap".
- Remedial per ujian (migrasi `c4d7a2e9b1f3`): `exams.remedial_bank_id` (kosong = soal sama) dan `exams.remedial_aturan`. Sesi selesai pertama = nilai awal; sesi berikutnya = remedial. Nilai awal selalu tampil paling atas. Aturan (`services/nilai_remedial.py`): `saran` (rekap tetap nilai awal, saran akhir tampil dan ada di Excel), `kkm` (maks nilai awal, min(remedial, KKM)), `rata` (rata-rata awal dan remedial, tidak di bawah awal), `tinggi` (nilai tertinggi). Contoh awal 67, remedial 89, KKM 75: kkm 75, rata 78, tinggi 89, saran tetap 67.
- Ujian lama dimigrasi ke `tinggi` (angka rekap tidak berubah); ujian baru bawaan `saran`. Pengaturan lewat chip "Remedial" di daftar ujian (`POST /teacher/exams/{id}/remedial-pengaturan`, tercatat di Catatan aksi).
- Bank soal yang dipakai sebagai bank remedial terkunci dan tidak bisa dihapus. Analisis butir hanya memakai percobaan pertama. Lembar "Remedial" ditambahkan di Excel nilai.

## Efek kaca dan interaksi (24 Nov 2026)
- Panel, kartu angka, dan sidebar guru serta panel dashboard siswa memakai kaca (`backdrop-filter`, gradasi tipis, garis cahaya atas). Tanpa dukungan `backdrop-filter`, tampilan lama (panel pekat) dipakai. Layar ujian siswa tidak tersentuh (aturan hanya berlaku di `.shell` dan `.s-main`).
- Interaksi: kartu angka dan kartu tautan terangkat saat hover, sorot mengikuti kursor, tautan menu bergeser halus, meter terisi animasi, panel muncul halus, angka besar naik pelan (`static/js/iw-kaca.js`). Semua dimatikan bila perangkat memilih gerak minimal (`prefers-reduced-motion`); angkat hover dimatikan di layar sentuh.

## Perbaikan UI popup dan teks remedial (24 Nov 2026)
- Daftar pilihan (`select`) kini selalu gelap dengan teks terang di semua halaman (sebelumnya putih di atas putih pada popup Remedial karena memakai class `input`). Pilihan nonaktif redup, pilihan terpilih disorot.
- Popup pengaturan di daftar ujian tidak lagi terpotong panel atau tertutup panel di bawahnya; saat dibuka halaman digulir halus agar popup tampil utuh, hanya satu popup terbuka, Esc atau klik di luar menutup (`static/js/iw-kaca.js`).
- Teks lama "nilai tertinggi yang dipakai" di halaman hasil guru dan hasil siswa diganti sesuai aturan remedial ujian itu.
