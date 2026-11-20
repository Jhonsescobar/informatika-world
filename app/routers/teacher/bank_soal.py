# app/routers/teacher/bank_soal.py
# Bank soal dan soal: buat bank, impor soal, ubah poin, hapus.

import json
import re

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.exam import Exam, ExamAnswer, ExamEvent, ExamSession, ExamViolation, RemedialRequest
from app.models.question import Question, QuestionBank, QuestionOption
from app.routers.teacher.umum import kelas_aktif, templates_env
from app.services import audit
from app.services.impor_soal import CONTOH, gabung_kode, periksa, PROMPT, prompt_ai
from app.utils.deps import require_teacher

router = APIRouter(tags=["Teacher"])


@router.get("/question-banks", response_class=HTMLResponse)
# Halaman daftar bank soal
async def list_banks(request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    
    banks = db.query(QuestionBank).filter(QuestionBank.class_target == kelas_aktif(request)).order_by(QuestionBank.created_at.desc()).all()
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


def _angka(teks) -> int:
    # nilai dari alamat (?n=...) ditampilkan di halaman dengan autoescape mati: hanya angka yang boleh lewat
    try:
        return max(0, int(teks or 0))
    except ValueError:
        return 0


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
        mode=mode or p.get("mode", "manual"), pesan=p.get("pesan"), n=_angka(p.get("n")), lewat=_angka(p.get("lewat")),
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
        item["kembar"] = _kunci_teks(gabung_kode(item["pertanyaan"], item["kode"], item.get("bahasa", "python"))) in ada
    if form.get("aksi") != "simpan" or hasil["galat"]:
        return halaman_bank(request, db, user, bank_id, impor=hasil, teks_impor=teks, mode="impor")

    disimpan = lewat = 0
    for item in hasil["soal"]:
        teks_soal = gabung_kode(item["pertanyaan"], item["kode"], item.get("bahasa", "python"))
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


@router.post("/question-banks/{bank_id}/points")
async def poin_massal(bank_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    """Memberi poin yang sama untuk banyak soal sekaligus: semua soal, semua PG, atau semua esai di bank ini."""
    form = await request.form()
    if not db.query(QuestionBank).filter(QuestionBank.id == bank_id).first():
        return RedirectResponse(url="/teacher/question-banks", status_code=303)
    if bank_terkunci(db, bank_id):
        return RedirectResponse(url=f"/teacher/question-banks/{bank_id}?pesan=poin_terkunci", status_code=303)
    try:
        poin = int(form.get("points") or "")
    except ValueError:
        poin = 0
    sasaran = form.get("sasaran")
    if not 1 <= poin <= 100 or sasaran not in ("semua", "pg", "esai"):
        return RedirectResponse(url=f"/teacher/question-banks/{bank_id}?pesan=poin_salah", status_code=303)
    q = db.query(Question).filter(Question.bank_id == bank_id)
    if sasaran == "esai":
        q = q.filter(Question.question_type == "esai")
    elif sasaran == "pg":
        # soal lama bisa tanpa tipe (NULL): dianggap pilihan ganda, sama seperti di halaman ujian
        q = q.filter((Question.question_type != "esai") | (Question.question_type.is_(None)))
    n = q.update({Question.points: poin}, synchronize_session=False)
    db.commit()
    return RedirectResponse(url=f"/teacher/question-banks/{bank_id}?pesan=poin_massal&n={n}", status_code=303)


@router.post("/questions/{question_id}/points")
async def ubah_poin(question_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_teacher)):
    form = await request.form()
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        return RedirectResponse(url="/teacher/question-banks", status_code=303)
    # bank yang sudah dipakai ujian: poin dikunci, karena nilai siswa yang sudah ada dihitung dari poin ini
    if bank_terkunci(db, q.bank_id):
        return RedirectResponse(url=f"/teacher/question-banks/{q.bank_id}?pesan=poin_terkunci", status_code=303)
    try:
        poin = int(form.get("points") or "")
    except ValueError:
        poin = 0
    if not 1 <= poin <= 100:
        return RedirectResponse(url=f"/teacher/question-banks/{q.bank_id}?pesan=poin_salah", status_code=303)
    q.points = poin
    db.commit()
    return RedirectResponse(url=f"/teacher/question-banks/{q.bank_id}?pesan=poin#soal-{q.id}", status_code=303)


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

    # Validasi di server juga (isian HTML bisa diakali): soal PG wajib punya minimal 2 opsi dan kuncinya
    # harus opsi yang terisi, kalau tidak poinnya tidak akan pernah bisa diraih siswa. Esai wajib punya kunci.
    opsi_isi = {h: (form.get(f"option_{h}") or "").strip()[:500] for h in "ABCD"}
    opsi_isi = {h: t for h, t in opsi_isi.items() if t}
    kunci_pg = form.get("correct_key")
    if jenis == "pg" and (len(opsi_isi) < 2 or kunci_pg not in opsi_isi):
        return RedirectResponse(url=f"/teacher/question-banks/{bank_id}?pesan=isian_pg", status_code=303)
    if jenis == "esai" and not (form.get("answer_key") or "").strip():
        return RedirectResponse(url=f"/teacher/question-banks/{bank_id}?pesan=isian_esai", status_code=303)

    new_question = Question(bank_id=bank_id, text=teks_soal, points=poin, question_type=jenis)
    if jenis == "esai":
        new_question.answer_key = (form.get("answer_key") or "").strip()
        new_question.keywords = (form.get("keywords") or "").strip() or None
    db.add(new_question)
    db.commit()
    db.refresh(new_question)

    if jenis == "pg":
        for key, option_text in opsi_isi.items():
            db.add(QuestionOption(question_id=new_question.id, text=option_text, is_correct=(key == kunci_pg)))
        db.commit()
    return RedirectResponse(url=f"/teacher/question-banks/{bank_id}", status_code=303)


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
        audit.catat(db, user, "Ujian", "Hapus bank soal", bank.title,
                    f"{len(question_ids)} soal, {len(exam_ids)} ujian ikut terhapus")
        db.delete(bank)
        db.commit()
        
    return RedirectResponse(url="/teacher/question-banks", status_code=303)
