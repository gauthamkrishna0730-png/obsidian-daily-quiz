@echo off
:: ─────────────────────────────────────────────────────────────
:: Obsidian Daily Quiz — Daily runner (Task Scheduler safe)
:: Credentials loaded from .env — never hardcoded here
:: ─────────────────────────────────────────────────────────────
cd /d "C:\Users\gauth\Downloads\obsidian-daily-quiz-main\obsidian-daily-quiz-main"

if not exist logs mkdir logs
echo [%DATE% %TIME%] Starting... >> logs\run.log

:: ── Load credentials from .env ───────────────────────────────
for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
    set "%%A=%%B"
)

:: ── Fix: force Python to see user site-packages ──────────────
set "PYTHONPATH=C:\Users\gauth\AppData\Roaming\Python\Python312\site-packages;%PYTHONPATH%"
set "PYTHONUSERBASE=C:\Users\gauth\AppData\Roaming\Python"

:: ── Run with full Python path ─────────────────────────────────
"C:\Users\gauth\AppData\Local\Programs\Python\Python312\python.exe" -X utf8 generate_quiz.py >> logs\run.log 2>&1

if %ERRORLEVEL% EQU 0 (
    echo [%DATE% %TIME%] SUCCESS >> logs\run.log
) else (
    echo [%DATE% %TIME%] FAILED with exit code %ERRORLEVEL% >> logs\run.log
)

exit /b 0
