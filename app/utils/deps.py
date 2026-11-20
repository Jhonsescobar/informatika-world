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


def _akun_sah(model, payload, kolom_hash: str):
    # Akun yang dihapus/dinonaktifkan, atau yang password/PIN-nya sudah diganti, langsung keluar
    # walau tokennya belum kedaluwarsa. Mengembalikan akunnya (kolom sudah terbaca) atau None.
    db = SessionLocal()
    try:
        akun = db.query(model).filter(model.id == int(payload.get("sub"))).first()
        if akun and akun.is_active and payload.get("v") == sidik(getattr(akun, kolom_hash)):
            return akun
        return None
    except (TypeError, ValueError):
        return None
    finally:
        db.close()


# Selama guru masih memakai sandi bawaan, hanya dua alamat ini yang boleh dibuka.
BOLEH_SAAT_WAJIB_GANTI = ("/teacher/account", "/teacher/account/password")


def require_teacher(request: Request):
    from app.models.user import User
    user = get_current_user(request)
    if user.get("role") != "teacher":
        raise HTTPException(status_code=403, detail="Akses ditolak!")
    akun = _akun_sah(User, user, "hashed_password")
    if not akun:
        raise ke_login()
    if akun.must_change_password and request.url.path.rstrip("/") not in BOLEH_SAAT_WAJIB_GANTI:
        raise HTTPException(status_code=303, detail="Ganti sandi dulu",
                            headers={"Location": "/teacher/account?pesan=wajib"})
    return user


def require_student(request: Request):
    from app.models.student import Student
    user = get_current_user(request)
    if user.get("role") != "student":
        raise HTTPException(status_code=403, detail="Akses ditolak!")
    if not _akun_sah(Student, user, "pin_hash"):
        raise ke_login()
    return user
