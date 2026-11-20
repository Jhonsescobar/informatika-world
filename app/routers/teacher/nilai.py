# app/routers/teacher/nilai.py
# Nilai: komponen nilai, rekap per kelas, ekspor Excel.

import logging
from datetime import datetime

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.academic import Rombel, SchoolClass
from app.models.exam import Exam
from app.models.grade import Score, ScoreComponent
from app.routers.teacher.umum import baca_kkm, kelas_aktif, templates_env, TINGKAT, unduh_xlsx, URUTAN
from app.services import audit
from app.services.excel import buku_rekap
from app.services.rekap import kkm_akhir, rekap_kelas, tahun_aktif, urutkan
from app.utils.deps import require_teacher

router = APIRouter(tags=["Teacher"])


@router.get("/grades", response_class=HTMLResponse)
# Komponen nilai & bobot per tingkat
async def grade_components(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    components = db.query(ScoreComponent).filter(ScoreComponent.class_target == kelas_aktif(request)).order_by(ScoreComponent.id).all()
    jumlah_ujian = dict(db.query(Exam.component_id, func.count(Exam.id)).filter(Exam.component_id != None)
                        .group_by(Exam.component_id).all())
    template = templates_env.get_template("teacher/grades.html")
    html_content = template.render(request=request, components=components, jumlah_ujian=jumlah_ujian,
                                   error=request.query_params.get("error"), pesan=request.query_params.get("pesan"),
                                   kkm_tahun=kkm_akhir(tahun_aktif(db)), user=user)
    return HTMLResponse(content=html_content)


@router.post("/grades/components/create")
# Menambah komponen nilai: total bobot per tingkat tidak boleh lebih dari 100%
async def create_component(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    form = await request.form()
    nama = (form.get("name") or "").strip()[:80]
    kelas = form.get("class_target")
    try:
        bobot = int(form.get("weight"))
    except (TypeError, ValueError):
        bobot = 0
    try:
        kkm_isi = baca_kkm(form.get("kkm"))
    except ValueError:
        return RedirectResponse(url="/teacher/grades?error=kkm", status_code=303)
    if not nama or kelas not in TINGKAT or not 1 <= bobot <= 100:
        return RedirectResponse(url="/teacher/grades?error=isian", status_code=303)
    terpakai = db.query(func.coalesce(func.sum(ScoreComponent.weight), 0)).filter(ScoreComponent.class_target == kelas).scalar()
    if terpakai + bobot > 100:
        return RedirectResponse(url=f"/teacher/grades?error=bobot&sisa={100 - terpakai}&kelas={kelas}", status_code=303)
    db.add(ScoreComponent(name=nama, weight=bobot, class_target=kelas, teacher_id=int(user.get("sub")), kkm=kkm_isi))
    db.commit()
    return RedirectResponse(url="/teacher/grades", status_code=303)


@router.post("/grades/components/{comp_id}/kkm")
# KKM komponen: kosong = ikut KKM tahun ajaran
async def set_kkm_komponen(comp_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    form = await request.form()
    comp = db.query(ScoreComponent).filter(ScoreComponent.id == comp_id).first()
    if not comp:
        return RedirectResponse(url="/teacher/grades", status_code=303)
    lama = comp.kkm
    try:
        comp.kkm = baca_kkm(form.get("kkm"))
    except ValueError:
        return RedirectResponse(url="/teacher/grades?error=kkm", status_code=303)
    if comp.kkm != lama:
        audit.catat(db, user, "Nilai", "Ubah KKM komponen", comp.name, f"{lama if lama is not None else 'ikut default'} → {comp.kkm if comp.kkm is not None else 'ikut default'}")
    db.commit()
    return RedirectResponse(url="/teacher/grades?pesan=kkm", status_code=303)


@router.get("/grades/class/{class_target}", response_class=HTMLResponse)
# Rekap nilai akhir per tingkat
async def class_grades(class_target: str, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    if class_target not in TINGKAT:
        return RedirectResponse(url="/teacher/grades", status_code=303)
    try:
        urut = request.query_params.get("urut", "nilai")
        urut = urut if urut in URUTAN else "nilai"
        rombel = request.query_params.get("rombel", "")
        rekap = rekap_kelas(db, class_target, int(rombel) if rombel.isdigit() else None)
        rekap["baris"] = urutkan(rekap["baris"], urut)
        rombels = (db.query(Rombel).join(SchoolClass, SchoolClass.id == Rombel.class_id)
                   .filter(SchoolClass.class_name == class_target).order_by(Rombel.rombel_name).all())
        template = templates_env.get_template("teacher/class_grades.html")
        html_content = template.render(request=request, rekap=rekap, class_target=class_target, urut=urut, urutan=URUTAN,
                                       rombels=rombels, rombel=rombel, kkm=kkm_akhir(tahun_aktif(db)), user=user)
        return HTMLResponse(content=html_content)
    except Exception:
        logging.getLogger("informatika").exception("Rekap nilai")
        template = templates_env.get_template("error.html")
        return HTMLResponse(content=template.render(kembali="/teacher/grades"), status_code=500)


@router.get("/grades/class/{class_target}/export")
async def export_class(class_target: str, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    if class_target not in TINGKAT:
        return RedirectResponse(url="/teacher/grades", status_code=303)
    urut = request.query_params.get("urut", "nilai")
    rekap = rekap_kelas(db, class_target)
    rekap["baris"] = urutkan(rekap["baris"], urut if urut in URUTAN else "nilai")
    return unduh_xlsx(buku_rekap([rekap]), f"rekap_nilai_kelas_{class_target}_{datetime.now():%Y%m%d}")


@router.get("/grades/export")
async def export_all(db: Session = Depends(get_db), user=Depends(require_teacher)):
    semua = []
    for kelas in TINGKAT:
        rekap = rekap_kelas(db, kelas)
        rekap["baris"] = urutkan(rekap["baris"], "az")
        semua.append(rekap)
    return unduh_xlsx(buku_rekap(semua), f"rekap_nilai_semua_kelas_{datetime.now():%Y%m%d}")


# --- DELETE KOMPONEN NILAI ---
@router.post("/grades/components/{comp_id}/delete")
async def delete_component(comp_id: int, db: Session = Depends(get_db), user=Depends(require_teacher)):
    comp = db.query(ScoreComponent).filter(ScoreComponent.id == comp_id).first()
    if comp:
        # Ujian yang memakai komponen ini dilepas (tidak ikut terhapus), nilai lama versi sebelumnya dibersihkan
        db.query(Exam).filter(Exam.component_id == comp_id).update({Exam.component_id: None}, synchronize_session=False)
        db.query(Score).filter(Score.component_id == comp_id).delete(synchronize_session=False)
        db.delete(comp)
        db.commit()
    return RedirectResponse(url="/teacher/grades", status_code=303)
