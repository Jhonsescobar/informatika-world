# update.ps1 - memasang paket pembaruan dengan satu perintah. Dijalankan lewat UPDATE.bat.
# Cara pakai: taruh file paket (rilis_*.tgz atau .zip) di folder ini atau di Downloads, klik dua kali UPDATE.bat.
# Yang dikerjakan otomatis, berurutan; bila ada langkah gagal, berhenti dan kode lama dikembalikan:
#   1. matikan web lama   2. cadangan database + kode lama   3. bongkar paket + cek keutuhan (SHA-256)
#   4. pasang library baru bila perlu   5. migrasi database   6. uji cepat   7. selesai (lalu jalankan ONLINE.bat)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
$python = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
function Tulis($t, $w = "Gray") { Write-Host $t -ForegroundColor $w }
function Gagal($t) { Tulis ""; Tulis "  GAGAL: $t" Red; Read-Host "Enter untuk keluar"; exit 1 }

if (-not (Test-Path $python)) { Gagal "venv tidak ditemukan di folder ini." }

# ---------- cari paket terbaru ----------
$lokasi = @($PSScriptRoot, (Join-Path $env:USERPROFILE "Downloads"))
$paket = $lokasi | ForEach-Object { Get-ChildItem -Path $_ -Include "rilis_*.tgz", "rilis_*.zip" -File -ErrorAction SilentlyContinue } |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $paket) { Gagal "Paket rilis_*.tgz / rilis_*.zip tidak ditemukan di folder ini atau di Downloads." }
Tulis ""
Tulis "  Paket: $($paket.FullName)" Cyan

# ---------- 1. matikan web lama ----------
Tulis "[1/6] Mematikan web lama ..." Cyan
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    $pr = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
    if ($pr -and $pr.ProcessName -like "python*") { Stop-Process -Id $pr.Id -Force -ErrorAction SilentlyContinue }
}
Start-Sleep -Seconds 2

# ---------- 2. cadangan ----------
Tulis "[2/6] Cadangan database dan kode lama ..." Cyan
& $python backup_db.py
if ($LASTEXITCODE -ne 0) { Gagal "Cadangan database gagal. Update dibatalkan, tidak ada yang diubah." }
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$cadKode = Join-Path $PSScriptRoot "backups\kode_$stamp"
New-Item -ItemType Directory -Force -Path $cadKode | Out-Null
foreach ($d in "app", "migrations") { if (Test-Path $d) { Copy-Item -Recurse -Force $d (Join-Path $cadKode $d) } }
foreach ($f in "requirements.txt", "online.ps1", "update.ps1", "ONLINE.bat", "UPDATE.bat", "alembic.ini", "backup_db.py") { if (Test-Path $f) { Copy-Item -Force $f $cadKode } }

function Kembalikan {
    Tulis "  Mengembalikan kode lama dari $cadKode ..." Yellow
    foreach ($d in "app", "migrations") { if (Test-Path (Join-Path $cadKode $d)) { Remove-Item -Recurse -Force $d -ErrorAction SilentlyContinue; Copy-Item -Recurse -Force (Join-Path $cadKode $d) $d } }
    Get-ChildItem $cadKode -File | ForEach-Object { Copy-Item -Force $_.FullName $PSScriptRoot }
}

# ---------- 3. bongkar + cek keutuhan ----------
Tulis "[3/6] Membongkar paket dan memeriksa keutuhan ..." Cyan
$tmp = Join-Path $env:TEMP "iw_update_$stamp"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
if ($paket.Extension -eq ".zip") { Expand-Archive -Path $paket.FullName -DestinationPath $tmp -Force }
else { tar -xzf $paket.FullName -C $tmp; if ($LASTEXITCODE -ne 0) { Gagal "Paket tidak bisa dibongkar (rusak atau terpotong saat diunduh)." } }
$manifest = Join-Path $tmp "MANIFEST.sha256"
if (-not (Test-Path $manifest)) { Gagal "Paket tidak memiliki MANIFEST.sha256 (bukan paket resmi atau rusak). Tidak ada yang diubah." }
$rusak = @()
foreach ($baris in Get-Content $manifest) {
    if ($baris -match "^([0-9a-fA-F]{64})\s+\*?(.+)$") {
        $berkas = Join-Path $tmp $Matches[2]
        if (-not (Test-Path $berkas) -or (Get-FileHash -Algorithm SHA256 $berkas).Hash -ne $Matches[1].ToUpper()) { $rusak += $Matches[2] }
    }
}
if ($rusak.Count -gt 0) { Gagal "Berkas dalam paket tidak utuh: $($rusak -join ', '). Unduh ulang paketnya. Tidak ada yang diubah." }
Get-ChildItem $tmp | Where-Object { $_.Name -ne "MANIFEST.sha256" } | ForEach-Object { Copy-Item -Recurse -Force $_.FullName $PSScriptRoot }
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue

# ---------- 4. library ----------
Tulis "[4/6] Memeriksa library ..." Cyan
& $python -m pip install -q -r requirements.txt
if ($LASTEXITCODE -ne 0) { Kembalikan; Gagal "Pemasangan library gagal (butuh internet). Kode lama dikembalikan." }

# ---------- 5. migrasi ----------
Tulis "[5/6] Migrasi database ..." Cyan
& $python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { Kembalikan; Gagal "Migrasi database gagal. Kode lama dikembalikan; data dari cadangan di folder backups bila perlu." }

# ---------- 6. uji cepat ----------
Tulis "[6/6] Uji cepat aplikasi ..." Cyan
& $python -c "import app.main; print('  aplikasi dapat dimuat')"
if ($LASTEXITCODE -ne 0) { Kembalikan; Gagal "Aplikasi tidak bisa dimuat dengan kode baru. Kode lama dikembalikan." }

Tulis ""
Tulis "  UPDATE SELESAI. Jalankan ONLINE.bat seperti biasa." Green
Read-Host "Enter untuk menutup"
