# START.ps1
# - "cd 없이" 실행 가능한 런처 (Windows PowerShell)
# - 프로젝트 루트를 자동 탐지(중첩 폴더여도 dashboard_server.py 위치를 찾아서 이동)
# - venv 생성/활성화
# - requirements 설치
# - 대시보드 실행 (http://127.0.0.1:8099)

$ErrorActionPreference = "Stop"

function Find-ProjectRoot {
    param(
        [string]$StartDir
    )

    # dashboard_server.py가 있는 디렉토리를 프로젝트 루트로 간주
    $candidates = Get-ChildItem -Path $StartDir -Recurse -Filter "dashboard_server.py" -ErrorAction SilentlyContinue

    if ($null -eq $candidates -or $candidates.Count -eq 0) {
        return $null
    }

    # 가장 먼저 발견된 파일의 폴더를 루트로 선택
    return (Split-Path -Parent $candidates[0].FullName)
}

try {
    # 1) 이 스크립트가 있는 폴더
    $Outer = Split-Path -Parent $MyInvocation.MyCommand.Path

    # 2) 프로젝트 루트 자동 탐지
    $Root = Find-ProjectRoot -StartDir $Outer
    if ([string]::IsNullOrWhiteSpace($Root)) {
        Write-Host "[FAIL] dashboard_server.py not found under: $Outer"
        Write-Host "압축을 풀었는데 폴더가 중첩되었거나, 파일이 누락된 상태일 수 있습니다."
        exit 1
    }

    Write-Host "[OK] PROJECT_ROOT = $Root"
    Set-Location $Root

    # 3) 파이프라인 핵심 파일 존재 체크
    if (-not (Test-Path ".\product_factory.py")) {
        Write-Host "[WARN] product_factory.py not found in PROJECT_ROOT."
        Write-Host "지금 루트가 구버전일 가능성이 큽니다."
        Write-Host "현재 위치: $Root"
        Write-Host "product_factory.py가 있는 폴더로 루트를 맞춰야 합니다."
    }

    # 4) venv 생성
    if (-not (Test-Path ".\.venv")) {
        Write-Host "[INFO] Creating venv..."
        python -m venv .venv
    }

    # 5) venv 활성화
    Write-Host "[INFO] Activating venv..."
    & .\.venv\Scripts\Activate.ps1

    # 6) pip 업그레이드 + requirements 설치
    Write-Host "[INFO] Upgrading pip..."
    python -m pip install --upgrade pip

    if (-not (Test-Path ".\requirements.txt")) {
        Write-Host "[FAIL] requirements.txt not found in PROJECT_ROOT: $Root"
        exit 1
    }

    Write-Host "[INFO] Installing requirements..."
    python -m pip install -r .\requirements.txt

    # 7) 대시보드 실행
    Write-Host ""
    Write-Host "==============================================="
    Write-Host "Dashboard URL: http://127.0.0.1:8099/"
    Write-Host "Stop: Ctrl+C"
    Write-Host "==============================================="
    Write-Host ""

    python .\dashboard_server.py
}
catch {
    Write-Host ""
    Write-Host "[FATAL] START.ps1 failed:"
    Write-Host $_.Exception.Message
    exit 1
}
