# app/routers/teacher/hasil.py
# Hasil ujian: daftar per rombel, detail sesi, nilai esai, hitung ulang, remedial.

from datetime import datetime, timezone

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.academic import Enrollment, Rombel
from app.models.exam import Exam, ExamAnswer, ExamEvent, ExamSession, ExamViolation, RemedialRequest
from app.models.grade import ScoreComponent
from app.models.question import Question, QuestionOption
from app.models.student import Student
from app.routers.teacher.umum import templates_env, unduh_xlsx, URUTAN
from app.services import audit
from app.services.esai import nilai_esai
from app.services.excel import _kunci_alami, buku_ujian
from app.services.kesempatan import henti_terakhir, info_henti
from app.services.penilaian import hitung_ulang_skor, id_soal_sesi, total_poin_sesi, tutup_sesi_lewat
from app.services.rekap import BATAS_REMEDIAL, kkm_akhir, kkm_ujian, tahun_aktif
from app.services.remedial import beri_remedial, daftar_remedial
from app.utils.deps import require_teacher

router = APIRouter(tags=["Teacher"])


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
    henti = henti_terakhir(db, [r["sesi"].id for r in rows])
    for r in rows:
        r["terakhir"] = terakhir[r["siswa"].id] is r
        r["remedial"] = remedial_aktif.get(r["siswa"].id)
        r["henti"] = info_henti(db, r["sesi"], henti) if r["terakhir"] else None    # data sesi yang boleh dibuka lagi
    # urutan: nilai tertinggi siswa dulu (default), atau nama A-Z / Z-A
    terbaik = {}
    for r in rows:
        terbaik[r["siswa"].id] = max(terbaik.get(r["siswa"].id, -1), r["persen"] if r["persen"] is not None else -1)
    urut = request.query_params.get("urut", "nilai")
    urut = urut if urut in URUTAN else "nilai"
    nama = lambda r: r["siswa"].name.lower()
    # status tuntas: nilai tertinggi siswa dibandingkan KKM ujian; ditandai di percobaan terakhir saja
    komp_ujian = {}
    if exam.component_id:
        k = db.query(ScoreComponent).filter(ScoreComponent.id == exam.component_id).first()
        if k:
            komp_ujian[k.id] = k
    kkm_uji = kkm_ujian(exam, komp_ujian, kkm_akhir(tahun))
    for r in rows:
        r["tuntas"] = r["terakhir"] and terbaik[r["siswa"].id] >= 0 and terbaik[r["siswa"].id] >= kkm_uji
    if urut == "az":
        rows.sort(key=lambda r: (nama(r), r["ke"]))
    elif urut == "za":
        rows.sort(key=lambda r: (nama(r), -r["ke"]), reverse=True)
    elif urut == "rendah":
        rows.sort(key=lambda r: (terbaik[r["siswa"].id], nama(r), r["ke"]))
    else:
        rows.sort(key=lambda r: (-terbaik[r["siswa"].id], nama(r), r["ke"]))
    if request.url.path.endswith("/export"):
        return unduh_xlsx(buku_ujian(exam, rows, kkm_uji), f"hasil_{exam.title}_{datetime.now():%Y%m%d}")
    permintaan = (db.query(RemedialRequest, Student).join(Student, Student.id == RemedialRequest.student_id)
                  .filter(RemedialRequest.exam_id == exam_id, RemedialRequest.status == "pending")
                  .order_by(RemedialRequest.created_at).all())
    # kelompok per rombel (urutan alami VIII.2 sebelum VIII.10); urutan baris di dalam kelompok mengikuti pilihan urut
    kelompok = {}
    for r in rows:
        kelompok.setdefault(r["rombel"] or "", []).append(r)
    grup = []
    for nama_r in sorted(kelompok, key=_kunci_alami):
        isi = kelompok[nama_r]
        siswa_ids = {r["siswa"].id for r in isi}
        nilai = [terbaik[i] for i in siswa_ids if terbaik[i] >= 0]
        grup.append({"nama": nama_r or "Tanpa rombel", "id": "rombel-" + (nama_r or "tanpa").replace(".", "-").replace(" ", "-"),
                     "baris": isi, "siswa": len(siswa_ids),
                     "rata": round(sum(nilai) / len(nilai)) if nilai else None,
                     "tuntas": sum(1 for v in nilai if v >= kkm_uji), "dinilai": len(nilai),
                     "pelanggaran": sum(r["pelanggaran"] for r in isi)})
    template = templates_env.get_template("teacher/exam_results.html")
    ada_esai = db.query(Question.id).filter(Question.bank_id.in_([b for b in (exam.bank_id, exam.remedial_bank_id) if b]),
                                            Question.question_type == "esai").first() is not None
    html_content = template.render(request=request, exam=exam, rows=rows, permintaan=permintaan, urut=urut, urutan=URUTAN,
                                   ada_esai=ada_esai, pesan=request.query_params.get("pesan"), n=request.query_params.get("n", "0"),
                                   batas=BATAS_REMEDIAL, total_poin=total_poin, kkm_uji=kkm_uji, user=user,
                                   remedial_daftar=daftar_remedial(db, exam), grup=grup)
    return HTMLResponse(content=html_content)


# --- DETAIL SESI: jawaban per soal, koreksi esai, log aktivitas ---
NAMA_KEJADIAN = {"mulai": "Mulai ujian", "lihat": "Melihat soal", "pilih": "Memilih jawaban", "esai": "Menulis esai",
                 "kirim": "Mengirim jawaban", "kunci": "Mengganti jawaban yang sudah terkunci", "pindah_tab": "Keluar dari halaman ujian", "keluar_layar_penuh": "Keluar layar penuh",
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
    sebelum = jawaban.manual_points
    try:
        jawaban.manual_points = None if teks == "" else max(0.0, min(float(soal.points or 0), float(teks)))
    except ValueError:
        pass
    if jawaban.manual_points != sebelum:
        nama = db.query(Student.name).filter(Student.id == sesi.student_id).scalar()
        judul = db.query(Exam.title).filter(Exam.id == sesi.exam_id).scalar()
        lama = "otomatis" if sebelum is None else f"{sebelum:g}"
        baru = "otomatis" if jawaban.manual_points is None else f"{jawaban.manual_points:g}"
        audit.catat(db, user, "Nilai", "Ubah poin esai", f"{nama} · {judul}", f"poin {lama} → {baru}")
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
        audit.catat(db, user, "Nilai", "Hitung ulang esai", exam.title, f"{berubah} poin berubah dari {len(sesi_ids)} sesi")
        db.commit()
    return RedirectResponse(url=f"/teacher/exams/{exam_id}/results?pesan=hitung&n={berubah}", status_code=303)


# --- REMEDIAL DARI GURU: memberi izin mengulang tanpa menunggu siswa mengajukan ---
@router.post("/exams/{exam_id}/sessions/{session_id}/remedial")
async def grant_remedial(exam_id: int, session_id: int, db: Session = Depends(get_db), user=Depends(require_teacher)):
    sesi = db.query(ExamSession).filter(ExamSession.id == session_id, ExamSession.exam_id == exam_id).first()
    if sesi and sesi.status != "active":
        beri_remedial(db, exam_id, sesi.student_id, sesi.id)
        nama = db.query(Student.name).filter(Student.id == sesi.student_id).scalar()
        judul = db.query(Exam.title).filter(Exam.id == exam_id).scalar()
        audit.catat(db, user, "Nilai", "Beri remedial", f"{nama} · {judul}")
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
        nama = db.query(Student.name).filter(Student.id == permintaan.student_id).scalar()
        judul = db.query(Exam.title).filter(Exam.id == permintaan.exam_id).scalar()
        audit.catat(db, user, "Nilai", "Setujui remedial" if keputusan == "approve" else "Tolak remedial", f"{nama} · {judul}")
        db.commit()
    return RedirectResponse(url=f"/teacher/exams/{permintaan.exam_id}/results", status_code=303)
