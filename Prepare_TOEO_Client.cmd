@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  set "TOEO_PYTHON=python"
) else (
  set "TOEO_PYTHON=py -3"
)
%TOEO_PYTHON% toeo-tests\prepare_original_client.py "%~1"
pause
