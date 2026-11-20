# app/routers/teacher_analisis.py
# Halaman guru yang membaca hasil belajar: analisis butir soal, daftar remedial, perkembangan siswa, rapor.
# (Dipisah dari teacher.py supaya file itu tidak makin besar; semuanya tetap di bawah /teacher.)

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.academic import Rombel, SchoolClass
from app.models.exam import Exam, ExamSession
from app.models.student import Student
from app.routers.teacher import TINGKAT, kelas_aktif, templates_env, unduh_xlsx
from app.services import audit
from app.services.analisis import analisis_butir
from app.services.excel import buku_remedial
from app.services.kesempatan import beri_kesempatan
from app.services.pantau import pantau_data
from app.services.perkembangan import bentuk_grafik, riwayat_siswa
from app.services.remedial import beri_remedial, daftar_remedial
from app.services.rekap import kkm_akhir, rekap_kelas, tahun_aktif, urutkan
from app.utils.deps import require_teacher

router = APIRouter(prefix="/teacher", tags=["Teacher analisis"])


def tampil(nama_template: str, **konteks) -> HTMLResponse:
    return HTMLResponse(content=templates_env.get_template(nama_template).render(**konteks))


# --- Analisis butir soal ---
@router.get("/exams/{exam_id}/analytics", response_class=HTMLResponse)
async def exam_analytics(exam_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        return RedirectResponse(url="/teacher/exams", status_code=303)
    return tampil("teacher/exam_analytics.html", request=request, exam=exam, analisis=analisis_butir(db, exam), user=user)


# --- Daftar remedial: lihat, unduh, beri izin sekaligus ---
@router.get("/exams/{exam_id}/remedial/export")
async def remedial_export(exam_id: int, db: Session = Depends(get_db), user=Depends(require_teacher)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        return RedirectResponse(url="/teacher/exams", status_code=303)
    return unduh_xlsx(buku_remedial(exam, daftar_remedial(db, exam)), f"remedial_{exam.title}_{datetime.now():%Y%m%d}")


@router.post("/exams/{exam_id}/remedial-semua")
async def remedial_semua(exam_id: int, db: Session = Depends(get_db), user=Depends(require_teacher)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        return RedirectResponse(url="/teacher/exams", status_code=303)
    diberi = 0
    for x in daftar_remedial(db, exam)["perlu"]:
        if x["status"] != "approved":
            beri_remedial(db, exam.id, x["siswa"].id, x["sesi_id"])
            diberi += 1
    db.commit()
    return RedirectResponse(url=f"/teacher/exams/{exam_id}/results?pesan=remedial&n={diberi}", status_code=303)


# --- Perkembangan satu siswa ---
@router.get("/students/{student_id}/progress", response_class=HTMLResponse)
async def student_progress(student_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    siswa = db.query(Student).filter(Student.id == student_id).first()
    if not siswa:
        return RedirectResponse(url="/teacher/students", status_code=303)
    riwayat = riwayat_siswa(db, student_id, bandingkan_rombel=True)
    return tampil("teacher/student_progress.html", request=request, siswa=siswa, riwayat=riwayat,
                  g=bentuk_grafik(riwayat["titik"]) if riwayat["titik"] else None, user=user)


# --- Rapor: halaman cetak (Ctrl+P lalu Simpan sebagai PDF), satu halaman per siswa ---
@router.get("/grades/class/{kelas}/rapor", response_class=HTMLResponse)
async def rapor(kelas: str, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    if kelas not in TINGKAT:
        return RedirectResponse(url="/teacher/grades", status_code=303)
    rombel = request.query_params.get("rombel", "")
    siswa = request.query_params.get("siswa", "")
    rekap = rekap_kelas(db, kelas, int(rombel) if rombel.isdigit() else None)
    rekap["baris"] = urutkan(rekap["baris"], "az")
    if siswa.isdigit():
        rekap["baris"] = [b for b in rekap["baris"] if b["siswa"].id == int(siswa)]
    nama_rombel = (db.query(Rombel.rombel_name).filter(Rombel.id == int(rombel)).scalar() if rombel.isdigit() else None)
    return tampil("teacher/rapor.html", request=request, rekap=rekap, kelas=kelas, nama_rombel=nama_rombel,
                  kkm=kkm_akhir(tahun_aktif(db)), dicetak=datetime.now(), user=user)


# --- Pantau: siswa yang online dan yang sedang mengerjakan ujian (diperbarui otomatis di halaman) ---
@router.get("/students/pantau", response_class=HTMLResponse)
async def pantau_page(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    kelas = kelas_aktif(request)
    return tampil("teacher/pantau.html", request=request, kelas=kelas, data=pantau_data(db, kelas), user=user)


@router.get("/students/pantau/data")
async def pantau_json(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    return JSONResponse(pantau_data(db, kelas_aktif(request)), headers={"Cache-Control": "no-store"})


# --- Kesempatan melanjutkan: sesi yang terkirim otomatis dibuka lagi, jawaban tetap, waktu memakai sisanya ---
@router.post("/exams/{exam_id}/sessions/{session_id}/lanjut")
async def beri_kesempatan_lanjut(exam_id: int, session_id: int, request: Request, db: Session = Depends(get_db),
                                 user=Depends(require_teacher)):
    sesi = (db.query(ExamSession).filter(ExamSession.id == session_id, ExamSession.exam_id == exam_id)
            .with_for_update().first())
    ok = bool(sesi) and beri_kesempatan(db, sesi)
    if ok:
        nama = db.query(Student.name).filter(Student.id == sesi.student_id).scalar()
        judul = db.query(Exam.title).filter(Exam.id == exam_id).scalar()
        audit.catat(db, user, "Nilai", "Beri kesempatan", f"{nama} · {judul}", "sesi dibuka lagi, jawaban dipertahankan")
    db.commit()
    kembali = f"/teacher/exams/{exam_id}/results"
    return RedirectResponse(url=f"{kembali}?pesan={'lanjut' if ok else 'lanjut_gagal'}", status_code=303)
