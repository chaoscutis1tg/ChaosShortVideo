@echo off
chcp 65001 >nul
title ChaosShortVideo - Local ^& LAN Web Studio (Port 8000)

echo ====================================================================
echo   CHAOSSHORTVIDEO - KHOI DONG HE THONG LOCAL ^& MANG LAN (PORT 8000)
echo   - Tren may chu nay:    http://127.0.0.1:8000
echo   - Dien thoai / LAN:    Xem dia chi IP LAN hien tren thanh tieu de Web
echo ====================================================================

cd /d "%~dp0"
if not exist ".env" (
    copy ".env.example" ".env" >nul
)

netsh advfirewall firewall show rule name="ShortVideo Studio AI LAN (TCP 8000)" >nul 2>&1
if errorlevel 1 (
    netsh advfirewall firewall add rule name="ShortVideo Studio AI LAN (TCP 8000)" dir=in action=allow protocol=TCP localport=8000 >nul 2>&1
)

set PYTHONPATH=%~dp0backend
start "" cmd /c "timeout /t 2 >nul & start http://127.0.0.1:8000"
python -m uvicorn app.m07_studio_api.main:app --host 0.0.0.0 --port 8000
pause
