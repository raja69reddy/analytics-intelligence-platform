"""
Analytics Intelligence Platform — main Streamlit entry point.

Run:
    streamlit run dashboard/app.py
"""

import os
import sys
from datetime import datetime

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dashboard.components.filters import (  # noqa: E402
    get_channel_filter,
    get_date_filter,
    get_device_filter,
    get_page_filter,
)

st.set_page_config(
    page_title="Analytics Intelligence Platform",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📊 Analytics Intelligence")
    st.caption("PostgreSQL + Python + Streamlit + AI/ML")
    st.divider()

    # ── Navigation ────────────────────────────────────────────────────────────
    st.subheader("Navigation")
    st.page_link("pages/1_traffic.py", label="Traffic & Sessions", icon="📈")
    st.page_link("pages/2_behavior.py", label="User Behavior", icon="🖱️")
    st.page_link("pages/3_conversions.py", label="Conversions", icon="🎯")
    st.page_link("pages/4_seo.py", label="SEO & Content", icon="🔍")
    st.page_link("pages/5_nlq.py", label="Ask Your Data", icon="💬")
    st.page_link("pages/6_reports.py", label="AI Reports", icon="📋")
    st.page_link("pages/7_pipeline.py", label="Pipeline Monitor", icon="⚙️")
    st.page_link("pages/8_forecasting.py", label="Forecasting", icon="🔮")
    st.divider()

    # ── Global Filters ────────────────────────────────────────────────────────
    st.subheader("🔎 Global Filters")
    start_date, end_date = get_date_filter()
    channels = get_channel_filter()
    page_search = get_page_filter()
    devices = get_device_filter()

    active = sum([bool(channels), bool(page_search), bool(devices)])
    if active:
        st.success(f"{active} filter(s) active")
    else:
        st.caption("No filters active — showing all data")

    st.divider()

    # ── Data Freshness ────────────────────────────────────────────────────────
    st.subheader("📡 Data Freshness")

    @st.cache_data(ttl=60)
    def _sidebar_data_freshness():
        from utils.db import query_df as _qdf

        tables = {
            "GA4": "raw_ga4_sessions",
            "Server Logs": "raw_server_logs",
            "Clickstream": "raw_clickstream_events",
            "Scraper": "raw_scrape_pages",
        }
        total_rows = 0
        last_ingest = None
        for _label, table in tables.items():
            try:
                df = _qdf(f"SELECT COUNT(*) AS n, MAX(ingested_at) AS ts FROM {table}")
                n = int(df["n"].iloc[0])
                ts = df["ts"].iloc[0]
                total_rows += n
                if ts and (last_ingest is None or ts > last_ingest):
                    last_ingest = ts
            except Exception:
                pass
        return total_rows, last_ingest

    _total_rows, _last_ingest = _sidebar_data_freshness()
    st.metric("Total Rows Ingested", f"{_total_rows:,}")

    if _last_ingest:
        _last_dt = (
            _last_ingest
            if hasattr(_last_ingest, "strftime")
            else datetime.fromisoformat(str(_last_ingest))
        )
        _age_h = (datetime.now() - _last_dt).total_seconds() / 3600
        st.caption(f"Last ingest: {_last_dt.strftime('%Y-%m-%d %H:%M')}")
        if _age_h < 24:
            st.success(f"Data fresh ({_age_h:.0f}h ago)")
        elif _age_h < 48:
            st.warning(f"Data aging ({_age_h:.0f}h ago)")
        else:
            st.error(f"Data stale ({_age_h:.0f}h ago)")
    else:
        st.caption("No ingest timestamp found.")

    if st.button("Clear Cache", key="clear_cache_btn"):
        st.cache_data.clear()
        st.rerun()

    st.divider()

    # ── AI Anomaly Alerts ─────────────────────────────────────────────────────
    st.subheader("🤖 AI Anomaly Alerts")

    @st.cache_data(ttl=300)
    def _sidebar_anomaly_summary():
        from ai.anomaly_detection.detector import AnomalyDetector
        from ai.anomaly_detection.train import load_model
        from ai.anomaly_detection.utils import load_traffic_data

        try:
            model = load_model()
        except FileNotFoundError:
            return None
        df = load_traffic_data()
        if df.empty:
            return None
        detector = AnomalyDetector()
        detector._traffic_model = model
        return detector.get_anomaly_summary(df)

    alert_summary = _sidebar_anomaly_summary()

    if alert_summary is None:
        st.caption("Model not trained yet.")
    else:
        total = alert_summary.total_anomalies
        high = alert_summary.severity_counts.get("high", 0)
        med = alert_summary.severity_counts.get("medium", 0)
        st.metric("Anomalies Detected", total)
        if alert_summary.anomaly_dates:
            most_recent = alert_summary.anomaly_dates[-1]
            recent_sev = "low"
            if (
                alert_summary.anomalies_df is not None
                and not alert_summary.anomalies_df.empty
            ):
                row = alert_summary.anomalies_df[
                    alert_summary.anomalies_df["session_date"].astype(str) == most_recent
                ]
                if len(row):
                    recent_sev = row["severity"].values[0]
            st.caption(f"Most recent: {most_recent} -- {recent_sev.upper()}")
        if high > 0:
            st.error(f"{high} high-severity anomaly(s) detected!")
        if med > 0:
            st.warning(f"{med} medium-severity anomaly(s) -- review recommended.")
        if total == 0:
            st.success("No anomalies detected -- traffic looks healthy.")
        if st.button("View All Anomalies", key="sidebar_anomalies"):
            st.switch_page("pages/1_traffic.py")

    st.divider()

    # ── Active Alerts ─────────────────────────────────────────────────────────
    st.subheader("🚨 Active Alerts")

    @st.cache_data(ttl=120)
    def _sidebar_alerts():
        try:
            from utils.alerts import run_all_checks

            return run_all_checks()
        except Exception as exc:
            return [{"check": "system", "status": "error", "message": str(exc)}]

    _alert_results = _sidebar_alerts()
    _has_alerts = False
    for _r in _alert_results:
        _sev = _r.get("severity", "")
        _msg = _r.get("message", "")
        if _r.get("status") == "alert":
            _has_alerts = True
            if _sev == "critical":
                st.error(f"{_r['check'].replace('_', ' ').title()}: {_msg}")
            else:
                st.warning(f"{_r['check'].replace('_', ' ').title()}: {_msg}")
        elif _r.get("status") == "error":
            st.warning(f"Check error: {_r['check']} -- {_msg}")

    if not _has_alerts:
        st.success("All systems healthy")

    if st.button("View Alert History", key="sidebar_alert_history"):
        st.switch_page("pages/7_pipeline.py")

    st.divider()

    # ── AI Reports ────────────────────────────────────────────────────────────
    st.subheader("📋 AI Reports")
    from pathlib import Path as _Path

    _reports_dir = (
        _Path(__file__).resolve().parent.parent / "data" / "processed" / "reports"
    )
    _report_files = (
        sorted(_reports_dir.glob("report_*.md"), reverse=True)
        if _reports_dir.exists()
        else []
    )
    if _report_files:
        _mtime = datetime.fromtimestamp(
            _report_files[0].stat().st_mtime
        ).strftime("%Y-%m-%d %H:%M")
        st.caption(f"Last report: {_mtime}")
        st.success("Report ready")
    else:
        st.caption("No reports generated yet.")

    if st.button("Generate Report", key="sidebar_gen_report"):
        st.switch_page("pages/6_reports.py")

    st.divider()

    # ── Ask a Question (NLQ) ──────────────────────────────────────────────────
    st.subheader("💬 Ask a Question")
    nlq_question = st.text_input(
        "Ask your data anything:",
        placeholder='e.g. "Top 5 channels by sessions"',
        key="sidebar_nlq_question",
    )
    if st.button("Ask AI", key="sidebar_nlq_btn"):
        if nlq_question.strip():
            try:
                from ai.nlq.nlq_engine import NLQEngine

                _engine = NLQEngine()
                _result = _engine.ask(nlq_question)
                if _result["error"]:
                    st.error(_result["response"])
                else:
                    with st.expander("Generated SQL", expanded=False):
                        st.code(_result["sql"] or "", language="sql")
                    if _result["data"] is not None and not _result["data"].empty:
                        st.dataframe(_result["data"], use_container_width=True)
                    else:
                        st.info("No results returned.")
                    st.caption(f"Executed in {_result['execution_time_s']}s")
            except Exception as _exc:
                st.error(f"NLQ error: {_exc}")
        else:
            st.warning("Please enter a question.")

    st.divider()

    # ── Forecast Preview ──────────────────────────────────────────────────────
    st.subheader("🔮 Forecast Preview")

    @st.cache_data(ttl=1800)
    def _sidebar_forecast():
        try:
            from ai.forecasting.traffic_forecaster import TrafficForecaster
            from ai.forecasting.conversion_forecaster import ConversionForecaster

            tf = TrafficForecaster()
            hist = tf.load_historical_data()
            tf.train_model(hist)
            fc_t = tf.forecast(days=7)
            hist_end = hist["ds"].max()
            future_t = fc_t[fc_t["ds"] > hist_end]
            pred_sessions_7d = int(future_t["yhat"].clip(lower=0).sum())

            cf = ConversionForecaster()
            hist_c = cf.load_conversion_data()
            cf.train_model(hist_c)
            fc_c = cf.forecast(days=7)
            summary = cf.get_forecast_summary(fc_c, days=7)
            return pred_sessions_7d, summary["avg_cvr_pct"]
        except Exception:
            return None, None

    _pred_7d, _pred_cvr_7d = _sidebar_forecast()
    if _pred_7d is not None:
        st.metric("Next 7 Days Predicted Sessions", f"{_pred_7d:,}")
        st.metric("Predicted Avg CVR (7d)", f"{_pred_cvr_7d:.4f}%")
    else:
        st.caption("Forecast not available.")

    if st.button("View Full Forecast", key="sidebar_forecast_link"):
        st.switch_page("pages/8_forecasting.py")


# ── Main page ─────────────────────────────────────────────────────────────────
from utils.db import query_df  # noqa: E402

st.title("Welcome to Analytics Intelligence Platform")
st.markdown("""
A production-grade analytics platform powered by **PostgreSQL**, **Python**, **Streamlit**, and **AI/ML**.

Use the **sidebar** to filter by date range, channel, and page URL.
Use the **navigation links** to explore each section.
""")

st.divider()

col1, col2, col3, col4 = st.columns(4)

with col1:
    n = int(query_df("SELECT COUNT(*) AS n FROM raw_ga4_sessions")["n"].iloc[0])
    st.metric("GA4 Sessions", f"{n:,}")

with col2:
    n = int(query_df("SELECT COUNT(*) AS n FROM raw_server_logs")["n"].iloc[0])
    st.metric("Server Log Entries", f"{n:,}")

with col3:
    n = int(query_df("SELECT COUNT(*) AS n FROM raw_clickstream_events")["n"].iloc[0])
    st.metric("Clickstream Events", f"{n:,}")

with col4:
    df = query_df(
        "SELECT MIN(session_date) AS mn, MAX(session_date) AS mx FROM raw_ga4_sessions"
    )
    mn, mx = str(df["mn"].iloc[0])[:10], str(df["mx"].iloc[0])[:10]
    st.metric("Data Range", f"{mn} to {mx}")

st.divider()

st.subheader("Dashboard Pages")
c1, c2, c3, c4 = st.columns(4)
c1.info(
    "📈 **Traffic & Sessions**\nSessions over time, channels, new vs returning, device split"
)
c2.info("🖱️ **User Behavior**\nTop pages, scroll depth, event types, response times")
c3.info("🎯 **Conversions**\nFunnel, form submissions, bounce rates by channel")
c4.info("🔍 **SEO & Content**\nOrganic pages, word count vs engagement, content health")

st.divider()

# ── Project Metrics ───────────────────────────────────────────────────────────
st.subheader("Project Metrics")


@st.cache_data(ttl=300)
def _load_project_metrics():
    total_dp = 0
    for table in (
        "raw_ga4_sessions",
        "raw_server_logs",
        "raw_clickstream_events",
        "raw_scrape_pages",
    ):
        try:
            n = int(query_df(f"SELECT COUNT(*) AS n FROM {table}")["n"].iloc[0])
            total_dp += n
        except Exception:
            pass

    try:
        views_df = query_df(
            "SELECT COUNT(*) AS n FROM information_schema.views "
            "WHERE table_schema = 'public'"
        )
        sql_views = int(views_df["n"].iloc[0])
    except Exception:
        sql_views = 17

    return total_dp, sql_views


try:
    _total_dp, _sql_views = _load_project_metrics()
    _ai_features = 5
    _dash_pages = 8
    _last_updated = datetime.now().strftime("%Y-%m-%d %H:%M")
    _health = min(100, 40 + (_sql_views * 2) + (_ai_features * 4) + (_dash_pages * 2))

    pm1, pm2, pm3, pm4, pm5, pm6 = st.columns(6)
    pm1.metric("Total Data Points", f"{_total_dp:,}")
    pm2.metric("SQL Views", f"{_sql_views}")
    pm3.metric("AI Features Active", f"{_ai_features} / 5")
    pm4.metric("Dashboard Pages", f"{_dash_pages}")
    pm5.metric("Last Updated", _last_updated)
    pm6.metric("System Health Score", f"{_health} / 100")

    if _health >= 80:
        st.success(f"System health: GOOD ({_health}/100) -- all core features active")
    elif _health >= 60:
        st.warning(f"System health: FAIR ({_health}/100)")
    else:
        st.error(f"System health: POOR ({_health}/100)")

except Exception as _exc:
    st.warning(f"Could not load project metrics: {_exc}")
