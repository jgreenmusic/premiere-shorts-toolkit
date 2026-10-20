@echo off
rem Builds the Windows app into dist\Shorts Toolkit and (if Inno Setup is installed) the installer.
cd /d "%~dp0.."
.venv\Scripts\python -m PyInstaller --noconfirm --clean --distpath dist --workpath build\pyi packaging\ShortsToolkit.spec || exit /b 1
rem Licence texts of every library this build packed, plus the notices file, next to the app.
.venv\Scripts\python tools\collect_licenses.py || exit /b 1
xcopy /e /i /q /y build\licenses "dist\Shorts Toolkit\licenses" >nul || exit /b 1
copy /y THIRD-PARTY-NOTICES.md "dist\Shorts Toolkit\" >nul || exit /b 1
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" packaging\installer.iss
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss
