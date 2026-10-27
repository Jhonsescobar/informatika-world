# app/main.py
# Titik masuk utama aplikasi FastAPI

from fastapi import FastAPI
# Mengimpor FastAPI

from fastapi.staticfiles import StaticFiles
# Mengimpor StaticFiles untuk melayani file CSS, JS, dan Gambar

from fastapi.responses import RedirectResponse
# Mengimpor RedirectResponse untuk mengalihkan halaman

from pathlib import Path
# Mengimpor Path untuk mengatur jalur folder

# --- 1. MEMBUAT OBJEK APLIKASI ---
app = FastAPI(
    title="INFORMATIKA WORLD",
    description="LMS Pembelajaran Informatika SMP - Learn • Explore • Challenge • Achieve",
    version="0.1.0"
)
# Membuat instance aplikasi FastAPI

# --- 2. KONFIGURASI FOLDER STATIS ---
BASE_DIR = Path(__file__).resolve().parent
# Mendapatkan jalur absolut folder 'app'

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
# Mengaitkan folder 'app/static' ke URL '/static'

# --- 3. MENDAFTARKAN SEMUA ROUTER ---
# Router HARUS didaftarkan SETELAH app = FastAPI() dibuat

from app.routers import auth
from app.routers import teacher
from app.routers import student
# Mengimpor semua router yang kita punya

app.include_router(auth.router)
app.include_router(teacher.router)
app.include_router(student.router)
# Mendaftarkan router ke aplikasi utama agar URL di dalamnya bisa diakses

# --- 4. ROUTE DEFAULT ---
@app.get("/")
# Route untuk halaman utama (root)
async def root():
    # Jika orang mengakses 127.0.0.1:8000/, langsung arahkan ke /login
    return RedirectResponse(url="/login")