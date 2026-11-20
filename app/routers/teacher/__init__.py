# app/routers/teacher/__init__.py
# Semua halaman guru, dipecah per fitur. Semua alamat diawali /teacher.
# URUTAN penyertaan di bawah menentukan urutan pencocokan alamat; jangan diubah tanpa menjalankan tests/test_rute_guru.py.

from fastapi import APIRouter

from app.routers.teacher import akun, analisis, bank_soal, hasil, materi, nilai, siswa, ujian

router = APIRouter(prefix="/teacher", tags=["Teacher"])
for _bagian in (akun, materi, bank_soal, ujian, hasil, nilai, siswa, analisis):
    router.include_router(_bagian.router)
