@echo off
rem Builds the Windows app into dist\Shorts Toolkit and (if Inno Setup is installed) the installer.
cd /d "%~dp0.."
.venv\Scripts\python -m PyInstaller --noconfirm --clean --distpath dist --workpath build\pyi packaging\ShortsToolkit.spec || exit /b 1
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" packaging\installer.iss
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss
