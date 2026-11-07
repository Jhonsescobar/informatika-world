# conftest.py
# Persiapan uji otomatis (pytest). Uji SELALU memakai database terpisah, tidak pernah database asli.
#
# Jalankan saja:
#     python -m pytest -q
# Database uji dibuat otomatis di server PostgreSQL yang sama dengan nama <database asli>_test
# (misalnya informatika_world_test). Database asli tidak pernah disentuh.
# Ingin database uji lain? Isi TEST_DATABASE_URL di .env (namanya wajib mengandung "test").
#
# Setiap uji dimulai dari data bersih (tabel dikosongkan lalu diisi data contoh dari tests/data_uji.py).

import os

import pytest
from dotenv import dotenv_values

_env = dotenv_values(".env")
URL_UJI = os.getenv("TEST_DATABASE_URL") or _env.get("TEST_DATABASE_URL")
URL_ASLI = os.getenv("DATABASE_URL") or _env.get("DATABASE_URL")

if not URL_UJI and URL_ASLI:
    from sqlalchemy.engine import make_url
    _u = make_url(URL_ASLI)
    URL_UJI = _u.set(database=f"{_u.database}_test").render_as_string(hide_password=False)
if not URL_UJI:
    pytest.exit("DATABASE_URL tidak ditemukan di .env.", returncode=2)
if URL_UJI == URL_ASLI or "test" not in URL_UJI.rsplit("/", 1)[-1]:
    pytest.exit("TEST_DATABASE_URL harus database KHUSUS uji (namanya mengandung 'test'), "
                "bukan database asli. Uji dibatalkan supaya data siswa aman.", returncode=2)

def _pastikan_database_uji_ada(url: str):
    from sqlalchemy import create_engine, text as _text
    from sqlalchemy.engine import make_url
    u = make_url(url)
    mesin = create_engine(u.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with mesin.connect() as c:
            ada = c.execute(_text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": u.database}).scalar()
            if not ada:
                c.execute(_text(f'CREATE DATABASE "{u.database}"'))
    except Exception as e:  # noqa: BLE001
        pytest.exit(f"Database uji '{u.database}' tidak bisa dibuat otomatis: {e}. "
                    "Buat manual di pgAdmin, lalu jalankan lagi.", returncode=2)
    finally:
        mesin.dispose()


_pastikan_database_uji_ada(URL_UJI)

# Harus diatur SEBELUM app diimpor: app membaca DATABASE_URL saat pertama dimuat.
os.environ["DATABASE_URL"] = URL_UJI
os.environ["SECRET_KEY"] = "kunci-khusus-uji-otomatis-bukan-asli"

from alembic import command                     # noqa: E402
from alembic.config import Config                # noqa: E402
from fastapi.testclient import TestClient        # noqa: E402
from sqlalchemy import text                      # noqa: E402

import app.models                                # noqa: E402,F401  (mendaftarkan semua tabel)
from app.database import Base, SessionLocal, engine   # noqa: E402
from app.main import app as aplikasi             # noqa: E402
from app.utils import ratelimit                  # noqa: E402
from tests import data_uji                       # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def skema():
    # Database uji dibangun lewat migrasi Alembic, jadi migrasinya ikut teruji.
    with engine.begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def data(skema):
    tabel = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as c:
        c.execute(text(f"TRUNCATE {tabel} RESTART IDENTITY CASCADE"))
    ratelimit._gagal.clear()
    db = SessionLocal()
    try:
        yield data_uji.isi(db)
    finally:
        db.close()


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


def klien() -> TestClient:
    return TestClient(aplikasi, follow_redirects=False)


@pytest.fixture
def client():
    return klien()


@pytest.fixture
def guru(data):
    c = klien()
    r = c.post("/auth/teacher/login", data={"email": data_uji.EMAIL_GURU, "password": data_uji.PASSWORD_GURU})
    assert r.headers["location"] == "/teacher/dashboard"
    return c


@pytest.fixture
def masuk_siswa():
    def masuk(student_id: int, pin: str = data_uji.PIN) -> TestClient:
        c = klien()
        r = c.post("/auth/student/verify", data={"student_id": str(student_id), "pin": pin})
        assert r.headers["location"] == "/student/dashboard", "login siswa gagal"
        return c
    return masuk
