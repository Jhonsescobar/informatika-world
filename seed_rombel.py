# seed_rombel.py
# Menyiapkan 9 rombel (VII.1 s/d IX.3) dan memasukkan siswa yang belum punya
# rombel ke VII.1 untuk sementara. Aman dijalankan berulang kali.
#
# Jalankan dari root proyek (PostgreSQL harus menyala, uvicorn tidak perlu):
#     python seed_rombel.py

from datetime import date

from app.database import SessionLocal
from app.models.academic import AcademicYear, Enrollment, Rombel, SchoolClass
from app.models.student import Student

TINGKAT = ("VII", "VIII", "IX")
ROMBEL_PER_TINGKAT = 3
ROMBEL_PENAMPUNG = "VII.1"   # rombel sementara untuk siswa yang belum punya rombel


def tahun_ajaran_berjalan():
    """Nama tahun ajaran saat ini. Tahun ajaran baru dimulai bulan Juli."""
    hari_ini = date.today()
    awal = hari_ini.year if hari_ini.month >= 7 else hari_ini.year - 1
    return f"{awal}/{awal + 1}"


def ambil_atau_buat(db, model, **kolom):
    """Kembalikan baris yang cocok dengan `kolom`; buat baru kalau belum ada."""
    baris = db.query(model).filter_by(**kolom).first()
    if baris is None:
        baris = model(**kolom)
        db.add(baris)
        db.flush()  # supaya baris.id langsung terisi
        print(f"   + {model.__name__} dibuat: {kolom}")
    return baris


def pilih_tahun_ajaran(db):
    """Pakai tahun ajaran aktif; kalau tidak ada, buat tahun ajaran berjalan."""
    aktif = (db.query(AcademicYear)
             .filter(AcademicYear.is_active == 1)
             .order_by(AcademicYear.id.desc())
             .first())
    if aktif:
        return aktif
    # is_active bertipe Integer di model ini, jadi isinya 1/0, bukan True/False
    return ambil_atau_buat(db, AcademicYear, year_name=tahun_ajaran_berjalan(), is_active=1)


def main():
    db = SessionLocal()
    try:
        print("[1] Tingkat kelas & rombel")
        for nama_tingkat in TINGKAT:
            kelas = ambil_atau_buat(db, SchoolClass, class_name=nama_tingkat)
            for nomor in range(1, ROMBEL_PER_TINGKAT + 1):
                ambil_atau_buat(db, Rombel, rombel_name=f"{nama_tingkat}.{nomor}", class_id=kelas.id)

        print("[2] Tahun ajaran")
        tahun = pilih_tahun_ajaran(db)
        print(f"   Dipakai: {tahun.year_name}")

        print(f"[3] Siswa tanpa rombel -> {ROMBEL_PENAMPUNG}")
        penampung = db.query(Rombel).filter_by(rombel_name=ROMBEL_PENAMPUNG).one()
        siswa_baru = db.query(Student).filter(~Student.enrollments.any()).all()
        for siswa in siswa_baru:
            db.add(Enrollment(student_id=siswa.id, rombel_id=penampung.id,
                              academic_year_id=tahun.id))
            print(f"   + {siswa.name}")
        if not siswa_baru:
            print("   Semua siswa sudah punya rombel.")

        db.commit()

        print("[4] Jumlah siswa per rombel")
        for rombel in db.query(Rombel).order_by(Rombel.id):
            jumlah = db.query(Enrollment).filter_by(rombel_id=rombel.id).count()
            print(f"   {rombel.rombel_name:<7} {jumlah} siswa")
        print("Selesai.")
    except Exception:
        db.rollback()  # tidak ada data setengah jadi yang tersimpan
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
