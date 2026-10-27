# app/utils/security.py
# Utilitas untuk mengamankan password, PIN, dan membuat token JWT

from datetime import datetime, timedelta
# Mengimpor modul waktu untuk menentukan masa berlaku token

from jose import JWTError, jwt
# Mengimpor JWTError (error JWT) dan jwt (fungsi buat/baca token)

from passlib.context import CryptContext
# Mengimpor CryptContext dari passlib untuk hashing password

from app.config import SECRET_KEY
# Mengimpor kunci rahasia dari file .env

ALGORITHM = "HS256"
# Algoritma standar untuk mengenkripsi JWT

ACCESS_TOKEN_EXPIRE_MINUTES = 60
# Karcis login (token) akan kedaluwarsa dalam 60 menit

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
# Mengatur passlib untuk menggunakan algoritma Argon2.
# Argon2 adalah pemenang kompetisi hashing, sangat aman dari serangan hacker.

def hash_password(password: str) -> str:
    # Fungsi untuk mengubah password/PIN mentah menjadi teks acak (hash)
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Fungsi untuk mengecek apakah password yang diketik cocok dengan hash di database
    # Mengembalikan True jika cocok, False jika salah
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    # Fungsi untuk membuat karcis digital (JWT)
    
    to_encode = data.copy()
    # Menyalin data yang akan dimasukkan ke token (biasanya ID dan peran user)
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # Menentukan waktu kadaluarsa token. Jika tidak ditentukan, pakai default 60 menit
    
    to_encode.update({"exp": expire})
    # Menambahkan waktu kadaluarsa ke data token
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    # Mengenkripsi data menjadi string JWT panjang menggunakan kunci rahasia dari .env
    
    return encoded_jwt

def decode_access_token(token: str) -> dict | None:
    # Fungsi untuk membaca/mendekripsi karcis JWT
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # Mendekripsi token menggunakan kunci rahasia
        return payload
        # Jika berhasil, kembalikan data di dalam token (contoh: {"sub": "user_id", "role": "teacher"})
    except JWTError:
        # Jika token palsu atau sudah kadaluarsa, akan terjadi error
        return None
        # Kembalikan None agar kita tahu token ini tidak valid