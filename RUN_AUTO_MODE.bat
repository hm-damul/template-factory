@echo off
cd /d "%~dp0"
echo Checking and installing dependencies...
pip install -r requirements.txt >nul 2>&1

echo Starting Dashboard Server (Web UI)...
start "Dashboard Server" cmd /k "python dashboard_server.py"

echo Starting Payment Server (5000)...
start "Payment Server" /min cmd /c "python backend/payment_server.py"

echo Starting Preview Server (8088)...
start "Preview Server" /min cmd /c "python preview_server.py"

echo Waiting for Dashboard to initialize...
set "DASHBOARD_URL=http://localhost:8099"
set "MAX_RETRIES=30"
set "RETRY_COUNT=0"

:check_dashboard
timeout /t 2 >nul
powershell -Command "try { $r = Invoke-WebRequest -Uri '%DASHBOARD_URL%/health' -UseBasicParsing; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }"
if %errorlevel% equ 0 (
    echo Dashboard is UP!
    goto :open_browser
)

set /a RETRY_COUNT+=1
if %RETRY_COUNT% geq %MAX_RETRIES% (
    echo [WARNING] Dashboard did not start within 60 seconds.
    echo Please check the 'Dashboard Server' window for errors.
    goto :start_daemon
)

echo Waiting for dashboard... (%RETRY_COUNT%/%MAX_RETRIES%)
goto :check_dashboard

:open_browser
echo Opening Dashboard in Browser...
start %DASHBOARD_URL%

:start_daemon
echo Starting Auto Promotion Mode (Daemon)...
python auto_mode_daemon.py
echo Daemon stopped unexpectedly. Restarting in 5 seconds...
timeout /t 5
goto :start_daemon
