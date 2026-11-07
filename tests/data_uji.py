# tests/data_uji.py
# Data contoh kecil untuk uji otomatis. Semua akun di sini HANYA ada di database uji.

from app.models.academic import AcademicYear, Enrollment, Rombel, SchoolClass
from app.models.exam import Exam
from app.models.question import Question, QuestionBank, QuestionOption
from app.models.student import Student
from app.models.user import User
from app.utils.security import hash_password

EMAIL_GURU = "guru@uji.local"
PASSWORD_GURU = "sandi-uji-guru-01"
PIN = "4826"

_cache = {}


def _hash(teks):
    # argon2 sengaja lambat; cukup dihitung sekali untuk semua uji
    if teks not in _cache:
        _cache[teks] = hash_password(teks)
    return _cache[teks]


def isi(db) -> dict:
    guru = User(email=EMAIL_GURU, full_name="Guru Uji", hashed_password=_hash(PASSWORD_GURU), role="teacher", is_active=True)
    lama = AcademicYear(year_name="2025/2026", is_active=0)
    aktif = AcademicYear(year_name="2026/2027", is_active=1)
    kelas = {n: SchoolClass(class_name=n) for n in ("VII", "VIII", "IX")}
    db.add_all([guru, lama, aktif, *kelas.values()])
    db.flush()
    rombel = {n: Rombel(rombel_name=n, class_id=kelas[n.split(".")[0]].id)
              for n in ("VII.1", "VII.2", "VIII.1", "IX.1")}
    db.add_all(rombel.values())
    db.flush()

    nama = {"Ani": "VII.1", "Budi": "VII.1", "Citra": "VII.1", "Dodi": "VII.2", "Eka": "VII.2", "Fajar": "VIII.1"}
    siswa = {}
    for n, r in nama.items():
        s = Student(name=n, pin_hash=_hash(PIN), is_active=True)
        db.add(s)
        db.flush()
        db.add(Enrollment(student_id=s.id, rombel_id=rombel[r].id, academic_year_id=aktif.id))
        siswa[n] = s.id
    nonaktif = Student(name="Gilang Nonaktif", pin_hash=_hash(PIN), is_active=False)
    db.add(nonaktif)
    db.flush()
    db.add(Enrollment(student_id=nonaktif.id, rombel_id=rombel["VII.1"].id, academic_year_id=aktif.id))

    # Bank PG kelas VII: 4 soal x 25 poin, jawaban benar selalu opsi pertama
    bank = QuestionBank(title="Berpikir Komputasional", class_target="VII", teacher_id=guru.id)
    db.add(bank)
    db.flush()
    soal = []
    for i in range(4):
        q = Question(bank_id=bank.id, text=f"Soal {i + 1}", points=25, question_type="pg")
        db.add(q)
        db.flush()
        ops = [QuestionOption(question_id=q.id, text=f"Opsi {j}", is_correct=(j == 0)) for j in range(4)]
        db.add_all(ops)
        db.flush()
        soal.append({"id": q.id, "benar": ops[0].id, "salah": ops[1].id})

    # Bank esai kelas VII: 1 soal 10 poin
    bank_esai = QuestionBank(title="Esai Perangkat Keras", class_target="VII", teacher_id=guru.id)
    db.add(bank_esai)
    db.flush()
    esai = Question(bank_id=bank_esai.id, text="Apa itu layar sentuh?", points=10, question_type="esai",
                    answer_key="Layar sentuh adalah layar yang dapat menerima input dari sentuhan jari",
                    keywords="layar, sentuh/raba, input/masukan, jari")
    db.add(esai)
    db.commit()
    return {"guru": guru.id, "tahun": aktif.id, "tahun_lama": lama.id, "rombel": {k: v.id for k, v in rombel.items()},
            "siswa": siswa, "nonaktif": nonaktif.id, "bank": bank.id, "bank_esai": bank_esai.id, "soal": soal,
            "esai": esai.id}


def buat_ujian(db, data, judul="Formatif 1", kelas="VII", bank=None, komponen=None, terbit=True, tahun=None, **lain) -> int:
    e = Exam(title=judul, bank_id=bank or data["bank"], class_target=kelas, duration_minutes=30, is_published=terbit,
             teacher_id=data["guru"], component_id=komponen, academic_year_id=tahun or data["tahun"], **lain)
    db.add(e)
    db.commit()
    return e.id


def kerjakan(c, exam_id: int, data, benar: int) -> int:
    """Siswa (klien c) mengerjakan ujian PG dengan `benar` jawaban benar dari 4. Mengembalikan id sesi."""
    r = c.post("/student/exam/start", data={"exam_id": str(exam_id)})
    lokasi = r.headers["location"]
    assert "/student/exam/take/" in lokasi, f"tidak bisa mulai ujian: {lokasi}"
    sesi = int(lokasi.rsplit("/", 1)[1])
    jawaban = {f"question_{s['id']}": str(s["benar"] if i < benar else s["salah"]) for i, s in enumerate(data["soal"])}
    r = c.post(f"/student/exam/submit/{sesi}", data=jawaban)
    assert r.headers["location"] == f"/student/exam/result/{sesi}"
    return sesi
