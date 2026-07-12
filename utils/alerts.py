"""
Smart alert checking functions for traffic, bounce rate, CVR, page speed,
AI anomalies, and data freshness. All alerts are logged to a flat file.
"""

import logging
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALERT_LOG = ROOT / "data" / "processed" / "pipeline_logs" / "alerts.log"
ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)

# Thresholds
TRAFFIC_DROP_DOD_THRESHOLD = 0.20  # 20% day-over-day drop
TRAFFIC_DROP_7D_THRESHOLD = 0.30  # 30% vs 7-day avg (legacy)
BOUNCE_SPIKE_THRESHOLD = 0.10  # 10% relative increase
CVR_DROP_THRESHOLD = 0.15  # 15% relative drop
PAGE_SPEED_THRESHOLD_MS = 2000  # ms
FRESHNESS_HOURS = 24
ERROR_RATE_THRESHOLD = 0.05  # 5%


def _qdf(sql: str):
    from utils.db import query_df

    return query_df(sql)


# ── Core alert functions ──────────────────────────────────────────────────────


def check_traffic_drop() -> dict:
    """Alert if sessions dropped >20% day-over-day."""
    try:
        df = _qdf("""
            WITH daily AS (
                SELECT session_date, SUM(sessions) AS s
                FROM raw_ga4_sessions GROUP BY session_date
            ),
            latest AS (SELECT MAX(session_date) AS today FROM daily),
            yday   AS (SELECT s AS y_sessions FROM daily, latest WHERE session_date = today - 1),
            d2ago  AS (SELECT s AS d2_sessions FROM daily, latest WHERE session_date = today - 2)
            SELECT y.y_sessions, d.d2_sessions,
                   ROUND((y.y_sessions - d.d2_sessions)::NUMERIC / NULLIF(d.d2_sessions, 0) * 100, 2) AS dod_pct
            FROM yday y, d2ago d
        """)
        if df.empty:
            return {
                "status": "ok",
                "message": "Insufficient data",
                "check": "traffic_drop",
            }
        dod = float(df["dod_pct"].iloc[0] or 0)
        if dod / 100 < -TRAFFIC_DROP_DOD_THRESHOLD:
            msg = f"Traffic dropped {abs(dod):.1f}% day-over-day (threshold: {TRAFFIC_DROP_DOD_THRESHOLD*100:.0f}%)"
            send_alert(msg, severity="critical")
            return {
                "status": "alert",
                "severity": "critical",
                "message": msg,
                "pct_change": dod,
                "recommended_action": "Check server health, tracking code, and recent deploys.",
                "check": "traffic_drop",
            }
        return {"status": "ok", "pct_change": dod, "check": "traffic_drop"}
    except Exception as exc:
        return {"status": "error", "message": str(exc), "check": "traffic_drop"}


def check_traffic_anomalies() -> dict:
    """Alert if traffic dropped >30% vs prior 7-day average (legacy)."""
    try:
        df = _qdf("""
            WITH daily AS (SELECT session_date, SUM(sessions) AS ds FROM raw_ga4_sessions GROUP BY session_date),
            latest AS (SELECT MAX(session_date) AS today FROM daily),
            recent AS (SELECT AVG(ds) avg7 FROM daily, latest WHERE session_date BETWEEN today - 7 AND today - 1),
            yday   AS (SELECT ds y_s FROM daily, latest WHERE session_date = today - 1)
            SELECT r.avg7, y.y_s,
                   ROUND((y.y_s - r.avg7) / NULLIF(r.avg7, 0) * 100, 2) AS pct_change
            FROM recent r, yday y
        """)
        if df.empty:
            return {
                "status": "ok",
                "message": "Insufficient data",
                "check": "traffic_anomalies",
            }
        pct = float(df["pct_change"].iloc[0] or 0)
        if pct / 100 < -TRAFFIC_DROP_7D_THRESHOLD:
            msg = f"Traffic dropped {abs(pct):.1f}% vs 7-day avg (threshold: {TRAFFIC_DROP_7D_THRESHOLD*100:.0f}%)"
            send_alert(msg, severity="critical")
            return {
                "status": "alert",
                "severity": "critical",
                "message": msg,
                "pct_change": pct,
                "recommended_action": "Review traffic sources and recent changes.",
                "check": "traffic_anomalies",
            }
        return {"status": "ok", "pct_change": pct, "check": "traffic_anomalies"}
    except Exception as exc:
        return {"status": "error", "message": str(exc), "check": "traffic_anomalies"}


def check_bounce_spike() -> dict:
    """Alert if bounce rate increased >10% relative vs prior day."""
    try:
        df = _qdf("""
            WITH daily AS (
                SELECT session_date,
                       ROUND(SUM(bounce::INT)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2) AS br
                FROM raw_ga4_sessions GROUP BY session_date
            ),
            latest AS (SELECT MAX(session_date) AS today FROM daily),
            yday   AS (SELECT br y_br FROM daily, latest WHERE session_date = today - 1),
            d2ago  AS (SELECT br d2_br FROM daily, latest WHERE session_date = today - 2)
            SELECT y.y_br, d.d2_br,
                   ROUND((y.y_br - d.d2_br) / NULLIF(d.d2_br, 0) * 100, 2) AS rel_change_pct
            FROM yday y, d2ago d
        """)
        if df.empty:
            return {
                "status": "ok",
                "message": "Insufficient data",
                "check": "bounce_spike",
            }
        rel = float(df["rel_change_pct"].iloc[0] or 0)
        if rel / 100 > BOUNCE_SPIKE_THRESHOLD:
            msg = f"Bounce rate spiked {rel:.1f}% relative to prior day (threshold: {BOUNCE_SPIKE_THRESHOLD*100:.0f}%)"
            send_alert(msg, severity="warning")
            return {
                "status": "alert",
                "severity": "warning",
                "message": msg,
                "pct_change": rel,
                "recommended_action": "Review landing page changes and traffic quality.",
                "check": "bounce_spike",
            }
        return {"status": "ok", "pct_change": rel, "check": "bounce_spike"}
    except Exception as exc:
        return {"status": "error", "message": str(exc), "check": "bounce_spike"}


def check_conversion_drop() -> dict:
    """Alert if CVR dropped >15% day-over-day."""
    try:
        df = _qdf("""
            WITH daily AS (
                SELECT session_date,
                       ROUND(SUM(conversions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 4) AS cvr
                FROM raw_ga4_sessions GROUP BY session_date
            ),
            latest AS (SELECT MAX(session_date) AS today FROM daily),
            avg7   AS (SELECT AVG(cvr) avg_cvr FROM daily, latest WHERE session_date BETWEEN today - 7 AND today - 1),
            yday   AS (SELECT cvr y_cvr FROM daily, latest WHERE session_date = today - 1)
            SELECT a.avg_cvr, y.y_cvr,
                   ROUND((y.y_cvr - a.avg_cvr) / NULLIF(a.avg_cvr, 0) * 100, 2) AS pct_change
            FROM avg7 a, yday y
        """)
        if df.empty:
            return {
                "status": "ok",
                "message": "Insufficient data",
                "check": "conversion_drop",
            }
        pct = float(df["pct_change"].iloc[0] or 0)
        if pct / 100 < -CVR_DROP_THRESHOLD:
            msg = f"CVR dropped {abs(pct):.1f}% vs 7-day avg (threshold: {CVR_DROP_THRESHOLD*100:.0f}%)"
            send_alert(msg, severity="critical")
            return {
                "status": "alert",
                "severity": "critical",
                "message": msg,
                "pct_change": pct,
                "recommended_action": "Check checkout flow, payment gateway, and offers.",
                "check": "conversion_drop",
            }
        return {"status": "ok", "pct_change": pct, "check": "conversion_drop"}
    except Exception as exc:
        return {"status": "error", "message": str(exc), "check": "conversion_drop"}


def check_page_speed_degradation() -> dict:
    """Alert if average page load time exceeds PAGE_SPEED_THRESHOLD_MS."""
    try:
        df = _qdf("""
            SELECT ROUND(AVG(load_time_ms), 0) AS avg_load_ms
            FROM raw_scrape_pages WHERE http_status = 200 AND load_time_ms IS NOT NULL
        """)
        if df.empty:
            return {"status": "ok", "message": "No scrape data", "check": "page_speed"}
        avg_ms = float(df["avg_load_ms"].iloc[0] or 0)
        if avg_ms > PAGE_SPEED_THRESHOLD_MS:
            msg = f"Avg page load time {avg_ms:.0f}ms exceeds {PAGE_SPEED_THRESHOLD_MS}ms threshold"
            send_alert(msg, severity="warning")
            return {
                "status": "alert",
                "severity": "warning",
                "message": msg,
                "avg_load_ms": avg_ms,
                "recommended_action": "Review slow pages in SEO dashboard, optimize images and server response.",
                "check": "page_speed",
            }
        return {"status": "ok", "avg_load_ms": avg_ms, "check": "page_speed"}
    except Exception as exc:
        return {"status": "error", "message": str(exc), "check": "page_speed"}


def check_anomaly_detected() -> dict:
    """Alert if the AI anomaly detector finds anomalies in recent traffic."""
    try:
        import pandas as pd

        anomaly_csv = ROOT / "data" / "processed" / "anomalies.csv"
        if not anomaly_csv.exists():
            return {
                "status": "ok",
                "message": "No anomaly file found",
                "check": "anomaly_detected",
            }
        df = pd.read_csv(anomaly_csv)
        if df.empty or "is_anomaly" not in df.columns:
            return {
                "status": "ok",
                "message": "No anomalies detected",
                "check": "anomaly_detected",
            }
        recent = df[df["is_anomaly"]]
        if not recent.empty:
            count = len(recent)
            high = (
                len(recent[recent.get("severity", pd.Series()) == "high"])
                if "severity" in recent.columns
                else 0
            )
            msg = f"{count} traffic anomaly(s) detected by AI model ({high} high-severity)"
            sev = "critical" if high > 0 else "warning"
            send_alert(msg, severity=sev)
            return {
                "status": "alert",
                "severity": sev,
                "message": msg,
                "anomaly_count": count,
                "recommended_action": "Review anomaly dates in Traffic dashboard.",
                "check": "anomaly_detected",
            }
        return {
            "status": "ok",
            "message": "No anomalies detected",
            "check": "anomaly_detected",
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc), "check": "anomaly_detected"}


def check_data_staleness() -> dict:
    """Alert if the most recent GA4 ingest is older than FRESHNESS_HOURS."""
    try:
        df = _qdf("SELECT MAX(ingested_at) AS last_ingest FROM raw_ga4_sessions")
        last = df["last_ingest"].iloc[0]
        if last is None:
            msg = "No data in raw_ga4_sessions"
            send_alert(msg, severity="warning")
            return {
                "status": "alert",
                "severity": "warning",
                "message": msg,
                "check": "data_staleness",
            }
        last_dt = last if hasattr(last, "hour") else datetime.fromisoformat(str(last))
        if hasattr(last_dt, "tzinfo") and last_dt.tzinfo is not None:
            last_dt = last_dt.replace(tzinfo=None)
        age_h = (datetime.now() - last_dt).total_seconds() / 3600
        if age_h > FRESHNESS_HOURS:
            msg = f"Data is {age_h:.1f}h old (threshold: {FRESHNESS_HOURS}h)"
            sev = "critical" if age_h > 48 else "warning"
            send_alert(msg, severity=sev)
            return {
                "status": "alert",
                "severity": sev,
                "message": msg,
                "age_hours": round(age_h, 1),
                "recommended_action": "Run ingestion/run_all.py --mode full to refresh data.",
                "check": "data_staleness",
            }
        return {"status": "ok", "age_hours": round(age_h, 1), "check": "data_staleness"}
    except Exception as exc:
        return {"status": "error", "message": str(exc), "check": "data_staleness"}


def check_data_freshness() -> dict:
    """Alias kept for backward compatibility."""
    return check_data_staleness()


def check_error_rate() -> dict:
    """Alert if server log error rate (4xx+5xx) exceeds threshold."""
    try:
        df = _qdf("""
            SELECT COUNT(*) AS total,
                   COUNT(CASE WHEN status_code >= 400 THEN 1 END) AS errors,
                   ROUND(
                       COUNT(CASE WHEN status_code >= 400 THEN 1 END)::NUMERIC
                       / NULLIF(COUNT(*), 0) * 100, 2
                   ) AS error_rate_pct
            FROM raw_server_logs WHERE log_time >= NOW() - INTERVAL '24 hours'
        """)
        if df.empty or int(df["total"].iloc[0]) == 0:
            return {
                "status": "ok",
                "message": "No server log data in last 24h",
                "check": "error_rate",
            }
        rate = float(df["error_rate_pct"].iloc[0] or 0) / 100
        if rate > ERROR_RATE_THRESHOLD:
            msg = f"Error rate is {rate*100:.1f}% (threshold: {ERROR_RATE_THRESHOLD*100:.0f}%)"
            sev = "critical" if rate > 0.10 else "warning"
            send_alert(msg, severity=sev)
            return {
                "status": "alert",
                "severity": sev,
                "message": msg,
                "error_rate_pct": round(rate * 100, 2),
                "recommended_action": "Check server logs for 5xx errors and review recent deploys.",
                "check": "error_rate",
            }
        return {
            "status": "ok",
            "error_rate_pct": round(rate * 100, 2),
            "check": "error_rate",
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc), "check": "error_rate"}


def generate_alert_summary() -> dict:
    """Run all checks and return a summary of active alerts."""
    results = run_all_checks()
    alerts = [r for r in results if r.get("status") == "alert"]
    critical = [r for r in alerts if r.get("severity") == "critical"]
    warnings = [r for r in alerts if r.get("severity") == "warning"]
    return {
        "total_checks": len(results),
        "active_alerts": len(alerts),
        "critical_count": len(critical),
        "warning_count": len(warnings),
        "all_clear": len(alerts) == 0,
        "alerts": alerts,
        "timestamp": datetime.now().isoformat(),
    }


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
    """Run all alert checks and return list of results."""
    checks = [
        check_traffic_drop,
        check_bounce_spike,
        check_conversion_drop,
        check_page_speed_degradation,
        check_anomaly_detected,
        check_data_staleness,
        check_error_rate,
    ]
    results = []
    for fn in checks:
        result = fn()
        results.append(result)
    return results
