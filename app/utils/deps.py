# app/utils/deps.py
# "Satpam" untuk melindungi route: cek cookie login, peran, dan status akun.

from fastapi import Request, HTTPException
from app.utils.security import decode_access_token, sidik
from app.database import SessionLocal


def ke_login():
    return HTTPException(status_code=307, detail="Not authenticated", headers={"Location": "/login"})


def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise ke_login()
    payload = decode_access_token(token.replace("Bearer ", ""))
    if not payload:
        raise ke_login()
    return payload


def _akun_aktif(model, payload, kolom_hash: str) -> bool:
    # Akun yang dihapus/dinonaktifkan, atau yang password/PIN-nya sudah diganti, langsung keluar
    # walau tokennya belum kedaluwarsa.
    db = SessionLocal()
    try:
        akun = db.query(model).filter(model.id == int(payload.get("sub"))).first()
        return bool(akun and akun.is_active and payload.get("v") == sidik(getattr(akun, kolom_hash)))
    except (TypeError, ValueError):
        return False
    finally:
        db.close()


def require_teacher(request: Request):
    from app.models.user import User
    user = get_current_user(request)
    if user.get("role") != "teacher":
        raise HTTPException(status_code=403, detail="Akses ditolak!")
    if not _akun_aktif(User, user, "hashed_password"):
        raise ke_login()
    return user


def require_student(request: Request):
    from app.models.student import Student
    user = get_current_user(request)
    if user.get("role") != "student":
        raise HTTPException(status_code=403, detail="Akses ditolak!")
    if not _akun_aktif(Student, user, "pin_hash"):
        raise ke_login()
    return user
