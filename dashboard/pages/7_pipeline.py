"""Pipeline Monitor dashboard page."""

import os
import sys
import subprocess
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
    "ga4": "raw_ga4_sessions",
    "server_logs": "raw_server_logs",
    "clickstream": "raw_clickstream_events",
    "scraper": "raw_scrape_pages",
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
                "table": table,
                "rows": int(df["n"].iloc[0]),
                "last_ingest": str(df["last_ingest"].iloc[0])[:19],
            }
        except Exception as exc:
            counts[name] = {
                "table": table,
                "rows": 0,
                "last_ingest": "error",
                "error": str(exc),
            }
    return counts


@st.cache_data(ttl=300)
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
    st.metric(
        "Active Alerts", n_active, delta=None if n_active == 0 else f"{n_active} firing"
    )
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
        msg = alert.get("message", "")
        rec = alert.get("recommended_action", "")
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
        _alert_log = (
            Path(__file__).resolve().parent.parent.parent
            / "data"
            / "processed"
            / "pipeline_logs"
            / "alerts.log"
        )
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
        color = (
            "#f8d7da" if sev == "critical" else "#fff3cd" if sev == "warning" else ""
        )
        if row.get("is_resolved"):
            color = "#d4edda"
        return [f"background-color: {color}"] * len(row)

    styled_alerts = db_alerts.style.apply(_alert_row_style, axis=1)
    st.dataframe(styled_alerts, use_container_width=True, hide_index=True)

    # Alert resolution rate
    total_db = len(db_alerts)
    resolved = (
        int(db_alerts["is_resolved"].sum()) if "is_resolved" in db_alerts.columns else 0
    )
    res_rate = round(resolved / total_db * 100, 1) if total_db else 0
    st.caption(f"Resolution rate: {res_rate}% ({resolved}/{total_db} alerts resolved)")
else:
    st.info(
        "No alerts in database yet. Alerts will appear here after the alert system writes to the DB."
    )

# ── Resolve alert button ───────────────────────────────────────────────────────
if not db_alerts.empty and "id" in db_alerts.columns:
    unresolved = db_alerts[~db_alerts["is_resolved"]]
    if not unresolved.empty:
        alert_ids = unresolved["id"].tolist()
        alert_options = {
            f"[{row['severity'].upper()}] {str(row['message'])[:60]}": row["id"]
            for _, row in unresolved.iterrows()
        }
        sel_label = st.selectbox(
            "Mark as Resolved", options=list(alert_options.keys()), key="resolve_select"
        )
        if st.button("Mark Selected as Resolved", key="mark_resolved"):
            sel_id = alert_options[sel_label]
            try:
                from sqlalchemy import text
                from utils.db import get_engine

                with get_engine().begin() as conn:
                    conn.execute(
                        text(
                            "UPDATE alerts SET is_resolved=TRUE, resolved_at=NOW() WHERE id=:id"
                        ),
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

_alert_log = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "processed"
    / "pipeline_logs"
    / "alerts.log"
)
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
            use_container_width=True,
            hide_index=True,
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
        detector = SmartAlertDetector()
        alerts = detector.run_all(df_traffic)
        summary = AlertSummary.from_alerts(alerts)
        return summary.to_dict()
    except Exception as exc:
        return {
            "error": str(exc),
            "total_alerts": 0,
            "critical_count": 0,
            "warning_count": 0,
            "all_clear": True,
            "alerts": [],
        }


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
            sev = alert.get("severity", "WARNING")
            icon = "🔴" if sev == "CRITICAL" else "🟡"
            with st.expander(f"{icon} [{sev}] {alert.get('title', '')}"):
                st.write(f"**Type:** `{alert.get('alert_type', '')}`")
                st.write(f"**Message:** {alert.get('message', '')}")
                st.write(
                    f"**Recommended action:** {alert.get('recommended_action', '')}"
                )
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

        fig_trend = px.bar(
            df_trend,
            x="alert_date",
            y="n",
            color="severity",
            color_discrete_map={
                "critical": "#d62728",
                "warning": "#ff7f0e",
                "info": "#636EFA",
            },
            title="Alert Trend Over Time",
            labels={"n": "Alerts", "alert_date": "Date"},
        )
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
    history_df = history_df.rename(
        columns={
            "timestamp": "Run Time",
            "name": "Pipeline",
            "status": "Status",
            "rows": "Rows",
            "duration_s": "Duration (s)",
        }
    )

    def _status_color(row):
        color = (
            "#d4edda"
            if row["Status"] == "success"
            else "#f8d7da" if str(row["Status"]).startswith("error") else "#fff3cd"
        )
        return [f"background-color: {color}"] * len(row)

    st.dataframe(
        history_df.style.apply(_status_color, axis=1),
        use_container_width=True,
        hide_index=True,
    )

st.divider()

# ── Pipeline stats ─────────────────────────────────────────────────────────────
st.subheader("Pipeline Statistics")
stats = get_pipeline_stats()
if stats:
    stats_rows = [
        {
            "Pipeline": name,
            "Total Runs": s["total_runs"],
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

        run_all_script = str(
            Path(__file__).resolve().parent.parent.parent / "ingestion" / "run_all.py"
        )
        with st.spinner("Running all pipelines..."):
            try:
                result = subprocess.run(
                    [_sys.executable, run_all_script, "--mode", "full"],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if result.returncode == 0:
                    st.success("All pipelines completed successfully.")
                    st.code(
                        result.stdout[-2000:]
                        if len(result.stdout) > 2000
                        else result.stdout
                    )
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

        run_all_script = str(
            Path(__file__).resolve().parent.parent.parent / "ingestion" / "run_all.py"
        )
        with st.spinner(f"Running {selected}..."):
            try:
                result = subprocess.run(
                    [
                        _sys.executable,
                        run_all_script,
                        "--mode",
                        "full",
                        "--pipeline",
                        selected,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode == 0:
                    st.success(f"{selected} pipeline completed.")
                    st.code(
                        result.stdout[-2000:]
                        if len(result.stdout) > 2000
                        else result.stdout
                    )
                    _load_table_counts.clear()
                else:
                    st.error(f"{selected} pipeline failed.")
                    st.code(result.stderr[-2000:])
            except subprocess.TimeoutExpired:
                st.error("Pipeline timed out.")
            except Exception as exc:
                st.error(f"Error: {exc}")

st.divider()

# ── Query Performance Log ─────────────────────────────────────────────────────
st.subheader("Query Performance Log")
st.caption("Execution times logged by utils/db.py for every query_df() call.")

_PERF_CSV = (
    __import__("pathlib").Path(__file__).resolve().parent.parent.parent
    / "data" / "processed" / "query_performance.csv"
)


@st.cache_data(ttl=300)
def _load_query_perf() -> pd.DataFrame:
    if not _PERF_CSV.exists():
        return pd.DataFrame(columns=["timestamp", "duration_ms", "query_preview"])
    return pd.read_csv(_PERF_CSV, encoding="utf-8")


with st.spinner("Loading query performance data..."):
    _qp_df = _load_query_perf()

if _qp_df.empty:
    st.info(
        "No query performance data yet. Query timings are recorded automatically "
        "in data/processed/query_performance.csv on each query_df() call."
    )
else:
    _qp_c1, _qp_c2, _qp_c3 = st.columns(3)
    with _qp_c1:
        st.metric("Total Queries Logged", f"{len(_qp_df):,}")
    with _qp_c2:
        st.metric("Avg Query Time", f"{_qp_df['duration_ms'].mean():.1f} ms")
    with _qp_c3:
        _slow = (_qp_df["duration_ms"] > 5000).sum()
        st.metric("Slow Queries (>5 s)", int(_slow))

    st.subheader("Slowest 5 Queries")
    _slowest = _qp_df.nlargest(5, "duration_ms")[
        ["timestamp", "duration_ms", "query_preview"]
    ].copy()
    _slowest.columns = ["Timestamp", "Duration (ms)", "Query Preview"]

    def _style_slow(val):
        if isinstance(val, (int, float)) and val > 5000:
            return "background-color:#d62728;color:white;font-weight:bold"
        if isinstance(val, (int, float)) and val > 2000:
            return "background-color:#ff7f0e;color:white"
        return ""

    st.dataframe(
        _slowest.style.applymap(_style_slow, subset=["Duration (ms)"]),
        use_container_width=True,
        hide_index=True,
    )

    # Optimization suggestions
    st.subheader("Query Optimization Suggestions")
    _avg_ms = float(_qp_df["duration_ms"].mean())
    _p95_ms = float(_qp_df["duration_ms"].quantile(0.95))
    _suggestions = []
    if _slow > 0:
        _suggestions.append(
            f"🔴 **{int(_slow)} query(ies) exceed 5 s** — add indexes on frequently filtered "
            "columns (session_date, channel_grouping, landing_page)."
        )
    if _p95_ms > 2000:
        _suggestions.append(
            f"🟡 **P95 query time is {_p95_ms:.0f} ms** — consider materialising heavy "
            "aggregations as scheduled views or summary tables."
        )
    if _avg_ms > 500:
        _suggestions.append(
            f"🟡 **Avg query time {_avg_ms:.0f} ms** — ensure `@st.cache_data(ttl=300)` "
            "is applied to every loader function to avoid repeated DB hits."
        )
    if not _suggestions:
        _suggestions.append("🟢 All queries are performing well (avg < 500 ms, no slow queries).")

    for _s in _suggestions:
        st.markdown(_s)

    _alerts_5s = _qp_df[_qp_df["duration_ms"] > 5000]
    if not _alerts_5s.empty:
        st.error(
            f"⚠️ {len(_alerts_5s)} query(ies) exceeded the 5-second threshold. "
            "Review the slowest queries above and add database indexes."
        )

    st.download_button(
        "⬇️ Download Performance Log CSV",
        _qp_df.to_csv(index=False),
        file_name="query_performance.csv",
        mime="text/csv",
        key="dl_qp_log",
    )

st.divider()

# ── SQL View Execution Times ──────────────────────────────────────────────────
st.subheader("SQL View Execution Times")
st.caption(
    "Live execution time for each key SQL view. "
    "🟡 Yellow = >1 s · 🔴 Red = >3 s · Suggestions shown for slow views."
)

_DASHBOARD_VIEWS = {
    "vw_traffic": "SELECT * FROM vw_traffic",
    "vw_daily_traffic": "SELECT * FROM vw_daily_traffic",
    "vw_behavior": "SELECT * FROM vw_behavior",
    "vw_top_pages": "SELECT * FROM vw_top_pages",
    "vw_funnel": "SELECT * FROM vw_funnel",
    "vw_conversions": "SELECT * FROM vw_conversions LIMIT 50",
    "vw_seo": "SELECT * FROM vw_seo",
    "vw_new_vs_returning": "SELECT * FROM vw_new_vs_returning LIMIT 30",
    "vw_scroll_depth": "SELECT * FROM vw_scroll_depth",
    "vw_engagement_events": "SELECT * FROM vw_engagement_events",
}

_OPTIMIZE_TIPS = {
    "vw_traffic": "Add index on raw_server_logs(log_time, url) if >1s.",
    "vw_daily_traffic": "Materialise with a REFRESH MATERIALIZED VIEW if >1s.",
    "vw_seo": "Ensure indexes on raw_scrape_pages(url, scraped_at).",
    "vw_conversions": "Index on vw_conversions.session_date can speed range queries.",
}


@st.cache_data(ttl=120)
def _measure_view_times() -> list[dict]:
    import time as _time

    results = []
    for view_name, sql in _DASHBOARD_VIEWS.items():
        t0 = _time.perf_counter()
        try:
            query_df(sql)
            ms = round((_time.perf_counter() - t0) * 1000, 1)
            status = "ok"
        except Exception as exc:
            ms = -1.0
            status = str(exc)[:80]
        results.append({"view": view_name, "duration_ms": ms, "status": status})
    return results


with st.spinner("Measuring SQL view execution times..."):
    _view_times = _measure_view_times()

_total_db_ms = sum(r["duration_ms"] for r in _view_times if r["duration_ms"] > 0)

_vt_c1, _vt_c2, _vt_c3 = st.columns(3)
with _vt_c1:
    st.metric("Views Measured", len(_view_times))
with _vt_c2:
    _slow_views = sum(1 for r in _view_times if r["duration_ms"] > 1000)
    st.metric("Slow Views (>1s)", _slow_views)
with _vt_c3:
    st.metric("Total DB Query Time", f"{_total_db_ms:.0f} ms")

_suggestions_shown = False
for _vt in sorted(_view_times, key=lambda x: -x["duration_ms"]):
    _ms = _vt["duration_ms"]
    _view = _vt["view"]

    if _ms < 0:
        _badge = "🔴"
        _badge_html = "<span style='background:#d62728;color:white;padding:2px 8px;border-radius:4px;font-size:12px'>ERROR</span>"
    elif _ms > 3000:
        _badge = "🔴"
        _badge_html = f"<span style='background:#d62728;color:white;padding:2px 8px;border-radius:4px;font-size:12px'>{_ms:.0f} ms — VERY SLOW</span>"
    elif _ms > 1000:
        _badge = "🟡"
        _badge_html = f"<span style='background:#ff7f0e;color:white;padding:2px 8px;border-radius:4px;font-size:12px'>{_ms:.0f} ms — SLOW</span>"
    else:
        _badge = "🟢"
        _badge_html = f"<span style='background:#2ca02c;color:white;padding:2px 8px;border-radius:4px;font-size:12px'>{_ms:.0f} ms</span>"

    _row_c1, _row_c2 = st.columns([3, 2])
    with _row_c1:
        st.markdown(f"`{_view}`", unsafe_allow_html=False)
    with _row_c2:
        st.markdown(_badge_html, unsafe_allow_html=True)

    if _ms > 1000 and _view in _OPTIMIZE_TIPS:
        st.caption(f"  💡 Optimize: {_OPTIMIZE_TIPS[_view]}")
        _suggestions_shown = True

if not _suggestions_shown:
    st.success("All SQL views performing within acceptable thresholds (< 1 s).")

st.divider()

# ── Database Statistics ───────────────────────────────────────────────────────
st.subheader("Database Statistics")
st.caption("Live statistics from PostgreSQL system tables (pg_stat_user_tables, pg_total_relation_size).")


@st.cache_data(ttl=120)
def _load_db_stats() -> pd.DataFrame:
    return query_df(
        """SELECT
               relname                                                  AS table_name,
               n_live_tup                                               AS live_rows,
               n_dead_tup                                               AS dead_rows,
               pg_size_pretty(pg_total_relation_size(relid))            AS total_size,
               pg_total_relation_size(relid)                            AS size_bytes,
               seq_scan                                                 AS seq_scans,
               idx_scan                                                 AS index_scans,
               CASE WHEN (seq_scan + COALESCE(idx_scan, 0)) = 0 THEN NULL
                    ELSE ROUND(COALESCE(idx_scan, 0)::numeric
                         / (seq_scan + COALESCE(idx_scan, 0)) * 100, 1)
               END                                                      AS index_usage_pct,
               last_analyze,
               last_vacuum
           FROM pg_stat_user_tables
           WHERE schemaname = 'public'
           ORDER BY size_bytes DESC"""
    )


@st.cache_data(ttl=300)
def _load_index_stats() -> pd.DataFrame:
    return query_df(
        """SELECT
               indexrelname                              AS index_name,
               relname                                   AS table_name,
               idx_scan                                  AS index_scans,
               idx_tup_read                              AS tuples_read,
               idx_tup_fetch                             AS tuples_fetched,
               pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
           FROM pg_stat_user_indexes
           WHERE schemaname = 'public'
           ORDER BY idx_scan DESC
           LIMIT 20"""
    )


@st.cache_data(ttl=300)
def _load_db_uptime() -> str:
    try:
        df = query_df(
            "SELECT pg_postmaster_start_time() AS start_time, "
            "NOW() - pg_postmaster_start_time() AS uptime"
        )
        start = df["start_time"].iloc[0]
        uptime = df["uptime"].iloc[0]
        return f"Started: {str(start)[:16]} · Uptime: {str(uptime)[:10]}"
    except Exception as exc:
        return f"Uptime unavailable: {exc}"


with st.spinner("Loading database statistics..."):
    try:
        _db_stat_df = _load_db_stats()
        _idx_stat_df = _load_index_stats()
        _db_uptime_str = _load_db_uptime()

        st.caption(f"PostgreSQL: {_db_uptime_str}")

        _dbs_c1, _dbs_c2, _dbs_c3 = st.columns(3)
        with _dbs_c1:
            _total_live = int(_db_stat_df["live_rows"].sum())
            st.metric("Total Live Rows", f"{_total_live:,}")
        with _dbs_c2:
            _total_tables = len(_db_stat_df)
            st.metric("User Tables", _total_tables)
        with _dbs_c3:
            _total_idx_scans = int(_idx_stat_df["index_scans"].sum())
            st.metric("Total Index Scans", f"{_total_idx_scans:,}")

        st.subheader("Table Sizes & Row Counts")
        _disp_stats = _db_stat_df[[
            "table_name", "live_rows", "total_size", "seq_scans",
            "index_scans", "index_usage_pct",
        ]].copy()
        _disp_stats.columns = [
            "Table", "Live Rows", "Total Size", "Seq Scans",
            "Index Scans", "Index Usage %",
        ]
        st.dataframe(
            _disp_stats.style.background_gradient(
                subset=["Index Usage %"], cmap="RdYlGn", vmin=0, vmax=100
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.subheader("Most Used Indexes (Top 20)")
        st.dataframe(_idx_stat_df, use_container_width=True, hide_index=True)

    except Exception as exc:
        st.error(f"Could not load database statistics: {exc}")
        if st.button("Retry", key="retry_db_stats"):
            st.cache_data.clear()
            st.rerun()

# ── Validation Report ──────────────────────────────────────────────────────────
st.header("✅ Data Validation Report")

_SOURCE_LABELS = {
    "ga4": "GA4 Sessions",
    "server_logs": "Server Logs",
    "clickstream": "Clickstream",
    "scraper": "Scrape Pages",
}


@st.cache_data(ttl=120)
def _load_val_summary() -> dict:
    from utils.validator import load_validation_summary
    return load_validation_summary()


@st.cache_data(ttl=120)
def _load_invalid_rows(source: str) -> pd.DataFrame | None:
    from utils.validator import latest_invalid_file
    path = latest_invalid_file(source)
    if path is None:
        return None
    try:
        return pd.read_csv(path)
    except Exception:
        return None


def _val_color(passed: int, failed: int) -> str:
    if failed == 0:
        return "🟢"
    pct = passed / max(passed + failed, 1) * 100
    return "🟡" if pct >= 90 else "🔴"


_val_data = _load_val_summary()

if not _val_data:
    st.info("No validation data yet — run an ingestion pipeline to generate results.")
else:
    # ── KPI row ───────────────────────────────────────────────────────────────
    _val_cols = st.columns(len(_SOURCE_LABELS))
    for i, (src, label) in enumerate(_SOURCE_LABELS.items()):
        with _val_cols[i]:
            if src in _val_data:
                _s = _val_data[src]
                _total = _s["passed"] + _s["failed"]
                _pct = round(_s["passed"] / max(_total, 1) * 100, 1)
                _icon = _val_color(_s["passed"], _s["failed"])
                st.metric(
                    f"{_icon} {label}",
                    f"{_pct}% pass",
                    f"{_s['passed']:,} / {_total:,} rows",
                )
            else:
                st.metric(f"⚫ {label}", "No data", "—")

    # ── Summary table ─────────────────────────────────────────────────────────
    st.subheader("Validation Summary by Source")
    _rows = []
    for src, label in _SOURCE_LABELS.items():
        if src not in _val_data:
            _rows.append({"Source": label, "Passed": "—", "Failed": "—",
                          "Pass %": "—", "Last Run": "—", "Status": "⚫ No data"})
            continue
        _s = _val_data[src]
        _total = _s["passed"] + _s["failed"]
        _pct = round(_s["passed"] / max(_total, 1) * 100, 1)
        _icon = _val_color(_s["passed"], _s["failed"])
        _status = (
            "All pass" if _s["failed"] == 0
            else f"{_s['failed']} failed"
        )
        _rows.append({
            "Source": label,
            "Passed": f"{_s['passed']:,}",
            "Failed": f"{_s['failed']:,}",
            "Pass %": f"{_pct}%",
            "Last Run": _s.get("last_run", "—"),
            "Status": f"{_icon} {_status}",
        })

    st.dataframe(pd.DataFrame(_rows), use_container_width=True, hide_index=True)

    # ── Top 3 most common errors across all sources ───────────────────────────
    _all_errors: dict[str, int] = {}
    for src, _s in _val_data.items():
        for err, cnt in _s.get("error_counts", {}).items():
            _all_errors[err] = _all_errors.get(err, 0) + cnt

    if _all_errors:
        st.subheader("Top Validation Errors")
        _top3 = sorted(_all_errors.items(), key=lambda x: -x[1])[:3]
        _e_cols = st.columns(len(_top3))
        for i, (err_name, count) in enumerate(_top3):
            with _e_cols[i]:
                st.metric(f"#{i + 1} {err_name.replace('_', ' ').title()}", f"{count:,} rows")
    else:
        st.success("No validation errors found across all sources.")

    # ── Invalid rows expanders ────────────────────────────────────────────────
    st.subheader("Invalid Rows (Latest Run per Source)")
    for src, label in _SOURCE_LABELS.items():
        _has_failed = src in _val_data and _val_data[src]["failed"] > 0
        _exp_label = f"🔴 {label} — {_val_data[src]['failed']:,} invalid rows" if _has_failed else f"🟢 {label} — no invalid rows"
        with st.expander(_exp_label, expanded=_has_failed):
            if not _has_failed:
                st.success("All rows passed validation.")
            else:
                _inv_df = _load_invalid_rows(src)
                if _inv_df is not None and not _inv_df.empty:
                    st.dataframe(_inv_df, use_container_width=True, hide_index=True)
                    st.download_button(
                        "Download Invalid Rows CSV",
                        data=_inv_df.to_csv(index=False).encode(),
                        file_name=f"{src}_invalid_rows.csv",
                        mime="text/csv",
                        key=f"dl_invalid_{src}",
                    )
                else:
                    st.info("Invalid rows file not found or empty.")

# ── Data Quality Scores ────────────────────────────────────────────────────────
st.header("📊 Data Quality Scores")

_PROFILE_SOURCES = {
    "ga4_sessions": "GA4 Sessions",
    "server_logs": "Server Logs",
    "scrape_pages": "Scrape Pages",
    "clickstream_events": "Clickstream Events",
}


@st.cache_data(ttl=300)
def _load_all_profiles() -> dict:
    from utils.data_profiler import load_profile
    return {name: load_profile(name) for name in _PROFILE_SOURCES}


def _score_color(score: float) -> str:
    if score >= 80:
        return "🟢"
    if score >= 60:
        return "🟡"
    return "🔴"


def _score_label(score: float) -> str:
    if score >= 80:
        return "Good"
    if score >= 60:
        return "Warning"
    return "Poor"


_profiles = _load_all_profiles()
_any_profile = any(v is not None for v in _profiles.values())

if not _any_profile:
    st.info("No profile data yet — run `python scripts/run_data_profiler.py` to generate reports.")
else:
    # ── Quality score KPI row ─────────────────────────────────────────────────
    _qcols = st.columns(len(_PROFILE_SOURCES))
    for i, (src, label) in enumerate(_PROFILE_SOURCES.items()):
        with _qcols[i]:
            p = _profiles.get(src)
            if p:
                score = p["quality"]["score"]
                icon = _score_color(score)
                st.metric(
                    f"{icon} {label}",
                    f"{score} / 100",
                    _score_label(score),
                )
            else:
                st.metric(f"⚫ {label}", "No data", "—")

    # ── Detailed quality breakdown table ──────────────────────────────────────
    st.subheader("Quality Breakdown by Source")
    _q_rows = []
    for src, label in _PROFILE_SOURCES.items():
        p = _profiles.get(src)
        if not p:
            _q_rows.append({"Source": label, "Score": "—", "Rows": "—",
                            "Null %": "—", "Dup %": "—", "Outlier %": "—",
                            "Cols w/ Nulls": "—", "Profiled At": "—"})
            continue
        q = p["quality"]
        _q_rows.append({
            "Source": label,
            "Score": f"{q['score']}",
            "Rows": f"{p['row_count']:,}",
            "Null %": f"{q['avg_null_pct']}%",
            "Dup %": f"{q['duplicate_pct']}%",
            "Outlier %": f"{q['avg_outlier_pct']}%",
            "Cols w/ Nulls": q["cols_with_nulls"],
            "Profiled At": p.get("profiled_at", "—"),
        })

    _q_df = pd.DataFrame(_q_rows)
    st.dataframe(_q_df, use_container_width=True, hide_index=True)

    # ── Per-source expandable detail ─────────────────────────────────────────
    st.subheader("Column-Level Detail")
    for src, label in _PROFILE_SOURCES.items():
        p = _profiles.get(src)
        if not p:
            continue
        score = p["quality"]["score"]
        icon = _score_color(score)
        with st.expander(f"{icon} {label} — score {score}/100"):
            _detail_cols = st.columns(3)
            with _detail_cols[0]:
                st.caption("**Null counts (top 5)**")
                null_items = sorted(
                    [(c, v["null_count"]) for c, v in p["null_summary"].items() if v["null_count"] > 0],
                    key=lambda x: -x[1],
                )[:5]
                if null_items:
                    for col, cnt in null_items:
                        pct = p["null_summary"][col]["null_pct"]
                        st.write(f"`{col}`: {cnt:,} ({pct}%)")
                else:
                    st.write("No nulls found")

            with _detail_cols[1]:
                st.caption("**Outliers (top 5)**")
                out_items = sorted(
                    p["outlier_summary"].items(),
                    key=lambda x: -x[1]["outlier_pct"],
                )[:5]
                if out_items:
                    for col, v in out_items:
                        st.write(f"`{col}`: {v['outlier_count']:,} ({v['outlier_pct']}%)")
                else:
                    st.write("No outliers found")

            with _detail_cols[2]:
                st.caption("**Column types**")
                type_summary: dict[str, int] = {}
                for v in p["data_types"].values():
                    dtype_grp = v["dtype"].split("[")[0]
                    type_summary[dtype_grp] = type_summary.get(dtype_grp, 0) + 1
                for dtype, cnt in sorted(type_summary.items(), key=lambda x: -x[1]):
                    st.write(f"`{dtype}`: {cnt} col(s)")
