# app/routers/teacher.py
# Router khusus untuk mengelola halaman Guru (CRUD Materi, dll)
import logging
import random
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from sqlalchemy.orm import Session
from app.models.exam import Exam

from app.database import get_db
from app.utils.deps import require_teacher

from app.models.grade import ScoreComponent, Score
from app.models.exam import Exam, ExamSession, ExamAnswer, RemedialRequest, ExamViolation, ExamEvent
from app.services.penilaian import id_soal_sesi, total_poin_sesi, hitung_ulang_skor, simpan_nilai_tertinggi
from app.services.esai import nilai_esai
from datetime import datetime, timezone
from sqlalchemy import func

from app.models.academic import SchoolClass, Rombel, Enrollment, AcademicYear
# Mengimpor model Kelas, Rombel, dan Enrollment untuk Grade Engine

from app.models.student import Student
# Mengimpor model Siswa untuk Grade Engine
# Mengimpor model Grade dan ExamSession
# Mengimpor satpam khusus guru
from app.models.student import Student
from app.utils.security import hash_password

from app.models.user import User
from app.models.achievement import StudentAchievement
from app.models.material import Material
# Mengimpor model Materi

router = APIRouter(prefix="/teacher", tags=["Teacher"])
# Semua URL di file ini otomatis diawali /teacher/

BASE_DIR = Path(__file__).resolve().parent.parent
templates_env = Environment(loader=FileSystemLoader(BASE_DIR / "templates"))

@router.get("/materials", response_class=HTMLResponse)
# Halaman daftar materi guru
async def list_materials(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    # Satpam require_teacher akan memastikan hanya guru yang bisa melihat ini
    
    materials = db.query(Material).order_by(Material.created_at.desc()).all()
    # Mengambil semua materi dari database, diurutkan dari terbaru
    
    template = templates_env.get_template("teacher/materials.html")
    html_content = template.render(request=request, materials=materials, now_ts=datetime.now(timezone.utc).timestamp(), user=user)
    # Mengirim data materi dan data user ke template HTML
    
    return HTMLResponse(content=html_content)

@router.post("/materials/create")
# Proses saat guru mengirim form buat materi baru
async def create_material(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    
    form = await request.form()
    # Ambil data dari form HTML
    
    new_material = Material(
        title=form.get("title"),
        description=form.get("description"),
        content=form.get("content"),
        class_target=form.get("class_target"),
        teacher_id=int(user.get("sub"))
        # teacher_id diambil dari ID guru yang login (ada di dalam JWT)
    )
    db.add(new_material)
    db.commit()
    db.refresh(new_material)
    # Simpan ke database
    
    return RedirectResponse(url="/teacher/materials", status_code=303)
    # Kembali ke halaman daftar materi

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
    
    bank = db.query(QuestionBank).filter(QuestionBank.id == bank_id).first()
    # Cari bank soal berdasarkan ID
    questions = db.query(Question).filter(Question.bank_id == bank_id).all()
    # Ambil semua soal di dalam bank ini
    
    template = templates_env.get_template("teacher/bank_detail.html")
    html_content = template.render(request=request, bank=bank, questions=questions, user=user)
    return HTMLResponse(content=html_content)

@router.post("/questions/create")
# Menambahkan soal baru ke dalam bank
async def create_question(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    form = await request.form()
    bank_id = int(form.get("bank_id"))
    try:
        poin = max(1, int(form.get("points") or 1))
    except ValueError:
        poin = 1
    jenis = "esai" if form.get("question_type") == "esai" else "pg"

    new_question = Question(bank_id=bank_id, text=form.get("question_text"), points=poin, question_type=jenis)
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
    html_content = template.render(request=request, exams=exams, banks=banks,
                                   remedial_pending=remedial_pending, user=user)
    return HTMLResponse(content=html_content)

@router.post("/exams/create")
# Membuat ujian baru
async def create_exam(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    
    form = await request.form()
    
    # Mengambil nilai checkbox. Jika dicentang, form mengirim "on", jika tidak, None.
    rand_q = True if form.get("randomize_questions") == "on" else False
    rand_o = True if form.get("randomize_options") == "on" else False
    
    new_exam = Exam(
        title=form.get("title"),
        bank_id=int(form.get("bank_id")),
        class_target=form.get("class_target"),
        duration_minutes=int(form.get("duration_minutes")),
        randomize_questions=rand_q,
        randomize_options=rand_o,
        is_published=False, # Saat baru dibuat, statusnya Draf
        teacher_id=int(user.get("sub")),
        # Jumlah soal per siswa (acak dari bank). Kosong / 0 = semua soal
        question_count=int(form.get("question_count")) if (form.get("question_count") or "").isdigit() and int(form.get("question_count")) > 0 else None
    )
    db.add(new_exam)
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

@router.get("/exams/{exam_id}/results", response_class=HTMLResponse)
# Melihat hasil pengerjaan ujian oleh siswa
async def exam_results(exam_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        return RedirectResponse(url="/teacher/exams", status_code=303)
    total_poin = db.query(func.coalesce(func.sum(Question.points), 0)).filter(Question.bank_id == exam.bank_id).scalar() or 0
    sessions = (db.query(ExamSession, Student).join(Student, Student.id == ExamSession.student_id)
                .filter(ExamSession.exam_id == exam_id).order_by(Student.name, ExamSession.id).all())
    pelanggaran = dict(db.query(ExamViolation.session_id, func.count(ExamViolation.id))
                       .join(ExamSession, ExamSession.id == ExamViolation.session_id)
                       .filter(ExamSession.exam_id == exam_id).group_by(ExamViolation.session_id).all())
    rows, percobaan = [], {}
    for sesi, siswa in sessions:
        percobaan[siswa.id] = percobaan.get(siswa.id, 0) + 1
        maks = total_poin_sesi(db, sesi, exam)      # soal tiap siswa bisa berbeda
        persen = round(sesi.score * 100 / maks) if (sesi.score is not None and maks) else None
        rows.append({"sesi": sesi, "siswa": siswa, "ke": percobaan[siswa.id], "persen": persen, "maks": maks,
                     "pelanggaran": pelanggaran.get(sesi.id, 0)})
    permintaan = (db.query(RemedialRequest, Student).join(Student, Student.id == RemedialRequest.student_id)
                  .filter(RemedialRequest.exam_id == exam_id, RemedialRequest.status == "pending")
                  .order_by(RemedialRequest.created_at).all())
    template = templates_env.get_template("teacher/exam_results.html")
    html_content = template.render(request=request, exam=exam, rows=rows, permintaan=permintaan,
                                   total_poin=total_poin, user=user)
    return HTMLResponse(content=html_content)

@router.get("/grades", response_class=HTMLResponse)
# Halaman manajemen komponen nilai (bobot)
async def grade_components(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    
    components = db.query(ScoreComponent).order_by(ScoreComponent.class_target).all()
    # Mengambil semua komponen nilai
    
    template = templates_env.get_template("teacher/grades.html")
    html_content = template.render(request=request, components=components, user=user)
    return HTMLResponse(content=html_content)

@router.post("/grades/components/create")
# Menambah komponen nilai baru
async def create_component(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    
    form = await request.form()
    new_comp = ScoreComponent(
        name=form.get("name"),
        weight=int(form.get("weight")),
        class_target=form.get("class_target"),
        teacher_id=int(user.get("sub"))
    )
    db.add(new_comp)
    db.commit()
    
    return RedirectResponse(url="/teacher/grades", status_code=303)

@router.get("/grades/class/{class_target}", response_class=HTMLResponse)
# Melihat rekap nilai akhir per kelas (Grade Engine)
async def class_grades(class_target: str, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    
    try:
        # 1. Cari ID Kelas (VII, VIII, IX)
        target_class = db.query(SchoolClass).filter(SchoolClass.class_name == class_target).first()
        if not target_class:
            return HTMLResponse(content="Kelas tidak ditemukan", status_code=404)
            
        # 2. Cari semua Rombel di kelas ini (misal: VII-A, VII-B)
        rombels_in_class = db.query(Rombel).filter(Rombel.class_id == target_class.id).all()
        rombel_ids = [r.id for r in rombels_in_class]
        # Kumpulkan ID rombelnya saja
        
        # 3. Cari semua Enrollment (pendaftaran) siswa di rombel-rombel tersebut
        enrollments = db.query(Enrollment).filter(Enrollment.rombel_id.in_(rombel_ids)).all()
        
        students_data = []
        for enr in enrollments:
            student = db.query(Student).filter(Student.id == enr.student_id).first()
            # 4. Cari komponen nilai untuk kelas ini
            components = db.query(ScoreComponent).filter(ScoreComponent.class_target == class_target).all()
            
            total_weighted_score = 0.0
            # 5. Hitung Grade Engine
            for comp in components:
                score_entry = db.query(Score).filter(Score.student_id == student.id, Score.component_id == comp.id).first()
                val = score_entry.score_value if score_entry else 0
                total_weighted_score += (val * comp.weight / 100)
                
            students_data.append({
                "id": student.id,
                "name": student.name,
                "final_score": round(total_weighted_score, 2)
            })
            
        template = templates_env.get_template("teacher/class_grades.html")
        html_content = template.render(request=request, students_data=students_data, class_target=class_target, user=user)
        return HTMLResponse(content=html_content)
        
    except Exception as e:
        # Jika masih ada error, tampilkan di layar
        logging.getLogger("informatika").exception("Rekap nilai")
        template = templates_env.get_template("error.html")
        return HTMLResponse(content=template.render(kembali="/teacher/grades"), status_code=500)

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

# --- BULK IMPORT SISWA + AUTO PIN ---
@router.post("/students/bulk-create")
async def bulk_create_students(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    form = await request.form()
    names_text = form.get("names_text") # Ambil teks dari textarea

    # Rombel tujuan dari dropdown (boleh kosong = siswa belum masuk rombel)
    rombel = None
    if form.get("rombel_id"):
        rombel = db.query(Rombel).filter(Rombel.id == int(form.get("rombel_id"))).first()
        if rombel is None:
            raise HTTPException(status_code=400, detail="Rombel tidak ditemukan")
        tahun = tahun_ajaran_aktif(db)
    
    # Pisahkan teks berdasarkan baris baru (enter)
    names = [n.strip() for n in names_text.split("\n") if n.strip()]
    
    created_students = []
    for name in names:
        # Generate PIN 4 digit random (1000-9999)
        pin = str(random.randint(1000, 9999))
        pin_hash = hash_password(pin)
        
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
    template = templates_env.get_template("teacher/student_pins.html")
    html_content = template.render(request=request, students=created_students, user=user)
    return HTMLResponse(content=html_content)

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
    jawaban = db.query(ExamAnswer).filter(ExamAnswer.id == answer_id).first()
    if not jawaban:
        return RedirectResponse(url="/teacher/exams", status_code=303)
    sesi = db.query(ExamSession).filter(ExamSession.id == jawaban.session_id).first()
    soal = db.query(Question).filter(Question.id == jawaban.question_id).first()
    form = await request.form()
    teks = (form.get("points") or "").strip().replace(",", ".")
    try:
        jawaban.manual_points = None if teks == "" else max(0.0, min(float(soal.points or 0), float(teks)))
    except ValueError:
        pass
    hitung_ulang_skor(db, sesi)
    exam = db.query(Exam).filter(Exam.id == sesi.exam_id).first()
    simpan_nilai_tertinggi(db, exam, sesi.student_id)
    db.commit()
    return RedirectResponse(url=f"/teacher/exams/{sesi.exam_id}/sessions/{sesi.id}?tersimpan=1#soal-{soal.id}", status_code=303)


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
    material = db.query(Material).filter(Material.id == material_id).first()
    if material:
        form = await request.form()
        if form.get("action") == "open":
            material.is_published = True
            batas = (form.get("close_at") or "").strip()
            try:
                # input datetime-local tanpa zona: dianggap jam di komputer server (WIB)
                material.close_at = datetime.strptime(batas, "%Y-%m-%dT%H:%M").astimezone() if batas else None
            except ValueError:
                material.close_at = None
        else:
            material.is_published = False
            material.close_at = None
        db.commit()
    return RedirectResponse(url="/teacher/materials", status_code=303)

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
    pin_hash = hash_password(form.get("pin"))
    new_student = Student(
        name=form.get("name"),
        nipd=form.get("nipd"),
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
    return RedirectResponse(url="/teacher/materials", status_code=303)

# --- DELETE KOMPONEN NILAI ---
@router.post("/grades/components/{comp_id}/delete")
async def delete_component(comp_id: int, db: Session = Depends(get_db), user=Depends(require_teacher)):
    comp = db.query(ScoreComponent).filter(ScoreComponent.id == comp_id).first()
    if comp:
        # Hapus semua nilai di komponen ini dulu (Foreign Key Constraint)
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
    if not ids or aksi not in ("move", "deactivate", "activate", "unenroll", "delete"):
        return RedirectResponse(url=kembali, status_code=303)

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
