Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "d:\auto\MetaPassiveIncome_FINAL"
WshShell.Run chr(34) & "d:\auto\MetaPassiveIncome_FINAL\RUN_AUTO_MODE.bat" & chr(34), 0
Set WshShell = Nothing
