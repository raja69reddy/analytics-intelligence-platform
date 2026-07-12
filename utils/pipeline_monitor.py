"""Pipeline run logging, history, stats, and failure alerting."""

import json
import logging
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "data" / "processed"
LOG_DIR = REPORTS_DIR / "pipeline_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

_HISTORY_FILE = LOG_DIR / "pipeline_history.json"

logger = logging.getLogger(__name__)


def _load_history() -> list[dict]:
    if _HISTORY_FILE.exists():
        try:
            return json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_history(history: list[dict]) -> None:
    _HISTORY_FILE.write_text(
        json.dumps(history, indent=2, default=str), encoding="utf-8"
    )


def log_pipeline_run(name: str, rows: int, duration: float, status: str) -> dict:
    """Append a pipeline run record and return it."""
    record = {
        "name": name,
        "rows": rows,
        "duration_s": round(duration, 2),
        "status": status,
        "timestamp": datetime.now().isoformat(),
    }
    history = _load_history()
    history.append(record)
    _save_history(history)
    logger.info(
        f"Logged pipeline run: {name} status={status} rows={rows} duration={duration:.1f}s"
    )
    return record


def get_pipeline_history(limit: int = 10) -> list[dict]:
    """Return the last `limit` run records (newest first)."""
    history = _load_history()
    return list(reversed(history))[:limit]


def get_pipeline_stats() -> dict[str, dict]:
    """
    Return per-pipeline stats: avg_duration_s, success_rate_pct, total_runs.
    """
    history = _load_history()
    stats: dict[str, dict] = {}
    for rec in history:
        name = rec["name"]
        if name not in stats:
            stats[name] = {"total_runs": 0, "successes": 0, "total_duration_s": 0.0}
        s = stats[name]
        s["total_runs"] += 1
        if rec.get("status") == "success":
            s["successes"] += 1
        s["total_duration_s"] += rec.get("duration_s", 0.0)

    result = {}
    for name, s in stats.items():
        result[name] = {
            "total_runs": s["total_runs"],
            "success_rate_pct": round(s["successes"] / s["total_runs"] * 100, 1),
            "avg_duration_s": round(s["total_duration_s"] / s["total_runs"], 2),
        }
    return result


def alert_on_failure(pipeline_name: str, error: str) -> None:
    """Log a failure alert and append it to the alert log file."""
    alert_log = LOG_DIR / "alerts.log"
    ts = datetime.now().isoformat()
    message = f"[{ts}] PIPELINE FAILURE: {pipeline_name} — {error}"
    logger.error(message)
    with open(alert_log, "a", encoding="utf-8") as f:
        f.write(message + "\n")


def save_run_report(report: dict) -> Path:
    """Save a pipeline run report dict as JSON to data/processed/."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORTS_DIR / f"pipeline_report_{ts}.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    logger.info(f"Pipeline report saved: {path}")
    return path
