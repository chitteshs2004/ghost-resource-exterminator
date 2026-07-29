#!/bin/bash
# ============================================================
# cron_setup.sh — Cron Job Setup for Ghost Resource Exterminator
# ============================================================
# This script adds a cron job that runs the zombie scanner
# automatically every day at 8:00 AM.
#
# Usage (Linux/macOS):
#   chmod +x cron_setup.sh
#   ./cron_setup.sh
# ============================================================

# Get the absolute path to this project
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$(which python3)"
RUN_SCRIPT="$PROJECT_DIR/run_scan.py"
LOG_FILE="$PROJECT_DIR/data/cron.log"

# ── Create log directory ────────────────────────────────────
mkdir -p "$PROJECT_DIR/data"

# ── Build the cron entry ────────────────────────────────────
# Schedule: Every day at 8:00 AM (24-hour format: minute hour day month weekday)
CRON_ENTRY="0 8 * * * $PYTHON_BIN $RUN_SCRIPT >> $LOG_FILE 2>&1"

# ── Add to crontab (only if it doesn't already exist) ───────
(crontab -l 2>/dev/null | grep -v "$RUN_SCRIPT"; echo "$CRON_ENTRY") | crontab -

echo "✅ Cron job added successfully!"
echo ""
echo "   Schedule : Every day at 08:00 AM"
echo "   Command  : $PYTHON_BIN $RUN_SCRIPT"
echo "   Log file : $LOG_FILE"
echo ""
echo "   To view current cron jobs, run: crontab -l"
echo "   To remove this job, run:        crontab -e"

# ── Windows Task Scheduler equivalent (PowerShell) ──────────
cat << 'EOF'

# ── For Windows users (run in PowerShell as Administrator) ──
# Uncomment and edit the lines below:

# $action  = New-ScheduledTaskAction -Execute "python" -Argument "C:\path\to\run_scan.py"
# $trigger = New-ScheduledTaskTrigger -Daily -At 8am
# Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "GhostResourceExterminator"

EOF
