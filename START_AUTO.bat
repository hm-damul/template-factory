@echo off
REM START_AUTO.bat
REM - 한 번 실행으로: Dashboard + Payment + Preview + Auto-Mode(자동 생성)까지 자동 기동
REM - 정상 루트만 선택(START.bat과 동일 로직)
REM 실행:
REM   더블클릭 또는 CMD에서: START_AUTO.bat

setlocal enabledelayedexpansion
set SCRIPT_DIR=%~dp0

REM root 선택
set ROOT=
if exist "%SCRIPT_DIR%requirements.txt" if exist "%SCRIPT_DIR%dashboard_server.py" (
  set ROOT=%SCRIPT_DIR%
) else (
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

REM Dashboard start (minimized)
if not exist "logs" mkdir "logs"
echo [INFO] Starting dashboard...
start "" /min cmd /c "python dashboard_server.py >> logs\dashboard_boot.log 2>&1"

REM Wait for health (max 60s)
set OK=0
for /l %%I in (1,1,60) do (
  powershell -NoProfile -Command "try{(Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:8099/health).StatusCode}catch{0}" | find "200" >nul && (set OK=1 & goto :ready)
  timeout /t 1 >nul
)

:ready
if "%OK%"=="0" (
  echo [FAIL] dashboard health check timeout (http://127.0.0.1:8099/health)
  echo        Check logs\dashboard_boot.log
  exit /b 1
)

echo [INFO] Starting payment server...
powershell -NoProfile -Command "Invoke-WebRequest -UseBasicParsing -TimeoutSec 10 http://127.0.0.1:8099/action/start_payment | Out-Null"

echo [INFO] Starting preview server...
powershell -NoProfile -Command "Invoke-WebRequest -UseBasicParsing -TimeoutSec 10 http://127.0.0.1:8099/action/start_preview | Out-Null"

echo [INFO] Starting auto-mode (create+deploy+publish)...
powershell -NoProfile -Command "$b=@{interval='3600';auto_batch='1';auto_deploy='1';auto_publish='1'}; Invoke-WebRequest -UseBasicParsing -TimeoutSec 10 -Method Post http://127.0.0.1:8099/action/start_auto_mode -Body $b | Out-Null"

echo.
echo ===============================================
echo Dashboard: http://127.0.0.1:8099/
echo Payment  : started
echo Preview  : started
echo AutoMode : started (interval 3600s, batch 1)
echo ===============================================
echo.

start "" "http://127.0.0.1:8099/"
endlocal
