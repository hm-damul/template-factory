# Helper script to push changes
$gitExe = "C:\Program Files\Git\cmd\git.exe"
if (-not (Test-Path $gitExe)) {
    $gitExe = "git"
}

& $gitExe add .
& $gitExe commit -m "Update requirements and configs for autonomous mode"
& $gitExe push origin main --force
Write-Host "Push completed."
