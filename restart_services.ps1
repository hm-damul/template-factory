
# Restart all services
Write-Host "Stopping existing Python processes..."
taskkill /F /IM python.exe /T
Start-Sleep -Seconds 2

Write-Host "Starting Payment Server (Port 5000)..."
$payment = Start-Process python -ArgumentList "backend/payment_server.py" -PassThru -WindowStyle Hidden
Write-Host "Payment Server PID: $($payment.Id)"

Write-Host "Starting Dashboard Server (Port 8099)..."
$dashboard = Start-Process python -ArgumentList "dashboard_server.py" -PassThru -WindowStyle Hidden
Write-Host "Dashboard Server PID: $($dashboard.Id)"

Write-Host "Starting Preview Server (Port 8088)..."
$preview = Start-Process python -ArgumentList "preview_server.py" -PassThru -WindowStyle Hidden
Write-Host "Preview Server PID: $($preview.Id)"

Write-Host "Starting Auto Daemon..."
$daemon = Start-Process python -ArgumentList "auto_mode_daemon.py" -PassThru -WindowStyle Hidden
Write-Host "Auto Daemon PID: $($daemon.Id)"

Write-Host "All services restarted."
