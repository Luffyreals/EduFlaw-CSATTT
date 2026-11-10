<#
Cài đặt EduFlaw trên máy Windows bằng một lệnh. Chạy lại nhiều lần vẫn an toàn: bước nào đã xong thì bỏ qua.
Xem docs/DEPLOY.md, mục 1.

Cách chạy (từ thư mục src):
    powershell -ExecutionPolicy Bypass -File .\setup.ps1
    powershell -ExecutionPolicy Bypass -File .\setup.ps1 -SkipTests     # bỏ qua bước chạy test

Với CSDL MỚI (chưa có bảng/chưa có người dùng) script tự tạo bảng và seed dữ liệu mẫu; CSDL đã có dữ liệu thì
giữ nguyên. Không in giá trị bí mật nào trong .env. Thoát mã 2 nếu chưa kết nối được CSDL.
#>
param(
    [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function Write-Step($message) { Write-Host "`n==> $message" -ForegroundColor Cyan }
function Write-Ok($message) { Write-Host "    OK: $message" -ForegroundColor Green }
function Write-Note($message) { Write-Host "    CHÚ Ý: $message" -ForegroundColor Yellow }
function Stop-Setup($message) {
    Write-Host "    LỖI: $message" -ForegroundColor Red
    exit 1
}

# Đọc kết quả Python bằng UTF-8 (mặc định của Windows PowerShell 5.1 làm hỏng tiếng Việt)
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Chạy một đoạn Python bằng interpreter cho trước; trả về các dòng in ra stdout.
# Ghi đoạn mã ra file tạm (UTF-8 không BOM) thay vì đưa qua stdin: tùy cấu hình console, PowerShell 5.1 chèn BOM
# vào đầu stdin (có khi hai lần) và Python báo SyntaxError. PYTHONPATH để đoạn mã import được app/, config.py từ src.
# Không dùng 2>&1: trên PowerShell 5.1 mỗi dòng stderr thành lỗi và dừng script.
function Invoke-Python($interpreter, $code) {
    $scriptFile = Join-Path ([System.IO.Path]::GetTempPath()) ("eduflaw_setup_" + [guid]::NewGuid().ToString('N') + '.py')
    [System.IO.File]::WriteAllText($scriptFile, $code, (New-Object System.Text.UTF8Encoding $false))
    $previousPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = $PSScriptRoot
        $output = & $interpreter $scriptFile
        return @($output | ForEach-Object { "$_" })
    } finally {
        $env:PYTHONPATH = $previousPath
        Remove-Item $scriptFile -ErrorAction SilentlyContinue
    }
}

# ---------- 1. Python >= 3.11 ----------
Write-Step 'Kiểm tra Python (cần bản 3.11 trở lên)'
$systemPython = $null
foreach ($name in @('python', 'py')) {
    $command = Get-Command $name -ErrorAction SilentlyContinue
    # python.exe trong WindowsApps chỉ là lối tắt mở Microsoft Store, không phải Python thật
    if ($command -and $command.Source -notmatch 'WindowsApps') {
        $systemPython = $command.Source
        break
    }
}
if (-not $systemPython -and -not (Test-Path '.venv\Scripts\python.exe')) {
    Stop-Setup 'Chưa cài Python. Chạy: winget install --id Python.Python.3.13 rồi mở terminal mới và chạy lại script này.'
}

$versionCheck = 'import sys; print("%d.%d" % sys.version_info[:2]); print(int(sys.version_info >= (3, 11)))'

# ---------- 2. Môi trường ảo .venv ----------
Write-Step 'Tạo môi trường ảo .venv'
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (Test-Path $venvPython) {
    Write-Ok '.venv đã có, dùng lại.'
} else {
    $version = @(Invoke-Python $systemPython $versionCheck)
    if ($version.Count -lt 2) { Stop-Setup "Không chạy được $systemPython (xem lỗi ở trên)." }
    if ($version[-1] -ne '1') {
        Stop-Setup "Python $($version[0]) quá cũ (pandas 3 cần >= 3.11). Cài bản mới: winget install --id Python.Python.3.13"
    }
    & $systemPython -m venv .venv
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPython)) { Stop-Setup 'Không tạo được .venv.' }
    Write-Ok "Đã tạo .venv bằng Python $($version[0])."
}
$venvVersion = @(Invoke-Python $venvPython $versionCheck)
if ($venvVersion.Count -lt 2) { Stop-Setup 'Không chạy được Python trong .venv. Xóa thư mục .venv rồi chạy lại script.' }
if ($venvVersion[-1] -ne '1') {
    Stop-Setup ".venv đang dùng Python $($venvVersion[0]) (cần >= 3.11). Xóa thư mục .venv rồi chạy lại script với Python mới."
}

# ---------- 3. Thư viện ----------
Write-Step 'Cài thư viện (requirements-dev.txt), lần đầu mất vài phút'
& $venvPython -m pip install --disable-pip-version-check -q -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { Stop-Setup 'pip install thất bại, xem lỗi ở trên.' }
Write-Ok 'Thư viện đã đủ.'

# ---------- 4. File .env + sinh khóa bí mật ----------
Write-Step 'Chuẩn bị .env và sinh khóa bí mật (SECRET_KEY, FIELD_ENCRYPTION_KEY, MASTER_PASSWORD)'
& $venvPython ensure_env.py
if ($LASTEXITCODE -ne 0) { Stop-Setup 'Không chuẩn bị được .env (xem lỗi ở trên).' }
Write-Ok '.env đã sẵn sàng (khóa còn trống được tự sinh, không in giá trị).'

# ---------- 5. CSDL: tự tạo bảng + seed nếu là CSDL mới ----------
# bootstrap_db.py: CSDL mới -> tạo bảng + seed; CSDL đã có dữ liệu -> giữ nguyên; chưa kết nối được -> mã 3.
Write-Step 'Chuẩn bị CSDL (tự tạo bảng + seed nếu CSDL mới)'
$dbReady = $true
& $venvPython bootstrap_db.py
$dbExit = $LASTEXITCODE
if ($dbExit -eq 3) {
    $dbReady = $false
    Write-Note 'Chưa kết nối được CSDL. Khởi động CSDL (vd: docker compose up -d ở gốc repo) rồi chạy lại setup.ps1.'
} elseif ($dbExit -ne 0) {
    Stop-Setup "Lỗi chuẩn bị CSDL (mã $dbExit), xem lỗi ở trên."
} else {
    Write-Ok 'CSDL đã sẵn sàng.'
}

# ---------- 6. cloudflared (để mở link công khai) ----------
Write-Step 'Kiểm tra cloudflared (chỉ cần khi mở link cho nhiều máy)'
$cloudflared = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cloudflared) {
    $cloudflared = @("${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe", "$env:ProgramFiles\cloudflared\cloudflared.exe") |
        Where-Object { Test-Path $_ } | Select-Object -First 1
}
if ($cloudflared) { Write-Ok 'Đã có cloudflared.' } else { Write-Note 'Chưa có cloudflared. Khi cần mở link công khai: winget install --id Cloudflare.cloudflared' }

# ---------- 7. Test ----------
if (-not $SkipTests) {
    Write-Step 'Chạy bộ test (không cần CSDL)'
    & $venvPython -m pytest -q
    if ($LASTEXITCODE -ne 0) { Stop-Setup 'Có test thất bại, xem lỗi ở trên.' }
    Write-Ok 'Toàn bộ test đều qua.'
}

Write-Host "`nCài đặt xong. Các lệnh tiếp theo (trong thư mục src):" -ForegroundColor Cyan
Write-Host '    .venv\Scripts\python run.py                                   # chạy trên máy mình: http://127.0.0.1:5000'
Write-Host '    powershell -ExecutionPolicy Bypass -File .\run_public.ps1     # mở link HTTPS cho nhiều máy cùng test'
Write-Host '    Đăng nhập Master: tài khoản MASTER_USERNAME, mật khẩu MASTER_PASSWORD trong .env'
if (-not $dbReady) { exit 2 }
