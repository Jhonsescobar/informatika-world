# app/services/pantau.py
# Data pantau guru: siapa yang sedang mengerjakan ujian dan siapa yang online di aplikasi.
#
#   online       = sinyal terakhir siswa kurang dari BATAS_ONLINE yang lalu (siswa mengirim sinyal tiap SINYAL_DETIK)
#   sedang ujian = sesi ujian berstatus aktif dan belum melewati batas waktunya
#
# Hanya kelas yang dipilih guru (kelas aktif) yang ditampilkan. Keluaran berupa angka dan teks saja (aman untuk JSON).

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.exam import Exam, ExamAnswer, ExamEvent, ExamSession, ExamViolation
from app.models.student import Student
from app.services.penilaian import id_soal_sesi
from app.services.rekap import siswa_kelas, tahun_aktif

SINYAL_DETIK = 60            # interval kiriman dari halaman siswa
BATAS_ONLINE = timedelta(minutes=2)   # satu sinyal boleh terlewat; lewat dari ini dianggap offline
PANTAU_DETIK = 10            # interval pembaruan halaman guru


def _detik_lalu(waktu, sekarang):
    if waktu is None:
        return None
    if waktu.tzinfo is None:
        waktu = waktu.replace(tzinfo=timezone.utc)
    return max(0, int((sekarang - waktu).total_seconds()))


def pantau_data(db: Session, kelas: str, sekarang: datetime | None = None) -> dict:
    sekarang = sekarang or datetime.now(timezone.utc)
    murid = siswa_kelas(db, kelas, tahun_aktif(db))
    rombel_siswa = {s.id: (s, rombel) for s, rombel, _ in murid}
    if not rombel_siswa:
        return {"kelas": kelas, "ringkas": {"online": 0, "ujian": 0, "pelanggaran": 0}, "ujian": [], "online": [],
                "sinyal_detik": SINYAL_DETIK, "pantau_detik": PANTAU_DETIK}

    sesi_aktif = (db.query(ExamSession, Exam)
                  .join(Exam, Exam.id == ExamSession.exam_id)
                  .filter(ExamSession.student_id.in_(rombel_siswa), ExamSession.status == "active",
                          ExamSession.expires_at > sekarang, Exam.class_target == kelas)
                  .order_by(ExamSession.started_at).all())
    ids_sesi = [s.id for s, _ in sesi_aktif]
    terjawab = dict(db.query(ExamAnswer.session_id, func.count(ExamAnswer.id))
                    .filter(ExamAnswer.session_id.in_(ids_sesi), ExamAnswer.selected_option_id.isnot(None))
                    .group_by(ExamAnswer.session_id).all()) if ids_sesi else {}
    esai_terisi = dict(db.query(ExamAnswer.session_id, func.count(ExamAnswer.id))
                       .filter(ExamAnswer.session_id.in_(ids_sesi), ExamAnswer.answer_text.isnot(None),
                               ExamAnswer.answer_text != "")
                       .group_by(ExamAnswer.session_id).all()) if ids_sesi else {}
    pelanggaran = dict(db.query(ExamViolation.session_id, func.count(ExamViolation.id))
                       .filter(ExamViolation.session_id.in_(ids_sesi))
                       .group_by(ExamViolation.session_id).all()) if ids_sesi else {}
    aktivitas = dict(db.query(ExamEvent.session_id, func.max(ExamEvent.created_at))
                     .filter(ExamEvent.session_id.in_(ids_sesi))
                     .group_by(ExamEvent.session_id).all()) if ids_sesi else {}

    daftar_ujian = []
    for sesi, exam in sesi_aktif:
        s, rombel = rombel_siswa[sesi.student_id]
        total = len(id_soal_sesi(db, sesi, exam))
        terakhir = aktivitas.get(sesi.id) or sesi.started_at
        daftar_ujian.append({
            "nama": s.name, "rombel": rombel, "ujian": exam.title,
            "terjawab": terjawab.get(sesi.id, 0) + esai_terisi.get(sesi.id, 0), "total": total,
            "pelanggaran": pelanggaran.get(sesi.id, 0),
            "mulai": sesi.started_at.astimezone().strftime("%H:%M") if sesi.started_at else "",
            "aktif_lalu": _detik_lalu(terakhir, sekarang),
        })

    sedang_ujian = {sesi.student_id for sesi, _ in sesi_aktif}
    sinyal = dict(db.query(Student.id, Student.last_seen)
                  .filter(Student.id.in_(rombel_siswa), Student.last_seen.isnot(None)).all())
    daftar_online = []
    for sid, (s, rombel) in rombel_siswa.items():
        lalu = _detik_lalu(sinyal.get(sid), sekarang)
        if lalu is not None and lalu <= BATAS_ONLINE.total_seconds():
            daftar_online.append({"nama": s.name, "rombel": rombel, "lalu": lalu, "ujian": sid in sedang_ujian})
    daftar_online.sort(key=lambda x: (x["lalu"], x["nama"]))

    return {
        "kelas": kelas,
        "ringkas": {"online": len(daftar_online), "ujian": len(daftar_ujian),
                    "pelanggaran": sum(x["pelanggaran"] for x in daftar_ujian)},
        "ujian": sorted(daftar_ujian, key=lambda x: x["nama"]),
        "online": daftar_online,
        "sinyal_detik": SINYAL_DETIK,
        "pantau_detik": PANTAU_DETIK,
    }
