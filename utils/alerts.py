"""
Alert checking functions for traffic anomalies, conversion drops, data freshness,
and error rates. Alerts are logged to the database alerts table or a flat file.
"""
import logging
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALERT_LOG = ROOT / "data" / "processed" / "pipeline_logs" / "alerts.log"
ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)

TRAFFIC_DROP_THRESHOLD  = 0.30   # 30% drop
CVR_DROP_THRESHOLD      = 0.20   # 20% drop
FRESHNESS_HOURS         = 24
ERROR_RATE_THRESHOLD    = 0.05   # 5%


def _qdf(sql: str):
    from utils.db import query_df
    return query_df(sql)


def check_traffic_anomalies() -> dict:
    """Alert if traffic dropped more than 30% vs prior 7-day average."""
    try:
        df = _qdf("""
            WITH daily AS (
                SELECT session_date, SUM(sessions) AS daily_sessions
                FROM raw_ga4_sessions GROUP BY session_date
            ),
            latest AS (SELECT MAX(session_date) AS today FROM daily),
            recent AS (
                SELECT AVG(daily_sessions) AS avg_last_7
                FROM daily, latest
                WHERE session_date BETWEEN today - 7 AND today - 1
            ),
            yesterday AS (
                SELECT daily_sessions AS yesterday_sessions
                FROM daily, latest WHERE session_date = today - 1
            )
            SELECT
                l.today,
                r.avg_last_7,
                y.yesterday_sessions,
                ROUND((y.yesterday_sessions - r.avg_last_7) / NULLIF(r.avg_last_7, 0) * 100, 2) AS pct_change
            FROM latest l, recent r, yesterday y
        """)
        if df.empty:
            return {"status": "ok", "message": "Insufficient data"}

        pct_change = float(df["pct_change"].iloc[0] or 0)
        drop = pct_change / 100
        if drop < -TRAFFIC_DROP_THRESHOLD:
            msg = f"Traffic dropped {abs(pct_change):.1f}% vs 7-day avg (threshold: {TRAFFIC_DROP_THRESHOLD*100:.0f}%)"
            send_alert(msg, severity="critical")
            return {"status": "alert", "severity": "critical", "message": msg, "pct_change": pct_change}
        return {"status": "ok", "pct_change": pct_change}
    except Exception as exc:
        logger.error(f"check_traffic_anomalies error: {exc}")
        return {"status": "error", "message": str(exc)}


def check_conversion_drop() -> dict:
    """Alert if today's CVR dropped more than 20% vs 7-day average."""
    try:
        df = _qdf("""
            WITH daily AS (
                SELECT session_date,
                       ROUND(SUM(conversions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 4) AS cvr
                FROM raw_ga4_sessions GROUP BY session_date
            ),
            latest AS (SELECT MAX(session_date) AS today FROM daily),
            avg7   AS (
                SELECT AVG(cvr) AS avg_cvr_7d FROM daily, latest
                WHERE session_date BETWEEN today - 7 AND today - 1
            ),
            yday   AS (
                SELECT cvr AS yesterday_cvr FROM daily, latest WHERE session_date = today - 1
            )
            SELECT a.avg_cvr_7d, y.yesterday_cvr,
                   ROUND((y.yesterday_cvr - a.avg_cvr_7d) / NULLIF(a.avg_cvr_7d, 0) * 100, 2) AS pct_change
            FROM avg7 a, yday y
        """)
        if df.empty:
            return {"status": "ok", "message": "Insufficient data"}

        pct_change = float(df["pct_change"].iloc[0] or 0)
        if pct_change / 100 < -CVR_DROP_THRESHOLD:
            msg = f"CVR dropped {abs(pct_change):.1f}% vs 7-day avg (threshold: {CVR_DROP_THRESHOLD*100:.0f}%)"
            send_alert(msg, severity="critical")
            return {"status": "alert", "severity": "critical", "message": msg, "pct_change": pct_change}
        return {"status": "ok", "pct_change": pct_change}
    except Exception as exc:
        logger.error(f"check_conversion_drop error: {exc}")
        return {"status": "error", "message": str(exc)}


def check_data_freshness() -> dict:
    """Alert if the most recent GA4 ingest is older than FRESHNESS_HOURS."""
    try:
        df = _qdf("SELECT MAX(ingested_at) AS last_ingest FROM raw_ga4_sessions")
        last_ingest = df["last_ingest"].iloc[0]
        if last_ingest is None:
            msg = "No data in raw_ga4_sessions"
            send_alert(msg, severity="warning")
            return {"status": "alert", "severity": "warning", "message": msg}

        last_dt = last_ingest if hasattr(last_ingest, "hour") else datetime.fromisoformat(str(last_ingest))
        # strip timezone for comparison if present
        if hasattr(last_dt, "tzinfo") and last_dt.tzinfo is not None:
            last_dt = last_dt.replace(tzinfo=None)
        age_h = (datetime.now() - last_dt).total_seconds() / 3600

        if age_h > FRESHNESS_HOURS:
            msg = f"Data is {age_h:.1f}h old (threshold: {FRESHNESS_HOURS}h)"
            severity = "critical" if age_h > 48 else "warning"
            send_alert(msg, severity=severity)
            return {"status": "alert", "severity": severity, "message": msg, "age_hours": age_h}
        return {"status": "ok", "age_hours": round(age_h, 1)}
    except Exception as exc:
        logger.error(f"check_data_freshness error: {exc}")
        return {"status": "error", "message": str(exc)}


def check_error_rate() -> dict:
    """Alert if the server log error rate (4xx+5xx) exceeds ERROR_RATE_THRESHOLD."""
    try:
        df = _qdf("""
            SELECT
                COUNT(*) AS total_requests,
                COUNT(CASE WHEN status_code >= 400 THEN 1 END) AS error_requests,
                ROUND(COUNT(CASE WHEN status_code >= 400 THEN 1 END)::NUMERIC
                      / NULLIF(COUNT(*), 0) * 100, 2) AS error_rate_pct
            FROM raw_server_logs
            WHERE log_time >= NOW() - INTERVAL '24 hours'
        """)
        if df.empty or int(df["total_requests"].iloc[0]) == 0:
            return {"status": "ok", "message": "No server log data in last 24h"}

        error_rate = float(df["error_rate_pct"].iloc[0] or 0) / 100
        if error_rate > ERROR_RATE_THRESHOLD:
            msg = f"Error rate is {error_rate*100:.1f}% (threshold: {ERROR_RATE_THRESHOLD*100:.0f}%)"
            severity = "critical" if error_rate > 0.10 else "warning"
            send_alert(msg, severity=severity)
            return {"status": "alert", "severity": severity, "message": msg, "error_rate_pct": error_rate * 100}
        return {"status": "ok", "error_rate_pct": round(error_rate * 100, 2)}
    except Exception as exc:
        logger.error(f"check_error_rate error: {exc}")
        return {"status": "error", "message": str(exc)}


def send_alert(message: str, severity: str = "warning") -> None:
    """Log alert to file and logger."""
    ts = datetime.now().isoformat()
    entry = f"[{ts}] [{severity.upper()}] {message}"
    logger.warning(entry)
    try:
        with open(ALERT_LOG, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except OSError as exc:
        logger.error(f"Failed to write alert log: {exc}")


def run_all_checks() -> list[dict]:
    """Run all checks and return list of results."""
    checks = [
        ("traffic_anomalies", check_traffic_anomalies),
        ("conversion_drop",   check_conversion_drop),
        ("data_freshness",    check_data_freshness),
        ("error_rate",        check_error_rate),
    ]
    results = []
    for name, fn in checks:
        result = fn()
        result["check"] = name
        results.append(result)
    return results
