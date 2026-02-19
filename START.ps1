# -*- coding: utf-8 -*-
<#
START.ps1
- "cd 없이" 실행 가능한 런처(정상 루트만 선택)
- legacy_versions 무시 + 중첩 폴더 제외 + requirements.txt 우선
- venv 생성/활성화
- requirements 설치
- 대시보드 실행 (http://127.0.0.1:8099)

실행(PowerShell):
  우클릭 > PowerShell에서 실행
  또는:
  powershell -ExecutionPolicy Bypass -File .\START.ps1
#>

# 1) 이 스크립트 위치(정상 루트 후보)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Test-ProjectRoot([string]$Path) {
  return (Test-Path (Join-Path $Path "requirements.txt")) -and (Test-Path (Join-Path $Path "dashboard_server.py"))
}

# 2) 정상 루트 결정
$Root = $null

# (A) 스크립트가 있는 폴더 자체가 정상 루트면 그대로 사용(가장 안전)
if (Test-ProjectRoot $ScriptDir) {
  $Root = $ScriptDir
} else {
  # (B) 아니면 "requirements.txt + dashboard_server.py"가 함께 있는 폴더를 얕게 탐색
  $Candidates = Get-ChildItem -Path $ScriptDir -Recurse -Depth 4 -Directory -ErrorAction SilentlyContinue |
    Where-Object {
      $_.FullName -notmatch "\\legacy_versions(\\|$)" -and
      $_.FullName -notmatch "\\runs(\\|$)" -and
      $_.FullName -notmatch "\\sample_outputs(\\|$)" -and
      (Test-Path (Join-Path $_.FullName "requirements.txt")) -and
      (Test-Path (Join-Path $_.FullName "dashboard_server.py"))
    } |
    Sort-Object { $_.FullName.Length }

  if ($Candidates -and $Candidates.Count -gt 0) {
    $Root = $Candidates[0].FullName
  }
}

if (-not $Root) {
  Write-Host "[FAIL] Normal project root not found under: $ScriptDir"
  Write-Host "       Expected: requirements.txt + dashboard_server.py (excluding legacy_versions / runs / sample_outputs)"
  exit 1
}

Write-Host "[OK] PROJECT_ROOT = $Root"
Set-Location $Root

# 3) venv 생성
if (!(Test-Path ".\.venv")) {
  Write-Host "[INFO] Creating venv..."
  python -m venv .venv
}

# 4) venv 활성화
Write-Host "[INFO] Activating venv..."
& .\.venv\Scripts\Activate.ps1

# 5) pip 업데이트 + 의존성 설치
Write-Host "[INFO] Upgrading pip..."
python -m pip install --upgrade pip

Write-Host "[INFO] Installing requirements..."
python -m pip install -r .\requirements.txt

# 6) 대시보드 실행
Write-Host ""
Write-Host "==============================================="
Write-Host "Dashboard: http://127.0.0.1:8099/"
Write-Host "==============================================="
Write-Host ""

python .\dashboard_server.py
