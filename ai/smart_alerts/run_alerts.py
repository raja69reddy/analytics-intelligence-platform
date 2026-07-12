"""
Smart alerts pipeline script.
Loads latest traffic data from PostgreSQL, runs SmartAlertDetector,
saves alerts to the DB alerts table, prints a summary, and saves
a markdown report to data/processed/alerts/.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

ALERTS_DIR = ROOT / "data" / "processed" / "alerts"
ALERTS_DIR.mkdir(parents=True, exist_ok=True)


def _load_traffic_df():
    """Load daily traffic data from vw_daily_traffic."""
    from utils.db import query_df

    return query_df("SELECT * FROM vw_daily_traffic ORDER BY session_date")


def _load_conversions_df():
    """Load daily conversion data for CVR analysis."""
    from utils.db import query_df

    return query_df("""
        SELECT session_date,
               SUM(sessions)         AS sessions,
               SUM(goal_completions) AS goal_completions
        FROM vw_conversions
        GROUP BY session_date
        ORDER BY session_date
    """)


def _save_alerts_to_db(alerts: list) -> int:
    """Insert alert records into the alerts table. Returns inserted count."""
    if not alerts:
        return 0
    from utils.db import get_engine
    from sqlalchemy import text

    engine = get_engine()
    inserted = 0
    with engine.begin() as conn:
        for alert in alerts:
            conn.execute(
                text("""
                INSERT INTO alerts
                    (alert_type, severity, message, recommended_action)
                VALUES
                    (:at, :sev, :msg, :rec)
            """),
                {
                    "at": alert.alert_type,
                    "sev": alert.severity.value.lower(),
                    "msg": alert.message,
                    "rec": alert.recommended_action,
                },
            )
            inserted += 1
    return inserted


def _save_report(summary, report_path: Path) -> None:
    """Write markdown alert report to disk."""
    lines = [
        "# Smart Alerts Report\n",
        f"**Generated:** {summary.generated_at.strftime('%Y-%m-%d %H:%M')}\n\n",
        "---\n\n",
        "## Summary\n\n",
        "| Metric | Value |\n|--------|-------|\n",
        f"| Total Alerts | {summary.total_alerts} |\n",
        f"| Critical | {summary.critical_count} |\n",
        f"| Warning | {summary.warning_count} |\n",
        f"| All Clear | {'Yes' if summary.all_clear else 'No'} |\n\n",
        "---\n\n",
        "## Alert Details\n\n",
    ]
    if not summary.alerts:
        lines.append("_No alerts detected._\n")
    else:
        for i, alert in enumerate(summary.alerts, 1):
            icon = "🔴" if alert.severity.value == "CRITICAL" else "🟡"
            lines += [
                f"### {i}. {icon} [{alert.severity.value}] {alert.title}\n\n",
                f"**Type:** `{alert.alert_type}`\n\n",
                f"**Message:** {alert.message}\n\n",
                f"**Recommended Action:** {alert.recommended_action}\n\n",
            ]
            if alert.metric_value is not None:
                lines.append(f"**Metric Value:** {alert.metric_value}\n\n")
            lines.append("---\n\n")

    report_path.write_text("".join(lines), encoding="utf-8")


def run_pipeline(save_to_db: bool = True, verbose: bool = True):
    """Main alert pipeline. Returns AlertSummary."""
    from ai.smart_alerts.detector import SmartAlertDetector
    from ai.smart_alerts.alert_models import AlertSummary

    if verbose:
        print("Loading traffic data from PostgreSQL...")
    df_traffic = _load_traffic_df()
    df_conv = _load_conversions_df()

    if verbose:
        print(f"  Traffic rows: {len(df_traffic)}")
        print(f"  Conversion rows: {len(df_conv)}")

    detector = SmartAlertDetector()

    # Run detectors
    alerts = detector.run_all(df_traffic)

    # CVR drops need the conversions dataframe
    alerts.extend(detector.detect_conversion_drops(df_conv))

    summary = AlertSummary.from_alerts(alerts)

    # Print summary
    if verbose:
        sep = "=" * 55
        print(f"\n{sep}")
        print("  SMART ALERTS SUMMARY")
        print(sep)
        print(f"  Total alerts:    {summary.total_alerts}")
        print(f"  Critical:        {summary.critical_count}")
        print(f"  Warning:         {summary.warning_count}")
        print(f"  All clear:       {summary.all_clear}")
        print(sep)
        if summary.alerts:
            print("\nSample alert messages:")
            for alert in summary.alerts[:3]:
                icon = (
                    "[CRITICAL]" if alert.severity.value == "CRITICAL" else "[WARNING]"
                )
                print(f"  {icon} {alert.title}")
                print(f"         {alert.message[:100]}")
                print()

    # Save to DB
    if save_to_db:
        inserted = _save_alerts_to_db(alerts)
        if verbose:
            print(f"Saved {inserted} alert(s) to PostgreSQL alerts table.")

    # Save markdown report
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    path = ALERTS_DIR / f"alert_report_{ts}.md"
    _save_report(summary, path)
    if verbose:
        print(f"Report saved: {path}")

    return summary


if __name__ == "__main__":
    summary = run_pipeline(save_to_db=True, verbose=True)
    sys.exit(0)
