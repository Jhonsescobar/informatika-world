# app/routers/teacher/ujian.py
# Ujian: daftar, buat, terbit, KKM, acak soal, hapus.

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.exam import Exam, ExamAnswer, ExamEvent, ExamSession, ExamViolation, RemedialRequest
from app.models.grade import ScoreComponent
from app.models.question import Question, QuestionBank
from app.routers.teacher.umum import baca_kkm, kelas_aktif, templates_env, TINGKAT
from app.services import audit
from app.services import watermark as wm
from app.services import nilai_remedial as nr
from app.services.rekap import tahun_aktif
from app.utils.deps import require_teacher

router = APIRouter(tags=["Teacher"])


@router.get("/exams", response_class=HTMLResponse)
# Halaman daftar ujian/formatif
async def list_exams(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    
    kelas = kelas_aktif(request)
    exams = db.query(Exam).filter(Exam.class_target == kelas).order_by(Exam.created_at.desc(), Exam.id.desc()).all()
    # Mengambil semua ujian
    
    banks = db.query(QuestionBank).filter(QuestionBank.class_target == kelas).all()
    # Bank soal kelas aktif (untuk form pilihan)
    
    template = templates_env.get_template("teacher/exams.html")
    remedial_pending = dict(db.query(RemedialRequest.exam_id, func.count(RemedialRequest.id))
                            .filter(RemedialRequest.status == "pending").group_by(RemedialRequest.exam_id).all())
    komponen = db.query(ScoreComponent).filter(ScoreComponent.class_target == kelas).order_by(ScoreComponent.id).all()
    html_content = template.render(request=request, exams=exams, banks=banks, komponen=komponen,
                                   nama_komponen={k.id: k for k in komponen}, remedial_pending=remedial_pending,
                                   error=request.query_params.get("error"), pesan=request.query_params.get("pesan"),
                                   watermark_pilihan=wm.TINGKAT, aturan_remedial=nr.ATURAN, user=user)
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
    try:
        kkm_ujian_isi = baca_kkm(form.get("kkm"))
    except ValueError:
        return RedirectResponse(url="/teacher/exams?error=kkm", status_code=303)
    tahun = tahun_aktif(db)
    new_exam = Exam(
        title=judul,
        bank_id=bank_id,
        class_target=kelas,
        duration_minutes=durasi,
        kkm=kkm_ujian_isi,
        randomize_questions=form.get("randomize_questions") == "on",
        randomize_options=form.get("randomize_options") == "on",
        watermark_persen=wm.persen_sah(form.get("watermark_persen"), wm.BAWAAN),
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


@router.post("/exams/{exam_id}/kkm")
# KKM ujian: hanya penanda tuntas, tidak mengubah nilai akhir
async def set_kkm_ujian(exam_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    form = await request.form()
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        return RedirectResponse(url="/teacher/exams", status_code=303)
    lama = exam.kkm
    try:
        exam.kkm = baca_kkm(form.get("kkm"))
    except ValueError:
        return RedirectResponse(url="/teacher/exams?error=kkm", status_code=303)
    if exam.kkm != lama:
        audit.catat(db, user, "Nilai", "Ubah KKM ujian", exam.title, f"{lama if lama is not None else 'ikut default'} → {exam.kkm if exam.kkm is not None else 'ikut default'}")
    db.commit()
    return RedirectResponse(url="/teacher/exams?pesan=kkm", status_code=303)


@router.post("/exams/{exam_id}/acak")
# Menyalakan / mematikan pengacakan soal atau opsi pada ujian yang sudah dibuat
async def toggle_acak(exam_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    form = await request.form()
    jenis = form.get("jenis")
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam or jenis not in ("soal", "opsi"):
        return RedirectResponse(url="/teacher/exams", status_code=303)
    if jenis == "opsi":
        # urutan opsi dihitung saat halaman dibuka: bila diubah ketika ada siswa sedang mengerjakan,
        # huruf A-D di layar mereka bisa berpindah di tengah ujian. Tolak dulu.
        aktif = db.query(ExamSession).filter(ExamSession.exam_id == exam.id, ExamSession.status == "active").count()
        if aktif:
            return RedirectResponse(url="/teacher/exams?error=opsi_aktif", status_code=303)
        exam.randomize_options = not exam.randomize_options
    else:
        # urutan soal disimpan di sesi saat siswa mulai: sesi yang sudah berjalan tidak berubah
        exam.randomize_questions = not exam.randomize_questions
    db.commit()
    return RedirectResponse(url="/teacher/exams", status_code=303)


@router.post("/exams/{exam_id}/watermark")
# Mengubah kekuatan watermark nama + jam di layar siswa. Hanya tampilan: sesi berjalan memakainya saat halaman dimuat ulang
async def set_watermark(exam_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    form = await request.form()
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    persen = wm.persen_sah(form.get("persen"))
    if not exam or persen is None:
        return RedirectResponse(url="/teacher/exams", status_code=303)
    if persen != exam.watermark_persen:
        audit.catat(db, user, "Ujian", "Ubah watermark", exam.title,
                    f"{wm.TINGKAT.get(exam.watermark_persen, exam.watermark_persen)} ke {wm.TINGKAT[persen]}")
        exam.watermark_persen = persen
        db.commit()
    return RedirectResponse(url="/teacher/exams", status_code=303)


@router.post("/exams/{exam_id}/remedial-pengaturan")
# Soal remedial (sama atau bank lain) dan aturan saran nilai akhir. Nilai awal tetap paling atas di rekap
async def set_remedial(exam_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    form = await request.form()
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        return RedirectResponse(url="/teacher/exams", status_code=303)
    aturan = nr.aturan_sah(form.get("aturan"))
    bank = None
    teks_bank = (form.get("bank") or "").strip()
    if aturan is None or (teks_bank and not teks_bank.isdigit()):
        return RedirectResponse(url="/teacher/exams?error=remedial", status_code=303)
    if teks_bank:
        bank = db.query(QuestionBank).filter(QuestionBank.id == int(teks_bank)).first()
        isi = bank and db.query(Question.id).filter(Question.bank_id == bank.id).first()
        if not bank or bank.class_target != exam.class_target or bank.id == exam.bank_id or not isi:
            return RedirectResponse(url="/teacher/exams?error=remedial", status_code=303)
    baru_bank = bank.id if bank else None
    if baru_bank != exam.remedial_bank_id and exam.remedial_bank_id and db.query(RemedialRequest.id).filter(
            RemedialRequest.exam_id == exam.id, RemedialRequest.status == "used").first():
        return RedirectResponse(url="/teacher/exams?error=remedial_terkunci", status_code=303)
    lama = (exam.remedial_bank_id, exam.remedial_aturan)
    if lama != (baru_bank, aturan):
        audit.catat(db, user, "Ujian", "Ubah pengaturan remedial", exam.title,
                    f"soal: {bank.title if bank else 'sama dengan ujian'}; nilai: {nr.ATURAN[aturan]}")
        exam.remedial_bank_id, exam.remedial_aturan = baru_bank, aturan
        db.commit()
    return RedirectResponse(url="/teacher/exams?pesan=remedial", status_code=303)


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
        audit.catat(db, user, "Ujian", "Hapus ujian", exam.title, f"{len(session_ids)} sesi pengerjaan ikut terhapus")
        db.delete(exam)
        db.commit()
    return RedirectResponse(url="/teacher/exams", status_code=303)
