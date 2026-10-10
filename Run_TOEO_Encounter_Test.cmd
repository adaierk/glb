@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  set "TOEO_PYTHON=python"
) else (
  set "TOEO_PYTHON=py -3"
)
%TOEO_PYTHON% -c "import frida; import PIL" >nul 2>nul
if errorlevel 1 (
  %TOEO_PYTHON% -m pip install frida pillow
  if errorlevel 1 exit /b 1
)
%TOEO_PYTHON% toeo-tests\run_session_bootstrap.py "%~1" --local-account --local-world --demo-character --world-profile rashuan --combat-preview --duration 0 --out local_world_userdata
pause
