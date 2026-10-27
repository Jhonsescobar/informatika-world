# app/services/gamification.py
# Logika untuk memberikan achievement otomatis berdasarkan aksi siswa

from sqlalchemy.orm import Session
from app.models.achievement import Achievement, StudentAchievement

def award_achievement(student_id: int, condition_type: str, db: Session):
    # Fungsi untuk mengecek dan memberikan lencana
    
    # 1. Cari apakah ada lencana dengan kondisi ini
    achievement = db.query(Achievement).filter(Achievement.condition_type == condition_type).first()
    if not achievement:
        return # Jika tidak ada lencana untuk kondisi ini, hentikan
        
    # 2. Cek apakah siswa SUDAH PERNAH mendapat lencana ini sebelumnya
    existing_award = db.query(StudentAchievement).filter(
        StudentAchievement.student_id == student_id,
        StudentAchievement.achievement_id == achievement.id
    ).first()
    
    if existing_award:
        return # Jika sudah punya, jangan kasih dua kali
        
    # 3. Jika belum punya, berikan lencana!
    new_award = StudentAchievement(student_id=student_id, achievement_id=achievement.id)
    db.add(new_award)
    db.commit()