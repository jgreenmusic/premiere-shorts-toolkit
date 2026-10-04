@echo off
rem Runs every test. Use it after any change and before building an installer.
rem   check.cmd          everything (about ten seconds; makes a test video and renders one Short)
rem   check.cmd quick    skips the render
cd /d "%~dp0"
set FAILED=0
.venv\Scripts\python.exe tests\test_logic.py || set FAILED=1
if /i "%~1"=="quick" (
  .venv\Scripts\python.exe tests\test_app.py QuickParts QuickPublish QuickServer || set FAILED=1
) else (
  .venv\Scripts\python.exe tests\test_app.py || set FAILED=1
)
echo.
if "%FAILED%"=="1" (
  echo SOMETHING FAILED - read the lines above.
  exit /b 1
)
echo ALL GOOD
