# app/routers/auth.py
# Router untuk menangani autentikasi (Login Guru dan Verifikasi Siswa)

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

BASE_DIR = Path(__file__).resolve().parent.parent
templates_env = Environment(loader=FileSystemLoader(BASE_DIR / "templates"))

# --- LOGIN GURU ---
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    template = templates_env.get_template("teacher/login.html")
    html_content = template.render(request=request)
    return HTMLResponse(content=html_content)

@router.post("/auth/teacher/login")
async def login_teacher(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    email = form_data.get("email")
    password = form_data.get("password")
    
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Email atau password salah")
    
    token_data = {"sub": str(user.id), "role": user.role}
    access_token = create_access_token(data=token_data)
    
    response = RedirectResponse(url="/teacher/dashboard", status_code=303)
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True, max_age=3600, samesite="lax")
    return response

# --- LOGIN SISWA ---
@router.get("/student/login", response_class=HTMLResponse)
async def student_login_page(request: Request):
    template = templates_env.get_template("student/login.html")
    html_content = template.render(request=request)
    return HTMLResponse(content=html_content)

@router.get("/auth/student/search")
async def search_student(name: str, db: Session = Depends(get_db)):
    if len(name) < 3:
        return []
    students = db.query(Student).filter(Student.name.ilike(f"%{name}%")).limit(5).all()
    results = [{"id": s.id, "name": s.name} for s in students]
    return results

@router.get("/student/verify", response_class=HTMLResponse)
async def student_verify_page(request: Request, student_id: int):
    template = templates_env.get_template("student/verify_pin.html")
    html_content = template.render(request=request, student_id=student_id)
    return HTMLResponse(content=html_content)

@router.post("/auth/student/verify")
async def verify_student_pin(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    student_id = form_data.get("student_id")
    pin = form_data.get("pin")
    
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student or not verify_password(pin, student.pin_hash):
        raise HTTPException(status_code=400, detail="PIN salah")
    
    token_data = {"sub": str(student.id), "role": "student"}
    access_token = create_access_token(data=token_data)
    
    response = RedirectResponse(url="/student/dashboard", status_code=303)
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True, max_age=3600, samesite="lax")
    return response

# --- REDIRECT DASHBOARD ---
@router.get("/teacher/dashboard")
async def teacher_dashboard(request: Request, user=Depends(require_teacher)):
    return RedirectResponse(url="/teacher/materials", status_code=303)