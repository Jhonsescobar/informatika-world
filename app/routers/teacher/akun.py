# app/routers/teacher/akun.py
# Akun guru: memilih kelas aktif, ganti password, dan catatan aksi.

from fastapi import APIRouter, Request, Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers.teacher.umum import KELAS_PILIHAN, templates_env
from app.services import audit
from app.utils import ratelimit
from app.utils.deps import require_teacher
from app.utils.security import create_access_token, hash_password, PASSWORD_UMUM, sidik, verify_password

router = APIRouter(tags=["Teacher"])


@router.post("/kelas")
async def pilih_kelas(request: Request, user=Depends(require_teacher)):
    form = await request.form()
    kelas = form.get("kelas")
    kembali = form.get("kembali") or "/teacher/materials"
    if not kembali.startswith("/teacher/") or kembali.startswith("//") or "\\" in kembali:
        kembali = "/teacher/materials"
    if kembali.startswith(("/teacher/exams/", "/teacher/question-banks/", "/teacher/materials/", "/teacher/grades/class/", "/teacher/students/")):
        kembali = "/" + "/".join(kembali.split("/")[1:3])      # halaman detail milik kelas lain: kembali ke daftarnya
    resp = RedirectResponse(url=kembali, status_code=303)
    if kelas in KELAS_PILIHAN:
        resp.set_cookie("iw_kelas", kelas, max_age=60 * 60 * 24 * 365, samesite="lax", path="/teacher")
    return resp


@router.get("/account", response_class=HTMLResponse)
async def account_page(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    template = templates_env.get_template("teacher/account.html")
    akun = db.query(User).filter(User.id == int(user.get("sub"))).first()
    wajib = bool(akun and akun.must_change_password)
    return HTMLResponse(content=template.render(request=request, user=user, pesan=request.query_params.get("pesan"), wajib=wajib))


@router.get("/account/catatan", response_class=HTMLResponse)
async def catatan_aksi(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    """Riwayat aksi guru yang berdampak pada data. Hanya baca."""
    try:
        halaman = int(request.query_params.get("hal", "1"))
    except ValueError:
        halaman = 1
    data = audit.baca(db, request.query_params.get("kategori"), halaman)
    template = templates_env.get_template("teacher/audit.html")
    return HTMLResponse(content=template.render(request=request, user=user, kategori_pilihan=audit.KATEGORI,
                                                per_halaman=audit.PER_HALAMAN, **data))


@router.post("/account/password")
async def change_password(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    form = await request.form()
    lama, baru, ulang = form.get("lama") or "", form.get("baru") or "", form.get("ulang") or ""
    kunci = f"ganti-pw:{user.get('sub')}"
    if ratelimit.sisa_kunci_detik(kunci):
        return RedirectResponse(url="/teacher/account?pesan=terkunci", status_code=303)
    akun = db.query(User).filter(User.id == int(user.get("sub"))).first()
    hash_lama = akun.hashed_password if akun else None
    db.rollback()   # lepaskan koneksi sebelum menunggu Argon2
    if not hash_lama or not await run_in_threadpool(verify_password, lama, hash_lama):
        ratelimit.catat_gagal(kunci)          # cegah menebak password lama dari komputer yang ditinggal login
        return RedirectResponse(url="/teacher/account?pesan=lama", status_code=303)
    if baru != ulang:
        return RedirectResponse(url="/teacher/account?pesan=beda", status_code=303)
    if len(baru) < 8 or len(baru) > 128 or baru.lower() in PASSWORD_UMUM or baru == lama:
        return RedirectResponse(url="/teacher/account?pesan=lemah", status_code=303)
    ratelimit.reset(kunci)
    hash_baru = await run_in_threadpool(hash_password, baru)
    akun = db.query(User).filter(User.id == int(user.get("sub"))).first()
    akun.hashed_password = hash_baru
    akun.must_change_password = False
    audit.catat(db, user, "Akun", "Ganti sandi", akun.email)
    db.commit()
    # perangkat lain yang masih login otomatis keluar; perangkat ini diberi karcis baru
    from app.routers.auth import pasang_cookie_login
    respon = RedirectResponse(url="/teacher/account?pesan=ok", status_code=303)
    pasang_cookie_login(request, respon, create_access_token(
        {"sub": str(akun.id), "role": akun.role, "v": sidik(akun.hashed_password)}))
    return respon
