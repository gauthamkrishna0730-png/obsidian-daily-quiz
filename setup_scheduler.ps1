# ─────────────────────────────────────────────────────────────
# setup_scheduler.ps1
# Run once (as Admin) to register the daily quiz task in
# Windows Task Scheduler — fires at 6:30 AM every day
# ─────────────────────────────────────────────────────────────

$taskName   = "ObsidianDailyQuiz"
$scriptPath = "C:\Users\gauth\Downloads\obsidian-daily-quiz-main\obsidian-daily-quiz-main\run_daily.bat"
$triggerTime = "06:30"

$action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$scriptPath`""
$trigger = New-ScheduledTaskTrigger -Daily -At $triggerTime
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
            -StartWhenAvailable -WakeToRun

Register-ScheduledTask `
    -TaskName   $taskName `
    -Action     $action `
    -Trigger    $trigger `
    -Settings   $settings `
    -Description "Generate 30 fresh Dermatology quiz questions from Obsidian vault every morning" `
    -RunLevel   Highest `
    -Force

Write-Host ""
Write-Host "✅  Task '$taskName' scheduled for $triggerTime daily." -ForegroundColor Green
Write-Host "    To run immediately: Start-ScheduledTask -TaskName '$taskName'"
Write-Host "    To remove:          Unregister-ScheduledTask -TaskName '$taskName'"
