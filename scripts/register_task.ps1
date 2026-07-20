# Registers the Windows Task Scheduler job for the desk loop.
# RUN THIS MANUALLY when ready to go live (spec gate: 5 clean manual runs first).
#   powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1
# Remove with: Unregister-ScheduledTask -TaskName "Henneth" -Confirm:$false

# The task NAME is a functional identifier, not a display string. The 2026-07-19 rebrand
# renamed it "PSX Trade Desk" -> "Henneth"; Task Scheduler has no rename, so simply
# changing the string would leave the OLD task still registered and firing alongside the
# new one — two cycles racing on one checkout. Retire the old name first, explicitly.
$LegacyName = "PSX Trade Desk"
if (Get-ScheduledTask -TaskName $LegacyName -ErrorAction SilentlyContinue) {
    Write-Host "Removing legacy task '$LegacyName' (renamed to 'Henneth')..."
    Unregister-ScheduledTask -TaskName $LegacyName -Confirm:$false
}

$Root = Split-Path -Parent $PSScriptRoot
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Root\scripts\run_desk.ps1`"" `
    -WorkingDirectory $Root

# Every 30 min, 08:45-16:45 daily; run_desk.ps1 itself skips weekends/holidays/closed hours.
$trigger = New-ScheduledTaskTrigger -Daily -At "08:45"
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At "08:45" `
    -RepetitionInterval (New-TimeSpan -Minutes 30) `
    -RepetitionDuration (New-TimeSpan -Hours 8)).Repetition

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Minutes 25)

Register-ScheduledTask -TaskName "Henneth" -Action $action -Trigger $trigger `
    -Settings $settings -Description "Henneth 30-min cycle (run_desk.ps1 gates market hours)" -Force

Write-Host "Registered. Verify with: Get-ScheduledTask -TaskName 'Henneth'"
