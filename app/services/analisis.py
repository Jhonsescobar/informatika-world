# app/services/analisis.py
# Analisis butir soal: setiap soal ditimbang dari jawaban siswa SEBENARNYA di ujian itu saja.
#
#   tingkat kesukaran (p) = rata-rata skor soal (benar = 1, salah/kosong = 0; esai = poin/poin soal)
#   daya pembeda      (D) = p kelompok atas (27% nilai tertinggi) dikurangi p kelompok bawah (27% terendah)
#   pengecoh              = berapa siswa memilih tiap opsi; opsi salah yang lebih laris dari kunci = "menjebak"
#
# Yang dihitung hanya satu sesi terbaik tiap siswa, supaya remedial tidak membuat siswa dihitung dua kali.

from collections import Counter, defaultdict
from sqlalchemy.orm import Session

from app.models.exam import ExamAnswer, ExamSession
from app.models.question import Question, QuestionOption
from app.services.penilaian import id_soal_sesi, poin_jawaban, total_poin_sesi

MIN_SISWA = 5          # di bawah ini angka terlalu goyah untuk dinilai
MIN_PEMBEDA = 6        # kelompok atas/bawah baru bermakna dari jumlah ini
BAGIAN_KELOMPOK = 0.27
BATAS_SULIT = 0.30
BATAS_MUDAH = 0.90
BATAS_PEMBEDA_BAIK = 0.20
BATAS_KUNCI_SALAH = -0.10      # D sekecil ini: siswa pandai justru banyak salah, kunci patut dicek
BATAS_MENJEBAK = 0.40          # satu opsi salah dipilih sekian bagian siswa dan lebih laris dari kunci

# kunci -> (nama tampil, nada warna, saran untuk guru); urutan = prioritas tampil
LABEL = {
    "periksa": ("Periksa kunci", "danger", "Siswa yang pandai justru banyak salah di sini. Cek kunci jawaban dan kalimat soalnya."),
    "menjebak": ("Menjebak", "amber", "Satu pilihan salah lebih laris dari kunci. Bahas ulang konsepnya, atau perjelas soalnya."),
    "sulit": ("Terlalu sulit", "danger", "Kurang dari 30% siswa menjawab benar. Bahas ulang materinya di kelas."),
    "mudah": ("Terlalu mudah", "muted", "Hampir semua siswa benar. Boleh diganti dengan soal yang lebih menantang."),
    "lemah": ("Pembeda lemah", "muted", "Siswa pandai dan kurang pandai sama-sama benar atau salah. Soal kurang membedakan."),
    "baik": ("Baik", "teal", "Tingkat kesukaran wajar dan membedakan siswa dengan baik."),
    "kurang": ("Data kurang", "muted", "Belum cukup siswa untuk menilai soal ini."),
}
URUTAN_LABEL = list(LABEL)


def sesi_terbaik(db: Session, exam_id: int) -> list[ExamSession]:
    """Satu sesi selesai per siswa: percobaan PERTAMA (nilai awal). Sesi remedial tidak dihitung karena bisa
    memakai bank soal lain dan hasil ulangan bukan gambaran soal ujian ini."""
    pertama: dict[int, ExamSession] = {}
    for s in (db.query(ExamSession).filter(ExamSession.exam_id == exam_id, ExamSession.status != "active",
                                           ExamSession.score != None).order_by(ExamSession.id)):
        pertama.setdefault(s.student_id, s)
    return list(pertama.values())


def tentukan_label(n: int, p: float, d, dominan: float, jebakan: bool) -> str:
    """Satu label per soal, memakai urutan prioritas di LABEL."""
    if n < MIN_SISWA:
        return "kurang"
    if d is not None and d <= BATAS_KUNCI_SALAH:
        return "periksa"
    if jebakan and dominan >= BATAS_MENJEBAK:
        return "menjebak"
    if p <= BATAS_SULIT:
        return "sulit"
    if p >= BATAS_MUDAH:
        return "mudah"
    if d is not None and d < BATAS_PEMBEDA_BAIK:
        return "lemah"
    return "baik"


def _rata(nilai: list[float]):
    return sum(nilai) / len(nilai) if nilai else None


def analisis_butir(db: Session, exam) -> dict | None:
    """None bila belum ada sesi selesai. Selain itu: ringkasan ujian + daftar butir (soal) beserta labelnya."""
    sesi = sesi_terbaik(db, exam.id)
    if not sesi:
        return None
    soal = {q.id: q for q in db.query(Question).filter(Question.bank_id == exam.bank_id).order_by(Question.id)}
    nomor = {qid: i for i, qid in enumerate(soal, 1)}
    opsi = defaultdict(list)
    for o in db.query(QuestionOption).filter(QuestionOption.question_id.in_(list(soal))).order_by(QuestionOption.id):
        opsi[o.question_id].append(o)
    jawaban = {(a.session_id, a.question_id): a
               for a in db.query(ExamAnswer).filter(ExamAnswer.session_id.in_([s.id for s in sesi]))}

    persen_sesi, diberi, skor = {}, defaultdict(list), {}      # skor[(sid, qid)] -> 0..1
    for s in sesi:
        maks = total_poin_sesi(db, s, exam)
        persen_sesi[s.id] = s.score * 100 / maks if maks else 0.0
        for qid in id_soal_sesi(db, s, exam):
            q = soal.get(qid)
            if q is None:
                continue
            diberi[qid].append(s.id)
            a = jawaban.get((s.id, qid))
            skor[(s.id, qid)] = min(1.0, poin_jawaban(a, q) / q.points) if (a and q.points) else 0.0

    # kelompok atas dan bawah menurut nilai total
    urut = sorted(sesi, key=lambda s: persen_sesi[s.id], reverse=True)
    k = max(1, round(len(urut) * BAGIAN_KELOMPOK))
    atas = {s.id for s in urut[:k]}
    bawah = {s.id for s in urut[-k:]}
    kelompok_ok = len(urut) >= MIN_PEMBEDA

    butir = []
    for qid, q in soal.items():
        ikut = diberi.get(qid, [])
        n = len(ikut)
        if not n:
            continue
        p = sum(skor[(sid, qid)] for sid in ikut) / n
        d = None
        if kelompok_ok and q.question_type != "esai":
            pa = _rata([skor[(sid, qid)] for sid in ikut if sid in atas])
            pb = _rata([skor[(sid, qid)] for sid in ikut if sid in bawah])
            d = round(pa - pb, 2) if pa is not None and pb is not None else None
        pilihan, dominan, jebakan = [], 0.0, False
        if q.question_type != "esai":
            dipilih = Counter(jawaban[(sid, qid)].selected_option_id for sid in ikut
                              if (sid, qid) in jawaban and jawaban[(sid, qid)].selected_option_id)
            for o in opsi[qid]:
                pilihan.append({"teks": o.text, "benar": bool(o.is_correct), "jumlah": dipilih.get(o.id, 0),
                                "persen": round(dipilih.get(o.id, 0) * 100 / n)})
            kosong = n - sum(dipilih.values())
            salah_terlaris = max((x for x in pilihan if not x["benar"]), key=lambda x: x["jumlah"], default=None)
            benar_jumlah = sum(x["jumlah"] for x in pilihan if x["benar"])
            if salah_terlaris and salah_terlaris["jumlah"] > benar_jumlah:
                jebakan, dominan = True, salah_terlaris["jumlah"] / n
                salah_terlaris["jebakan"] = True
        else:
            kosong = 0
        kunci = tentukan_label(n, p, d, dominan, jebakan)
        nama, nada, saran = LABEL[kunci]
        butir.append({"no": nomor[qid], "soal": q, "esai": q.question_type == "esai", "n": n, "p": round(p * 100),
                      "d": d, "opsi": pilihan, "kosong": kosong, "label": kunci, "nama": nama, "nada": nada,
                      "saran": saran})

    ringkas = Counter(b["label"] for b in butir)
    butir.sort(key=lambda b: (URUTAN_LABEL.index(b["label"]), b["no"]))
    persen = list(persen_sesi.values())
    return {"siswa": len(sesi), "rata": round(sum(persen) / len(persen), 1), "tertinggi": round(max(persen), 1),
            "terendah": round(min(persen), 1), "butir": butir, "ringkas": ringkas, "label": LABEL,
            "urutan_label": URUTAN_LABEL, "pembeda_dihitung": kelompok_ok}
