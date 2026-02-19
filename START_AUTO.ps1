# -*- coding: utf-8 -*-
<#
START_AUTO.ps1
- 한 번 실행으로: Dashboard + Payment + Preview + Auto-Mode(자동 생성)까지 자동 기동
- 정상 루트만 선택(START.ps1과 동일 로직)
- 실행 후 브라우저로 대시보드 오픈

실행:
  powershell -ExecutionPolicy Bypass -File .\START_AUTO.ps1
#>

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Test-ProjectRoot([string]$Path) {
  return (Test-Path (Join-Path $Path "requirements.txt")) -and (Test-Path (Join-Path $Path "dashboard_server.py"))
}

$Root = $null
if (Test-ProjectRoot $ScriptDir) {
  $Root = $ScriptDir
} else {
  $Candidates = Get-ChildItem -Path $ScriptDir -Recurse -Depth 4 -Directory -ErrorAction SilentlyContinue |
    Where-Object {
      $_.FullName -notmatch "\\legacy_versions(\\|$)" -and
      $_.FullName -notmatch "\\runs(\\|$)" -and
      $_.FullName -notmatch "\\sample_outputs(\\|$)" -and
      (Test-Path (Join-Path $_.FullName "requirements.txt")) -and
      (Test-Path (Join-Path $_.FullName "dashboard_server.py"))
    } |
    Sort-Object { $_.FullName.Length }
  if ($Candidates -and $Candidates.Count -gt 0) { $Root = $Candidates[0].FullName }
}

if (-not $Root) {
  Write-Host "[FAIL] Normal project root not found under: $ScriptDir"
  exit 1
}

Write-Host "[OK] PROJECT_ROOT = $Root"
Set-Location $Root

# venv
if (!(Test-Path ".\.venv")) {
  Write-Host "[INFO] Creating venv..."
  python -m venv .venv
}
Write-Host "[INFO] Activating venv..."
& .\.venv\Scripts\Activate.ps1

Write-Host "[INFO] Upgrading pip..."
python -m pip install --upgrade pip

Write-Host "[INFO] Installing requirements..."
python -m pip install -r .\requirements.txt

# Dashboard 백그라운드 실행
$dashLog = Join-Path $Root "logs\dashboard_boot.log"
New-Item -ItemType Directory -Force -Path (Join-Path $Root "logs") | Out-Null

Write-Host "[INFO] Starting dashboard..."
Start-Process -FilePath $env:COMSPEC -ArgumentList "/c", "python dashboard_server.py >> `"$dashLog`" 2>&1" -WorkingDirectory $Root -WindowStyle Minimized | Out-Null

# health 체크 대기
$ok = $false
for ($i=0; $i -lt 60; $i++) {
  try {
    $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 -Uri "http://127.0.0.1:8099/health"
    if ($r.StatusCode -eq 200) { $ok = $true; break }
  } catch { Start-Sleep -Seconds 1 }
}

if (-not $ok) {
  Write-Host "[FAIL] dashboard health check timeout (http://127.0.0.1:8099/health)"
  Write-Host "       Check logs: $dashLog"
  exit 1
}

# Payment / Preview / Auto-Mode 자동 기동
Write-Host "[INFO] Starting payment server..."
Invoke-WebRequest -UseBasicParsing -TimeoutSec 10 -Uri "http://127.0.0.1:8099/action/start_payment" | Out-Null

Write-Host "[INFO] Starting preview server..."
Invoke-WebRequest -UseBasicParsing -TimeoutSec 10 -Uri "http://127.0.0.1:8099/action/start_preview" | Out-Null

Write-Host "[INFO] Starting auto-mode (create+deploy+publish)..."
$body = @{
  interval="3600"
  auto_batch="1"
  auto_deploy="1"
  auto_publish="1"
}
Invoke-WebRequest -UseBasicParsing -TimeoutSec 10 -Method Post -Uri "http://127.0.0.1:8099/action/start_auto_mode" -Body $body | Out-Null

Write-Host ""
Write-Host "==============================================="
Write-Host "Dashboard: http://127.0.0.1:8099/"
Write-Host "Payment  : started"
Write-Host "Preview  : started"
Write-Host "AutoMode : started (interval 3600s, batch 1)"
Write-Host "==============================================="
Write-Host ""

Start-Process "http://127.0.0.1:8099/" | Out-Null
