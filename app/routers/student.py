# app/routers/student.py
# Router khusus untuk logika CBT Siswa

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

import random
import traceback

from app.database import get_db
from app.utils.deps import require_student
from app.models.student import Student
from app.models.exam import Exam, ExamSession, ExamAnswer
from app.models.question import Question, QuestionOption
from app.models.academic import SchoolClass, Rombel, Enrollment
from app.models.grade import ScoreComponent, Score
from app.models.achievement import Achievement, StudentAchievement

try:
    from app.services.gamification import award_achievement
except ImportError:
    award_achievement = None

router = APIRouter(prefix="/student", tags=["Student"])
BASE_DIR = Path(__file__).resolve().parent.parent
templates_env = Environment(loader=FileSystemLoader(BASE_DIR / "templates"))

# --- DASHBOARD ---
@router.get("/dashboard", response_class=HTMLResponse)
async def student_dashboard(request: Request, db: Session = Depends(get_db), user=Depends(require_student)):
    try:
        student_id = int(user.get("sub"))
        exams = db.query(Exam).filter(Exam.is_published == True).all()
        template = templates_env.get_template("student/dashboard.html")
        html_content = template.render(request=request, exams=exams, student_id=student_id, user=user, active_page="home")
        return HTMLResponse(content=html_content)
    except Exception as e:
        return HTMLResponse(content=f"Error Dashboard: {traceback.format_exc()}", status_code=500)

# --- MULAI UJIAN ---
@router.post("/exam/start")
async def start_exam(request: Request, db: Session = Depends(get_db), user=Depends(require_student)):
    try:
        form = await request.form()
        exam_id = int(form.get("exam_id"))
        student_id = int(user.get("sub"))
        
        exam = db.query(Exam).filter(Exam.id == exam_id).first()
        
        existing_session = db.query(ExamSession).filter(
            ExamSession.student_id == student_id, 
            ExamSession.exam_id == exam_id, 
            ExamSession.status == "active"
        ).first()
        
        if existing_session:
            return RedirectResponse(url=f"/student/exam/take/{existing_session.id}", status_code=303)
        
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=exam.duration_minutes)
        
        new_session = ExamSession(
            student_id=student_id,
            exam_id=exam_id,
            started_at=now,
            expires_at=expires_at,
            status="active"
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        
        return RedirectResponse(url=f"/student/exam/take/{new_session.id}", status_code=303)
    except Exception as e:
        return HTMLResponse(content=f"Error Start Exam: {traceback.format_exc()}", status_code=500)

# --- HALAMAN UJIAN ---
@router.get("/exam/take/{session_id}", response_class=HTMLResponse)
async def take_exam(session_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_student)):
    try:
        session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
        exam = db.query(Exam).filter(Exam.id == session.exam_id).first()
        
        if datetime.now(timezone.utc) > session.expires_at:
            session.status = "expired"
            db.commit()
            raise HTTPException(status_code=400, detail="Waktu ujian telah habis!")
            
        questions = db.query(Question).filter(Question.bank_id == exam.bank_id).all()
        
        if exam.randomize_questions:
            random.shuffle(questions)
            
        exam_data = []
        for q in questions:
            options = db.query(QuestionOption).filter(QuestionOption.question_id == q.id).all()
            if exam.randomize_options:
                random.shuffle(options)
            exam_data.append({"question": q, "options": options})
            
        template = templates_env.get_template("student/take_exam.html")
        html_content = template.render(
            request=request, exam=exam, exam_data=exam_data, session=session,
            expires_at=session.expires_at.isoformat()
        )
        return HTMLResponse(content=html_content)
    except Exception as e:
        return HTMLResponse(content=f"Error Take Exam: {traceback.format_exc()}", status_code=500)

# --- SUBMIT UJIAN (BULLETPROOF & AUTO-SYNC) ---
@router.post("/exam/submit/{session_id}")
async def submit_exam(session_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_student)):
    try:
        session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
        exam = db.query(Exam).filter(Exam.id == session.exam_id).first()
        student_id = int(user.get("sub"))
        
        session.submitted_at = datetime.now(timezone.utc)
        session.status = "completed"
        
        form = await request.form()
        total_score = 0
        total_wrong = 0
        
        for key, selected_option_id in form.items():
            if key.startswith("question_"):
                q_id = int(key.replace("question_", ""))
                opt_id = int(selected_option_id)
                
                option = db.query(QuestionOption).filter(QuestionOption.id == opt_id).first()
                question = db.query(Question).filter(Question.id == q_id).first()
                
                is_correct = option.is_correct
                if is_correct:
                    total_score += question.points
                else:
                    total_wrong += 1
                    
                answer = ExamAnswer(
                    session_id=session.id,
                    question_id=q_id,
                    selected_option_id=opt_id,
                    is_correct=is_correct
                )
                db.add(answer)
                
        session.score = total_score
        db.commit()
        
        # --- LOGIKA AUTO-SYNC GRADE ENGINE (CERDAS) ---
        score_comp = db.query(ScoreComponent).filter(ScoreComponent.name == exam.title).first()
        
        if not score_comp:
            score_comp = ScoreComponent(
                name=exam.title,
                weight=100,
                class_target=exam.class_target,
                teacher_id=exam.teacher_id
            )
            db.add(score_comp)
            db.commit()
            db.refresh(score_comp)
            
        existing_score = db.query(Score).filter(
            Score.student_id == student_id, 
            Score.component_id == score_comp.id
        ).first()
        
        if existing_score:
            existing_score.score_value = total_score
        else:
            new_score_entry = Score(student_id=student_id, component_id=score_comp.id, score_value=total_score)
            db.add(new_score_entry)
            
        db.commit()
        # -------------------------------------------
        
        # --- ACHIEVEMENT LOGIC ---
        try:
            if award_achievement is not None:
                award_achievement(student_id=student_id, condition_type="FIRST_EXAM", db=db)
                if total_wrong == 0:
                    award_achievement(student_id=student_id, condition_type="PERFECT_SCORE", db=db)
        except Exception as ach_err:
            print(f"Warning: Achievement gagal - {ach_err}")
            
        return RedirectResponse(url=f"/student/exam/result/{session.id}", status_code=303)
        
    except Exception as e:
        return HTMLResponse(content=f"Error Submit Exam: {traceback.format_exc()}", status_code=500)

# --- HASIL UJIAN ---
@router.get("/exam/result/{session_id}", response_class=HTMLResponse)
async def exam_result(session_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_student)):
    try:
        session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
        answers = db.query(ExamAnswer).filter(ExamAnswer.session_id == session_id).all()
        
        template = templates_env.get_template("student/exam_result.html")
        html_content = template.render(request=request, session=session, answers=answers)
        return HTMLResponse(content=html_content)
    except Exception as e:
        return HTMLResponse(content=f"Error Result: {traceback.format_exc()}", status_code=500)

# --- LEADERBOARD ---
@router.get("/leaderboard", response_class=HTMLResponse)
async def leaderboard_page(request: Request, db: Session = Depends(get_db), user=Depends(require_student)):
    try:
        student_id = int(user.get("sub"))
        student = db.query(Student).filter(Student.id == student_id).first()
        enrollment = db.query(Enrollment).filter(Enrollment.student_id == student_id).first()
        
        if not enrollment:
            return HTMLResponse(content="Siswa belum terdaftar di rombel manapun.")
            
        rombel = db.query(Rombel).filter(Rombel.id == enrollment.rombel_id).first()
        kelas = db.query(SchoolClass).filter(SchoolClass.id == rombel.class_id).first()
        
        rombel_enrollments = db.query(Enrollment).filter(Enrollment.rombel_id == rombel.id).all()
        rombel_scores = []
        for enr in rombel_enrollments:
            s = db.query(Student).filter(Student.id == enr.student_id).first()
            components = db.query(ScoreComponent).filter(ScoreComponent.class_target == kelas.class_name).all()
            total_score = 0.0
            for comp in components:
                score_entry = db.query(Score).filter(Score.student_id == s.id, Score.component_id == comp.id).first()
                val = score_entry.score_value if score_entry else 0
                total_score += (val * comp.weight / 100)
            rombel_scores.append({"name": s.name, "score": round(total_score, 2)})
        rombel_scores.sort(key=lambda x: x["score"], reverse=True)
        
        all_rombels_in_class = db.query(Rombel).filter(Rombel.class_id == kelas.id).all()
        rombel_ids = [r.id for r in all_rombels_in_class]
        all_enrollments = db.query(Enrollment).filter(Enrollment.rombel_id.in_(rombel_ids)).all()
        angkatan_scores = []
        for enr in all_enrollments:
            s = db.query(Student).filter(Student.id == enr.student_id).first()
            components = db.query(ScoreComponent).filter(ScoreComponent.class_target == kelas.class_name).all()
            total_score = 0.0
            for comp in components:
                score_entry = db.query(Score).filter(Score.student_id == s.id, Score.component_id == comp.id).first()
                val = score_entry.score_value if score_entry else 0
                total_score += (val * comp.weight / 100)
            angkatan_scores.append({"name": s.name, "score": round(total_score, 2)})
        angkatan_scores.sort(key=lambda x: x["score"], reverse=True)
        
        template = templates_env.get_template("student/leaderboard.html")
        html_content = template.render(
            request=request, user=user, rombel_name=rombel.rombel_name, 
            class_name=kelas.class_name, rombel_scores=rombel_scores, 
            angkatan_scores=angkatan_scores, active_page="leaderboard"
        )
        return HTMLResponse(content=html_content)
    except Exception as e:
        return HTMLResponse(content=f"Error Leaderboard: {traceback.format_exc()}", status_code=500)

# --- ACHIEVEMENTS ---
@router.get("/achievements", response_class=HTMLResponse)
async def achievements_page(request: Request, db: Session = Depends(get_db), user=Depends(require_student)):
    try:
        student_id = int(user.get("sub"))
        all_achievements = db.query(Achievement).all()
        my_awards = db.query(StudentAchievement).filter(StudentAchievement.student_id == student_id).all()
        my_award_ids = [aw.achievement_id for aw in my_awards]
        
        template = templates_env.get_template("student/achievements.html")
        html_content = template.render(
            request=request, user=user, all_achievements=all_achievements, 
            my_award_ids=my_award_ids, active_page="achievements"
        )
        return HTMLResponse(content=html_content)
    except Exception as e:
        return HTMLResponse(content=f"Error Achievements: {traceback.format_exc()}", status_code=500)