@echo off
cd /d "%~dp0"
echo Checking and installing dependencies...
pip install -r requirements.txt
echo Starting Interactive Channel Setup...
python interactive_setup.py
pause