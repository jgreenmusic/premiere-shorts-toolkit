@echo off
rem Starts Shorts Auto Run in its own window: every step in one go, then your review and sign-off.
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" desktop.py --autorun
