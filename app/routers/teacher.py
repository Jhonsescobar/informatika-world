# app/routers/teacher.py
# Router khusus untuk mengelola halaman Guru (CRUD Materi, dll)

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from sqlalchemy.orm import Session
from app.models.exam import Exam

from app.database import get_db
from app.utils.deps import require_teacher

from app.models.grade import ScoreComponent, Score
from app.models.exam import Exam, ExamSession, ExamAnswer

from app.models.academic import SchoolClass, Rombel, Enrollment
# Mengimpor model Kelas, Rombel, dan Enrollment untuk Grade Engine

from app.models.student import Student
# Mengimpor model Siswa untuk Grade Engine
# Mengimpor model Grade dan ExamSession
# Mengimpor satpam khusus guru

from app.models.user import User
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
    html_content = template.render(request=request, materials=materials, user=user)
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
    
    # 1. Buat soalnya dulu
    new_question = Question(
        bank_id=bank_id,
        text=form.get("question_text"),
        points=int(form.get("points", 1))
    )
    db.add(new_question)
    db.commit()
    db.refresh(new_question) # Refresh agar kita dapat ID soal yang baru dibuat
    
    # 2. Buat 4 opsi jawaban
    correct_key = form.get("correct_key")
    # Mengambil kunci jawaban dari form (contoh: "A")
    
    for key in ["A", "B", "C", "D"]:
        option_text = form.get(f"option_{key}")
        # Ambil teks opsi (option_A, option_B, dll)
        
        if option_text: # Jika opsi tidak kosong
            is_correct = (key == correct_key)
            # Cek apakah huruf ini adalah kunci jawaban benar
            
            new_option = QuestionOption(
                question_id=new_question.id,
                text=option_text,
                is_correct=is_correct
                # KITA SIMPAN is_correct (True/False), BUKAN hurufnya!
            )
            db.add(new_option)
            
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
    html_content = template.render(request=request, exams=exams, banks=banks, user=user)
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
        teacher_id=int(user.get("sub"))
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
    sessions = db.query(ExamSession).filter(ExamSession.exam_id == exam_id, ExamSession.status == "completed").all()
    # Mengambil sesi ujian yang statusnya completed
    
    template = templates_env.get_template("teacher/exam_results.html")
    html_content = template.render(request=request, exam=exam, sessions=sessions, user=user)
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
        return HTMLResponse(content=f"Error Grade Engine: {str(e)}", status_code=500)

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
    # Hapus ujian beserta sesi dan jawaban di dalamnya
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam:
        # 1. Cari semua sesi ujian ini
        sessions = db.query(ExamSession).filter(ExamSession.exam_id == exam_id).all()
        for s in sessions:
            # 2. Hapus semua jawaban di sesi ini
            db.query(ExamAnswer).filter(ExamAnswer.session_id == s.id).delete()
        # 3. Hapus semua sesi
        db.query(ExamSession).filter(ExamSession.exam_id == exam_id).delete()
        # 4. Hapus ujiannya sendiri
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
            if session_ids:
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