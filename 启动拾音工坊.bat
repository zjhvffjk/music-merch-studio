@echo off
chcp 65001 >nul
title Music Merch Studio
cd /d "%~dp0"
set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"
if not defined PY set "PY=python"
"%PY%" "workbench\server.py" --force
pause
