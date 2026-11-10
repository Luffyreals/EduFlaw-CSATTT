<#
Chạy EduFlaw ở chế độ production và mở link HTTPS công khai qua Cloudflare Quick Tunnel,
để nhiều máy cùng truy cập và test. Xem docs/DEPLOY.md, mục 4.

Cách chạy (từ thư mục src):
    powershell -ExecutionPolicy Bypass -File .\run_public.ps1
    powershell -ExecutionPolicy Bypass -File .\run_public.ps1 -Http2    # khi mạng chặn QUIC

Link công khai (https://<tên ngẫu nhiên>.trycloudflare.com) nằm trong khung cloudflared in ra
và đổi sau mỗi lần chạy. Bấm Ctrl+C để dừng cả tunnel lẫn máy chủ.
#>
param(
    [int]$Port = 8000,
    [switch]$Http2
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Write-Error 'Chưa có môi trường ảo src\.venv. Làm theo mục 1 trong docs/DEPLOY.md.'
}
if (-not (Test-Path (Join-Path $PSScriptRoot '.env'))) {
    Write-Error 'Chưa có file src\.env. Sao chép từ .env.example rồi điền giá trị thật.'
}
# Terminal mở trước khi cài cloudflared chưa có nó trong PATH: tìm thêm ở thư mục winget cài mặc định
$cloudflared = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cloudflared) {
    $cloudflared = @("${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe", "$env:ProgramFiles\cloudflared\cloudflared.exe") |
        Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $cloudflared) {
    Write-Error 'Chưa cài cloudflared. Chạy: winget install --id Cloudflare.cloudflared'
}

$portInUse = $false
try {
    $client = New-Object Net.Sockets.TcpClient
    $client.Connect('127.0.0.1', $Port)
    $client.Close()
    $portInUse = $true
} catch {}
if ($portInUse) {
    Write-Error "Cổng $Port đang bị chiếm (có thể app đang chạy ở terminal khác). Tắt nó hoặc thêm -Port <cổng khác>."
}

# Chỉ áp dụng cho tiến trình này, không sửa .env.
# HOST=127.0.0.1: chỉ nhận request đi qua tunnel, không mở thẳng ra mạng LAN.
$env:APP_ENV = 'production'
$env:TRUST_PROXY = '1'
$env:HOST = '127.0.0.1'
$env:PORT = "$Port"

$server = Start-Process -FilePath $python -ArgumentList 'serve.py' -NoNewWindow -PassThru
try {
    $ready = $false
    for ($i = 0; $i -lt 60 -and -not $ready; $i++) {
        Start-Sleep -Seconds 1
        if ($server.HasExited) {
            throw 'Máy chủ dừng ngay khi khởi động. Xem lỗi ở trên (thường do thiếu biến trong .env).'
        }
        try {
            Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 "http://127.0.0.1:$Port/healthz" | Out-Null
            $ready = $true
        } catch {}
    }
    if (-not $ready) {
        throw "Máy chủ không phản hồi ở cổng $Port sau 60 giây (kiểm tra kết nối CSDL trong .env)."
    }
    Write-Host "Máy chủ đã chạy ở http://127.0.0.1:$Port. Đang mở tunnel, link công khai sẽ hiện trong khung bên dưới..."

    $tunnelArgs = @('tunnel')
    if ($Http2) { $tunnelArgs += @('--protocol', 'http2') }
    $tunnelArgs += @('--url', "http://127.0.0.1:$Port")
    & $cloudflared @tunnelArgs
}
finally {
    if (-not $server.HasExited) {
        Stop-Process -Id $server.Id -Force
    }
}
