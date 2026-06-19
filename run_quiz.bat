@echo off
:: ─────────────────────────────────────────────────────────────
:: Obsidian Daily Quiz Generator — scheduled every 3 hours
:: Runs generate_quiz.py and logs output to run_quiz.log
:: ─────────────────────────────────────────────────────────────
setlocal

:: Path where you cloned the repo
set REPO=C:\Users\ravin\Desktop\Obsidian_Daily_Quiz

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
python "%REPO%\generate_quiz.py" >> "%LOGFILE%" 2>&1

echo Run finished: %DATE% %TIME% >> "%LOGFILE%"

endlocal
