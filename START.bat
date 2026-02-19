@echo off
REM START.bat
REM - "cd 없이" 실행 가능한 런처(정상 루트만 선택)
REM - legacy_versions 무시 + 중첩 폴더 제외 + requirements.txt 우선
REM - venv 생성/활성화
REM - requirements 설치
REM - 대시보드 실행 (http://127.0.0.1:8099)

setlocal enabledelayedexpansion
set SCRIPT_DIR=%~dp0

REM (A) 스크립트 폴더 자체가 정상 루트면 그대로 사용
set ROOT=
if exist "%SCRIPT_DIR%requirements.txt" if exist "%SCRIPT_DIR%dashboard_server.py" (
  set ROOT=%SCRIPT_DIR%
) else (
  REM (B) 아니면 requirements.txt + dashboard_server.py 조합을 얕게 찾기(최대 4단계)
  for /f "delims=" %%D in ('dir /ad /b /s "%SCRIPT_DIR%" 2^>nul') do (
    echo %%D | find /i "\legacy_versions\" >nul && goto :cont
    echo %%D | find /i "\runs\" >nul && goto :cont
    echo %%D | find /i "\sample_outputs\" >nul && goto :cont
    if exist "%%D\requirements.txt" if exist "%%D\dashboard_server.py" (
      set ROOT=%%D\
      goto :found
    )
    :cont
  )
)

:found
if "%ROOT%"=="" (
  echo [FAIL] Normal project root not found under: %SCRIPT_DIR%
  echo        Expected: requirements.txt + dashboard_server.py (excluding legacy_versions / runs / sample_outputs)
  exit /b 1
)

echo [OK] PROJECT_ROOT = %ROOT%
cd /d "%ROOT%"

if not exist ".venv" (
  echo [INFO] Creating venv...
  python -m venv .venv
)

echo [INFO] Activating venv...
call ".venv\Scripts\activate.bat"

echo [INFO] Upgrading pip...
python -m pip install --upgrade pip

echo [INFO] Installing requirements...
python -m pip install -r requirements.txt

echo.
echo ===============================================
echo Dashboard: http://127.0.0.1:8099/
echo ===============================================
echo.

python dashboard_server.py
endlocal
