# migrations/env.py
# File konfigurasi lingkungan Alembic


from logging.config import fileConfig
# Mengimpor utilitas logging dari Python

from sqlalchemy import engine_from_config
# Mengimpor fungsi untuk membuat mesin database dari dictionary konfigurasi

from sqlalchemy import pool
# Mengimpor pool untuk mengatur koneksi database agar efisien

from alembic import context
# Mengimpor context Alembic (informasi tentang migrasi yang sedang berjalan)

# --- BAGIAN TAMBAHAN UNTUK FASTAPI KITA ---
import os
# Mengimpor os untuk mengakses environment variable

from dotenv import load_dotenv
# Mengimpor dotenv untuk membaca file .env

load_dotenv()
# Memuat isi file .env

from app.database import Base
# Mengimpor kelas Base dari aplikasi kita (ini wajib agar Alembic tahu tabel apa yang kita punya)

import app.models.user
import app.models.student
import app.models.academic
import app.models.material
import app.models.question 
import app.models.exam
import app.models.grade 
import app.models.achievement 
# Mengimpor file-file model yang akan kita buat sebentar lagi
# Walau kelihatannya tidak dipakai, ini WAJIB ditulis agar Base.metadata tahu tabel-tabel di dalamnya
# -------------------------------------------

config = context.config
# Mengambil konfigurasi dari alembic.ini

config.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL"))
# MENIMPA URL database: Mengambil URL dari file .env dan memasukkannya ke konfigurasi Alembic

if config.config_file_name is not None:
    fileConfig(config.config_file_name)
    # Mengatur logging berdasarkan file alembic.ini

target_metadata = Base.metadata
# INI SANGAT PENTING: Memberitahu Alembic semua struktur tabel yang kita buat di Python
# Alembic akan membandingkan Base.metadata dengan database asli untuk mencari perbedaan

def run_migrations_offline() -> None:
    # Fungsi untuk generate migrasi tanpa koneksi database (tidak sering dipakai pemula)
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    # Fungsi untuk menjalankan migrasi langsung ke database PostgreSQL
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    # Membuat koneksi sementara ke database

    with connectable.connect() as connection:
        # Membuka koneksi
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        # Mengatur context Alembic dengan koneksi ini

        with context.begin_transaction():
            context.run_migrations()
            # Menjalankan script perubahan database (upgrade/downgrade)

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()