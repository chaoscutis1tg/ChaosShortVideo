@echo off
chcp 65001 >nul
title ChaosShortVideo - Local ^& LAN Web Studio (Port 8000)

echo ====================================================================
echo   CHAOSSHORTVIDEO - KHOI DONG HE THONG LOCAL ^& MANG LAN (PORT 8000)
echo   - Tren may chu nay:    http://127.0.0.1:8000
echo   - Dien thoai / LAN:    Xem nut QR LAN tren thanh tieu de Web
echo ====================================================================

cd /d "%~dp0"

:: Neu vua clone tu GitHub chua build giao dien -> tu dong chay setup_env.bat
if not exist "%~dp0frontend\dist\index.html" (
    echo [THONG BAO] Phat hien lan chay dau tien sau khi clone GitHub!
    echo Dang tu dong thiet lap moi truong qua setup_env.bat...
    call "%~dp0setup_env.bat"
    if errorlevel 1 exit /b 1
)

if not exist ".env" (
    copy ".env.example" ".env" >nul
)

set "PY_EXE=python"
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY_EXE=%~dp0.venv\Scripts\python.exe"
)

if not exist "%~dp0assets\bin\ffmpeg.exe" (
    echo [THONG BAO] Dang bo sung cong cu FFmpeg va tai nguyen khoi dong...
    "%PY_EXE%" "%~dp0scripts\bootstrap_assets.py"
)

netsh advfirewall firewall show rule name="ChaosShortVideo LAN (TCP 8000)" >nul 2>&1
if errorlevel 1 (
    netsh advfirewall firewall add rule name="ChaosShortVideo LAN (TCP 8000)" dir=in action=allow protocol=TCP localport=8000 >nul 2>&1
)

set "PATH=%~dp0assets\bin;%PATH%"
set "PYTHONPATH=%~dp0backend"
start "" cmd /c "timeout /t 2 >nul & start http://127.0.0.1:8000"
"%PY_EXE%" -m uvicorn app.m07_studio_api.main:app --host 0.0.0.0 --port 8000
pause
