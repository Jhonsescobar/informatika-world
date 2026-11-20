# app/routers/teacher/materi.py
# Materi pembelajaran: daftar, buat, ubah, jadwal buka/tutup, hapus.

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.material import Material
from app.routers.teacher.umum import kelas_aktif, templates_env, TINGKAT
from app.services.materi import baca_waktu, sekarang as materi_sekarang, status_materi
from app.utils.deps import require_teacher

router = APIRouter(tags=["Teacher"])


PESAN_MATERI = {
    "dibuka": "Materi dibuka untuk siswa.",
    "terjadwal": "Materi dijadwalkan. Siswa melihatnya mulai waktu yang Anda pilih.",
    "ditutup": "Materi ditutup untuk siswa.",
    "disimpan": "Materi disimpan.",
    "dihapus": "Materi dihapus.",
    "lewat": "Batas tutup harus di masa depan. Kosongkan bila materi dibuka sampai Anda tutup sendiri.",
    "urutan": "Waktu tutup harus setelah waktu mulai tampil.",
    "isian": "Judul wajib diisi dan kelas harus VII, VIII, atau IX.",
}


@router.get("/materials", response_class=HTMLResponse)
# Halaman daftar materi guru
async def list_materials(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    materials = db.query(Material).filter(Material.class_target == kelas_aktif(request)).order_by(Material.created_at.desc()).all()
    kini = materi_sekarang()
    status = {m.id: status_materi(m, kini) for m in materials}
    pesan = request.query_params.get("pesan")
    template = templates_env.get_template("teacher/materials.html")
    html_content = template.render(request=request, materials=materials, status=status, pesan=pesan,
                                   teks_pesan=PESAN_MATERI.get(pesan), user=user)
    return HTMLResponse(content=html_content)


def _isian_materi(form):
    judul = (form.get("title") or "").strip()[:200]
    kelas = form.get("class_target")
    if not judul or kelas not in TINGKAT:
        return None
    return {"title": judul, "class_target": kelas, "description": (form.get("description") or "").strip()[:300] or None,
            "content": (form.get("content") or "")[:500_000]}


@router.post("/materials/create")
async def create_material(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    isian = _isian_materi(await request.form())
    if not isian:
        return RedirectResponse(url="/teacher/materials?pesan=isian", status_code=303)
    db.add(Material(teacher_id=int(user.get("sub")), **isian))
    db.commit()
    return RedirectResponse(url="/teacher/materials?pesan=disimpan", status_code=303)


@router.get("/materials/{material_id}", response_class=HTMLResponse)
# Pratinjau: tampil persis seperti di layar siswa
async def view_material(material_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    m = db.query(Material).filter(Material.id == material_id).first()
    if not m:
        return RedirectResponse(url="/teacher/materials", status_code=303)
    template = templates_env.get_template("teacher/material_view.html")
    return HTMLResponse(content=template.render(request=request, m=m, status=status_materi(m), user=user))


@router.get("/materials/{material_id}/edit", response_class=HTMLResponse)
async def edit_material_page(material_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    m = db.query(Material).filter(Material.id == material_id).first()
    if not m:
        return RedirectResponse(url="/teacher/materials", status_code=303)
    template = templates_env.get_template("teacher/material_edit.html")
    return HTMLResponse(content=template.render(request=request, m=m, user=user, pesan=request.query_params.get("pesan")))


@router.post("/materials/{material_id}/edit")
async def edit_material(material_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    isian = _isian_materi(await request.form())      # form dibaca sebelum memegang koneksi database
    m = db.query(Material).filter(Material.id == material_id).first()
    if not m:
        return RedirectResponse(url="/teacher/materials", status_code=303)
    if not isian:
        return RedirectResponse(url=f"/teacher/materials/{material_id}/edit?pesan=isian", status_code=303)
    for k, v in isian.items():
        setattr(m, k, v)
    db.commit()
    return RedirectResponse(url="/teacher/materials?pesan=disimpan", status_code=303)


# --- KISI-KISI: buka / tutup materi untuk siswa ---
@router.post("/materials/{material_id}/visibility")
async def material_visibility(material_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    form = await request.form()                     # form dibaca sebelum memegang koneksi database
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        return RedirectResponse(url="/teacher/materials", status_code=303)
    if form.get("action") != "open":
        material.is_published, material.open_at, material.close_at = False, None, None
        db.commit()
        return RedirectResponse(url="/teacher/materials?pesan=ditutup", status_code=303)
    kini = materi_sekarang()
    mulai, tutup = baca_waktu(form.get("open_at")), baca_waktu(form.get("close_at"))
    if tutup and tutup <= kini:            # dulu diterima diam-diam -> langsung "Batas waktu lewat"
        return RedirectResponse(url="/teacher/materials?pesan=lewat", status_code=303)
    if mulai and tutup and tutup <= mulai:
        return RedirectResponse(url="/teacher/materials?pesan=urutan", status_code=303)
    material.is_published = True
    material.open_at = mulai if mulai and mulai > kini else None
    material.close_at = tutup
    db.commit()
    return RedirectResponse(url=f"/teacher/materials?pesan={'terjadwal' if material.open_at else 'dibuka'}", status_code=303)


# --- DELETE MATERI ---
@router.post("/materials/{material_id}/delete")
async def delete_material(material_id: int, db: Session = Depends(get_db), user=Depends(require_teacher)):
    material = db.query(Material).filter(Material.id == material_id).first()
    if material:
        db.delete(material)
        db.commit()
    return RedirectResponse(url="/teacher/materials?pesan=dihapus", status_code=303)
