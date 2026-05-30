@echo off
:: ─────────────────────────────────────────────────────────────
:: Obsidian Daily Quiz – run this file every morning
:: Add it to Windows Task Scheduler to auto-run at 6 AM
:: ─────────────────────────────────────────────────────────────
cd /d "C:\Users\ravin\Desktop\Obsidian_Daily_Quiz"

:: Load env vars from .env file
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    set "%%A=%%B"
)

:: Run the generator
python generate_quiz.py

:: Open the quiz in browser after generation
start "" "https://gauthamkrishna0730-png.github.io/obsidian-daily-quiz/"

echo.
echo Done! Quiz is live.
pause
