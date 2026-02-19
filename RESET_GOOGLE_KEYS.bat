@echo off
cd /d "%~dp0"
echo Clearing Google (Blogger/YouTube) Credentials...
python -c "import json, os; p='data/secrets.json'; s=json.load(open(p)) if os.path.exists(p) else {}; s.pop('BLOGGER_CLIENT_ID',0); s.pop('BLOGGER_CLIENT_SECRET',0); s.pop('YOUTUBE_CLIENT_ID',0); s.pop('YOUTUBE_CLIENT_SECRET',0); json.dump(s, open(p,'w'), indent=2)"
echo Done. You can now run SETUP_CHANNELS.bat again to enter new keys.
pause