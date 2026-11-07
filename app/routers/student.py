# app/routers/student.py
# Router khusus untuk logika CBT Siswa

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

import logging
import random

from app.database import get_db
from app.utils.deps import require_student
from app.models.student import Student
from app.models.exam import Exam, ExamSession, ExamAnswer, RemedialRequest, ExamViolation, ExamEvent
from app.services.penilaian import id_soal_sesi, total_poin_sesi
from app.services.rekap import rekap_kelas, BATAS_REMEDIAL as BATAS_REMEDIAL_REKAP
from app.services.esai import nilai_esai
import json
from app.models.material import Material
from fastapi.responses import JSONResponse
from sqlalchemy import func
from app.models.question import Question, QuestionOption
from app.models.academic import SchoolClass, Rombel, Enrollment, AcademicYear
from app.models.achievement import Achievement, StudentAchievement

try:
    from app.services.gamification import award_achievement
except ImportError:
    award_achievement = None

router = APIRouter(prefix="/student", tags=["Student"])
BASE_DIR = Path(__file__).resolve().parent.parent
templates_env = Environment(loader=FileSystemLoader(BASE_DIR / "templates"))
log = logging.getLogger("informatika")

# --- PENGAMAN SESI UJIAN ---
# Toleransi keterlambatan kirim jawaban (jaringan lambat / tombol ditekan saat waktu habis)
TOLERANSI_KIRIM = timedelta(minutes=2)


def gagal(label: str, kembali: str = "/student/dashboard"):
    # Detail error hanya dicatat di konsol server; siswa melihat halaman umum
    log.exception(label)
    template = templates_env.get_template("error.html")
    return HTMLResponse(content=template.render(kembali=kembali), status_code=500)


def sesi_milik(db: Session, session_id: int, student_id: int):
    # Sesi ujian hanya boleh dibuka oleh siswa pemiliknya
    return db.query(ExamSession).filter(ExamSession.id == session_id, ExamSession.student_id == student_id).first()


BATAS_REMEDIAL = 60      # nilai (persen) di bawah ini boleh mengajukan remedial
MAKS_PELANGGARAN = 3     # keluar dari layar ujian sebanyak ini: jawaban dikirim otomatis


def tingkat_siswa(db: Session, student_id: int):
    # Tingkat (VII/VIII/IX) dari rombel siswa di tahun ajaran aktif; None jika belum punya rombel
    q = (db.query(SchoolClass.class_name)
         .join(Rombel, Rombel.class_id == SchoolClass.id)
         .join(Enrollment, Enrollment.rombel_id == Rombel.id)
         .outerjoin(AcademicYear, AcademicYear.id == Enrollment.academic_year_id)
         .filter(Enrollment.student_id == student_id)
         .order_by(AcademicYear.is_active.desc(), Enrollment.id.desc()))
    baris = q.first()
    return baris[0] if baris else None


def persen_nilai(db: Session, sesi, exam):
    total = total_poin_sesi(db, sesi, exam)      # soal tiap siswa bisa berbeda
    if sesi.score is None or not total:
        return 0
    return round(sesi.score * 100 / total)


def sudah_lewat(sesi, toleransi=timedelta(0)):
    return datetime.now(timezone.utc) > sesi.expires_at + toleransi


# --- DASHBOARD ---
@router.get("/dashboard", response_class=HTMLResponse)
async def student_dashboard(request: Request, db: Session = Depends(get_db), user=Depends(require_student)):
    try:
        student_id = int(user.get("sub"))
        student = db.query(Student).filter(Student.id == student_id).first()
        tingkat = tingkat_siswa(db, student_id)
        # Hanya ujian untuk tingkat siswa ini (siswa tanpa rombel belum melihat ujian apa pun)
        exams = (db.query(Exam).filter(Exam.is_published == True, Exam.class_target == tingkat).all()
                 if tingkat else [])
        # Sesi terakhir yang sudah selesai per ujian: tampil "Selesai", bukan tombol Mulai
        selesai = {}
        for sesi in (db.query(ExamSession).filter(ExamSession.student_id == student_id, ExamSession.status != "active")
                     .order_by(ExamSession.id)):
            selesai[sesi.exam_id] = sesi
        remedial = {r.exam_id: r.status for r in db.query(RemedialRequest).filter(
            RemedialRequest.student_id == student_id, RemedialRequest.status.in_(["pending", "approved"]))}
        template = templates_env.get_template("student/dashboard.html")
        html_content = template.render(request=request, exams=exams, student_id=student_id, selesai=selesai,
                                       remedial=remedial, tingkat=tingkat,
                                       student_name=student.name if student else "", user=user, active_page="home")
        return HTMLResponse(content=html_content)
    except Exception:
        return gagal("Dashboard siswa", "/login")

# --- MULAI UJIAN ---
@router.post("/exam/start")
async def start_exam(request: Request, db: Session = Depends(get_db), user=Depends(require_student)):
    try:
        form = await request.form()
        exam_id = int(form.get("exam_id"))
        student_id = int(user.get("sub"))

        exam = db.query(Exam).filter(Exam.id == exam_id, Exam.is_published == True).first()
        if not exam or exam.class_target != tingkat_siswa(db, student_id):   # belum terbit / bukan tingkatnya
            return RedirectResponse(url="/student/dashboard", status_code=303)

        # Satu siswa satu kali mengerjakan: kalau sudah selesai/habis waktu, tampilkan hasilnya
        sesi_lama = db.query(ExamSession).filter(
            ExamSession.student_id == student_id,
            ExamSession.exam_id == exam_id,
        ).order_by(ExamSession.id.desc()).first()
        if sesi_lama:
            if sesi_lama.status == "active" and not sudah_lewat(sesi_lama, TOLERANSI_KIRIM):
                return RedirectResponse(url=f"/student/exam/take/{sesi_lama.id}", status_code=303)
            if sesi_lama.status == "active":
                sesi_lama.status = "expired"
                db.commit()
            # Sudah pernah mengerjakan: hanya boleh lagi bila remedial disetujui guru (dipakai sekali)
            izin = db.query(RemedialRequest).filter(RemedialRequest.student_id == student_id,
                                                    RemedialRequest.exam_id == exam_id,
                                                    RemedialRequest.status == "approved").first()
            if not izin:
                return RedirectResponse(url=f"/student/exam/result/{sesi_lama.id}", status_code=303)
            izin.status = "used"

        now = datetime.now(timezone.utc)
        # Soal untuk siswa ini: diambil acak dari bank bila guru membatasi jumlahnya,
        # lalu urutannya dikunci di sesi supaya tetap sama walau halaman dimuat ulang
        semua_id = [q.id for q in db.query(Question.id).filter(Question.bank_id == exam.bank_id).order_by(Question.id)]
        if exam.question_count and exam.question_count < len(semua_id):
            dipilih = random.sample(semua_id, exam.question_count)
            if not exam.randomize_questions:
                dipilih.sort()
        else:
            dipilih = semua_id[:]
            if exam.randomize_questions:
                random.shuffle(dipilih)
        new_session = ExamSession(
            student_id=student_id,
            exam_id=exam_id,
            started_at=now,
            expires_at=now + timedelta(minutes=exam.duration_minutes),
            status="active",
            question_ids=",".join(map(str, dipilih)),
        )
        db.add(new_session)
        db.flush()
        db.add(ExamEvent(session_id=new_session.id, kind="mulai", detail=f"{len(dipilih)} soal"))
        db.commit()
        db.refresh(new_session)
        return RedirectResponse(url=f"/student/exam/take/{new_session.id}", status_code=303)
    except Exception:
        db.rollback()
        return gagal("Mulai ujian")

# --- HALAMAN UJIAN ---
@router.get("/exam/take/{session_id}", response_class=HTMLResponse)
async def take_exam(session_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_student)):
    try:
        session = sesi_milik(db, session_id, int(user.get("sub")))
        if not session:
            return RedirectResponse(url="/student/dashboard", status_code=303)
        if session.status != "active":
            return RedirectResponse(url=f"/student/exam/result/{session.id}", status_code=303)
        if sudah_lewat(session):
            session.status = "expired"
            db.commit()
            return RedirectResponse(url=f"/student/exam/result/{session.id}", status_code=303)

        exam = db.query(Exam).filter(Exam.id == session.exam_id).first()
        ids = id_soal_sesi(db, session, exam)
        per_id = {q.id: q for q in db.query(Question).filter(Question.id.in_(ids))} if ids else {}
        # Jawaban terakhir yang tercatat di log: dipulihkan bila halaman dimuat ulang
        pilihan, esai = {}, {}
        for e in db.query(ExamEvent).filter(ExamEvent.session_id == session.id,
                                            ExamEvent.kind.in_(["pilih", "esai"])).order_by(ExamEvent.id):
            if e.kind == "pilih":
                pilihan[e.question_id] = e.option_id
            else:
                esai[e.question_id] = e.detail or ""
        exam_data = []
        for qid in ids:
            q = per_id.get(qid)
            if not q:
                continue
            options = db.query(QuestionOption).filter(QuestionOption.question_id == q.id).all()
            if exam.randomize_options:
                # urutan opsi tetap per siswa (acak tapi stabil saat dimuat ulang)
                random.Random(f"{session.id}-{q.id}").shuffle(options)
            exam_data.append({"question": q, "options": options,
                              "terpilih": pilihan.get(q.id), "teks": esai.get(q.id, "")})
        template = templates_env.get_template("student/take_exam.html")
        html_content = template.render(
            request=request, exam=exam, exam_data=exam_data, session=session,
            expires_at=session.expires_at.isoformat(),
            student_name=db.query(Student.name).filter(Student.id == session.student_id).scalar() or "",
            sekarang=datetime.now().strftime("%d/%m/%Y %H:%M"), maks_pelanggaran=MAKS_PELANGGARAN
        )
        return HTMLResponse(content=html_content)
    except Exception:
        return gagal("Halaman ujian")

# --- SUBMIT UJIAN ---
@router.post("/exam/submit/{session_id}")
async def submit_exam(session_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_student)):
    try:
        student_id = int(user.get("sub"))
        session = sesi_milik(db, session_id, student_id)
        if not session:
            return RedirectResponse(url="/student/dashboard", status_code=303)
        if session.status != "active":          # sudah dikirim / sudah habis: tidak bisa dikirim ulang
            return RedirectResponse(url=f"/student/exam/result/{session.id}", status_code=303)
        if sudah_lewat(session, TOLERANSI_KIRIM):
            session.status = "expired"
            db.commit()
            return RedirectResponse(url=f"/student/exam/result/{session.id}", status_code=303)

        exam = db.query(Exam).filter(Exam.id == session.exam_id).first()
        session.submitted_at = datetime.now(timezone.utc)
        session.status = "completed"

        # Hanya soal yang didapat siswa di sesi ini, dan opsi harus milik soal tersebut (skor dihitung server)
        ids = id_soal_sesi(db, session, exam)
        soal = {q.id: q for q in db.query(Question).filter(Question.id.in_(ids))} if ids else {}
        opsi = {o.id: o for o in db.query(QuestionOption).filter(QuestionOption.question_id.in_(list(soal)))}

        form = await request.form()
        total_score = 0.0
        total_wrong = len(soal)

        # Esai: dinilai otomatis dari kemiripan dengan kunci guru (guru bisa mengoreksi)
        for key, teks in form.items():
            if not key.startswith("essay_") or not key[6:].isdigit():
                continue
            question = soal.get(int(key[6:]))
            if not question or question.question_type != "esai":
                continue
            teks = (teks or "").strip()[:5000]
            hasil = nilai_esai(teks, question.answer_key, question.keywords)
            poin = round((question.points or 0) * hasil["persen"], 1)
            total_score += poin
            if hasil["persen"] >= 1:
                total_wrong -= 1
            db.add(ExamAnswer(session_id=session.id, question_id=question.id, answer_text=teks,
                              similarity=hasil["kemiripan"], auto_points=poin, is_correct=hasil["persen"] >= 1))

        for key, selected_option_id in form.items():
            if not key.startswith("question_"):
                continue
            try:
                q_id = int(key.replace("question_", ""))
                opt_id = int(selected_option_id)
            except ValueError:
                continue
            question = soal.get(q_id)
            option = opsi.get(opt_id)
            if not question or question.question_type == "esai" or not option or option.question_id != q_id:
                continue
            if option.is_correct:
                total_score += question.points
                total_wrong -= 1
            db.add(ExamAnswer(session_id=session.id, question_id=q_id,
                              selected_option_id=opt_id, is_correct=option.is_correct))
        total_score = int(round(total_score))
        session.score = total_score
        db.add(ExamEvent(session_id=session.id, kind="kirim", detail="otomatis" if form.get("otomatis") else None))
        db.commit()

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
    except Exception:
        db.rollback()
        return gagal("Kirim jawaban")

# --- HASIL UJIAN ---
@router.get("/exam/result/{session_id}", response_class=HTMLResponse)
async def exam_result(session_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_student)):
    try:
        student_id = int(user.get("sub"))
        session = sesi_milik(db, session_id, student_id)
        if not session:
            return RedirectResponse(url="/student/dashboard", status_code=303)
        exam = db.query(Exam).filter(Exam.id == session.exam_id).first()
        answers = db.query(ExamAnswer).filter(ExamAnswer.session_id == session_id).all()
        terakhir = (db.query(ExamSession.id).filter(ExamSession.student_id == student_id, ExamSession.exam_id == exam.id)
                    .order_by(ExamSession.id.desc()).first()[0] == session.id)
        permintaan = (db.query(RemedialRequest).filter(RemedialRequest.student_id == student_id,
                                                       RemedialRequest.exam_id == exam.id)
                      .order_by(RemedialRequest.id.desc()).first())
        persen = persen_nilai(db, session, exam)
        boleh_ajukan = (terakhir and session.status != "active" and persen < BATAS_REMEDIAL
                        and not (permintaan and permintaan.status in ("pending", "approved")))
        template = templates_env.get_template("student/exam_result.html")
        html_content = template.render(request=request, session=session, answers=answers, exam=exam, persen=persen,
                                       batas=BATAS_REMEDIAL, terakhir=terakhir, permintaan=permintaan,
                                       boleh_ajukan=boleh_ajukan)
        return HTMLResponse(content=html_content)
    except Exception:
        return gagal("Hasil ujian")

# --- REMEDIAL: siswa mengajukan, guru yang memutuskan ---
@router.post("/exam/remedial/{session_id}")
async def request_remedial(session_id: int, db: Session = Depends(get_db), user=Depends(require_student)):
    student_id = int(user.get("sub"))
    session = sesi_milik(db, session_id, student_id)
    if not session or session.status == "active":
        return RedirectResponse(url="/student/dashboard", status_code=303)
    exam = db.query(Exam).filter(Exam.id == session.exam_id).first()
    terakhir = (db.query(ExamSession.id).filter(ExamSession.student_id == student_id, ExamSession.exam_id == exam.id)
                .order_by(ExamSession.id.desc()).first()[0])
    masih_ada = db.query(RemedialRequest).filter(RemedialRequest.student_id == student_id, RemedialRequest.exam_id == exam.id,
                                                 RemedialRequest.status.in_(["pending", "approved"])).first()
    if terakhir == session.id and not masih_ada and persen_nilai(db, session, exam) < BATAS_REMEDIAL:
        db.add(RemedialRequest(student_id=student_id, exam_id=exam.id, session_id=session.id, status="pending"))
        db.commit()
    return RedirectResponse(url=f"/student/exam/result/{session.id}", status_code=303)

# --- LOG AKTIVITAS: soal dilihat, jawaban dipilih/diganti, esai diketik ---
MAKS_KEJADIAN_SESI = 3000

@router.post("/exam/events/{session_id}")
async def log_events(session_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_student)):
    session = sesi_milik(db, session_id, int(user.get("sub")))
    if not session or session.status != "active":
        return JSONResponse({"ok": False})
    try:
        data = json.loads((await request.body())[:200_000] or b"[]")
    except ValueError:
        return JSONResponse({"ok": False})
    if not isinstance(data, list):
        return JSONResponse({"ok": False})
    exam = db.query(Exam).filter(Exam.id == session.exam_id).first()
    ids = set(id_soal_sesi(db, session, exam))
    opsi_soal = {o.id: o.question_id for o in db.query(QuestionOption).filter(QuestionOption.question_id.in_(list(ids)))}
    sisa = MAKS_KEJADIAN_SESI - db.query(func.count(ExamEvent.id)).filter(ExamEvent.session_id == session.id).scalar()
    simpan = 0
    for item in data[:100]:
        if simpan >= sisa or not isinstance(item, dict):
            break
        jenis, qid, oid = item.get("k"), item.get("q"), item.get("o")
        if jenis not in ("lihat", "pilih", "esai") or not isinstance(qid, int) or qid not in ids:
            continue
        if jenis == "pilih" and (not isinstance(oid, int) or opsi_soal.get(oid) != qid):
            continue
        detail = str(item.get("d") or "")[:5000] if jenis == "esai" else None
        db.add(ExamEvent(session_id=session.id, kind=jenis, question_id=qid,
                         option_id=oid if jenis == "pilih" else None, detail=detail))
        simpan += 1
    db.commit()
    return JSONResponse({"ok": True, "saved": simpan})

# --- ANTI-CHEAT: catat pelanggaran selama ujian ---
JENIS_PELANGGARAN = {"pindah_tab", "keluar_layar_penuh", "salin", "tempel", "klik_kanan", "screenshot", "cetak", "devtools"}

@router.post("/exam/violation/{session_id}")
async def log_violation(session_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_student)):
    session = sesi_milik(db, session_id, int(user.get("sub")))
    if not session or session.status != "active":
        return JSONResponse({"count": 0, "limit": MAKS_PELANGGARAN, "active": False})
    form = await request.form()
    jenis = form.get("kind") if form.get("kind") in JENIS_PELANGGARAN else "lainnya"
    db.add(ExamViolation(session_id=session.id, kind=jenis))
    db.commit()
    # Hanya pindah tab / keluar layar penuh yang dihitung menuju kirim otomatis
    hitung = db.query(func.count(ExamViolation.id)).filter(
        ExamViolation.session_id == session.id, ExamViolation.kind.in_(["pindah_tab", "keluar_layar_penuh"])).scalar()
    return JSONResponse({"count": hitung, "limit": MAKS_PELANGGARAN, "active": True})

# --- KISI-KISI MATERI ---
def materi_terbuka(db: Session, tingkat):
    sekarang = datetime.now(timezone.utc)
    if not tingkat:
        return []
    return (db.query(Material).filter(Material.is_published == True, Material.class_target == tingkat,
                                      (Material.close_at == None) | (Material.close_at > sekarang))
            .order_by(Material.created_at.desc()).all())

@router.get("/materials", response_class=HTMLResponse)
async def materials_page(request: Request, db: Session = Depends(get_db), user=Depends(require_student)):
    try:
        materi = materi_terbuka(db, tingkat_siswa(db, int(user.get("sub"))))
        template = templates_env.get_template("student/materials.html")
        return HTMLResponse(content=template.render(request=request, materials=materi, active_page="materials"))
    except Exception:
        return gagal("Kisi-kisi")

@router.get("/materials/{material_id}", response_class=HTMLResponse)
async def material_read(material_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_student)):
    try:
        student_id = int(user.get("sub"))
        materi = next((m for m in materi_terbuka(db, tingkat_siswa(db, student_id)) if m.id == material_id), None)
        if not materi:   # tertutup, kedaluwarsa, atau bukan untuk tingkatnya
            return RedirectResponse(url="/student/materials", status_code=303)
        student = db.query(Student).filter(Student.id == student_id).first()
        template = templates_env.get_template("student/material_read.html")
        return HTMLResponse(content=template.render(request=request, m=materi, student_name=student.name,
                                                    sekarang=datetime.now().strftime("%d/%m/%Y %H:%M"),
                                                    active_page="materials"))
    except Exception:
        return gagal("Baca kisi-kisi", "/student/materials")

# --- LEADERBOARD ---
@router.get("/leaderboard", response_class=HTMLResponse)
async def leaderboard_page(request: Request, db: Session = Depends(get_db), user=Depends(require_student)):
    try:
        student_id = int(user.get("sub"))
        kelas = tingkat_siswa(db, student_id)
        template = templates_env.get_template("student/leaderboard.html")
        if not kelas:
            return HTMLResponse(content=template.render(request=request, user=user, rombel_name="–", class_name="–",
                                                        rombel_scores=[], angkatan_scores=[], active_page="leaderboard"))
        # Sumber nilai sama persis dengan rekap guru (nilai akhir tahun ajaran aktif)
        rekap = rekap_kelas(db, kelas)
        milik = next((r for r in rekap["baris"] if r["siswa"].id == student_id), None)
        angkatan = sorted(({"name": r["siswa"].name, "score": r["akhir"] or 0, "rombel_id": r["rombel_id"]}
                           for r in rekap["baris"]), key=lambda x: (-x["score"], x["name"].lower()))
        rombel_id = milik["rombel_id"] if milik else None
        html_content = template.render(
            request=request, user=user, rombel_name=milik["rombel"] if milik else "–", class_name=kelas,
            rombel_scores=[a for a in angkatan if a["rombel_id"] == rombel_id],
            angkatan_scores=angkatan, active_page="leaderboard"
        )
        return HTMLResponse(content=html_content)
    except Exception as e:
        return gagal("Peringkat")

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
        return gagal("Lencana")