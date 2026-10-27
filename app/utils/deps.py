# app/utils/deps.py
# File ini berisi fungsi "satpam" untuk melindungi route

from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from app.utils.security import decode_access_token

def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        # Jika tidak ada token, langsung paksa redirect ke login
        raise HTTPException(status_code=307, detail="Not authenticated", headers={"Location": "/student/login"})
    
    token = token.replace("Bearer ", "")
    payload = decode_access_token(token)
    
    if not payload:
        raise HTTPException(status_code=307, detail="Invalid token", headers={"Location": "/student/login"})
    
    return payload

def require_teacher(request: Request):
    user = get_current_user(request)
    if user.get("role") != "teacher":
        raise HTTPException(status_code=403, detail="Akses ditolak!")
    return user

def require_student(request: Request):
    user = get_current_user(request)
    if user.get("role") != "student":
        raise HTTPException(status_code=403, detail="Akses ditolak!")
    return user