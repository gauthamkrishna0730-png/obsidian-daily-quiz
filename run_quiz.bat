@echo off
:: ─────────────────────────────────────────────────────────────
:: Obsidian Daily Quiz Generator — scheduled every 3 hours
:: Runs generate_quiz.py and logs output to run_quiz.log
:: ─────────────────────────────────────────────────────────────
setlocal

:: Path where the repo lives
set REPO=C:\Users\gauth\Downloads\obsidian-daily-quiz-main\obsidian-daily-quiz-main

:: Log file (one file per day, appended every 3 hours)
set LOGFILE=%REPO%\run_quiz.log
echo. >> "%LOGFILE%"
echo ============================================================ >> "%LOGFILE%"
echo Run started: %DATE% %TIME% >> "%LOGFILE%"
echo ============================================================ >> "%LOGFILE%"

:: Pull latest changes before running (in case of manual edits)
cd /d "%REPO%"
git pull --no-rebase origin main >> "%LOGFILE%" 2>&1

:: Run the quiz generator
"C:\Users\gauth\AppData\Local\Programs\Python\Python312\python.exe" "%REPO%\generate_quiz.py" >> "%LOGFILE%" 2>&1

echo Run finished: %DATE% %TIME% >> "%LOGFILE%"

endlocal
