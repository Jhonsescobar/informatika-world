# conftest.py
# Konfigurasi dasar untuk pytest

import pytest
from fastapi.testclient import TestClient
from app.main import app
# Mengimpor aplikasi FastAPI utama kita

@pytest.fixture
def client():
    # Fixture ini membuat klien tes yang bisa dipakai berulang kali
    with TestClient(app) as c:
        yield c