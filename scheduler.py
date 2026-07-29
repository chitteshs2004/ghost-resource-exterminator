"""
scheduler.py
============
Cron-job automation for Ghost Resource Exterminator.

Uses the Python `schedule` library to run zombie scans automatically
on a configurable interval. Run this as a background process.

Usage:
    python scheduler.py              # Runs daily at 08:00 AM
    python scheduler.py --interval 6 # Runs every 6 hours

Also see: cron_setup.sh for Linux/macOS cron-based scheduling.
"""

from __future__ import annotations
from typing import Optional
import schedule  # type: ignore[import-not-found]
import time
import sys
import os
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data/scheduler.log", mode="a"),
    ],
)
logger = logging.getLogger(__name__)


def run_scheduled_scan() -> None:
    """
    Scheduled scan job — called automatically by the scheduler.
    Runs a full zombie detection scan and saves results to DB.
    """
    logger.info("=" * 55)
    logger.info("⏰ Scheduled scan starting...")
    logger.info("=" * 55)

    try:
        from zombie_detector import scan_all  # type: ignore[import-not-found]
        resources = scan_all(clear_before_scan=True)
        zombies = [r for r in resources if r["status"] == "Zombie"]
        logger.info(f"✅ Scan complete. Found {len(zombies)} zombie resources.")
    except Exception as e:
        logger.error(f"❌ Scheduled scan failed: {e}", exc_info=True)

    logger.info(f"⏭️  Next scan scheduled automatically.")


def start_scheduler(daily_time: str = "08:00", interval_hours: Optional[int] = None) -> None:
    """
    Starts the scheduling loop.

    Args:
        daily_time: Time of day to run daily (HH:MM, 24-hour format).
                    Used only when interval_hours is None.
        interval_hours: If set, run every N hours instead of daily.
    """
    os.makedirs("data", exist_ok=True)  # Ensure log directory exists

    if interval_hours:
        logger.info(f"🕐 Scheduler started — every {interval_hours} hour(s)")
        schedule.every(interval_hours).hours.do(run_scheduled_scan)
    else:
        logger.info(f"🕐 Scheduler started — daily at {daily_time}")
        schedule.every().day.at(daily_time).do(run_scheduled_scan)

    # Run an immediate scan on startup
    logger.info("🚀 Running immediate scan on startup...")
    run_scheduled_scan()

    # Keep the scheduler alive in a loop
    logger.info("🔄 Scheduler is running. Press Ctrl+C to stop.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logger.info("🛑 Scheduler stopped by user.")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    args = sys.argv[1:]  # type: ignore

    # Parse --interval flag (e.g. --interval 6 for every 6 hours)
    interval = None
    if "--interval" in args:
        idx = args.index("--interval")
        try:
            raw_val: str = args[idx + 1]
            interval = int(raw_val)
        except (IndexError, ValueError):
            print("Usage: python scheduler.py --interval <hours>")
            sys.exit(1)

    start_scheduler(interval_hours=interval)
