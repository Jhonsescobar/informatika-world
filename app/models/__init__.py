# app/models/__init__.py
# Mendaftarkan SEMUA model ke SQLAlchemy setiap kali salah satu model diimpor.
# Tanpa ini, script yang hanya mengimpor app.models.academic akan error:
#   "expression 'Student' failed to locate a name"
# karena relationship("Student") di Enrollment butuh model Student sudah terdaftar.
from app.models import (  # noqa: F401
    academic,
    achievement,
    exam,
    grade,
    material,
    question,
    student,
    user,
)
