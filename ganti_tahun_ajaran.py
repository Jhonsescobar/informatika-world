# ganti_tahun_ajaran.py
# Menjadikan 2026/2027 tahun ajaran aktif. Keanggotaan rombel yang tercatat di
# tahun ajaran aktif sebelumnya ikut dipindahkan ke 2026/2027.
# Aman dijalankan berulang kali.
#
#     python ganti_tahun_ajaran.py

from app.database import SessionLocal
from app.models.academic import AcademicYear, Enrollment

TAHUN_BARU = "2026/2027"


def main():
    db = SessionLocal()
    try:
        lama = [t for t in db.query(AcademicYear).filter(AcademicYear.is_active == 1)
                if t.year_name != TAHUN_BARU]

        baru = db.query(AcademicYear).filter_by(year_name=TAHUN_BARU).first()
        if baru is None:
            baru = AcademicYear(year_name=TAHUN_BARU, is_active=1)
            db.add(baru)
            db.flush()
            print(f"+ Tahun ajaran {TAHUN_BARU} dibuat")
        baru.is_active = 1

        for t in lama:
            t.is_active = 0
            jumlah = (db.query(Enrollment)
                      .filter(Enrollment.academic_year_id == t.id)
                      .update({Enrollment.academic_year_id: baru.id}, synchronize_session=False))
            print(f"- {t.year_name} dinonaktifkan, {jumlah} keanggotaan rombel dipindah ke {TAHUN_BARU}")

        db.commit()
        for t in db.query(AcademicYear).order_by(AcademicYear.id):
            print(f"  {t.year_name:<10} {'AKTIF' if t.is_active == 1 else 'nonaktif'}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
