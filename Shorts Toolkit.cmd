@echo off
rem Starts the Shorts Toolkit app in your browser.
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" app.py
