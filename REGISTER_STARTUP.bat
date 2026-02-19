@echo off
set "TARGET=%~dp0RUN_BACKGROUND.vbs"
set "SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\MetaPassiveIncome.lnk"
echo Creating startup shortcut...
powershell "$s=(New-Object -COM WScript.Shell).CreateShortcut('%SHORTCUT%');$s.TargetPath='%TARGET%';$s.WorkingDirectory='%~dp0';$s.Save()"
echo Done! The system will now start automatically when you log in.
echo You can close this window.
pause
