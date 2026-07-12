# PSX Trade Desk cycle runner. Called by Task Scheduler every 30 min.
# Decides: skip (market closed/holiday), full (first run of day), or light cycle.
# Logs everything to logs\.

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$now = Get-Date   # assumes system clock is PKT
$stamp = $now.ToString("yyyy-MM-dd_HHmm")
$logFile = Join-Path $Root "logs\$stamp.log"
New-Item -ItemType Directory -Force -Path (Join-Path $Root "logs") | Out-Null

function Log($msg) { "$((Get-Date).ToString('HH:mm:ss')) $msg" | Tee-Object -FilePath $logFile -Append }

# --- market open? ---  (-Force bypasses all gates for manual testing)
$force = $args -contains "-Force"
$dow = $now.DayOfWeek
if (-not $force -and ($dow -eq "Saturday" -or $dow -eq "Sunday")) { Log "weekend, skip"; exit 0 }

$calPath = Join-Path $Root "state\calendar.json"
if (Test-Path $calPath) {
    $cal = Get-Content $calPath -Raw | ConvertFrom-Json
    $today = $now.ToString("yyyy-MM-dd")
    if ($cal.holidays -contains $today) { Log "holiday ($today), skip"; exit 0 }
}

$t = $now.TimeOfDay
$preMarketStart = [TimeSpan]"08:40"
if ($dow -eq "Friday") { $close = [TimeSpan]"16:35" } else { $close = [TimeSpan]"15:35" }
if (-not $force -and ($t -lt $preMarketStart -or $t -gt $close.Add([TimeSpan]"00:30"))) { Log "outside hours, skip"; exit 0 }
# Friday Jumma break: sessions are 09:17-12:00 and 14:32-16:30, skip the gap
if (-not $force -and $dow -eq "Friday" -and $t -gt [TimeSpan]"12:10" -and $t -lt [TimeSpan]"14:25") { Log "friday jumma break, skip"; exit 0 }

# --- full or light? full = first run of the day (before 09:30), or forced ---
$mode = "light"
$flagPath = Join-Path $Root "state\last_full_run.txt"
$today = $now.ToString("yyyy-MM-dd")
$lastFull = if (Test-Path $flagPath) { (Get-Content $flagPath -Raw).Trim() } else { "" }
if ($lastFull -ne $today) { $mode = "full" }
if ($args -contains "-Full") { $mode = "full" }

$prompt = Get-Content (Join-Path $Root "prompts\cycle-$mode.md") -Raw
Log "mode=$mode starting claude -p"

& claude -p $prompt --permission-mode acceptEdits 2>&1 | Tee-Object -FilePath $logFile -Append
$code = $LASTEXITCODE
Log "claude exited $code"

if ($mode -eq "full" -and $code -eq 0) { $today | Out-File $flagPath -Encoding ascii -NoNewline }
exit $code
