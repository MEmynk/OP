@echo off
setlocal EnableDelayedExpansion
title Order Priority System
cd /d "%~dp0"

echo ==========================================================
echo    ORDER PRIORITY SYSTEM
echo ==========================================================
echo.

REM ---------- 1. Python check ----------
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY python --version >nul 2>&1 && set "PY=python"

if not defined PY (
  echo [X] Python nahi mila.
  echo.
  echo     https://www.python.org/downloads/  se Python install karo.
  echo     Install karte waqt "Add Python to PATH" ka box zaroor tick karna.
  echo.
  pause
  exit /b 1
)
echo [OK] Python mil gaya.

REM ---------- 2. Virtual environment ----------
if not exist ".venv\Scripts\python.exe" (
  echo [..] Pehli baar chal raha hai - environment ban raha hai...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo [X] Environment nahi ban paya.
    pause
    exit /b 1
  )
  set "FIRSTRUN=1"
)

call ".venv\Scripts\activate.bat"

REM ---------- 3. Libraries ----------
if defined FIRSTRUN goto install
".venv\Scripts\python.exe" -c "import streamlit, pandas" >nul 2>&1
if errorlevel 1 goto install
goto run

:install
echo [..] Libraries install ho rahi hain - 2-3 minute lag sakte hain...
echo      (Internet chalu rakhna. Ye sirf pehli baar hota hai.)
echo.
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
if exist "requirements.txt" (
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
) else (
  ".venv\Scripts\python.exe" -m pip install streamlit pandas gspread openpyxl
)
if errorlevel 1 (
  echo.
  echo [X] Install fail ho gaya. Internet check karo aur dobara chalao.
  pause
  exit /b 1
)
echo [OK] Sab install ho gaya.

:run
if not exist "app.py" (
  echo [X] app.py is folder me nahi hai.
  echo     Is .bat file ko app.py wale folder me hi rakho.
  pause
  exit /b 1
)

echo.
echo ==========================================================
echo   Dashboard khul raha hai... browser apne aap open hoga.
echo   Address:  http://localhost:8501
echo.
echo   BAND KARNE KE LIYE: is black window me Ctrl+C dabao
echo   ya window band kar do.
echo ==========================================================
echo.

".venv\Scripts\python.exe" -m streamlit run app.py

echo.
echo Dashboard band ho gaya.
pause