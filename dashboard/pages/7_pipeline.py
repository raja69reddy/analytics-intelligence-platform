"""Pipeline Monitor dashboard page."""
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from utils.db import query_df
from utils.pipeline_monitor import (
    get_pipeline_history,
    get_pipeline_stats,
)

st.set_page_config(page_title="Pipeline Monitor", page_icon="⚙️", layout="wide")
st.title("⚙️ Pipeline Monitor")

# ── DB guard ──────────────────────────────────────────────────────────────────
try:
    query_df("SELECT 1 AS ok")
except Exception as exc:
    st.error(f"Database connection failed: {exc}")
    st.stop()

# ── Row counts for all raw tables ─────────────────────────────────────────────
PIPELINE_TABLES = {
    "ga4":         "raw_ga4_sessions",
    "server_logs": "raw_server_logs",
    "clickstream": "raw_clickstream_events",
    "scraper":     "raw_scrape_pages",
}


@st.cache_data(ttl=60)
def _load_table_counts() -> dict:
    counts = {}
    for name, table in PIPELINE_TABLES.items():
        try:
            df = query_df(
                f"SELECT COUNT(*) AS n, MAX(ingested_at) AS last_ingest FROM {table}"
            )
            counts[name] = {
                "table":       table,
                "rows":        int(df["n"].iloc[0]),
                "last_ingest": str(df["last_ingest"].iloc[0])[:19],
            }
        except Exception as exc:
            counts[name] = {"table": table, "rows": 0, "last_ingest": "error", "error": str(exc)}
    return counts


@st.cache_data(ttl=120)
def _load_alert_summary() -> dict:
    from utils.alerts import generate_alert_summary
    return generate_alert_summary()


@st.cache_data(ttl=120)
def _load_db_alerts(limit: int = 20) -> pd.DataFrame:
    try:
        return query_df(f"""
            SELECT id, alert_type, severity, message, is_resolved, created_at, resolved_at
            FROM alerts
            ORDER BY created_at DESC
            LIMIT {limit}
        """)
    except Exception:
        return pd.DataFrame()


st.subheader("Table Row Counts & Last Ingest")
with st.spinner("Querying table stats..."):
    table_counts = _load_table_counts()

cols = st.columns(4)
for i, (name, info) in enumerate(table_counts.items()):
    with cols[i]:
        rows = info.get("rows", 0)
        last = info.get("last_ingest", "—")
        st.metric(label=f"{name}", value=f"{rows:,} rows")
        st.caption(f"Last ingest: {last}")

st.divider()

# ── Active Alerts Summary ─────────────────────────────────────────────────────
st.subheader("Active Alerts")

alert_col1, alert_col2, alert_col3, alert_col4 = st.columns(4)
with st.spinner("Checking alerts..."):
    summary = _load_alert_summary()

with alert_col1:
    st.metric("Total Checks", summary.get("total_checks", 0))
with alert_col2:
    n_active = summary.get("active_alerts", 0)
    st.metric("Active Alerts", n_active, delta=None if n_active == 0 else f"{n_active} firing")
with alert_col3:
    st.metric("Critical", summary.get("critical_count", 0))
with alert_col4:
    st.metric("Warning", summary.get("warning_count", 0))

if summary.get("all_clear"):
    st.success("All checks passed — no active alerts.")
else:
    for alert in summary.get("alerts", []):
        sev = alert.get("severity", "warning")
        icon = "🔴" if sev == "critical" else "🟡"
        msg  = alert.get("message", "")
        rec  = alert.get("recommended_action", "")
        with st.expander(f"{icon} [{sev.upper()}] {msg}"):
            if rec:
                st.write(f"**Recommended action:** {rec}")

c1, c2 = st.columns(2)
with c1:
    if st.button("Run Alert Check Now", key="run_alerts"):
        _load_alert_summary.clear()
        st.rerun()
with c2:
    if st.button("Dismiss All Alert Log Entries", key="dismiss_log"):
        _alert_log = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "pipeline_logs" / "alerts.log"
        if _alert_log.exists():
            _alert_log.write_text("", encoding="utf-8")
        st.success("Alert log cleared.")
        st.rerun()

st.divider()

# ── Alert History Table (DB) ───────────────────────────────────────────────────
st.subheader("Alert History (Last 20)")

db_alerts = _load_db_alerts(limit=20)
if not db_alerts.empty:
    def _alert_row_style(row):
        sev = str(row.get("severity", "")).lower()
        color = "#f8d7da" if sev == "critical" else "#fff3cd" if sev == "warning" else ""
        if row.get("is_resolved"):
            color = "#d4edda"
        return [f"background-color: {color}"] * len(row)

    styled_alerts = db_alerts.style.apply(_alert_row_style, axis=1)
    st.dataframe(styled_alerts, use_container_width=True, hide_index=True)

    # Alert resolution rate
    total_db = len(db_alerts)
    resolved = int(db_alerts["is_resolved"].sum()) if "is_resolved" in db_alerts.columns else 0
    res_rate = round(resolved / total_db * 100, 1) if total_db else 0
    st.caption(f"Resolution rate: {res_rate}% ({resolved}/{total_db} alerts resolved)")
else:
    st.info("No alerts in database yet. Alerts will appear here after the alert system writes to the DB.")

# ── Resolve alert button ───────────────────────────────────────────────────────
if not db_alerts.empty and "id" in db_alerts.columns:
    unresolved = db_alerts[db_alerts["is_resolved"] == False]
    if not unresolved.empty:
        alert_ids = unresolved["id"].tolist()
        alert_options = {
            f"[{row['severity'].upper()}] {str(row['message'])[:60]}": row["id"]
            for _, row in unresolved.iterrows()
        }
        sel_label = st.selectbox("Mark as Resolved", options=list(alert_options.keys()), key="resolve_select")
        if st.button("Mark Selected as Resolved", key="mark_resolved"):
            sel_id = alert_options[sel_label]
            try:
                from sqlalchemy import text
                from utils.db import get_engine
                with get_engine().begin() as conn:
                    conn.execute(
                        text("UPDATE alerts SET is_resolved=TRUE, resolved_at=NOW() WHERE id=:id"),
                        {"id": sel_id},
                    )
                _load_db_alerts.clear()
                st.success(f"Alert #{sel_id} marked as resolved.")
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to resolve alert: {exc}")

st.divider()

# ── Alert Trend Chart ─────────────────────────────────────────────────────────
st.subheader("Alert Trend (Log File)")

_alert_log = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "pipeline_logs" / "alerts.log"
if _alert_log.exists():
    _lines = _alert_log.read_text(encoding="utf-8").strip().splitlines()
    if _lines:
        _last_50 = list(reversed(_lines[-50:]))

        def _alert_row_color(row):
            line = row["Alert"]
            if "[CRITICAL]" in line:
                return ["background-color: #f8d7da"]
            if "[WARNING]" in line:
                return ["background-color: #fff3cd"]
            return [""]

        st.dataframe(
            pd.DataFrame({"Alert": _last_50}).style.apply(_alert_row_color, axis=1),
            use_container_width=True, hide_index=True,
        )
    else:
        st.success("No alerts logged.")
else:
    st.info("Alert log not found — alerts will appear here after checks run.")

st.divider()

# ── Smart Alert Detector ───────────────────────────────────────────────────────
st.subheader("AI Smart Alert Detector")


@st.cache_data(ttl=300)
def _run_smart_alerts() -> dict:
    try:
        from ai.smart_alerts.detector import SmartAlertDetector
        from ai.smart_alerts.alert_models import AlertSummary
        df_traffic = query_df("SELECT * FROM vw_daily_traffic ORDER BY session_date")
        detector   = SmartAlertDetector()
        alerts     = detector.run_all(df_traffic)
        summary    = AlertSummary.from_alerts(alerts)
        return summary.to_dict()
    except Exception as exc:
        return {"error": str(exc), "total_alerts": 0, "critical_count": 0,
                "warning_count": 0, "all_clear": True, "alerts": []}


with st.spinner("Running SmartAlertDetector..."):
    smart = _run_smart_alerts()

if "error" in smart and smart["error"]:
    st.error(f"SmartAlertDetector error: {smart['error']}")
else:
    # Real-time alert count by severity
    sa1, sa2, sa3, sa4 = st.columns(4)
    with sa1:
        st.metric("AI Alerts (total)", smart.get("total_alerts", 0))
    with sa2:
        st.metric("Critical", smart.get("critical_count", 0))
    with sa3:
        st.metric("Warning", smart.get("warning_count", 0))
    with sa4:
        status_label = "All Clear" if smart.get("all_clear") else "Issues Found"
        st.metric("Status", status_label)

    if smart.get("all_clear"):
        st.success("SmartAlertDetector: No anomalies or threshold breaches detected.")
    else:
        # Alert details — expandable cards
        for alert in smart.get("alerts", []):
            sev  = alert.get("severity", "WARNING")
            icon = "🔴" if sev == "CRITICAL" else "🟡"
            with st.expander(f"{icon} [{sev}] {alert.get('title', '')}"):
                st.write(f"**Type:** `{alert.get('alert_type', '')}`")
                st.write(f"**Message:** {alert.get('message', '')}")
                st.write(f"**Recommended action:** {alert.get('recommended_action', '')}")
                mv = alert.get("metric_value")
                tv = alert.get("threshold_value")
                if mv is not None:
                    st.caption(f"Metric: {mv} | Baseline: {tv}")

    # Alert trend chart over time (from DB)
    df_trend = query_df("""
        SELECT created_at::DATE AS alert_date, severity, COUNT(*) AS n
        FROM alerts
        GROUP BY alert_date, severity
        ORDER BY alert_date
    """)
    if not df_trend.empty:
        import plotly.express as px
        fig_trend = px.bar(df_trend, x="alert_date", y="n", color="severity",
                           color_discrete_map={"critical": "#d62728", "warning": "#ff7f0e", "info": "#636EFA"},
                           title="Alert Trend Over Time", labels={"n": "Alerts", "alert_date": "Date"})
        fig_trend.update_layout(template="plotly_white", legend_title="Severity")
        st.plotly_chart(fig_trend, use_container_width=True)

    if st.button("Re-run Smart Alert Detection", key="rerun_smart"):
        _run_smart_alerts.clear()
        st.rerun()

st.divider()

# ── Pipeline run history ───────────────────────────────────────────────────────
st.subheader("Pipeline Run History")

history = get_pipeline_history(limit=20)
if not history:
    st.info("No pipeline runs logged yet. Run a pipeline to see history.")
else:
    history_df = pd.DataFrame(history)
    history_df = history_df[["timestamp", "name", "status", "rows", "duration_s"]]
    history_df = history_df.rename(columns={
        "timestamp":  "Run Time",
        "name":       "Pipeline",
        "status":     "Status",
        "rows":       "Rows",
        "duration_s": "Duration (s)",
    })

    def _status_color(row):
        color = (
            "#d4edda" if row["Status"] == "success"
            else "#f8d7da" if str(row["Status"]).startswith("error")
            else "#fff3cd"
        )
        return [f"background-color: {color}"] * len(row)

    st.dataframe(
        history_df.style.apply(_status_color, axis=1),
        use_container_width=True, hide_index=True,
    )

st.divider()

# ── Pipeline stats ─────────────────────────────────────────────────────────────
st.subheader("Pipeline Statistics")
stats = get_pipeline_stats()
if stats:
    stats_rows = [
        {
            "Pipeline":     name,
            "Total Runs":   s["total_runs"],
            "Success Rate": f"{s['success_rate_pct']}%",
            "Avg Duration": f"{s['avg_duration_s']}s",
        }
        for name, s in stats.items()
    ]
    st.dataframe(pd.DataFrame(stats_rows), use_container_width=True, hide_index=True)
else:
    st.info("No stats available yet.")

st.divider()

# ── Run pipelines ─────────────────────────────────────────────────────────────
st.subheader("Run Pipelines")

col_a, col_b = st.columns(2)

with col_a:
    st.markdown("**Run All Pipelines**")
    if st.button("▶ Run All Pipelines (Full Mode)", type="primary"):
        import sys as _sys
        run_all_script = str(Path(__file__).resolve().parent.parent.parent / "ingestion" / "run_all.py")
        with st.spinner("Running all pipelines..."):
            try:
                result = subprocess.run(
                    [_sys.executable, run_all_script, "--mode", "full"],
                    capture_output=True, text=True, timeout=300,
                )
                if result.returncode == 0:
                    st.success("All pipelines completed successfully.")
                    st.code(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
                    _load_table_counts.clear()
                else:
                    st.error("Pipeline run failed.")
                    st.code(result.stderr[-2000:])
            except subprocess.TimeoutExpired:
                st.error("Pipeline timed out after 5 minutes.")
            except Exception as exc:
                st.error(f"Error launching pipeline: {exc}")

with col_b:
    st.markdown("**Run Single Pipeline**")
    selected = st.selectbox(
        "Choose pipeline",
        options=["ga4", "server_logs", "clickstream", "scraper"],
        key="single_pipeline_select",
    )
    if st.button(f"▶ Run {selected}", key="run_single"):
        import sys as _sys
        run_all_script = str(Path(__file__).resolve().parent.parent.parent / "ingestion" / "run_all.py")
        with st.spinner(f"Running {selected}..."):
            try:
                result = subprocess.run(
                    [_sys.executable, run_all_script, "--mode", "full", "--pipeline", selected],
                    capture_output=True, text=True, timeout=120,
                )
                if result.returncode == 0:
                    st.success(f"{selected} pipeline completed.")
                    st.code(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
                    _load_table_counts.clear()
                else:
                    st.error(f"{selected} pipeline failed.")
                    st.code(result.stderr[-2000:])
            except subprocess.TimeoutExpired:
                st.error("Pipeline timed out.")
            except Exception as exc:
                st.error(f"Error: {exc}")
