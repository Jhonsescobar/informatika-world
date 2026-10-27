# app/add_achievements.py
from app.database import SessionLocal
from app.models.achievement import Achievement

def seed_achievements():
    db = SessionLocal()
    
    # Cek apakah achievement sudah ada
    if db.query(Achievement).first():
        print("Achievements sudah ada di database.")
        db.close()
        return
        
    print("Membuat Achievements...")
    ach1 = Achievement(name="Computer Explorer", description="Menyelesaikan ujian pertama", icon="🚀", condition_type="FIRST_EXAM")
    ach2 = Achievement(name="Perfect Logic", description="Mendapat skor sempurna (sesuai poin soal)", icon="💎", condition_type="PERFECT_SCORE")
    ach3 = Achievement(name="Digital Citizen", description="Terdaftar di kelas digital", icon="🌐", condition_type="ENROLLED")
    
    db.add_all([ach1, ach2, ach3])
    db.commit()
    print("✅ 3 Achievements berhasil dibuat!")
    db.close()

if __name__ == "__main__":
    seed_achievements()