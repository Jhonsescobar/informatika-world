# Panduan sesi ujian

Web hanya dinyalakan saat ujian, dari laptop guru. Semua aset (font, tampilan, animasi) ada di laptop,
jadi web tetap rapi walau internet sekolah lambat atau putus.

## Sekali saja (persiapan)

1. Pasang paket baru: `venv\Scripts\activate` lalu `pip install -r requirements.txt`
2. Perbarui database: `alembic upgrade head`
3. Ganti password guru (di web: menu **Akun**, atau `python ganti_password_guru.py`)
4. Untuk mode internet: unduh `cloudflared-windows-amd64.exe` dari
   https://github.com/cloudflare/cloudflared/releases/latest, ganti nama jadi `cloudflared.exe`,
   taruh di `D:\informatika-world`
5. (Disarankan) Salinan cadangan ke awan: pasang Google Drive for desktop, lalu tambahkan ke `.env`:
   `BACKUP_COPY_DIR=G:\My Drive\Backup Informatika` (sesuaikan huruf drive)

## Setiap sesi ujian

1. Colokkan charger laptop
2. Klik dua kali **`ONLINE.bat`**, pilih mode:
   - **1 Internet**: siswa membuka alamat `https://....trycloudflare.com/login` dari mana saja
   - **2 Lokal**: siswa terhubung ke WiFi sekolah / hotspot laptop yang sama, membuka `http://192.168.x.x:8000/login`.
     Tidak butuh internet. Saat pertama kali, Windows bertanya izin firewall: centang **Private networks** → Allow
3. Alamat tampil kuning dan sudah tersalin. Tempel ke grup kelas
4. Selama jendela terbuka: laptop dicegah tidur, web/tunnel yang mati dinyalakan ulang otomatis
   (tunnel baru = alamat baru, bagikan ulang; jawaban siswa tidak hilang)
5. Selesai: tekan **Q** di jendela itu. **Jangan tutup dengan X** (kalau terlanjur, jalankan ONLINE.bat lagi; sisa web lama dibereskan otomatis)

Cadangan dibuat otomatis **sebelum dan sesudah** sesi di folder `backups\`:
`informatika_*.dump` (database utuh) dan `nilai_*.xlsx` (rekap nilai, bisa langsung dibuka Excel).
30 cadangan terbaru disimpan.

## Kalau ada masalah

| Gejala | Tindakan |
|---|---|
| "Web gagal menyala" | Buka `logs\web.log`. Biasanya PostgreSQL belum jalan atau `.env` salah |
| Siswa lupa PIN / PIN terkunci 5x salah | Menu Siswa → **Reset PIN** pada nama siswa (atau centang beberapa → Reset PIN). PIN baru tampil sekali |
| Siswa terlempar saat ujian | Login lagi, buka ujian: jawaban yang sudah dipilih kembali otomatis |
| Data rusak / terhapus tidak sengaja | Matikan web (Q), jalankan `python pulihkan_db.py`, pilih cadangan, ketik `PULIHKAN`. Keadaan sebelum dipulihkan disimpan dulu di `backups\pengaman_*.dump` |
| Tunnel tidak muncul | Internet laptop bermasalah. Jalankan ulang, pilih mode 2 (lokal) |

## Batasan yang perlu diketahui

- Alamat mode internet berganti setiap sesi. Alamat tetap butuh domain sendiri + Cloudflare Tunnel bernama
- Satu laptop = satu titik gagal. Laptop mati di tengah ujian: siswa tunggu, nyalakan lagi, jawaban yang sudah terpilih tetap ada
- Anti-cheat tidak bisa mencegah foto layar dengan HP lain (lihat bagian di bawah)

## Mengurangi foto layar dengan HP lain

Tidak ada web yang bisa mencegah kamera HP kedua. Yang sudah dipasang dan yang perlu dilakukan:
- **Soal per siswa** (isi "Soal per siswa" saat membuat ujian) + acak soal & opsi: foto satu siswa tidak berguna untuk teman
- Bank soal lebih besar dari jumlah soal per siswa (misal bank 40, tiap siswa 20)
- Waktu ujian ketat, esai lebih banyak dari PG
- Pengawasan langsung di kelas, HP dikumpulkan; untuk ujian dari rumah, anggap sebagai formatif, bukan sumatif

## Uji otomatis (untuk pengembang)

Jalankan `python -m pytest -q` (72 uji, ±15 detik). Database uji `<nama database>_test` dibuat otomatis di PostgreSQL yang sama; database asli tidak disentuh, dan uji menolak berjalan bila diarahkan ke database asli.

## QR untuk siswa

Setelah alamat siap, ONLINE.bat membuka halaman **QR Siswa** di browser (atau buka menu QR Siswa di halaman guru).
Tayangkan di proyektor dan tekan **Layar penuh**. Siswa memindai dengan kamera HP dan langsung sampai di halaman masuk.
Bila tunnel putus lalu menyala dengan alamat baru, QR ikut berganti sendiri dalam beberapa detik.
Mode lokal: HP siswa tetap harus tersambung ke WiFi/hotspot yang sama dengan laptop.
