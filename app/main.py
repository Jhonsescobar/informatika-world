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
    version="0.1.0",
    # Halaman dokumentasi API dimatikan: tidak perlu terlihat oleh siswa / publik
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
# Membuat instance aplikasi FastAPI

# --- 1a. PERLINDUNGAN CSRF: kiriman form hanya dari halaman milik web ini ---
from urllib.parse import urlsplit
from fastapi.responses import PlainTextResponse


def _host_sama(alamat: str, request) -> bool:
    asal = urlsplit(alamat).netloc.lower()
    tuan = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].strip().lower()
    return bool(asal) and asal == tuan


@app.middleware("http")
async def tolak_kiriman_lintas_situs(request, call_next):
    # Browser selalu menyertakan Origin (atau Referer) pada kiriman form. Bila ada dan bukan dari web ini, ditolak.
    # Cookie sudah SameSite=Lax; pemeriksaan ini lapis kedua. Klien tanpa kedua header (bukan browser) tidak dipaksa.
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        asal = request.headers.get("origin") or request.headers.get("referer")
        if asal and not _host_sama(asal, request):
            return PlainTextResponse("Permintaan ditolak: berasal dari situs lain.", status_code=403)
    return await call_next(request)


# --- 1b. HEADER KEAMANAN di setiap respons ---
@app.middleware("http")
async def header_keamanan(request, call_next):
    respon = await call_next(request)
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
        respon.headers.setdefault("Strict-Transport-Security", "max-age=15552000")   # 6 bulan: browser selalu memakai HTTPS
    respon.headers.setdefault("X-Content-Type-Options", "nosniff")      # browser tidak menebak jenis file
    respon.headers.setdefault("X-Frame-Options", "DENY")                # web tidak bisa disisipkan di situs lain (clickjacking)
    respon.headers.setdefault("Referrer-Policy", "same-origin")
    respon.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.url.path.startswith(("/teacher", "/student")):
        respon.headers.setdefault("Cache-Control", "no-store")          # halaman berisi nilai tidak tersimpan di cache
    return respon

# --- 2. KONFIGURASI FOLDER STATIS ---
BASE_DIR = Path(__file__).resolve().parent
# Mendapatkan jalur absolut folder 'app'

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
# Mengaitkan folder 'app/static' ke URL '/static'

# --- 3. MENDAFTARKAN SEMUA ROUTER ---
# Router HARUS didaftarkan SETELAH app = FastAPI() dibuat

from app.routers import auth
from app.routers import teacher
from app.routers import teacher_analisis
from app.routers import student
# Mengimpor semua router yang kita punya

app.include_router(auth.router)
app.include_router(teacher.router)
app.include_router(teacher_analisis.router)
app.include_router(student.router)
# Mendaftarkan router ke aplikasi utama agar URL di dalamnya bisa diakses

# --- 4. ROUTE DEFAULT ---
@app.get("/")
# Route untuk halaman utama (root)
async def root():
    # Jika orang mengakses 127.0.0.1:8000/, langsung arahkan ke /login
    return RedirectResponse(url="/login")