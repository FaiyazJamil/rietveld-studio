@echo off
cd /d "%~dp0"
set "RIETVELD_PYTHON=.venv-rietveld\Scripts\python.exe"
if not exist "%RIETVELD_PYTHON%" set "RIETVELD_PYTHON=.venv\Scripts\python.exe"
if not exist "%RIETVELD_PYTHON%" (
  echo Run setup_windows.ps1 first. See START_HERE.md.
  pause
  exit /b 1
)
set "GSASII_PATH=%~dp0.engine\GSAS-II"
"%RIETVELD_PYTHON%" -m rietveld_studio %*
if errorlevel 1 pause

