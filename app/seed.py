# app/seed.py
# Script untuk mengisi database dengan data awal yang diperlukan oleh sistem

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
# Mengimpor pabrik sesi database dan mesin database

from app.models.achievement import Achievement
from app.models.user import User
from app.models.student import Student
from app.models.academic import AcademicYear, SchoolClass, Rombel
# Mengimpor model-model tabel yang akan kita isi

from app.utils.security import hash_password
# Mengimpor fungsi hash_password untuk mengamankan password guru

def seed_database():
    # Fungsi utama untuk menjalankan proses seeding
    
    db = SessionLocal()
    # Membuka koneksi ke database

    try:
        # 1. CEK APAKAH DATA SUDAH ADA (Agar tidak dobel jika script dijalankan 2x)
        existing_user = db.query(User).filter(User.email == "guru@informatika.world").first()
        # Cek apakah email guru sudah ada di database

        if existing_user:
            print("Data awal sudah ada. Tidak perlu di-seed lagi.")
            return
            # Jika sudah ada, hentikan proses

        # 2. MEMBUAT AKUN GURA ADMIN
        print("Membuat akun Guru...")
        hashed_pwd = hash_password("guru123")
        # Mengubah password 'guru123' menjadi teks hash Argon2 yang aman

        guru = User(
            email="guru@informatika.world",
            full_name="Guru Informatika",
            hashed_password=hashed_pwd,
            role="teacher",
            is_active=True
        )
        db.add(guru)
        # Menambahkan data guru ke sesi database

        # 3. MEMBUAT TAHUN AJARAN
        print("Membuat Tahun Ajaran...")
        tahun_ajar = AcademicYear(year_name="2024/2025", is_active=1)
        db.add(tahun_ajar)

        # 4. MEMBUAT KELAS (VII, VIII, IX)
        print("Membuat Tingkat Kelas...")
        kelas_7 = SchoolClass(class_name="VII")
        kelas_8 = SchoolClass(class_name="VIII")
        kelas_9 = SchoolClass(class_name="IX")
        db.add_all([kelas_7, kelas_8, kelas_9])
        # Menambahkan 3 kelas sekaligus

        # 6. MEMBUAT SISWA CONTOH
        print("Membuat akun Siswa contoh...")
        pin_hash = hash_password("1234") # PIN 4 digit
        siswa_andi = Student(name="Andi Pratama", nipd="12345", pin_hash=pin_hash, is_active=True)
        db.add(siswa_andi)

                # 7. MEMBUAT ACHIEVEMENTS
        print("Membuat Achievements...")
        ach1 = Achievement(name="Computer Explorer", description="Menyelesaikan ujian pertama", icon="🚀", condition_type="FIRST_EXAM")
        ach2 = Achievement(name="Perfect Logic", description="Mendapat skor sempurna (100)", icon="💎", condition_type="PERFECT_SCORE")
        ach3 = Achievement(name="Digital Citizen", description="Terdaftar di kelas digital", icon="🌐", condition_type="ENROLLED")
        db.add_all([ach1, ach2, ach3])

        # 5. COMMIT (Simpan permanen ke PostgreSQL)
        db.commit()
        print("✅ Seeding berhasil! Akun guru dan struktur kelas telah dibuat.")

    except Exception as e:
        print(f"❌ Error saat seeding: {e}")
        db.rollback()
        # Jika ada error, batalkan semua perubahan yang belum tersimpan
    finally:
        db.close()
        # Pastikan koneksi database selalu ditutup

if __name__ == "__main__":
    # Jika file ini dijalankan langsung dari terminal (python -m app.seed)
    print("Memulai proses seeding database...")
    seed_database()