# online.ps1 - menyalakan web untuk sesi ujian, lalu menampilkan alamat untuk siswa.
# Dijalankan lewat ONLINE.bat (klik dua kali). Tekan Q di jendela ini untuk mematikan.
#
# Yang dikerjakan otomatis:
#   - cadangan database + rekap nilai Excel SEBELUM dan SESUDAH sesi (folder backups/)
#   - laptop dicegah tidur selama jendela ini terbuka (layar boleh mati)
#   - web/tunnel yang mati sendiri dinyalakan ulang otomatis
#   - dua mode: internet (Cloudflare) atau jaringan lokal saja (WiFi sekolah / hotspot laptop)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # tanpa bilah progres: Invoke-WebRequest jauh lebih cepat
Set-Location -Path $PSScriptRoot

$python = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
$cloudflared = Join-Path $PSScriptRoot "cloudflared.exe"
$folderLog = Join-Path $PSScriptRoot "logs"
$logTunnel = Join-Path $folderLog "cloudflared.log"
$PORT = 8000
$MAKS_RESTART = 5
$fileAlamat = Join-Path $folderLog "alamat.json"   # dibaca web untuk halaman QR guru
$alamatSekarang = $null
$alamatLain = @()

function Tulis($teks, $warna = "Gray") { Write-Host $teks -ForegroundColor $warna }
function Berhenti($pesan) { Tulis $pesan Red; Read-Host "Enter untuk keluar"; exit 1 }

# Alamat untuk halaman QR guru. Ditulis ulang setiap alamat berganti DAN setiap web dinyalakan ulang
# (web menganggap file yang lebih tua dari dirinya sebagai sisa sesi lama).
function Simpan-Alamat {
    if (-not $script:alamatSekarang) { return }
    $isi = @{ url = $script:alamatSekarang; lain = @($script:alamatLain); waktu = (Get-Date -Format s) } | ConvertTo-Json -Compress
    try {
        [IO.File]::WriteAllText("$fileAlamat.tmp", $isi)
        Move-Item -Force -Path "$fileAlamat.tmp" -Destination $fileAlamat
    } catch { Tulis "  (alamat untuk halaman QR gagal disimpan: $($_.Exception.Message))" DarkGray }
}
function Hapus-Alamat { Remove-Item -Path $fileAlamat, "$fileAlamat.tmp" -Force -ErrorAction SilentlyContinue }
function Buka-QR {
    Tulis "  Halaman QR untuk proyektor dibuka di browser: http://127.0.0.1:$PORT/teacher/qr" DarkGray
    try { Start-Process "http://127.0.0.1:$PORT/teacher/qr" } catch {}
}


if (-not (Test-Path $python)) { Berhenti "venv tidak ditemukan di folder ini." }
New-Item -ItemType Directory -Force -Path $folderLog | Out-Null

# ---------- pilih mode ----------
Tulis ""
Tulis "  Mode sesi ujian:" Cyan
Tulis "    1  Internet  - siswa membuka lewat alamat trycloudflare (butuh internet di laptop)"
Tulis "    2  Lokal     - siswa terhubung ke WiFi/hotspot yang sama dengan laptop (tanpa internet)"
$mode = (Read-Host "  Pilih 1 atau 2 [1]").Trim()
if ($mode -ne "2") { $mode = "1" }
if ($mode -eq "1" -and -not (Test-Path $cloudflared)) { Berhenti "cloudflared.exe belum ada di folder ini. Lihat PANDUAN_ONLINE.md, atau pilih mode 2." }
# mode lokal harus menerima koneksi dari perangkat lain; mode internet cukup dari laptop ini (lebih aman)
$alamatIkat = if ($mode -eq "2") { "0.0.0.0" } else { "127.0.0.1" }

# ---------- bereskan sisa sesi lalu (mis. jendela ditutup dengan X, bukan Q) ----------
try {
    Get-NetTCPConnection -LocalPort $PORT -State Listen -ErrorAction Stop | ForEach-Object {
        $lama = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
        if ($lama -and $lama.ProcessName -like "python*") { Stop-Process -Id $lama.Id -Force -ErrorAction SilentlyContinue; Tulis "  Web sisa sesi sebelumnya dimatikan." DarkGray }
        elseif ($lama) { Berhenti "Port $PORT sedang dipakai program lain ($($lama.ProcessName)). Tutup program itu dulu." }
    }
} catch {}
Get-Process -Name cloudflared -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $cloudflared } | Stop-Process -Force -ErrorAction SilentlyContinue
Hapus-Alamat   # alamat sesi lalu (tunnel lama) jangan sampai tampil di QR

# ---------- cadangan sebelum mulai ----------
Tulis ""
Tulis "[1/3] Cadangan sebelum sesi ..." Cyan
& $python backup_db.py
if ($LASTEXITCODE -ne 0) { Tulis "  Cadangan gagal (lihat pesan di atas). Web tetap dinyalakan." Yellow }

# ---------- cegah laptop tidur ----------
try {
    Add-Type -Namespace IW -Name Daya -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);'
    # ES_CONTINUOUS | ES_SYSTEM_REQUIRED: sistem tidak tidur, layar tetap boleh mati
    [IW.Daya]::SetThreadExecutionState([uint32]2147483649) | Out-Null
    $jagaBangun = $true
} catch { $jagaBangun = $false }

# ---------- fungsi menyalakan web & tunnel ----------
function Nyalakan-Web {
    $p = Start-Process -FilePath $python -ArgumentList "-m", "uvicorn", "app.main:app", "--host", $alamatIkat, "--port", "$PORT" `
        -WindowStyle Hidden -PassThru -RedirectStandardError (Join-Path $folderLog "web.log") -RedirectStandardOutput (Join-Path $folderLog "web-out.log")
    for ($i = 0; $i -lt 30; $i++) {
        try { Invoke-WebRequest -Uri "http://127.0.0.1:$PORT/login" -UseBasicParsing -TimeoutSec 2 | Out-Null; return $p }
        catch { if ($p.HasExited) { break }; Start-Sleep -Seconds 1 }
    }
    Stop-Process -Id $p.Id -ErrorAction SilentlyContinue
    return $null
}

function Nyalakan-Tunnel {
    if (Test-Path $logTunnel) { Remove-Item $logTunnel -Force -ErrorAction SilentlyContinue }
    $p = Start-Process -FilePath $cloudflared -ArgumentList "tunnel", "--url", "http://localhost:$PORT", "--logfile", $logTunnel -WindowStyle Hidden -PassThru
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 1
        if ($p.HasExited) { break }
        # log bisa sedang ditulis cloudflared; "api.trycloudflare.com" bukan alamat untuk siswa
        try {
            $isi = Get-Content -Path $logTunnel -Raw -ErrorAction Stop
            if ($isi -match "https://(?!api\.)[a-z0-9-]+\.trycloudflare\.com") { return @{ Proses = $p; Url = $Matches[0] } }
        } catch {}
    }
    Stop-Process -Id $p.Id -ErrorAction SilentlyContinue
    return $null
}

function Tampilkan-Alamat($alamat, $catatan) {
    try { Set-Clipboard -Value $alamat } catch {}
    Tulis ""
    Tulis "  ONLINE. Bagikan alamat ini ke siswa (sudah disalin):" Green
    Tulis ""
    Tulis "  $alamat" Yellow
    Tulis ""
    foreach ($c in $catatan) { Tulis "  $c" }
}

function Alamat-Lokal {
    try {
        Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
            Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" -and $_.InterfaceAlias -notmatch "vEthernet|VirtualBox|VMware|Loopback" } |
            Select-Object -ExpandProperty IPAddress
    } catch { @() }
}

# ---------- nyalakan ----------
Tulis "[2/3] Menyalakan web di port $PORT ..." Cyan
$web = Nyalakan-Web
if (-not $web) { Berhenti "Web gagal menyala. Lihat logs\web.log (biasanya PostgreSQL belum jalan atau .env salah)." }

$tunnel = $null
if ($mode -eq "1") {
    Tulis "[3/3] Membuka tunnel Cloudflare ..." Cyan
    $tunnel = Nyalakan-Tunnel
    if (-not $tunnel) { Tulis "Tunnel gagal dibuat. Cek internet. Web tetap menyala; bisa pakai mode lokal (jalankan ulang, pilih 2)." Red }
    else {
        $alamatSekarang = "$($tunnel.Url)/login"; Simpan-Alamat
        Tampilkan-Alamat $alamatSekarang @("Alamat berganti setiap kali ONLINE.bat dijalankan ulang.", "Atau tayangkan QR: menu QR Siswa di halaman guru.")
        Buka-QR
    }
} else {
    Tulis "[3/3] Mode jaringan lokal" Cyan
    $ip = @(Alamat-Lokal)
    if ($ip.Count -eq 0) { Tulis "Laptop belum terhubung ke WiFi/hotspot mana pun." Red }
    else {
        $alamatSekarang = "http://$($ip[0]):$PORT/login"
        $alamatLain = @($ip | Select-Object -Skip 1 | ForEach-Object { "http://$($_):$PORT/login" })
        Simpan-Alamat
        Buka-QR
        Tampilkan-Alamat $alamatSekarang (@(
            "Siswa harus terhubung ke WiFi/hotspot yang sama dengan laptop ini.",
            "Jika Windows menanyakan izin firewall untuk Python, centang 'Private networks' lalu Allow."
        ) + ($ip | Select-Object -Skip 1 | ForEach-Object { "Alamat lain bila yang di atas tidak bisa: http://$($_):$PORT/login" }))
    }
}
Tulis ""
if ($jagaBangun) { Tulis "  Laptop dicegah tidur selama jendela ini terbuka. Tetap colokkan charger." DarkGray }
Tulis "  Tekan Q untuk MEMATIKAN web (cadangan dibuat otomatis). Jangan tutup dengan tombol X." White

# ---------- jaga: nyalakan ulang yang mati ----------
$restartWeb = 0; $restartTunnel = 0
try {
    while ($true) {
        if ([Console]::KeyAvailable) {
            $k = [Console]::ReadKey($true)
            if ($k.Key -eq "Q") { break }
        }
        if ($web.HasExited) {
            if ($restartWeb -ge $MAKS_RESTART) { Tulis "Web mati berulang kali. Lihat logs\web.log." Red; break }
            $restartWeb++
            Tulis "$(Get-Date -Format HH:mm:ss)  Web berhenti, menyalakan ulang ($restartWeb/$MAKS_RESTART) ..." Yellow
            $baru = Nyalakan-Web
            if ($baru) { $web = $baru; Simpan-Alamat; Tulis "  Web menyala lagi. Siswa cukup memuat ulang halaman; jawaban tersimpan." Green }
        }
        if ($tunnel -and $tunnel.Proses.HasExited) {
            if ($restartTunnel -ge $MAKS_RESTART) { Tulis "Tunnel putus berulang kali. Cek internet, atau pakai mode lokal." Red; $tunnel = $null; $alamatSekarang = $null; Hapus-Alamat }
            else {
                $restartTunnel++
                Tulis "$(Get-Date -Format HH:mm:ss)  Tunnel putus, membuka ulang ($restartTunnel/$MAKS_RESTART) ..." Yellow
                Hapus-Alamat   # QR lama menunjuk tunnel yang sudah mati
                $baru = Nyalakan-Tunnel
                if ($baru) {
                    $tunnel = $baru; $alamatSekarang = "$($tunnel.Url)/login"; Simpan-Alamat
                    Tampilkan-Alamat $alamatSekarang @("ALAMAT BARU. Bagikan ulang ke siswa; jawaban mereka tetap tersimpan.", "QR di halaman guru ikut berganti sendiri.")
                }
            }
        }
        Start-Sleep -Milliseconds 500
    }
} finally {
    Hapus-Alamat
    if ($tunnel) { Stop-Process -Id $tunnel.Proses.Id -ErrorAction SilentlyContinue }
    if ($web) { Stop-Process -Id $web.Id -ErrorAction SilentlyContinue }
    if ($jagaBangun) { [IW.Daya]::SetThreadExecutionState([uint32]2147483648) | Out-Null }
}

Tulis ""
Tulis "Web sudah offline. Cadangan sesudah sesi ..." Cyan
& $python backup_db.py
Tulis ""
Read-Host "Selesai. Enter untuk menutup"
