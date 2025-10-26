@echo off
setlocal
REM Always run relative to this file
cd /d "%~dp0"

REM ===== Settings =====
set "ENTRY=app\Main.py"   REM App entry (capital M)
set "PORT=8501"           REM Fixed single port

REM Locate pythonw.exe inside your Conda env (try common paths)
set "PYW=%UserProfile%\.conda\envs\streamlit-app\pythonw.exe"
if not exist "%PYW%" set "PYW=%UserProfile%\anaconda3\envs\streamlit-app\pythonw.exe"
if not exist "%PYW%" set "PYW=%UserProfile%\miniconda3\envs\streamlit-app\pythonw.exe"
if not exist "%PYW%" set "PYW=C:\ProgramData\anaconda3\envs\streamlit-app\pythonw.exe"

if not exist "%PYW%" (
  echo [Error] Cannot find pythonw.exe for env "streamlit-app".
  echo Please edit PYW path in this file.
  pause
  exit /b 1
)

REM If an existing server is already listening on 8501, open browser and quit
for /f "tokens=5" %%A in ('netstat -ano ^| findstr /r /c:":%PORT% .*LISTENING"') do (
  start "" http://localhost:%PORT%/
  exit /b 0
)

REM Start a new server (no console window because we use pythonw.exe)
start "" "%PYW%" -m streamlit run "%ENTRY%" --server.port %PORT% --server.headless=false --logger.level=error

REM Immediately exit this launcher
exit /b 0
