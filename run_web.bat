@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Dang khoi dong Web UI tai http://127.0.0.1:8080 ...
python main.py --web
pause
