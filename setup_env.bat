@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title ChaosShortVideo - Cai Dat Moi Truong Tu Dong (Fresh Clone Setup)

echo ============================================================================
echo   CHAOSSHORTVIDEO - CAI DAT MOI TRUONG TU DONG SAU KHI CLONE TU GITHUB
echo ============================================================================
echo.

cd /d "%~dp0"

:: [1/6] Kiem tra Python 3.10+ va Node.js
echo [1/6] Kiem tra Python va Node.js tren may...
where python >nul 2>&1
if errorlevel 1 goto :NO_PYTHON

where npm >nul 2>&1
if errorlevel 1 goto :NO_NODE

for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo   - Da tim thay %%i
for /f "tokens=*" %%i in ('node --version 2^>^&1') do echo   - Da tim thay Node.js %%i

:: [2/6] Khoi tao tep cau hinh .env neu chua co
echo.
echo [2/6] Khoi tao tep cau hinh .env...
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo   - Da tao tep .env tu .env.example
) else (
    echo   - Giu nguyen tep .env hien co
)

:: [3/6] Tao moi truong ao Python (.venv)
echo.
echo [3/6] Thiet lap moi truong ao Python (.venv)...
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 goto :ERR_VENV
)
set "PY_EXE=%~dp0.venv\Scripts\python.exe"
"%PY_EXE%" -m pip install --upgrade pip wheel setuptools >nul

:: [4/6] Tu dong nhan dien Card NVIDIA RTX/GTX de cai PyTorch CUDA hoac CPU
echo.
echo [4/6] Cai dat PyTorch va thu vien Backend AI...
nvidia-smi >nul 2>&1
if errorlevel 1 goto :INSTALL_CPU_TORCH

echo   - Phat hien Card do hoa NVIDIA! Dang cai PyTorch CUDA 12.4 + cuBLAS/cuDNN...
"%PY_EXE%" -m pip install torch --index-url https://download.pytorch.org/whl/cu124
if errorlevel 1 (
    echo   - Thu lai voi kenh PyTorch CUDA 12.6 cho Python phien ban moi...
    "%PY_EXE%" -m pip install torch --index-url https://download.pytorch.org/whl/cu126
)
"%PY_EXE%" -m pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
goto :INSTALL_REQS

:INSTALL_CPU_TORCH
echo   - Khong phat hien Card NVIDIA, dang cai PyTorch ban CPU on dinh...
"%PY_EXE%" -m pip install torch

:INSTALL_REQS
echo   - Dang cai dat danh sach thu vien trong backend\requirements.txt...
"%PY_EXE%" -m pip install -r backend\requirements.txt
if errorlevel 1 goto :ERR_PIP

:: [5/6] Cai thu vien va dong goi Giao dien Web React (frontend/dist)
echo.
echo [5/6] Dong goi giao dien Web Frontend (npm install ^& npm run build)...
pushd frontend
call npm install
if errorlevel 1 (
    popd
    goto :ERR_NPM
)
call npm run build
if errorlevel 1 (
    popd
    goto :ERR_NPM
)
popd

:: [6/6] Tai FFmpeg 7.0.2 NVENC + Giong Offline Ngoc Huyen va Kiem tra tong the
echo.
echo [6/6] Tai cong cu FFmpeg NVENC, giong doc Offline va kiem tra he thong...
"%PY_EXE%" scripts\bootstrap_assets.py

echo ============================================================================
echo   HOAN TAT CAI DAT! Ban co the bam dup vao "start_studio.bat" de su dung ngay!
echo ============================================================================
pause
exit /b 0

:NO_PYTHON
echo [LOI] May chua cai Python ^(3.10 - 3.12^)!
echo Vui long tai Python tai: https://www.python.org/downloads/
echo ^(Luu y tich chon o "Add Python to PATH" khi cai dat^)
pause
exit /b 1

:NO_NODE
echo [LOI] May chua cai Node.js ^(18 LTS hoac 20 LTS^)!
echo Vui long tai Node.js tai: https://nodejs.org/
pause
exit /b 1

:ERR_VENV
echo [LOI] Khong the tao moi truong ao .venv. Vui long kiem tra lai Python.
pause
exit /b 1

:ERR_PIP
echo [LOI] Qua trinh cai thu vien Python gap su co mang. Hay chay lai setup_env.bat.
pause
exit /b 1

:ERR_NPM
echo [LOI] Qua trinh build giao dien Frontend that bai. Hay kiem tra Node.js / mang Internet.
pause
exit /b 1
