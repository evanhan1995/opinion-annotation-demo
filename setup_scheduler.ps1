# -*- coding: utf-8 -*-
# setup_scheduler.ps1 — Register Windows Task Scheduler tasks for 舆情标注Wiki
#
# Usage (run as Administrator):
#   powershell -ExecutionPolicy Bypass -File setup_scheduler.ps1
#
# Creates TWO approaches (choose one):
#   Option A (recommended): Single boot task → python scheduler.py daemon
#   Option B: Individual timed tasks → python scheduler.py --daily / --pipeline / --monitor
#
# The Python scheduler daemon reads config/scheduler_config.json for actual times.
# Option A is simpler — one task, scheduler handles all timing internally.

param(
    [string]$PythonPath = "python",
    [string]$ProjectDir = "D:\Claude code\舆情标注Wiki",
    [string]$TaskPrefix = "舆情标注Wiki",
    [switch]$OptionB = $false
)

$ErrorActionPreference = "Stop"
$schedulerScript = Join-Path $ProjectDir "scheduler.py"

# Verify project exists
if (-not (Test-Path $schedulerScript)) {
    Write-Error "scheduler.py not found at: $schedulerScript"
    exit 1
}

# ── Option A: Single daemon task (starts on boot) ────────────────────
if (-not $OptionB) {
    $taskName = "$TaskPrefix-调度器守护进程"
    Write-Host "=== Option A: Registering single daemon task ===" -ForegroundColor Cyan
    Write-Host "Task: $taskName"
    Write-Host "Command: $PythonPath `"$schedulerScript`""
    Write-Host "Trigger: At system startup"
    Write-Host ""

    # Delete existing task if present
    schtasks /Delete /TN $taskName /F 2>$null

    schtasks /Create `
        /TN $taskName `
        /TR "$PythonPath `"$schedulerScript`"" `
        /SC ONSTART `
        /DELAY 0001:00 `
        /RL HIGHEST `
        /F

    Write-Host "Task created. The scheduler will run continuously and handle:" -ForegroundColor Green
    Write-Host "  - Daily report (time from config/scheduler_config.json)"
    Write-Host "  - Pipeline (time/frequency from config)"
    Write-Host "  - Monitor patrol (interval from config)"
    Write-Host ""
    Write-Host "To start immediately: schtasks /Run /TN `"$taskName`"" -ForegroundColor Yellow
    Write-Host "To stop:            schtasks /End /TN `"$taskName`"" -ForegroundColor Yellow
    Write-Host "To remove:          schtasks /Delete /TN `"$taskName`" /F" -ForegroundColor Yellow
}
else {
    # ── Option B: Individual timed tasks ─────────────────────────────
    Write-Host "=== Option B: Registering individual timed tasks ===" -ForegroundColor Cyan
    Write-Host "Times are from config/scheduler_config.json defaults:"
    Write-Host "  Daily report: 21:07"
    Write-Host "  Pipeline:     22:07"
    Write-Host "  Monitor:      00:07, 06:07, 12:07, 18:07"
    Write-Host ""

    $tasks = @(
        @{Name="日报生成"; Time="21:07"; Arg="--daily"},
        @{Name="流水线执行"; Time="22:07"; Arg="--pipeline"},
        @{Name="Monitor巡检-00"; Time="00:07"; Arg="--monitor"},
        @{Name="Monitor巡检-06"; Time="06:07"; Arg="--monitor"},
        @{Name="Monitor巡检-12"; Time="12:07"; Arg="--monitor"},
        @{Name="Monitor巡检-18"; Time="18:07"; Arg="--monitor"}
    )

    foreach ($t in $tasks) {
        $tn = "$TaskPrefix-$($t.Name)"
        schtasks /Delete /TN $tn /F 2>$null
        schtasks /Create `
            /TN $tn `
            /TR "$PythonPath `"$schedulerScript`" $($t.Arg)" `
            /SC DAILY `
            /ST $t.Time `
            /RL HIGHEST `
            /F
        Write-Host "  Created: $tn @ $($t.Time)" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Done. Use 'schtasks /Query /TN `"$TaskPrefix-*`"' to verify." -ForegroundColor Cyan
