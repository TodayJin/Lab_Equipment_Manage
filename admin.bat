@echo off
cd /d "%~dp0"

REM 优先用 venv 里的 Python，没有就用系统 Python
if exist "venv\Scripts\pythonw.exe" (
    start "" venv\Scripts\pythonw src\admin.py
) else if exist "venv\Scripts\python.exe" (
    start "" venv\Scripts\python src\admin.py
) else (
    start "" python src\admin.py
)
