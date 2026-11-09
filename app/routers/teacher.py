# app/routers/teacher.py
# Router khusus untuk mengelola halaman Guru (CRUD Materi, dll)
import logging
import random
import secrets
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.concurrency import run_in_threadpool
import re
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from sqlalchemy.orm import Session
from app.models.exam import Exam

from app.database import get_db
from app.utils.deps import require_teacher

from app.models.grade import ScoreComponent, Score
from app.models.exam import Exam, ExamSession, ExamAnswer, RemedialRequest, ExamViolation, ExamEvent
from app.services.penilaian import id_soal_sesi, total_poin_sesi, hitung_ulang_skor, tutup_sesi_lewat
from app.services.rekap import rekap_kelas, urutkan, persen_terbaik, tahun_aktif, KKM, BATAS_REMEDIAL
from app.services.excel import buku_rekap, buku_ujian
from app.services.esai import nilai_esai
from app.services.materi import status_materi, baca_waktu, sekarang as materi_sekarang
from app.services.impor_soal import periksa, gabung_kode, prompt_ai, CONTOH, PROMPT
import json
from datetime import datetime, timezone
from sqlalchemy import func

from app.models.academic import SchoolClass, Rombel, Enrollment, AcademicYear
# Mengimpor model Kelas, Rombel, dan Enrollment untuk Grade Engine

from app.models.student import Student
# Mengimpor model Siswa untuk Grade Engine
# Mengimpor model Grade dan ExamSession
# Mengimpor satpam khusus guru
from app.models.student import Student
from app.utils.security import hash_password, verify_password, create_access_token, sidik
from app.utils import ratelimit

from app.models.user import User
from app.models.achievement import StudentAchievement
from app.models.material import Material
# Mengimpor model Materi

router = APIRouter(prefix="/teacher", tags=["Teacher"])
# Semua URL di file ini otomatis diawali /teacher/

BASE_DIR = Path(__file__).resolve().parent.parent
templates_env = Environment(loader=FileSystemLoader(BASE_DIR / "templates"))
from app.services.teks import pasang as _pasang_filter
_pasang_filter(templates_env)   # filter |soal: teks soal aman + blok kode

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
    materials = db.query(Material).order_by(Material.created_at.desc()).all()
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

    # --- TAMBAHAN FASE 7: BANK SOAL ---

from app.models.question import QuestionBank, Question, QuestionOption
# Mengimpor model-model bank soal

@router.get("/question-banks", response_class=HTMLResponse)
# Halaman daftar bank soal
async def list_banks(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    
    banks = db.query(QuestionBank).order_by(QuestionBank.created_at.desc()).all()
    # Mengambil semua bank soal dari database
    
    template = templates_env.get_template("teacher/question_banks.html")
    html_content = template.render(request=request, banks=banks, user=user)
    return HTMLResponse(content=html_content)

@router.post("/question-banks/create")
# Membuat bank soal baru
async def create_bank(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    
    form = await request.form()
    new_bank = QuestionBank(
        title=form.get("title"),
        class_target=form.get("class_target"),
        teacher_id=int(user.get("sub"))
    )
    db.add(new_bank)
    db.commit()
    
    return RedirectResponse(url="/teacher/question-banks", status_code=303)

@router.get("/question-banks/{bank_id}", response_class=HTMLResponse)
# Melihat isi soal dalam sebuah bank soal
async def view_bank(bank_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    return halaman_bank(request, db, user, bank_id)


def bank_terkunci(db, bank_id: int) -> bool:
    """Bank yang ujiannya sudah pernah dikerjakan: soalnya tidak boleh dihapus (hasil lama bisa rusak)."""
    return db.query(ExamSession.id).join(Exam, Exam.id == ExamSession.exam_id).filter(Exam.bank_id == bank_id).first() is not None


def halaman_bank(request, db, user, bank_id: int, impor=None, teks_impor="", mode=None):
    bank = db.query(QuestionBank).filter(QuestionBank.id == bank_id).first()
    if not bank:
        return RedirectResponse(url="/teacher/question-banks", status_code=303)
    questions = db.query(Question).filter(Question.bank_id == bank_id).order_by(Question.id).all()
    # Question tidak punya relasi .options: opsi diambil sekali untuk semua soal (dulu q.options kosong diam-diam)
    opsi_soal = {}
    for o in (db.query(QuestionOption).filter(QuestionOption.question_id.in_([q.id for q in questions]))
              .order_by(QuestionOption.id) if questions else []):
        opsi_soal.setdefault(o.question_id, []).append(o)
    p = request.query_params
    template = templates_env.get_template("teacher/bank_detail.html")
    html_content = template.render(
        request=request, bank=bank, questions=questions, user=user, impor=impor, teks_impor=teks_impor,
        opsi_soal=opsi_soal,
        mode=mode or p.get("mode", "manual"), pesan=p.get("pesan"), n=p.get("n", "0"), lewat=p.get("lewat", "0"),
        terkunci=bank_terkunci(db, bank_id), prompt=prompt_ai(bank.title, bank.class_target, 10, 2, "sedang"),
        prompt_templat=PROMPT.replace("{contoh}", json.dumps(CONTOH, ensure_ascii=False, indent=2)),
        contoh=json.dumps(CONTOH, ensure_ascii=False, indent=2))
    return HTMLResponse(content=html_content)


def _kunci_teks(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip().lower())


@router.post("/question-banks/{bank_id}/import")
# Impor soal dari JSON hasil AI: "periksa" menampilkan pratinjau, "simpan" menyimpan bila tanpa kesalahan
async def import_questions(bank_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    form = await request.form()                     # form dibaca sebelum memegang koneksi database
    bank = db.query(QuestionBank).filter(QuestionBank.id == bank_id).first()
    if not bank:
        return RedirectResponse(url="/teacher/question-banks", status_code=303)
    teks = (form.get("teks") or "")[:400_000]
    hasil = periksa(teks)
    ada = {_kunci_teks(q.text) for q in db.query(Question.text).filter(Question.bank_id == bank_id)}
    for item in hasil["soal"]:
        item["kembar"] = _kunci_teks(gabung_kode(item["pertanyaan"], item["kode"])) in ada
    if form.get("aksi") != "simpan" or hasil["galat"]:
        return halaman_bank(request, db, user, bank_id, impor=hasil, teks_impor=teks, mode="impor")

    disimpan = lewat = 0
    for item in hasil["soal"]:
        teks_soal = gabung_kode(item["pertanyaan"], item["kode"])
        if _kunci_teks(teks_soal) in ada:      # soal yang sama sudah ada (misalnya tempel dua kali): dilewati
            lewat += 1
            continue
        ada.add(_kunci_teks(teks_soal))
        q = Question(bank_id=bank_id, text=teks_soal, points=item["poin"], question_type=item["tipe"])
        if item["tipe"] == "esai":
            q.answer_key, q.keywords = item["kunci"], item["kata_kunci"] or None
        db.add(q)
        db.flush()
        if item["tipe"] == "pg":
            for i, o in enumerate(item["opsi"]):
                db.add(QuestionOption(question_id=q.id, text=o, is_correct=(i == item["benar"])))
        disimpan += 1
    db.commit()
    return RedirectResponse(url=f"/teacher/question-banks/{bank_id}?pesan=impor&n={disimpan}&lewat={lewat}", status_code=303)


@router.post("/questions/{question_id}/delete")
async def delete_question(question_id: int, db: Session = Depends(get_db), user=Depends(require_teacher)):
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        return RedirectResponse(url="/teacher/question-banks", status_code=303)
    if bank_terkunci(db, q.bank_id):
        return RedirectResponse(url=f"/teacher/question-banks/{q.bank_id}?pesan=terkunci", status_code=303)
    bank_id = q.bank_id
    db.query(QuestionOption).filter(QuestionOption.question_id == q.id).delete(synchronize_session=False)
    db.delete(q)
    db.commit()
    return RedirectResponse(url=f"/teacher/question-banks/{bank_id}?pesan=hapus", status_code=303)

@router.post("/questions/create")
# Menambahkan soal baru ke dalam bank
async def create_question(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    form = await request.form()
    try:
        bank_id = int(form.get("bank_id"))
    except (TypeError, ValueError):
        return RedirectResponse(url="/teacher/question-banks", status_code=303)
    if not db.query(QuestionBank).filter(QuestionBank.id == bank_id).first():
        return RedirectResponse(url="/teacher/question-banks", status_code=303)
    try:
        poin = min(100, max(1, int(form.get("points") or 1)))
    except ValueError:
        poin = 1
    jenis = "esai" if form.get("question_type") == "esai" else "pg"
    teks_soal = gabung_kode((form.get("question_text") or "").strip()[:4000], (form.get("code") or "").strip("\n")[:4000])
    if not teks_soal.strip():
        return RedirectResponse(url=f"/teacher/question-banks/{bank_id}?pesan=isian", status_code=303)

    new_question = Question(bank_id=bank_id, text=teks_soal, points=poin, question_type=jenis)
    if jenis == "esai":
        new_question.answer_key = (form.get("answer_key") or "").strip()
        new_question.keywords = (form.get("keywords") or "").strip() or None
    db.add(new_question)
    db.commit()
    db.refresh(new_question)

    if jenis == "pg":
        correct_key = form.get("correct_key")
        for key in ["A", "B", "C", "D"]:
            option_text = form.get(f"option_{key}")
            if option_text:
                db.add(QuestionOption(question_id=new_question.id, text=option_text, is_correct=(key == correct_key)))
        db.commit()
    return RedirectResponse(url=f"/teacher/question-banks/{bank_id}", status_code=303)
# --- TAMBAHAN FASE 8: EXAM ENGINE ---

@router.get("/exams", response_class=HTMLResponse)
# Halaman daftar ujian/formatif
async def list_exams(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    
    exams = db.query(Exam).order_by(Exam.created_at.desc()).all()
    # Mengambil semua ujian
    
    banks = db.query(QuestionBank).all()
    # Mengambil semua bank soal (untuk ditampilkan di form pilihan)
    
    template = templates_env.get_template("teacher/exams.html")
    remedial_pending = dict(db.query(RemedialRequest.exam_id, func.count(RemedialRequest.id))
                            .filter(RemedialRequest.status == "pending").group_by(RemedialRequest.exam_id).all())
    komponen = db.query(ScoreComponent).order_by(ScoreComponent.class_target, ScoreComponent.id).all()
    html_content = template.render(request=request, exams=exams, banks=banks, komponen=komponen,
                                   nama_komponen={k.id: k for k in komponen}, remedial_pending=remedial_pending,
                                   error=request.query_params.get("error"), user=user)
    return HTMLResponse(content=html_content)

@router.post("/exams/create")
# Membuat ujian baru
async def create_exam(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    form = await request.form()
    try:
        bank_id = int(form.get("bank_id"))
        durasi = int(form.get("duration_minutes"))
    except (TypeError, ValueError):
        return RedirectResponse(url="/teacher/exams?error=isian", status_code=303)
    kelas = form.get("class_target")
    judul = (form.get("title") or "").strip()[:150]
    if not judul or kelas not in TINGKAT or not 1 <= durasi <= 300 or not db.query(QuestionBank).filter(QuestionBank.id == bank_id).first():
        return RedirectResponse(url="/teacher/exams?error=isian", status_code=303)
    komponen_id = None
    if (form.get("component_id") or "").isdigit():
        komp = db.query(ScoreComponent).filter(ScoreComponent.id == int(form.get("component_id"))).first()
        if not komp or komp.class_target != kelas:      # komponen harus satu tingkat dengan ujian
            return RedirectResponse(url="/teacher/exams?error=komponen", status_code=303)
        komponen_id = komp.id
    jumlah = form.get("question_count") or ""
    tahun = tahun_aktif(db)
    new_exam = Exam(
        title=judul,
        bank_id=bank_id,
        class_target=kelas,
        duration_minutes=durasi,
        randomize_questions=form.get("randomize_questions") == "on",
        randomize_options=form.get("randomize_options") == "on",
        is_published=False,          # Saat baru dibuat, statusnya Draf
        teacher_id=int(user.get("sub")),
        question_count=int(jumlah) if jumlah.isdigit() and int(jumlah) > 0 else None,
        component_id=komponen_id,
        academic_year_id=tahun.id if tahun else None,
    )
    db.add(new_exam)
    db.commit()
    return RedirectResponse(url="/teacher/exams", status_code=303)

@router.post("/exams/{exam_id}/component")
# Memindahkan ujian ke komponen nilai lain (atau melepasnya); nilai siswa ikut pindah otomatis
async def set_exam_component(exam_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    form = await request.form()
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        return RedirectResponse(url="/teacher/exams", status_code=303)
    pilihan = form.get("component_id") or ""
    if pilihan == "":
        exam.component_id = None
    elif pilihan.isdigit():
        komp = db.query(ScoreComponent).filter(ScoreComponent.id == int(pilihan)).first()
        if not komp or komp.class_target != exam.class_target:
            return RedirectResponse(url="/teacher/exams?error=komponen", status_code=303)
        exam.component_id = komp.id
    db.commit()
    return RedirectResponse(url="/teacher/exams", status_code=303)

@router.post("/exams/{exam_id}/toggle-publish")
# Mengubah status ujian dari Draf menjadi Published (atau sebaliknya)
async def toggle_publish(exam_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    # Cari ujian berdasarkan ID
    
    if exam:
        exam.is_published = not exam.is_published
        # Membalik status. Jika True jadi False, jika False jadi True
        
        db.commit()
        # Simpan perubahan
        
    return RedirectResponse(url="/teacher/exams", status_code=303)
# --- TAMBAHAN FASE 10: GRADE ENGINE ---

@router.get("/exams/{exam_id}/results/export")
@router.get("/exams/{exam_id}/results", response_class=HTMLResponse)
# Melihat hasil pengerjaan ujian oleh siswa
async def exam_results(exam_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    tutup_sesi_lewat(db, [exam_id])     # sesi yang waktunya habis tanpa terkirim: nilai dari log
    if not exam:
        return RedirectResponse(url="/teacher/exams", status_code=303)
    total_poin = db.query(func.coalesce(func.sum(Question.points), 0)).filter(Question.bank_id == exam.bank_id).scalar() or 0
    sessions = (db.query(ExamSession, Student).join(Student, Student.id == ExamSession.student_id)
                .filter(ExamSession.exam_id == exam_id).order_by(Student.name, ExamSession.id).all())
    pelanggaran = dict(db.query(ExamViolation.session_id, func.count(ExamViolation.id))
                       .join(ExamSession, ExamSession.id == ExamViolation.session_id)
                       .filter(ExamSession.exam_id == exam_id).group_by(ExamViolation.session_id).all())
    tahun = tahun_aktif(db)
    q_rombel = db.query(Enrollment.student_id, Rombel.rombel_name).join(Rombel, Rombel.id == Enrollment.rombel_id)
    rombel_siswa = dict((q_rombel.filter(Enrollment.academic_year_id == tahun.id) if tahun else q_rombel).all())
    remedial_aktif = {r.student_id: r.status for r in db.query(RemedialRequest).filter(
        RemedialRequest.exam_id == exam_id, RemedialRequest.status.in_(["pending", "approved"]))}
    rows, percobaan = [], {}
    for sesi, siswa in sessions:
        percobaan[siswa.id] = percobaan.get(siswa.id, 0) + 1
        maks = total_poin_sesi(db, sesi, exam)      # soal tiap siswa bisa berbeda
        persen = round(sesi.score * 100 / maks) if (sesi.score is not None and maks) else None
        rows.append({"sesi": sesi, "siswa": siswa, "ke": percobaan[siswa.id], "persen": persen, "maks": maks,
                     "pelanggaran": pelanggaran.get(sesi.id, 0), "rombel": rombel_siswa.get(siswa.id, "")})
    # sesi terakhir tiap siswa: tempat tombol "Beri remedial"
    terakhir = {}
    for r in rows:
        terakhir[r["siswa"].id] = r
    for r in rows:
        r["terakhir"] = terakhir[r["siswa"].id] is r
        r["remedial"] = remedial_aktif.get(r["siswa"].id)
    # urutan: nilai tertinggi siswa dulu (default), atau nama A-Z / Z-A
    terbaik = {}
    for r in rows:
        terbaik[r["siswa"].id] = max(terbaik.get(r["siswa"].id, -1), r["persen"] if r["persen"] is not None else -1)
    urut = request.query_params.get("urut", "nilai")
    urut = urut if urut in URUTAN else "nilai"
    nama = lambda r: r["siswa"].name.lower()
    if urut == "az":
        rows.sort(key=lambda r: (nama(r), r["ke"]))
    elif urut == "za":
        rows.sort(key=lambda r: (nama(r), -r["ke"]), reverse=True)
    elif urut == "rendah":
        rows.sort(key=lambda r: (terbaik[r["siswa"].id], nama(r), r["ke"]))
    else:
        rows.sort(key=lambda r: (-terbaik[r["siswa"].id], nama(r), r["ke"]))
    if request.url.path.endswith("/export"):
        return unduh_xlsx(buku_ujian(exam, rows), f"hasil_{exam.title}_{datetime.now():%Y%m%d}")
    permintaan = (db.query(RemedialRequest, Student).join(Student, Student.id == RemedialRequest.student_id)
                  .filter(RemedialRequest.exam_id == exam_id, RemedialRequest.status == "pending")
                  .order_by(RemedialRequest.created_at).all())
    template = templates_env.get_template("teacher/exam_results.html")
    ada_esai = db.query(Question.id).filter(Question.bank_id == exam.bank_id, Question.question_type == "esai").first() is not None
    html_content = template.render(request=request, exam=exam, rows=rows, permintaan=permintaan, urut=urut, urutan=URUTAN,
                                   ada_esai=ada_esai, pesan=request.query_params.get("pesan"), n=request.query_params.get("n", "0"),
                                   batas=BATAS_REMEDIAL, total_poin=total_poin, user=user)
    return HTMLResponse(content=html_content)

@router.get("/grades", response_class=HTMLResponse)
# Komponen nilai & bobot per tingkat
async def grade_components(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    components = db.query(ScoreComponent).order_by(ScoreComponent.class_target, ScoreComponent.id).all()
    jumlah_ujian = dict(db.query(Exam.component_id, func.count(Exam.id)).filter(Exam.component_id != None)
                        .group_by(Exam.component_id).all())
    template = templates_env.get_template("teacher/grades.html")
    html_content = template.render(request=request, components=components, jumlah_ujian=jumlah_ujian,
                                   error=request.query_params.get("error"), user=user)
    return HTMLResponse(content=html_content)

TINGKAT = ("VII", "VIII", "IX")

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
    if not nama or kelas not in TINGKAT or not 1 <= bobot <= 100:
        return RedirectResponse(url="/teacher/grades?error=isian", status_code=303)
    terpakai = db.query(func.coalesce(func.sum(ScoreComponent.weight), 0)).filter(ScoreComponent.class_target == kelas).scalar()
    if terpakai + bobot > 100:
        return RedirectResponse(url=f"/teacher/grades?error=bobot&sisa={100 - terpakai}&kelas={kelas}", status_code=303)
    db.add(ScoreComponent(name=nama, weight=bobot, class_target=kelas, teacher_id=int(user.get("sub"))))
    db.commit()
    return RedirectResponse(url="/teacher/grades", status_code=303)

URUTAN = {"nilai": "Nilai tertinggi", "rendah": "Nilai terendah", "az": "Nama A–Z", "za": "Nama Z–A"}

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
                                       rombels=rombels, rombel=rombel, kkm=KKM, user=user)
        return HTMLResponse(content=html_content)
    except Exception:
        logging.getLogger("informatika").exception("Rekap nilai")
        template = templates_env.get_template("error.html")
        return HTMLResponse(content=template.render(kembali="/teacher/grades"), status_code=500)


def unduh_xlsx(isi: bytes, nama: str):
    # nama file hanya huruf/angka/strip supaya header tidak bisa disisipi
    aman = re.sub(r"[^A-Za-z0-9_-]+", "_", nama)[:80] or "nilai"
    return Response(content=isi, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{aman}.xlsx"', "Cache-Control": "no-store"})


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

# --- TAMBAHAN FASE 13: TEACHER ANALYTICS ---

@router.get("/exams/{exam_id}/analytics", response_class=HTMLResponse)
# Halaman analitik mendalam untuk satu ujian
async def exam_analytics(exam_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    sessions = db.query(ExamSession).filter(ExamSession.exam_id == exam_id, ExamSession.status == "completed").all()
    
    if not sessions:
        # Jika belum ada yang mengerjakan
        template = templates_env.get_template("teacher/exam_analytics.html")
        return HTMLResponse(content=template.render(request=request, exam=exam, analytics=None, user=user))
        
    # 1. KALKULASI SKOR
    scores = [s.score for s in sessions if s.score is not None]
    total_students = len(scores)
    avg_score = round(sum(scores) / total_students, 2) if total_students > 0 else 0
    highest_score = max(scores) if scores else 0
    lowest_score = min(scores) if scores else 0
    
    # 2. KALKULASI SOAL PALING SULIT (Paling banyak salah)
    # Ambil semua soal di bank ujian ini
    questions = db.query(Question).filter(Question.bank_id == exam.bank_id).all()
    question_stats = []
    
    for q in questions:
        # Hitung berapa kali soal ini dijawab salah
        wrong_answers = db.query(ExamAnswer).filter(
            ExamAnswer.question_id == q.id, 
            ExamAnswer.is_correct == False
        ).count()
        
        # Hitung berapa kali soal ini dijawab benar
        correct_answers = db.query(ExamAnswer).filter(
            ExamAnswer.question_id == q.id, 
            ExamAnswer.is_correct == True
        ).count()
        
        total_attempts = wrong_answers + correct_answers
        error_rate = round((wrong_answers / total_attempts) * 100, 1) if total_attempts > 0 else 0
        
        question_stats.append({
            "text": q.text,
            "wrong": wrong_answers,
            "correct": correct_answers,
            "error_rate": error_rate
        })
        
    # Urutkan soal berdasarkan tingkat kesalahan tertinggi
    question_stats.sort(key=lambda x: x["error_rate"], reverse=True)
    
    analytics = {
        "total_students": total_students,
        "avg_score": avg_score,
        "highest_score": highest_score,
        "lowest_score": lowest_score,
        "hardest_questions": question_stats[:3] # Ambil 3 soal teratas yang paling sulit
    }
    
    template = templates_env.get_template("teacher/exam_analytics.html")
    html_content = template.render(request=request, exam=exam, analytics=analytics, user=user)
    return HTMLResponse(content=html_content)

    # --- FITUR HAPUS (CRUD) ---

@router.post("/exams/{exam_id}/delete")
async def delete_exam(exam_id: int, db: Session = Depends(get_db), user=Depends(require_teacher)):
    # Hapus ujian beserta sesi, jawaban, catatan pelanggaran, dan permintaan remedialnya
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam:
        session_ids = [s.id for s in db.query(ExamSession.id).filter(ExamSession.exam_id == exam_id)]
        db.query(RemedialRequest).filter(RemedialRequest.exam_id == exam_id).delete(synchronize_session=False)
        if session_ids:
            db.query(ExamEvent).filter(ExamEvent.session_id.in_(session_ids)).delete(synchronize_session=False)
            db.query(ExamViolation).filter(ExamViolation.session_id.in_(session_ids)).delete(synchronize_session=False)
            db.query(ExamAnswer).filter(ExamAnswer.session_id.in_(session_ids)).delete(synchronize_session=False)
        db.query(ExamSession).filter(ExamSession.exam_id == exam_id).delete(synchronize_session=False)
        db.delete(exam)
        db.commit()
    return RedirectResponse(url="/teacher/exams", status_code=303)

@router.post("/question-banks/{bank_id}/delete")
async def delete_bank(bank_id: int, db: Session = Depends(get_db), user=Depends(require_teacher)):
    # Hapus bank soal beserta seluruh riwayat ujian yang memakainya
    bank = db.query(QuestionBank).filter(QuestionBank.id == bank_id).first()
    if bank:
        # 1. Cari semua soal di bank ini
        questions = db.query(Question).filter(Question.bank_id == bank_id).all()
        question_ids = [q.id for q in questions]
        
        # 2. Cari semua ujian yang memakai bank soal ini
        exams = db.query(Exam).filter(Exam.bank_id == bank_id).all()
        exam_ids = [e.id for e in exams]
        
        # 3. Hapus riwayat ujian (jika ada ujian yang pakai bank ini)
        if exam_ids:
            sessions = db.query(ExamSession).filter(ExamSession.exam_id.in_(exam_ids)).all()
            session_ids = [s.id for s in sessions]
            db.query(RemedialRequest).filter(RemedialRequest.exam_id.in_(exam_ids)).delete(synchronize_session=False)
            if session_ids:
                db.query(ExamEvent).filter(ExamEvent.session_id.in_(session_ids)).delete(synchronize_session=False)
                db.query(ExamViolation).filter(ExamViolation.session_id.in_(session_ids)).delete(synchronize_session=False)
                # Hapus semua jawaban siswa dulu
                db.query(ExamAnswer).filter(ExamAnswer.session_id.in_(session_ids)).delete(synchronize_session=False)
            # Hapus semua sesi ujian
            db.query(ExamSession).filter(ExamSession.exam_id.in_(exam_ids)).delete(synchronize_session=False)
            # Hapus semua ujiannya
            db.query(Exam).filter(Exam.id.in_(exam_ids)).delete(synchronize_session=False)
        
        # 4. Hapus opsi jawaban dan soal (jika ada)
        if question_ids:
            db.query(QuestionOption).filter(QuestionOption.question_id.in_(question_ids)).delete(synchronize_session=False)
            db.query(Question).filter(Question.id.in_(question_ids)).delete(synchronize_session=False)
        
        # 5. Terakhir, hapus bank soalnya
        db.delete(bank)
        db.commit()
        
    return RedirectResponse(url="/teacher/question-banks", status_code=303)

def tahun_ajaran_aktif(db: Session):
    # Tahun ajaran yang sedang aktif (is_active = 1); dipakai saat siswa dimasukkan ke rombel
    tahun = db.query(AcademicYear).filter(AcademicYear.is_active == 1).order_by(AcademicYear.id.desc()).first()
    if tahun is None:
        raise HTTPException(status_code=400, detail="Belum ada tahun ajaran aktif. Jalankan: python ganti_tahun_ajaran.py")
    return tahun

def pin_baru() -> str:
    # secrets (bukan random) supaya PIN tidak bisa ditebak dari pola bilangan acak
    return str(1000 + secrets.randbelow(9000))


def halaman_pin(request, daftar, user, judul="siap login", reset=False):
    template = templates_env.get_template("teacher/student_pins.html")
    html = template.render(request=request, students=daftar, user=user, judul=judul, reset=reset)
    # PIN hanya tampil sekali: jangan disimpan cache browser
    return HTMLResponse(content=html, headers={"Cache-Control": "no-store"})


def reset_pin_siswa(db, ids):
    hasil = []
    for siswa in db.query(Student).filter(Student.id.in_(ids)).order_by(Student.name):
        pin = pin_baru()
        siswa.pin_hash = hash_password(pin)   # token lama siswa ikut gugur (sidik berubah)
        ratelimit.reset(f"siswa:{siswa.id}")  # kunci 5x salah dibuka
        hasil.append({"name": siswa.name, "pin": pin})
    db.commit()
    return hasil


@router.post("/students/{student_id}/reset-pin")
async def reset_pin(student_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    daftar = await run_in_threadpool(reset_pin_siswa, db, [student_id])
    if not daftar:
        return RedirectResponse(url="/teacher/students", status_code=303)
    return halaman_pin(request, daftar, user, judul="PIN baru", reset=True)


# --- AKUN GURU: ganti password lewat web ---
@router.get("/account", response_class=HTMLResponse)
async def account_page(request: Request, user=Depends(require_teacher)):
    template = templates_env.get_template("teacher/account.html")
    return HTMLResponse(content=template.render(request=request, user=user, pesan=request.query_params.get("pesan")))


PASSWORD_UMUM = {"password", "12345678", "123456789", "guru1234", "informatika", "qwertyui", "admin123", "password1"}

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
    db.commit()
    # perangkat lain yang masih login otomatis keluar; perangkat ini diberi karcis baru
    from app.routers.auth import pasang_cookie_login
    respon = RedirectResponse(url="/teacher/account?pesan=ok", status_code=303)
    pasang_cookie_login(request, respon, create_access_token(
        {"sub": str(akun.id), "role": akun.role, "v": sidik(akun.hashed_password)}))
    return respon


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
    
    # Render halaman khusus untuk menampilkan hasil PIN
    return halaman_pin(request, created_students, user)

# --- KELOLA SISWA ---
@router.get("/students", response_class=HTMLResponse)
async def list_students(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    # Daftar rombel diambil dari database (bukan ID yang ditulis manual di template)
    rombels = db.query(Rombel, SchoolClass).join(SchoolClass, Rombel.class_id == SchoolClass.id).order_by(SchoolClass.id, Rombel.rombel_name).all()
    nama_rombel = {r.id: r.rombel_name for r, _ in rombels}
    jumlah_per_rombel = dict(db.query(Enrollment.rombel_id, func.count(func.distinct(Enrollment.student_id)))
                             .group_by(Enrollment.rombel_id).all())
    semua = db.query(Student).order_by(Student.name).all()
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
    html_content = template.render(request=request, students=students, semua=semua, rombels=rombels,
                                   jumlah_per_rombel=jumlah_per_rombel, jumlah_tanpa_rombel=len(tanpa_rombel),
                                   filter_rombel=filter_rombel, cari=cari, pesan=pesan, user=user)
    return HTMLResponse(content=html_content)

# --- DETAIL SESI: jawaban per soal, koreksi esai, log aktivitas ---
NAMA_KEJADIAN = {"mulai": "Mulai ujian", "lihat": "Melihat soal", "pilih": "Memilih jawaban", "esai": "Menulis esai",
                 "kirim": "Mengirim jawaban", "pindah_tab": "Keluar dari halaman ujian", "keluar_layar_penuh": "Keluar layar penuh",
                 "salin": "Mencoba menyalin", "tempel": "Mencoba menempel", "klik_kanan": "Klik kanan",
                 "screenshot": "Menekan PrintScreen", "cetak": "Mencoba mencetak", "devtools": "Membuka alat pengembang",
                 "lainnya": "Pelanggaran lain"}


@router.get("/exams/{exam_id}/sessions/{session_id}", response_class=HTMLResponse)
async def session_detail(exam_id: int, session_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    sesi = db.query(ExamSession).filter(ExamSession.id == session_id, ExamSession.exam_id == exam_id).first()
    if not sesi:
        return RedirectResponse(url=f"/teacher/exams/{exam_id}/results", status_code=303)
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    siswa = db.query(Student).filter(Student.id == sesi.student_id).first()
    ids = id_soal_sesi(db, sesi, exam)
    soal = {q.id: q for q in db.query(Question).filter(Question.id.in_(ids))} if ids else {}
    opsi = {o.id: o for o in db.query(QuestionOption).filter(QuestionOption.question_id.in_(ids))} if ids else {}
    jawaban = {a.question_id: a for a in db.query(ExamAnswer).filter(ExamAnswer.session_id == sesi.id)}
    kejadian = db.query(ExamEvent).filter(ExamEvent.session_id == sesi.id).order_by(ExamEvent.created_at, ExamEvent.id).all()
    pelanggaran = db.query(ExamViolation).filter(ExamViolation.session_id == sesi.id).order_by(ExamViolation.created_at).all()

    # Ringkasan per soal dari log: kapan pertama dilihat/dijawab, berapa kali jawaban diganti
    per_soal = {}
    for e in kejadian:
        if e.question_id is None:
            continue
        info = per_soal.setdefault(e.question_id, {"lihat": None, "jawab": None, "pilihan": [], "dilihat": 0})
        if e.kind == "lihat":
            info["dilihat"] += 1
            info["lihat"] = info["lihat"] or e.created_at
        elif e.kind in ("pilih", "esai"):
            info["jawab"] = info["jawab"] or e.created_at
            if e.kind == "pilih" and (not info["pilihan"] or info["pilihan"][-1] != e.option_id):
                info["pilihan"].append(e.option_id)
    baris = []
    for no, qid in enumerate(ids, 1):
        q, a = soal.get(qid), jawaban.get(qid)
        if not q:
            continue
        info = per_soal.get(qid, {"lihat": None, "jawab": None, "pilihan": [], "dilihat": 0})
        analisis = nilai_esai(a.answer_text, q.answer_key, q.keywords) if (q.question_type == "esai" and a) else None
        baris.append({"no": no, "q": q, "a": a, "opsi": opsi.get(a.selected_option_id) if a and a.selected_option_id else None,
                      "benar": next((o for o in opsi.values() if o.question_id == qid and o.is_correct), None),
                      "ganti": max(0, len(info["pilihan"]) - 1), "dilihat": info["dilihat"], "analisis": analisis,
                      "detik": int((info["jawab"] - sesi.started_at).total_seconds()) if info["jawab"] and sesi.started_at else None})

    linimasa = sorted([(e.created_at, e.kind, e) for e in kejadian] + [(v.created_at, v.kind, None) for v in pelanggaran],
                      key=lambda x: x[0] or sesi.started_at)
    durasi = int((sesi.submitted_at - sesi.started_at).total_seconds()) if sesi.submitted_at and sesi.started_at else None
    template = templates_env.get_template("teacher/session_detail.html")
    html_content = template.render(request=request, exam=exam, sesi=sesi, siswa=siswa, baris=baris, linimasa=linimasa,
                                   opsi=opsi, soal=soal, nama_kejadian=NAMA_KEJADIAN, durasi=durasi,
                                   maks=total_poin_sesi(db, sesi, exam), jml_pelanggaran=len(pelanggaran),
                                   tersimpan=request.query_params.get("tersimpan") == "1", user=user)
    return HTMLResponse(content=html_content)


@router.post("/answers/{answer_id}/score")
async def override_essay_score(answer_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    # Guru mengoreksi poin esai; kosongkan isian untuk kembali ke nilai otomatis
    form = await request.form()                     # form dibaca sebelum memegang koneksi database
    jawaban = db.query(ExamAnswer).filter(ExamAnswer.id == answer_id).first()
    if not jawaban:
        return RedirectResponse(url="/teacher/exams", status_code=303)
    sesi = db.query(ExamSession).filter(ExamSession.id == jawaban.session_id).first()
    soal = db.query(Question).filter(Question.id == jawaban.question_id).first()
    teks = (form.get("points") or "").strip().replace(",", ".")
    try:
        jawaban.manual_points = None if teks == "" else max(0.0, min(float(soal.points or 0), float(teks)))
    except ValueError:
        pass
    hitung_ulang_skor(db, sesi)
    db.commit()
    return RedirectResponse(url=f"/teacher/exams/{sesi.exam_id}/sessions/{sesi.id}?tersimpan=1#soal-{soal.id}", status_code=303)


# --- HITUNG ULANG ESAI: setelah aturan penilaian diperbarui / kunci diperbaiki ---
@router.post("/exams/{exam_id}/recalc")
async def recalc_essays(exam_id: int, db: Session = Depends(get_db), user=Depends(require_teacher)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        return RedirectResponse(url="/teacher/exams", status_code=303)
    sesi_ids = [s.id for s in db.query(ExamSession.id).filter(ExamSession.exam_id == exam_id, ExamSession.status != "active")]
    berubah = 0
    if sesi_ids:
        for jawab, soal in (db.query(ExamAnswer, Question).join(Question, Question.id == ExamAnswer.question_id)
                            .filter(ExamAnswer.session_id.in_(sesi_ids), Question.question_type == "esai")):
            hasil = nilai_esai(jawab.answer_text or "", soal.answer_key, soal.keywords)
            poin = round((soal.points or 0) * hasil["persen"], 1)
            if jawab.auto_points != poin:
                berubah += 1
            jawab.auto_points, jawab.similarity = poin, hasil["kemiripan"]
            if jawab.manual_points is None:            # koreksi guru tetap dihormati
                jawab.is_correct = hasil["persen"] >= 1
        db.flush()
        for sesi in db.query(ExamSession).filter(ExamSession.id.in_(sesi_ids)):
            hitung_ulang_skor(db, sesi)
        db.commit()
    return RedirectResponse(url=f"/teacher/exams/{exam_id}/results?pesan=hitung&n={berubah}", status_code=303)


# --- REMEDIAL DARI GURU: memberi izin mengulang tanpa menunggu siswa mengajukan ---
@router.post("/exams/{exam_id}/sessions/{session_id}/remedial")
async def grant_remedial(exam_id: int, session_id: int, db: Session = Depends(get_db), user=Depends(require_teacher)):
    sesi = db.query(ExamSession).filter(ExamSession.id == session_id, ExamSession.exam_id == exam_id).first()
    if sesi and sesi.status != "active":
        ada = db.query(RemedialRequest).filter(RemedialRequest.student_id == sesi.student_id, RemedialRequest.exam_id == exam_id,
                                               RemedialRequest.status.in_(["pending", "approved"])).first()
        if ada:
            ada.status = "approved"          # permintaan siswa yang menunggu langsung disetujui
            ada.decided_at = datetime.now(timezone.utc)
        else:
            db.add(RemedialRequest(student_id=sesi.student_id, exam_id=exam_id, session_id=sesi.id, status="approved",
                                   decided_at=datetime.now(timezone.utc)))
        db.commit()
    return RedirectResponse(url=f"/teacher/exams/{exam_id}/results", status_code=303)


# --- REMEDIAL: guru menyetujui / menolak permintaan mengulang ujian ---
@router.post("/remedial/{request_id}/{keputusan}")
async def decide_remedial(request_id: int, keputusan: str, db: Session = Depends(get_db), user=Depends(require_teacher)):
    permintaan = db.query(RemedialRequest).filter(RemedialRequest.id == request_id).first()
    if not permintaan or keputusan not in ("approve", "reject"):
        return RedirectResponse(url="/teacher/exams", status_code=303)
    if permintaan.status == "pending":
        permintaan.status = "approved" if keputusan == "approve" else "rejected"
        permintaan.decided_at = datetime.now(timezone.utc)
        db.commit()
    return RedirectResponse(url=f"/teacher/exams/{permintaan.exam_id}/results", status_code=303)

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
    db.commit()
    return RedirectResponse(url="/teacher/students", status_code=303)

# ============================================
# COMPLETE CRUD - DELETE ROUTES
# ============================================

# --- DELETE MATERI ---
@router.post("/materials/{material_id}/delete")
async def delete_material(material_id: int, db: Session = Depends(get_db), user=Depends(require_teacher)):
    material = db.query(Material).filter(Material.id == material_id).first()
    if material:
        db.delete(material)
        db.commit()
    return RedirectResponse(url="/teacher/materials?pesan=dihapus", status_code=303)

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


def baca_ids(teks: str) -> list[int]:
    return sorted({int(x) for x in (teks or "").split(",") if x.strip().isdigit()})


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
        for q in data_terkait_siswa(db, ids).values():
            q.delete(synchronize_session=False)
        n = db.query(Student).filter(Student.id.in_(ids)).delete(synchronize_session=False)
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
        return halaman_pin(request, await run_in_threadpool(reset_pin_siswa, db, ids), user, judul="PIN baru", reset=True)

    if aksi == "delete":
        return RedirectResponse(url=f"/teacher/students/delete?ids={','.join(map(str, ids))}", status_code=303)

    if aksi in ("deactivate", "activate"):
        n = db.query(Student).filter(Student.id.in_(ids)).update({Student.is_active: aksi == "activate"}, synchronize_session=False)
        db.commit()
        return RedirectResponse(url=f"{kembali}{sambung}pesan={'aktif' if aksi == 'activate' else 'nonaktif'}&n={n}", status_code=303)

    if aksi == "unenroll":
        db.query(Enrollment).filter(Enrollment.student_id.in_(ids)).delete(synchronize_session=False)
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
    db.commit()
    return RedirectResponse(url=f"/teacher/students?rombel={rombel.id}&pesan=pindah&n={n}&r={rombel.id}", status_code=303)

# --- TOGGLE ACTIVE SISWA (Soft Delete) ---
@router.post("/students/{student_id}/toggle-active")
async def toggle_student_active(student_id: int, db: Session = Depends(get_db), user=Depends(require_teacher)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if student:
        student.is_active = not student.is_active
        db.commit()
    return RedirectResponse(url="/teacher/students", status_code=303)
