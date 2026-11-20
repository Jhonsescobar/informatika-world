# app/routers/teacher/siswa.py
# Siswa: daftar, tambah, PIN, rombel, QR login, nonaktif, hapus.

import secrets

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.academic import Enrollment, Rombel, SchoolClass
from app.models.achievement import StudentAchievement
from app.models.exam import ExamAnswer, ExamEvent, ExamSession, ExamViolation, RemedialRequest
from app.models.grade import Score
from app.models.student import Student
from app.routers.teacher.umum import baca_ids, kelas_aktif, tahun_ajaran_aktif, templates_env
from app.services import audit
from app.services.alamat import alamat_siswa, svg_qr
from app.utils import ratelimit
from app.utils.deps import require_teacher
from app.utils.security import hash_password

router = APIRouter(tags=["Teacher"])


def pin_baru() -> str:
    # secrets (bukan random) supaya PIN tidak bisa ditebak dari pola bilangan acak
    return str(1000 + secrets.randbelow(9000))


def halaman_pin(request, daftar, user, judul="siap login", reset=False):
    template = templates_env.get_template("teacher/student_pins.html")
    html = template.render(request=request, students=daftar, user=user, judul=judul, reset=reset)
    # PIN hanya tampil sekali: jangan disimpan cache browser
    return HTMLResponse(content=html, headers={"Cache-Control": "no-store"})


def reset_pin_siswa(db, ids, user=None):
    hasil = []
    for siswa in db.query(Student).filter(Student.id.in_(ids)).order_by(Student.name):
        pin = pin_baru()
        siswa.pin_hash = hash_password(pin)   # token lama siswa ikut gugur (sidik berubah)
        ratelimit.reset(f"siswa:{siswa.id}")  # kunci 5x salah dibuka
        hasil.append({"name": siswa.name, "pin": pin})
    if hasil:   # PIN-nya sendiri tidak pernah dicatat
        audit.catat(db, user, "Siswa", "Reset PIN", f"{len(hasil)} siswa", audit.daftar_nama([h["name"] for h in hasil]))
    db.commit()
    return hasil


@router.post("/students/{student_id}/reset-pin")
async def reset_pin(student_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    daftar = await run_in_threadpool(reset_pin_siswa, db, [student_id], user)
    if not daftar:
        return RedirectResponse(url="/teacher/students", status_code=303)
    return halaman_pin(request, daftar, user, judul="PIN baru", reset=True)


# --- AKUN GURU: ganti password lewat web ---
@router.get("/qr", response_class=HTMLResponse)
async def halaman_qr(request: Request, user=Depends(require_teacher)):
    """QR besar untuk ditayangkan di proyektor: siswa memindai lalu langsung ke halaman masuk."""
    alamat = alamat_siswa(str(request.base_url))
    template = templates_env.get_template("teacher/qr.html")
    return HTMLResponse(content=template.render(request=request, user=user, alamat=alamat,
                                                svg=svg_qr(alamat["url"]) if alamat else None))


@router.get("/qr/status")
async def status_qr(request: Request, user=Depends(require_teacher)):
    """Dipanggil halaman QR tiap beberapa detik: bila alamat berganti (tunnel putus lalu menyala lagi),
    halaman dimuat ulang dengan QR baru."""
    alamat = alamat_siswa(str(request.base_url))
    return {"url": alamat["url"] if alamat else None}


# --- BULK IMPORT SISWA + AUTO PIN ---
@router.post("/students/bulk-create")
async def bulk_create_students(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    form = await request.form()
    names_text = form.get("names_text") # Ambil teks dari textarea
    names = [n.strip()[:100] for n in (names_text or "").split("\n") if n.strip()][:300]
    # PIN & hash dibuat dulu (di thread terpisah), sebelum memegang koneksi database
    pin_siap = await run_in_threadpool(lambda: [(p, hash_password(p)) for p in (pin_baru() for _ in names)])

    # Rombel tujuan dari dropdown (boleh kosong = siswa belum masuk rombel)
    rombel = None
    if form.get("rombel_id"):
        rombel = db.query(Rombel).filter(Rombel.id == int(form.get("rombel_id"))).first()
        if rombel is None:
            raise HTTPException(status_code=400, detail="Rombel tidak ditemukan")
        tahun = tahun_ajaran_aktif(db)
    
    created_students = []
    for name, (pin, pin_hash) in zip(names, pin_siap):
        
        new_student = Student(
            name=name,
            nipd=None, # NIPD bisa diisi nanti
            pin_hash=pin_hash,
            is_active=True
        )
        db.add(new_student)
        db.commit()
        db.refresh(new_student)

        if rombel:
            # Langsung daftarkan siswa ke rombel yang dipilih
            db.add(Enrollment(student_id=new_student.id, rombel_id=rombel.id, academic_year_id=tahun.id))
            db.commit()
        
        # Simpan nama + PIN plain text untuk ditampilkan ke guru
        created_students.append({"name": name, "pin": pin})
    
    if created_students:
        audit.catat(db, user, "Siswa", "Tambah siswa massal", f"{len(created_students)} siswa",
                    ((f"rombel {rombel.rombel_name}; " if rombel else "") + audit.daftar_nama([c["name"] for c in created_students])))
        db.commit()
    # Render halaman khusus untuk menampilkan hasil PIN
    return halaman_pin(request, created_students, user)


# --- KELOLA SISWA ---
@router.get("/students", response_class=HTMLResponse)
async def list_students(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    # Daftar rombel diambil dari database (bukan ID yang ditulis manual di template)
    rombels = (db.query(Rombel, SchoolClass).join(SchoolClass, Rombel.class_id == SchoolClass.id)
               .filter(SchoolClass.class_name == kelas_aktif(request)).order_by(SchoolClass.id, Rombel.rombel_name).all())
    semua_rombel = db.query(Rombel, SchoolClass).join(SchoolClass, Rombel.class_id == SchoolClass.id).order_by(SchoolClass.id, Rombel.rombel_name).all()   # tujuan pindah/tambah boleh lintas kelas
    nama_rombel = {r.id: r.rombel_name for r, _ in semua_rombel}
    jumlah_per_rombel = dict(db.query(Enrollment.rombel_id, func.count(func.distinct(Enrollment.student_id)))
                             .group_by(Enrollment.rombel_id).all())
    id_rombel_kelas = {r.id for r, _ in rombels}
    semua = [s for s in db.query(Student).order_by(Student.name).all()
             if not s.enrollments or any(e.rombel_id in id_rombel_kelas for e in s.enrollments)]   # siswa kelas ini + yang belum punya rombel
    tanpa_rombel = [s for s in semua if not s.enrollments]

    # Saring: ?rombel=<id> | none, ?q=<nama>
    filter_rombel = request.query_params.get("rombel", "")
    cari = (request.query_params.get("q") or "").strip()
    students = semua
    if filter_rombel == "none":
        students = tanpa_rombel
    elif filter_rombel.isdigit():
        students = [s for s in semua if any(e.rombel_id == int(filter_rombel) for e in s.enrollments)]
    if cari:
        students = [s for s in students if cari.lower() in s.name.lower()]

    # Pesan setelah aksi massal (hanya angka dari URL, teksnya disusun di sini)
    p = request.query_params
    pesan = None
    n = int(p.get("n")) if (p.get("n") or "").isdigit() else 0
    if p.get("deleted") == "1" or p.get("pesan") == "hapus":
        pesan = f"{n or 1} siswa beserta seluruh datanya sudah dihapus permanen."
    elif p.get("pesan") == "pindah" and (p.get("r") or "").isdigit():
        pesan = f"{n} siswa dipindah ke rombel {nama_rombel.get(int(p.get('r')), '?')}."
    elif p.get("pesan") in ("nonaktif", "aktif"):
        pesan = f"{n} siswa di{'non' if p.get('pesan') == 'nonaktif' else ''}aktifkan."
    elif p.get("pesan") == "keluar":
        pesan = f"{n} siswa dikeluarkan dari rombelnya."
    elif p.get("pesan") == "pin_salah":
        pesan = "Siswa tidak disimpan: nama wajib diisi dan PIN harus 4–6 angka."

    template = templates_env.get_template("teacher/students.html")
    html_content = template.render(request=request, students=students, semua=semua, rombels=rombels, semua_rombel=semua_rombel,
                                   jumlah_per_rombel=jumlah_per_rombel, jumlah_tanpa_rombel=len(tanpa_rombel),
                                   filter_rombel=filter_rombel, cari=cari, pesan=pesan, user=user)
    return HTMLResponse(content=html_content)


# --- KELUARKAN SISWA DARI ROMBEL ---
# Hanya menghapus keanggotaan (enrollment). Akun siswa dan nilainya tetap ada.
@router.post("/enrollments/{enrollment_id}/delete")
async def remove_from_rombel(enrollment_id: int, db: Session = Depends(get_db), user=Depends(require_teacher)):
    enrollment = db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
    if enrollment:
        db.delete(enrollment)
        db.commit()
    return RedirectResponse(url="/teacher/students", status_code=303)


@router.post("/students/create")
async def create_student(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    form = await request.form()
    pin = (form.get("pin") or "").strip()
    nama = (form.get("name") or "").strip()[:100]
    if not nama or not pin.isdigit() or not 4 <= len(pin) <= 6:
        return RedirectResponse(url="/teacher/students?pesan=pin_salah", status_code=303)
    pin_hash = await run_in_threadpool(hash_password, pin)
    new_student = Student(
        name=nama,
        nipd=(form.get("nipd") or "").strip()[:30] or None,
        pin_hash=pin_hash,
        is_active=True
    )
    db.add(new_student)
    audit.catat(db, user, "Siswa", "Tambah siswa", nama)
    db.commit()
    return RedirectResponse(url="/teacher/students", status_code=303)


# --- HAPUS SISWA PERMANEN ---
# Menghapus siswa beserta SEMUA datanya. Konfirmasi: ketik HAPUS.
def data_terkait_siswa(db: Session, student_ids: list[int]):
    # Query per tabel yang menyimpan data milik siswa (urut: anak dulu, baru induk)
    sesi_ids = [s.id for s in db.query(ExamSession.id).filter(ExamSession.student_id.in_(student_ids))]
    return {
        "Keanggotaan rombel": db.query(Enrollment).filter(Enrollment.student_id.in_(student_ids)),
        "Permintaan remedial": db.query(RemedialRequest).filter(RemedialRequest.student_id.in_(student_ids)),
        "Catatan pelanggaran ujian": db.query(ExamViolation).filter(ExamViolation.session_id.in_(sesi_ids)),
        "Log aktivitas ujian": db.query(ExamEvent).filter(ExamEvent.session_id.in_(sesi_ids)),
        "Jawaban ujian": db.query(ExamAnswer).filter(ExamAnswer.session_id.in_(sesi_ids)),
        "Sesi ujian": db.query(ExamSession).filter(ExamSession.student_id.in_(student_ids)),
        "Nilai": db.query(Score).filter(Score.student_id.in_(student_ids)),
        "Achievement": db.query(StudentAchievement).filter(StudentAchievement.student_id.in_(student_ids)),
    }


@router.get("/students/delete", response_class=HTMLResponse)
async def confirm_delete_students(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    ids = baca_ids(request.query_params.get("ids", ""))
    students = db.query(Student).filter(Student.id.in_(ids)).order_by(Student.name).all() if ids else []
    if not students:
        return RedirectResponse(url="/teacher/students", status_code=303)
    ids = [s.id for s in students]
    counts = {label: q.count() for label, q in data_terkait_siswa(db, ids).items()}
    template = templates_env.get_template("teacher/student_delete.html")
    html_content = template.render(request=request, students=students, ids=",".join(map(str, ids)), counts=counts,
                                   error=request.query_params.get("error"), user=user)
    return HTMLResponse(content=html_content)


@router.post("/students/delete")
async def delete_students(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    form = await request.form()
    ids = baca_ids(form.get("ids", ""))
    if not ids:
        return RedirectResponse(url="/teacher/students", status_code=303)
    if (form.get("confirm_text") or "").strip().upper() != "HAPUS":
        return RedirectResponse(url=f"/teacher/students/delete?ids={','.join(map(str, ids))}&error=konfirmasi", status_code=303)
    try:
        # Semua dalam satu transaksi: gagal satu, batal semua
        nama = [n for (n,) in db.query(Student.name).filter(Student.id.in_(ids)).order_by(Student.name)]
        for q in data_terkait_siswa(db, ids).values():
            q.delete(synchronize_session=False)
        n = db.query(Student).filter(Student.id.in_(ids)).delete(synchronize_session=False)
        audit.catat(db, user, "Siswa", "Hapus siswa", f"{n} siswa", audit.daftar_nama(nama))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return RedirectResponse(url=f"/teacher/students?pesan=hapus&n={n}", status_code=303)


@router.get("/students/{student_id}/delete")
async def confirm_delete_one(student_id: int, user=Depends(require_teacher)):
    return RedirectResponse(url=f"/teacher/students/delete?ids={student_id}", status_code=303)


# --- AKSI MASSAL: pindah rombel / nonaktifkan / aktifkan / keluarkan / hapus ---
@router.post("/students/bulk")
async def bulk_students(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    form = await request.form()
    ids = sorted({int(x) for x in form.getlist("student_ids") if str(x).isdigit()})
    aksi = form.get("action")
    kembali = form.get("kembali") or ""
    if not kembali.startswith("/teacher/students"):          # hanya boleh kembali ke halaman ini
        kembali = "/teacher/students"
    sambung = "&" if "?" in kembali else "?"
    if not ids or aksi not in ("move", "deactivate", "activate", "unenroll", "delete", "reset_pin"):
        return RedirectResponse(url=kembali, status_code=303)

    if aksi == "reset_pin":
        return halaman_pin(request, await run_in_threadpool(reset_pin_siswa, db, ids, user), user, judul="PIN baru", reset=True)

    if aksi == "delete":
        return RedirectResponse(url=f"/teacher/students/delete?ids={','.join(map(str, ids))}", status_code=303)

    if aksi in ("deactivate", "activate"):
        n = db.query(Student).filter(Student.id.in_(ids)).update({Student.is_active: aksi == "activate"}, synchronize_session=False)
        nama = [x for (x,) in db.query(Student.name).filter(Student.id.in_(ids)).order_by(Student.name)]
        audit.catat(db, user, "Siswa", "Aktifkan siswa" if aksi == "activate" else "Nonaktifkan siswa", f"{n} siswa", audit.daftar_nama(nama))
        db.commit()
        return RedirectResponse(url=f"{kembali}{sambung}pesan={'aktif' if aksi == 'activate' else 'nonaktif'}&n={n}", status_code=303)

    if aksi == "unenroll":
        nama = [x for (x,) in db.query(Student.name).filter(Student.id.in_(ids)).order_by(Student.name)]
        db.query(Enrollment).filter(Enrollment.student_id.in_(ids)).delete(synchronize_session=False)
        audit.catat(db, user, "Siswa", "Keluarkan dari rombel", f"{len(ids)} siswa", audit.daftar_nama(nama))
        db.commit()
        return RedirectResponse(url=f"{kembali}{sambung}pesan=keluar&n={len(ids)}", status_code=303)

    # move: pindahkan ke rombel tujuan di tahun ajaran aktif
    rombel_id = form.get("rombel_id")
    rombel = db.query(Rombel).filter(Rombel.id == int(rombel_id)).first() if str(rombel_id).isdigit() else None
    if not rombel:
        return RedirectResponse(url=kembali, status_code=303)
    tahun = tahun_ajaran_aktif(db)
    n = 0
    for sid in ids:
        if not db.query(Student.id).filter(Student.id == sid).first():
            continue
        di_tahun_ini = (db.query(Enrollment).filter(Enrollment.student_id == sid, Enrollment.academic_year_id == tahun.id)
                        .order_by(Enrollment.id).all())
        if di_tahun_ini:
            di_tahun_ini[0].rombel_id = rombel.id
            for lebih in di_tahun_ini[1:]:          # rapikan kalau ada keanggotaan ganda
                db.delete(lebih)
        else:
            db.add(Enrollment(student_id=sid, rombel_id=rombel.id, academic_year_id=tahun.id))
        n += 1
    audit.catat(db, user, "Siswa", "Pindah rombel", f"{n} siswa", f"ke {rombel.rombel_name}")
    db.commit()
    return RedirectResponse(url=f"/teacher/students?rombel={rombel.id}&pesan=pindah&n={n}&r={rombel.id}", status_code=303)


# --- TOGGLE ACTIVE SISWA (Soft Delete) ---
@router.post("/students/{student_id}/toggle-active")
async def toggle_student_active(student_id: int, db: Session = Depends(get_db), user=Depends(require_teacher)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if student:
        student.is_active = not student.is_active
        audit.catat(db, user, "Siswa", "Aktifkan siswa" if student.is_active else "Nonaktifkan siswa", student.name)
        db.commit()
    return RedirectResponse(url="/teacher/students", status_code=303)
