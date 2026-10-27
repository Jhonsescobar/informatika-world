# tests/test_main.py
# Tes otomatis untuk rute utama dan keamanan dasar

def test_root_redirects_to_login(client):
    # Tes 1: Jika orang mengakses root (/), apakah dia dialihkan ke /login?
    response = client.get("/", follow_redirects=False)
    # follow_redirects=False agar kita bisa cek kode redirect (303/307)
    
    assert response.status_code in [303, 307]
    # Cek apakah statusnya adalah redirect
    
    assert "/login" in response.headers["location"]
    # Cek apakah tujuan redirect mengandung kata "/login"

def test_login_page_loads(client):
    # Tes 2: Apakah halaman login guru bisa dimuat?
    response = client.get("/login")
    
    assert response.status_code == 200
    # Cek apakah statusnya OK (200)

def test_student_search_too_short(client):
    # Tes 3: Keamanan Autocomplete - Jika mengetik <3 huruf, harusnya kosong
    response = client.get("/auth/student/search?name=an")
    # Hanya 2 huruf
    
    assert response.status_code == 200
    # Harus sukses
    
    assert response.json() == []
    # Harus mengembalikan array kosong [] karena terlalu pendek

def test_student_search_exact_length(client):
    # Tes 4: Autocomplete - Jika mengetik 3 huruf0harusnya mulai mencari
    response = client.get("/auth/student/search?name=and")
    # 3 huruf
    
    assert response.status_code == 200
    # Harus sukses
    
    # Kita tidak cek isi datanya (tergantung DB), tapi kita cek sistem tidak error 500
    assert isinstance(response.json(), list)
    # Hasilnya harus berupa list