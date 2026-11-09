# app/database.py
# File ini mengatur koneksi ke database dan membuat session (sesi) koneksi

from sqlalchemy import create_engine
# Mengimpor create_engine: Ini adalah 'mesin' yang membuka koneksi ke database

from sqlalchemy.orm import sessionmaker, DeclarativeBase
# sessionmaker: Pabrik untuk membuat sesi koneksi ke database
# DeclarativeBase: Kelas dasar yang akan dipakai oleh semua Model tabel kita nanti

from app.config import DATABASE_URL
# Mengimpor alamat database dari file config.py yang baru saja kita buat

engine = create_engine(
    DATABASE_URL,
    pool_size=20, max_overflow=20,   # cukup untuk 40 siswa bersamaan
    pool_timeout=10,                 # koneksi habis: gagal dalam 10 dtk, bukan menunggu tanpa batas
    pool_pre_ping=True,              # koneksi yang putus (PostgreSQL restart / laptop tidur) diganti otomatis
)
# ATURAN: di route `async def`, jangan `await` (request.form, run_in_threadpool, dst.) setelah memakai `db`
# tanpa db.rollback()/commit() dulu. Koneksi yang dipegang sambil menunggu bisa membuat server macet total
# (ditemukan saat simulasi 30 siswa, 9 Nov 2026).
# Membuat mesin koneksi ke PostgreSQL menggunakan URL yang ada di .env

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Membuat 'pabrik' sesi. 
# autocommit=False: Kita harus bilang secara eksplisit kapan data harus disimpan (commit)
# autoflush=False: Kita kontrol kapan perubahan dikirim ke database
# bind=engine: Sesi ini terikat ke mesin PostgreSQL yang tadi kita buat

class Base(DeclarativeBase):
    pass
# Membuat kelas Base. Semua tabel database yang akan kita buat di file models/ 
# HARUS mewarisi (inherit) kelas ini agar SQLAlchemy mengenalinya sebagai tabel

def get_db():
    # Fungsi ini khusus untuk FastAPI (disebut Dependency Injection)
    # Fungsi ini akan memberikan koneksi database ke setiap fungsi yang membutuhkan
    
    db = SessionLocal()
    # Membuka sesi/koneksi baru ke database
    
    try:
        yield db
        # 'yield' artinya kita 'meminjamkan' koneksi ini ke fungsi yang meminta
        # Setelah fungsi selesai, kode di bawah 'finally' akan dijalankan
    finally:
        db.close()
        # Apapun yang terjadi (sukses atau error), koneksi database HARUS ditutup
        # Jika tidak ditutup, koneksi akan menumpuk dan database bisa hang