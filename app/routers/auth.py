# app/routers/auth.py
# Router autentikasi: halaman login baru (pilih Guru/Siswa), login guru,
# login siswa (cari nama -> halaman PIN), dan redirect dashboard.
#
# ================= DAFTAR PERUBAHAN VERSI INI =================
# 1. GET /login       -> sekarang menampilkan halaman PILIH (login_pilih.html)
# 2. GET /login/guru  -> BARU: halaman login guru (login_guru.html)
# 3. GET /login/siswa -> BARU: halaman cari nama siswa (login_siswa.html)
# 4. GET /student/login (alamat lama) -> di-redirect ke /login/siswa
# 5. GET /auth/student/search -> minimal 1 huruf (dulu 3), urut A-Z, maks 10 hasil
# 6. GET /student/verify -> ikut mengirim nama siswa agar halaman PIN lebih ramah
# Route POST (/auth/teacher/login & /auth/student/verify) TIDAK diubah sama sekali.
# ===============================================================

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.utils.security import verify_password, create_access_token
from app.models.user import User
from app.models.student import Student
from app.utils.deps import require_teacher, require_student

router = APIRouter(tags=["Auth"])

BASE_DIR = Path(__file__).resolve().parent.parent          # folder app/
templates_env = Environment(loader=FileSystemLoader(BASE_DIR / "templates"))  # cari template di app/templates/

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
# BAGIAN 2 - LOGIN GURU (POST) - LOGIKA ASLI, TIDAK DIUBAH
# ============================================================
@router.post("/auth/teacher/login")
async def login_teacher(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()                 # ambil data yang dikirim form login guru
    email = form_data.get("email")                   # field name="email" di login_guru.html
    password = form_data.get("password")             # field name="password" di login_guru.html

    user = db.query(User).filter(User.email == email).first()   # cari user berdasarkan email
    if not user or not verify_password(password, user.hashed_password):  # user tidak ada / password salah
        raise HTTPException(status_code=400, detail="Email atau password salah")

    token_data = {"sub": str(user.id), "role": user.role}       # isi token: id user + role
    access_token = create_access_token(data=token_data)         # bikin token JWT

    response = RedirectResponse(url="/teacher/dashboard", status_code=303)  # berhasil -> dashboard guru
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True, max_age=3600, samesite="lax")  # simpan token di cookie
    return response

# ============================================================
# BAGIAN 3 - LOGIN SISWA (alur 2 langkah: cari nama -> PIN)
# ============================================================

# API pencarian nama siswa untuk AUTOCOMPLETE
# (dipanggil oleh JavaScript di login_siswa.html setiap siswa berhenti mengetik)
# PERUBAHAN: minimal 1 huruf (dulu harus 3), hasil diurutkan A-Z, maksimal 10 nama
@router.get("/auth/student/search")
async def search_student(name: str, db: Session = Depends(get_db)):
    keyword = name.strip()                            # buang spasi di awal/akhir teks
    if len(keyword) < 1:                              # kalau kata kunci kosong (dulu: < 3)
        return []                                     # kembalikan list kosong
    students = (                                       # cari siswa yang namanya MENGANDUNG kata kunci
        db.query(Student)
        .filter(Student.name.ilike(f"%{keyword}%"))    # ilike = tidak peduli huruf besar/kecil
        .order_by(Student.name)                        # urutkan A-Z supaya hasil konsisten
        .limit(10)                                     # maksimal 10 nama (dulu 5, dinaikkan karena 1 huruf bisa cocok banyak nama)
        .all()
    )
    results = [{"id": s.id, "name": s.name} for s in students]  # kirim sebagai JSON
    return results

# Halaman PIN (langkah ke-2 login siswa): siswa sudah memilih nama, sekarang isi PIN
# PERUBAHAN KECIL: nama siswa ikut dikirim ke template agar halaman PIN bisa menyapa
@router.get("/student/verify", response_class=HTMLResponse)
async def student_verify_page(request: Request, student_id: int, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()   # ambil data siswa dari database
    if not student:                                    # id siswa tidak ditemukan (misal URL diubah manual)
        return RedirectResponse(url="/login/siswa", status_code=303)       # -> balik ke halaman cari nama
    template = templates_env.get_template("student/verify_pin.html")
    # student_name dikirim agar halaman PIN bisa menampilkan "Halo, Andi Pratama!"
    html_content = template.render(request=request, student_id=student_id, student_name=student.name)
    return HTMLResponse(content=html_content)

# POST verifikasi PIN - LOGIKA ASLI, TIDAK DIUBAH
@router.post("/auth/student/verify")
async def verify_student_pin(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()                  # ambil data dari form halaman PIN
    student_id = form_data.get("student_id")          # id siswa (tersembunyi di form)
    pin = form_data.get("pin")                        # PIN yang diketik siswa

    student = db.query(Student).filter(Student.id == student_id).first()   # cari siswa berdasarkan id
    if not student or not verify_password(pin, student.pin_hash):          # siswa tidak ada / PIN salah
        raise HTTPException(status_code=400, detail="PIN salah")

    token_data = {"sub": str(student.id), "role": "student"}   # isi token: id siswa + role student
    access_token = create_access_token(data=token_data)        # bikin token JWT

    response = RedirectResponse(url="/student/dashboard", status_code=303)  # berhasil -> dashboard siswa
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True, max_age=3600, samesite="lax")  # simpan token di cookie
    return response

# ============================================================
# BAGIAN 4 - ALAMAT LAMA & REDIRECT
# ============================================================

# Alamat lama /student/login sekarang diarahkan ke halaman baru /login/siswa
# (supaya link/bookmark lama tetap jalan, tidak 404)
@router.get("/student/login")
async def student_login_lama():
    return RedirectResponse(url="/login/siswa", status_code=303)

# Redirect dashboard guru (guru langsung diarahkan ke halaman materi)
@router.get("/teacher/dashboard")
async def teacher_dashboard(request: Request, user=Depends(require_teacher)):
    return RedirectResponse(url="/teacher/materials", status_code=303)