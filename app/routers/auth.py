# app/routers/auth.py
# Autentikasi guru dan siswa.
#   GET  /login                 pilih masuk sebagai guru atau siswa
#   GET  /login/guru            form email + password
#   POST /auth/teacher/login    cek password guru (dibatasi 5x salah / 10 menit)
#   GET  /login/siswa           cari nama (GET /auth/student/search, minimal 3 huruf)
#   GET  /student/verify        form PIN untuk siswa yang dipilih
#   POST /auth/student/verify   cek PIN siswa (dibatasi 5x salah / 10 menit)
#   POST /logout                hapus cookie login

import re
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.utils.security import verify_password, create_access_token, sidik, ACCESS_TOKEN_EXPIRE_MINUTES
from app.models.user import User
from app.models.student import Student
from app.utils.deps import require_teacher, require_student
from app.utils import ratelimit


def pasang_cookie_login(request: Request, response, token: str):
    # Secure aktif otomatis bila diakses lewat HTTPS (misalnya lewat tunnel Cloudflare)
    https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    response.set_cookie(key="access_token", value=f"Bearer {token}", httponly=True,
                        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60, samesite="lax", secure=https)

router = APIRouter(tags=["Auth"])

# Satu kelas lewat WiFi sekolah / tunnel terlihat sebagai SATU alamat: batas per perangkat harus muat
# 30-40 siswa yang login bersamaan (tiap siswa ±10 pencarian saat mengetik nama, kadang salah PIN).
BATAS_CARI_PER_MENIT = 600
BATAS_PIN_SALAH_PER_PERANGKAT = 200   # per 10 menit

BASE_DIR = Path(__file__).resolve().parent.parent          # folder app/
templates_env = Environment(loader=FileSystemLoader(BASE_DIR / "templates"))  # cari template di app/templates/
from app.services.teks import pasang as _pasang_filter
_pasang_filter(templates_env)   # aset() untuk penanda versi file statis

# ============================================================
# BAGIAN 1 - HALAMAN LOGIN BARU (3 halaman, semuanya GET)
# ============================================================

# Halaman depan: pilih mau login sebagai Guru atau Siswa
@router.get("/login", response_class=HTMLResponse)
async def login_pilih_page(request: Request):
    template = templates_env.get_template("login_pilih.html")   # file di app/templates/ (root, bukan subfolder)
    html_content = template.render(request=request)             # render jadi HTML
    return HTMLResponse(content=html_content)                   # kirim ke browser

# Halaman login khusus Guru (form email + password)
@router.get("/login/guru", response_class=HTMLResponse)
async def login_guru_page(request: Request):
    template = templates_env.get_template("login_guru.html")    # file di app/templates/
    html_content = template.render(request=request)
    return HTMLResponse(content=html_content)

# Halaman login khusus Siswa (ketik nama -> muncul rekomendasi -> pilih -> lanjut ke halaman PIN)
@router.get("/login/siswa", response_class=HTMLResponse)
async def login_siswa_page(request: Request):
    template = templates_env.get_template("login_siswa.html")   # file di app/templates/
    html_content = template.render(request=request)
    return HTMLResponse(content=html_content)

# ============================================================
# BAGIAN 2 - LOGIN GURU (POST)
# ============================================================
@router.post("/auth/teacher/login")
async def login_teacher(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()                 # ambil data yang dikirim form login guru
    email = form_data.get("email")                   # field name="email" di login_guru.html
    password = form_data.get("password")             # field name="password" di login_guru.html

    # kunci per email + perangkat: orang lain yang sengaja salah password tidak bisa mengunci guru dari laptopnya
    kunci = "guru:" + (email or "").strip().lower() + "@" + ratelimit.ip_klien(request)
    if ratelimit.sisa_kunci_detik(kunci):              # terlalu banyak salah: tunggu dulu
        return RedirectResponse(url="/login/guru?error=terkunci", status_code=303)
    user = db.query(User).filter(User.email == email).first()   # cari user berdasarkan email
    hash_tersimpan = user.hashed_password if user and user.is_active else None
    db.rollback()   # lepaskan koneksi database SEBELUM menunggu (lihat lepas_lalu_tunggu di bawah)
    # Argon2 sengaja lambat (±0,1 dtk): dijalankan di thread terpisah agar siswa lain tidak ikut tertahan
    if not hash_tersimpan or not await run_in_threadpool(verify_password, password or "", hash_tersimpan):
        ratelimit.catat_gagal(kunci)
        return RedirectResponse(url="/login/guru?error=salah", status_code=303)
    ratelimit.reset(kunci)

    token_data = {"sub": str(user.id), "role": user.role, "v": sidik(hash_tersimpan)}       # isi token: id user + role
    access_token = create_access_token(data=token_data)         # bikin token JWT

    response = RedirectResponse(url="/teacher/dashboard", status_code=303)  # berhasil -> dashboard guru
    pasang_cookie_login(request, response, access_token)
    return response

# ============================================================
# BAGIAN 3 - LOGIN SISWA (alur 2 langkah: cari nama -> PIN)
# ============================================================

# API pencarian nama siswa untuk AUTOCOMPLETE
# (dipanggil oleh JavaScript di login_siswa.html setiap siswa berhenti mengetik)
# Minimal 3 huruf supaya daftar nama siswa tidak bisa diintip dengan mengetik 1 huruf.
# Hanya siswa aktif yang muncul, diurutkan A-Z, maksimal 10 nama.
@router.get("/auth/student/search")
async def search_student(name: str, request: Request, db: Session = Depends(get_db)):
    keyword = name.strip()[:60]                       # buang spasi di awal/akhir teks
    # huruf saja yang dihitung: "%%%" atau "___" dulu menampilkan nama siapa pun
    if len(re.sub(r"[^A-Za-z]", "", keyword)) < 3:
        return []
    # batas per perangkat: mencegah daftar nama siswa disedot otomatis dari internet
    if not ratelimit.boleh("cari:" + ratelimit.ip_klien(request), BATAS_CARI_PER_MENIT, 60):
        return []
    keyword = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    students = (                                       # cari siswa yang namanya MENGANDUNG kata kunci
        db.query(Student)
        .filter(Student.name.ilike(f"%{keyword}%", escape="\\"))    # ilike = tidak peduli huruf besar/kecil
        .filter(Student.is_active == True)             # siswa nonaktif tidak bisa login, jadi tidak ditampilkan
        .order_by(Student.name)                        # urutkan A-Z supaya hasil konsisten
        .limit(10)                                     # maksimal 10 nama (dulu 5, dinaikkan karena 1 huruf bisa cocok banyak nama)
        .all()
    )
    results = [{"id": s.id, "name": s.name} for s in students]  # kirim sebagai JSON
    return results

# Halaman PIN (langkah ke-2 login siswa): siswa sudah memilih nama, sekarang isi PIN
# Nama siswa dikirim ke template agar halaman PIN bisa menyapa
@router.get("/student/verify", response_class=HTMLResponse)
async def student_verify_page(request: Request, student_id: int, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()   # ambil data siswa dari database
    if not student or not student.is_active:           # tidak ditemukan / nonaktif
        return RedirectResponse(url="/login/siswa", status_code=303)       # -> balik ke halaman cari nama
    template = templates_env.get_template("student/verify_pin.html")
    # student_name dikirim agar halaman PIN bisa menampilkan "Halo, Andi Pratama!"
    html_content = template.render(request=request, student_id=student_id, student_name=student.name)
    return HTMLResponse(content=html_content)

# POST verifikasi PIN
@router.post("/auth/student/verify")
async def verify_student_pin(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()                  # ambil data dari form halaman PIN
    student_id = form_data.get("student_id")          # id siswa (tersembunyi di form)
    pin = form_data.get("pin")                        # PIN yang diketik siswa

    if not str(student_id or "").isdigit():           # id dari form berupa teks: pastikan angka
        return RedirectResponse(url="/login/siswa", status_code=303)
    kembali = f"/student/verify?student_id={int(student_id)}"
    kunci = f"siswa:{int(student_id)}"
    kunci_ip = "pin-ip:" + ratelimit.ip_klien(request)
    # satu perangkat yang mencoba PIN banyak siswa sekaligus ikut dikunci
    if ratelimit.jumlah_gagal(kunci_ip) >= BATAS_PIN_SALAH_PER_PERANGKAT:
        return RedirectResponse(url=f"/student/verify?student_id={int(student_id)}&error=terkunci", status_code=303)
    if ratelimit.sisa_kunci_detik(kunci):              # 5x salah dalam 10 menit: PIN dikunci sementara
        return RedirectResponse(url=kembali + "&error=terkunci", status_code=303)
    student = db.query(Student).filter(Student.id == int(student_id)).first()   # cari siswa berdasarkan id
    if not student or not student.is_active:           # tidak ada / dinonaktifkan guru
        return RedirectResponse(url="/login/siswa", status_code=303)
    hash_tersimpan = student.pin_hash
    db.rollback()   # lepaskan koneksi database sebelum menunggu: 15 siswa login bersamaan dulu bisa membuat server macet
    if not await run_in_threadpool(verify_password, pin or "", hash_tersimpan):
        ratelimit.catat_gagal(kunci)
        ratelimit.catat_gagal(kunci_ip)
        return RedirectResponse(url=kembali + "&error=pin", status_code=303)
    ratelimit.reset(kunci)

    token_data = {"sub": str(int(student_id)), "role": "student", "v": sidik(hash_tersimpan)}   # isi token: id siswa + role student
    access_token = create_access_token(data=token_data)        # bikin token JWT

    response = RedirectResponse(url="/student/dashboard", status_code=303)  # berhasil -> dashboard siswa
    pasang_cookie_login(request, response, access_token)
    return response

# ============================================================
# BAGIAN 4 - ALAMAT LAMA & REDIRECT
# ============================================================

# Alamat lama /student/login sekarang diarahkan ke halaman baru /login/siswa
# (supaya link/bookmark lama tetap jalan, tidak 404)
# Keluar: hapus cookie login lalu kembali ke halaman pilih login.
# POST (bukan GET) supaya tidak bisa dipicu lewat link/gambar dari situs lain.
@router.post("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response

@router.get("/student/login")
async def student_login_lama():
    return RedirectResponse(url="/login/siswa", status_code=303)

# Redirect dashboard guru (guru langsung diarahkan ke halaman materi)
@router.get("/teacher/dashboard")
async def teacher_dashboard(request: Request, user=Depends(require_teacher)):
    return RedirectResponse(url="/teacher/materials", status_code=303)