"""
Smart Alerts Scheduler.

Provides functions to run alert detection on a schedule and documents
how to wire this up with Windows Task Scheduler.

Usage (manual):
    python -m ai.smart_alerts.scheduler --mode hourly
    python -m ai.smart_alerts.scheduler --mode daily

Windows Task Scheduler (one-time setup):
    1. Open Task Scheduler → Create Basic Task
    2. Name: "Analytics Smart Alerts - Hourly"
    3. Trigger: Daily, repeat every 1 hour
    4. Action: Start a program
       Program/script: C:\\path\\to\\python.exe
       Arguments:  -m ai.smart_alerts.scheduler --mode hourly
       Start in:   C:\\Users\\rajas\\web-analytics
    5. Repeat for "daily" mode with "Once a day" trigger

The scheduler writes a timestamped log to data/processed/alerts/scheduler.log.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ALERTS_DIR = ROOT / "data" / "processed" / "alerts"
ALERTS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE   = ALERTS_DIR / "scheduler.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def run_hourly_check() -> None:
    """
    Lightweight hourly alert check.
    Runs traffic anomaly detection and bounce spike check only.
    Saves any new alerts to the DB and logs a summary line.
    """
    logger.info("Starting hourly alert check...")
    try:
        from ai.smart_alerts.detector import SmartAlertDetector
        from ai.smart_alerts.alert_models import AlertSummary
        from ai.smart_alerts.run_alerts import _load_traffic_df, _save_alerts_to_db

        df = _load_traffic_df()
        detector = SmartAlertDetector()
        alerts   = (
            detector.detect_traffic_anomalies(df)
            + detector.detect_bounce_spikes(df)
        )
        summary  = AlertSummary.from_alerts(alerts)
        inserted = _save_alerts_to_db(alerts)
        logger.info(
            "Hourly check complete: %d alerts detected (%d critical, %d warning), %d saved to DB.",
            summary.total_alerts, summary.critical_count, summary.warning_count, inserted,
        )
    except Exception as exc:
        logger.error("Hourly check failed: %s", exc)
        raise


def run_daily_check() -> None:
    """
    Full daily alert sweep — runs all detectors and saves a markdown report.
    """
    logger.info("Starting daily full alert sweep...")
    try:
        from ai.smart_alerts.run_alerts import run_pipeline
        summary = run_pipeline(save_to_db=True, verbose=False)
        logger.info(
            "Daily check complete: %d alerts (%d critical, %d warning). All clear: %s.",
            summary.total_alerts, summary.critical_count, summary.warning_count,
            summary.all_clear,
        )
    except Exception as exc:
        logger.error("Daily check failed: %s", exc)
        raise


def schedule_alerts(mode: str = "daily") -> None:
    """
    Entry point for scheduled execution.
    mode: 'hourly' | 'daily'
    """
    logger.info("Scheduler invoked with mode=%s", mode)
    if mode == "hourly":
        run_hourly_check()
    elif mode == "daily":
        run_daily_check()
    else:
        logger.error("Unknown mode: %s. Use 'hourly' or 'daily'.", mode)
        sys.exit(1)


def get_next_run_time(mode: str = "hourly") -> datetime:
    """
    Return the next scheduled run time.
    - hourly: next full hour (e.g. if now is 14:23 → 15:00)
    - daily:  next midnight
    """
    now = datetime.now()
    if mode == "hourly":
        next_run = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    else:
        next_run = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return next_run


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart Alerts Scheduler")
    parser.add_argument(
        "--mode",
        choices=["hourly", "daily"],
        default="daily",
        help="Run mode: 'hourly' (traffic + bounce) or 'daily' (full sweep)",
    )
    args = parser.parse_args()

    next_run = get_next_run_time(args.mode)
    logger.info("Next scheduled run after this one: %s", next_run.strftime("%Y-%m-%d %H:%M"))
    schedule_alerts(args.mode)
