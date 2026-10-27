@echo off
title Orbit AI Windows Local Agent
echo ================================================================
echo Starting Orbit AI Windows Local Agent on http://127.0.0.1:8001
echo ================================================================

if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0start_local_agent.py"
) else (
    python "%~dp0start_local_agent.py"
)
pause
