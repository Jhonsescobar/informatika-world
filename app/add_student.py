# app/add_student.py
# Script khusus untuk menambahkan siswa tes dan mendaftarkannya ke rombel

from app.database import SessionLocal
from app.models.student import Student
from app.models.academic import AcademicYear, SchoolClass, Rombel, Enrollment
from app.utils.security import hash_password

def add_test_student():
    db = SessionLocal()
    
    # 1. Cek apakah Kelas VII ada
    kelas_7 = db.query(SchoolClass).filter(SchoolClass.class_name == "VII").first()
    if not kelas_7:
        print("❌ Data Kelas VII belum ada. Jalankan python -m app.seed dulu.")
        db.close()
        return

    # 2. BUAT ROMBEL VII-A JIKA BELUM ADA
    rombel_7a = db.query(Rombel).filter(Rombel.rombel_name == "VII-A").first()
    if not rombel_7a:
        print("Membuat Rombel VII-A...")
        rombel_7a = Rombel(rombel_name="VII-A", class_id=kelas_7.id)
        db.add(rombel_7a)
        db.commit()
        db.refresh(rombel_7a)
        # Refresh agar ID rombel_7a terupdate di variabel Python

    # 3. BUAT SISWA ANDI JIKA BELUM ADA
    existing = db.query(Student).filter(Student.nipd == "12345").first()
    if not existing:
        print("Membuat Siswa Andi Pratama...")
        pin_hash = hash_password("1234")
        siswa = Student(name="Andi Pratama", nipd="12345", pin_hash=pin_hash, is_active=True)
        db.add(siswa)
        db.commit()
        db.refresh(siswa)
        existing = siswa

    # 4. Cek Tahun Ajaran
    tahun = db.query(AcademicYear).first()
    if not tahun:
        print("❌ Tahun ajaran belum ada.")
        db.close()
        return

    # 5. DAFTARKAN ANDI KE VII-A
    existing_enrollment = db.query(Enrollment).filter(Enrollment.student_id == existing.id).first()
    if not existing_enrollment:
        print("Mendaftarkan Andi ke VII-A...")
        new_enr = Enrollment(student_id=existing.id, academic_year_id=tahun.id, rombel_id=rombel_7a.id)
        db.add(new_enr)
        db.commit()
    else:
        print("Andi sudah terdaftar di rombel.")
        
    print("✅ Setup Siswa & Rombel selesai!")
    db.close()

if __name__ == "__main__":
    add_test_student()