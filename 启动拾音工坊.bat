@echo off
chcp 65001 >nul
title ???? - ??????
cd /d "%~dp0"
set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY if exist "C:\Users\CH\WorkBuddy\?????\.venv\Scripts\python.exe" set "PY=C:\Users\CH\WorkBuddy\?????\.venv\Scripts\python.exe"
if not defined PY set "PY=python"
"%PY%" "workbench\server.py" --port 8780 --force
pause
