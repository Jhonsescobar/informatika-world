# app/config.py
# File ini bertugas memuat variabel rahasia dari file .env

import os
# Mengimpor library bawaan Python 'os' untuk berinteraksi dengan sistem operasi

from dotenv import load_dotenv
# Mengimpor fungsi load_dotenv dari library python-dotenv yang kita install tadi

load_dotenv()
# Menjalankan fungsi ini akan membaca file .env dan memasukkan isinya ke environment system

DATABASE_URL = os.getenv("DATABASE_URL")
# Mengambil nilai dari key DATABASE_URL di file .env dan menyimpannya di variabel ini

SECRET_KEY = os.getenv("SECRET_KEY")
# Mengambil nilai dari key SECRET_KEY di file .env untuk keamanan session nanti
# Kunci rahasia wajib ada dan cukup panjang: token login ditandatangani dengan kunci ini.
# Kunci pendek/kosong = siapa pun bisa memalsukan login guru.
if not SECRET_KEY or len(SECRET_KEY) < 16:
    raise RuntimeError("SECRET_KEY di file .env kosong atau terlalu pendek (minimal 16 karakter). "
                       "Buat yang baru: python -c \"import secrets; print(secrets.token_urlsafe(32))\"")
