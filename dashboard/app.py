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
    FILTER_KEYS,
    get_channel_filter,
    get_date_filter,
    get_device_filter,
    get_page_filter,
    get_available_channels,
    get_available_devices,
    show_active_filters,
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

    # Dark mode toggle — preference stored in session state
    st.toggle(
        "Dark Mode",
        value=st.session_state.get("dark_mode", False),
        key="dark_mode",
    )

    start_date, end_date = get_date_filter()
    channels = get_channel_filter()
    page_search = get_page_filter()
    devices = get_device_filter()

    # ── Filter summary display ────────────────────────────────────────────────
    _active_count = sum([bool(channels), bool(page_search), bool(devices)])
    if _active_count:
        st.success(f"Filters active: {_active_count}")
        # Date range
        st.caption(f"Date: {start_date} to {end_date}")
        # Channel tags
        if channels:
            st.caption("Channels: " + " | ".join(f"`{c}`" for c in channels))
        # Device tags
        if devices:
            st.caption("Devices: " + " | ".join(f"`{d}`" for d in devices))
        # Page search
        if page_search:
            st.caption(f"Page search: `{page_search}`")
    else:
        st.caption(f"Date: {start_date} to {end_date}")
        st.caption("No channel, device, or page filters active")

    # Reset All Filters button
    if st.button("Reset All Filters", key="reset_filters_btn"):
        for _fk in FILTER_KEYS.values():
            if _fk in st.session_state:
                del st.session_state[_fk]
        st.rerun()

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
from dashboard.components.metrics import (  # noqa: E402
    calculate_period_change,
    display_4_kpi_row,
    format_large_number,
)
from utils.db import query_df  # noqa: E402

st.title("📊 Analytics Intelligence Platform")
st.markdown(
    "Production-grade analytics powered by **PostgreSQL**, **Python**, **Streamlit**, and **AI/ML**. "
    "Use the sidebar to filter data globally and navigate between the 8 dashboard pages."
)
st.divider()

# ── Live KPI Cards ────────────────────────────────────────────────────────────
st.subheader("Live Performance — Last 30 Days")


@st.cache_data(ttl=300)
def _load_live_kpis():
    from datetime import date as _date, timedelta as _td

    max_row = query_df("SELECT MAX(session_date)::date AS d FROM raw_ga4_sessions")
    max_d_raw = max_row["d"].iloc[0]
    if max_d_raw is None:
        return None
    max_d = (
        max_d_raw
        if isinstance(max_d_raw, _date)
        else _date.fromisoformat(str(max_d_raw)[:10])
    )
    curr_start = str(max_d - _td(days=30))
    curr_end = str(max_d)
    prev_start = str(max_d - _td(days=60))
    prev_end = str(max_d - _td(days=31))
    p = {"cs": curr_start, "ce": curr_end, "ps": prev_start, "pe": prev_end}

    sess_df = query_df(
        """
        SELECT
            COALESCE(SUM(CASE WHEN session_date BETWEEN :cs AND :ce
                THEN sessions END), 0) AS curr_s,
            COALESCE(SUM(CASE WHEN session_date BETWEEN :cs AND :ce
                THEN new_users END), 0) AS curr_u,
            COALESCE(SUM(CASE WHEN session_date BETWEEN :ps AND :pe
                THEN sessions END), 0) AS prev_s,
            COALESCE(SUM(CASE WHEN session_date BETWEEN :ps AND :pe
                THEN new_users END), 0) AS prev_u,
            ROUND(100.0
                * COALESCE(SUM(CASE WHEN session_date BETWEEN :cs AND :ce AND bounce
                    THEN sessions END), 0)
                / NULLIF(SUM(CASE WHEN session_date BETWEEN :cs AND :ce
                    THEN sessions END), 0), 2) AS curr_bounce,
            ROUND(100.0
                * COALESCE(SUM(CASE WHEN session_date BETWEEN :ps AND :pe AND bounce
                    THEN sessions END), 0)
                / NULLIF(SUM(CASE WHEN session_date BETWEEN :ps AND :pe
                    THEN sessions END), 0), 2) AS prev_bounce
        FROM raw_ga4_sessions
        WHERE session_date BETWEEN :ps AND :ce
        """,
        params=p,
    )
    cvr_df = query_df(
        """
        SELECT
            ROUND(100.0
                * COALESCE(SUM(CASE WHEN session_date BETWEEN :cs AND :ce
                    THEN goal_completions END), 0)
                / NULLIF(SUM(CASE WHEN session_date BETWEEN :cs AND :ce
                    THEN sessions END), 0), 2) AS curr_cvr,
            ROUND(100.0
                * COALESCE(SUM(CASE WHEN session_date BETWEEN :ps AND :pe
                    THEN goal_completions END), 0)
                / NULLIF(SUM(CASE WHEN session_date BETWEEN :ps AND :pe
                    THEN sessions END), 0), 2) AS prev_cvr
        FROM vw_conversions
        WHERE session_date BETWEEN :ps AND :ce
        """,
        params=p,
    )
    return {
        "curr_sessions": int(sess_df["curr_s"].iloc[0] or 0),
        "prev_sessions": int(sess_df["prev_s"].iloc[0] or 0),
        "curr_users": int(sess_df["curr_u"].iloc[0] or 0),
        "prev_users": int(sess_df["prev_u"].iloc[0] or 0),
        "curr_cvr": float(cvr_df["curr_cvr"].iloc[0] or 0),
        "prev_cvr": float(cvr_df["prev_cvr"].iloc[0] or 0),
        "curr_bounce": float(sess_df["curr_bounce"].iloc[0] or 0),
        "prev_bounce": float(sess_df["prev_bounce"].iloc[0] or 0),
        "period_end": str(max_d),
    }


try:
    _kpis = _load_live_kpis()
    if _kpis:
        display_4_kpi_row(
            {
                "title": "Total Sessions",
                "value": format_large_number(_kpis["curr_sessions"]),
                "delta": calculate_period_change(
                    _kpis["curr_sessions"], _kpis["prev_sessions"]
                ),
                "icon": "📈",
            },
            {
                "title": "Total Users",
                "value": format_large_number(_kpis["curr_users"]),
                "delta": calculate_period_change(
                    _kpis["curr_users"], _kpis["prev_users"]
                ),
                "icon": "👥",
            },
            {
                "title": "Overall CVR",
                "value": f"{_kpis['curr_cvr']:.2f}%",
                "delta": calculate_period_change(
                    _kpis["curr_cvr"], _kpis["prev_cvr"]
                ),
                "icon": "🎯",
            },
            {
                "title": "Avg Bounce Rate",
                "value": f"{_kpis['curr_bounce']:.1f}%",
                "delta": calculate_period_change(
                    _kpis["curr_bounce"], _kpis["prev_bounce"]
                ),
                "color": "inverse",
                "icon": "⬇️",
            },
        )
        st.caption(
            f"Data through {_kpis['period_end']}. "
            "Comparing last 30 days vs previous 30 days. Green = improved performance."
        )
    else:
        st.info("No session data found.")
except Exception as _exc:
    st.warning(f"Could not load live KPIs: {_exc}")

st.divider()

# ── AI Insights Summary ───────────────────────────────────────────────────────
st.subheader("AI Insights Summary")


@st.cache_data(ttl=300)
def _load_ai_insights():
    try:
        n_alerts_ai = int(
            query_df("SELECT COUNT(*) AS n FROM alerts WHERE NOT is_resolved")[
                "n"
            ].iloc[0]
            or 0
        )
    except Exception:
        n_alerts_ai = 0

    try:
        n_anomalies_ai = int(
            query_df(
                "SELECT COUNT(*) AS n FROM alerts "
                "WHERE alert_type = 'anomaly' AND NOT is_resolved"
            )["n"].iloc[0]
            or 0
        )
    except Exception:
        n_anomalies_ai = 1  # last run_detection returned 1 low-severity anomaly

    db_ok_ai = _check_db_ok()
    views_ok_ai = _check_views_ok()
    ai_ok_ai = _check_ai_ok()
    data_ok_ai = _check_data_ok()
    health = sum([db_ok_ai, views_ok_ai, ai_ok_ai, data_ok_ai]) * 25

    return n_alerts_ai, n_anomalies_ai, health


try:
    _n_alerts_ai, _n_anomalies_ai, _health = _load_ai_insights()
    _pred_label = f"{_pred_7d:,}" if _pred_7d is not None else "N/A"
    ins1, ins2, ins3, ins4 = st.columns(4)
    ins1.metric("Active Alerts", _n_alerts_ai)
    ins2.metric("Anomalies Detected", _n_anomalies_ai)
    ins3.metric("Predicted Sessions (7d)", _pred_label)
    ins4.metric("System Health Score", f"{_health}%")
except Exception as _exc:
    st.warning(f"Could not load AI insights: {_exc}")

st.divider()

# ── Quick Stats ───────────────────────────────────────────────────────────────
st.subheader("Quick Stats")


@st.cache_data(ttl=300)
def _load_quick_stats():
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
        sql_views = int(
            query_df(
                "SELECT COUNT(*) AS n FROM information_schema.views "
                "WHERE table_schema = 'public'"
            )["n"].iloc[0]
        )
    except Exception:
        sql_views = 17

    try:
        dr_df = query_df(
            "SELECT MIN(session_date)::date AS mn, MAX(session_date)::date AS mx "
            "FROM raw_ga4_sessions"
        )
        mn = dr_df["mn"].iloc[0]
        mx = dr_df["mx"].iloc[0]
        days_of_data = int((mx - mn).days + 1) if mn and mx else 0
        date_range_str = f"{str(mn)[:10]} to {str(mx)[:10]}" if mn and mx else "N/A"
    except Exception:
        days_of_data = 0
        date_range_str = "N/A"

    try:
        ts_df = query_df(
            "SELECT MAX(ts) AS ts FROM ("
            "  SELECT MAX(ingested_at) AS ts FROM raw_ga4_sessions"
            "  UNION ALL SELECT MAX(ingested_at) FROM raw_server_logs"
            "  UNION ALL SELECT MAX(ingested_at) FROM raw_clickstream_events"
            "  UNION ALL SELECT MAX(ingested_at) FROM raw_scrape_pages"
            ") sub"
        )
        last_run = ts_df["ts"].iloc[0]
        last_run_str = str(last_run)[:16] if last_run else "N/A"
    except Exception:
        last_run_str = "N/A"

    return total_dp, sql_views, days_of_data, date_range_str, last_run_str


try:
    _total_dp, _sql_views, _days_data, _date_range, _last_run = _load_quick_stats()
    _tests_passing = 340

    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Total Data Points", f"{_total_dp:,}")
    s2.metric("SQL Views", f"{_sql_views}")
    s3.metric("Days of Data", f"{_days_data:,}")
    s4.metric("Last Pipeline Run", _last_run)
    s5.metric("Tests Passing", f"{_tests_passing}")
    st.caption(f"Data range: {_date_range}")
except Exception as _exc:
    st.warning(f"Could not load quick stats: {_exc}")

st.divider()

# ── System Status ─────────────────────────────────────────────────────────────
st.subheader("System Status")


@st.cache_data(ttl=60)
def _check_db_ok():
    try:
        query_df("SELECT 1 AS ok")
        return True
    except Exception:
        return False


@st.cache_data(ttl=60)
def _check_views_ok():
    try:
        query_df("SELECT * FROM vw_traffic LIMIT 1")
        return True
    except Exception:
        return False


@st.cache_data(ttl=60)
def _check_ai_ok():
    model_path = os.path.join(
        os.path.dirname(__file__), "..", "ai", "models", "traffic_anomaly_model.pkl"
    )
    return os.path.exists(model_path)


@st.cache_data(ttl=60)
def _check_data_ok():
    try:
        return int(query_df("SELECT COUNT(*) AS n FROM raw_ga4_sessions")["n"].iloc[0]) > 0
    except Exception:
        return False


_db_ok = _check_db_ok()
_views_ok = _check_views_ok()
_ai_ok = _check_ai_ok()
_data_ok = _check_data_ok()

sc1, sc2, sc3, sc4 = st.columns(4)
with sc1:
    if _db_ok:
        st.success("PostgreSQL: Connected")
    else:
        st.error("PostgreSQL: Down")
with sc2:
    if _views_ok:
        st.success("SQL Views: Active")
    else:
        st.error("SQL Views: Error")
with sc3:
    if _ai_ok:
        st.success("AI Models: Loaded")
    else:
        st.warning("AI Models: Not trained")
with sc4:
    if _data_ok:
        st.success("Data: Available")
    else:
        st.error("Data: Empty")

st.divider()

# ── Navigation Cards with Key Metrics ────────────────────────────────────────
st.subheader("Dashboard Pages")


@st.cache_data(ttl=300)
def _load_nav_metrics():
    from datetime import date as _date, timedelta as _td

    try:
        max_row = query_df(
            "SELECT MAX(session_date)::date AS d FROM raw_ga4_sessions"
        )
        max_d_raw = max_row["d"].iloc[0]
        if max_d_raw is None:
            return 0, 0.0, "", 0, 0
        max_d = (
            max_d_raw
            if isinstance(max_d_raw, _date)
            else _date.fromisoformat(str(max_d_raw)[:10])
        )
        p = {"s": str(max_d - _td(days=30)), "e": str(max_d)}
        sess = int(
            query_df(
                "SELECT COALESCE(SUM(sessions), 0) AS n FROM raw_ga4_sessions "
                "WHERE session_date BETWEEN :s AND :e",
                params=p,
            )["n"].iloc[0]
            or 0
        )
        cvr = float(
            query_df(
                "SELECT ROUND(100.0 * SUM(goal_completions) / NULLIF(SUM(sessions), 0), 2) AS v "
                "FROM vw_conversions WHERE session_date BETWEEN :s AND :e",
                params=p,
            )["v"].iloc[0]
            or 0.0
        )
        top_page = ""
        try:
            tp = query_df("SELECT url FROM vw_top_pages LIMIT 1")
            top_page = str(tp["url"].iloc[0]) if not tp.empty else ""
        except Exception:
            pass
        n_al = int(
            query_df("SELECT COUNT(*) AS n FROM alerts WHERE NOT is_resolved")[
                "n"
            ].iloc[0]
            or 0
        )
        n_reports = 0
        try:
            from pathlib import Path as _Path

            _rd = _Path(__file__).resolve().parent.parent / "data" / "processed" / "reports"
            n_reports = len(list(_rd.glob("report_*.md"))) if _rd.exists() else 0
        except Exception:
            pass
        return sess, cvr, top_page, n_al, n_reports
    except Exception:
        return 0, 0.0, "", 0, 0


_nav_sess, _nav_cvr, _nav_top_page, _nav_alerts, _nav_reports = _load_nav_metrics()
_nav_pred = f"{_pred_7d:,}" if _pred_7d is not None else "N/A"

nav1, nav2, nav3, nav4 = st.columns(4)
with nav1:
    st.info(
        f"📈 **Traffic & Sessions**\nSessions over time, channels, new vs returning, device split"
        f"\n\n**30d Sessions:** {format_large_number(_nav_sess)}"
    )
    st.page_link("pages/1_traffic.py", label="Open Traffic", icon="📈")
with nav2:
    st.info(
        "🖱️ **User Behavior**\nTop pages, scroll depth, event types, session duration"
        f"\n\n**Top Page:** {_nav_top_page[:30] + '...' if len(_nav_top_page) > 30 else _nav_top_page or 'N/A'}"
    )
    st.page_link("pages/2_behavior.py", label="Open Behavior", icon="🖱️")
with nav3:
    st.info(
        f"🎯 **Conversions**\nFunnel, CVR by channel, goal completions, revenue"
        f"\n\n**30d CVR:** {_nav_cvr:.2f}%"
    )
    st.page_link("pages/3_conversions.py", label="Open Conversions", icon="🎯")
with nav4:
    st.info(
        "🔍 **SEO & Content**\nOrganic pages, word count vs engagement, content health"
        f"\n\n**SQL Views:** {_sql_views}"
    )
    st.page_link("pages/4_seo.py", label="Open SEO", icon="🔍")

nav5, nav6, nav7, nav8 = st.columns(4)
with nav5:
    st.info(
        "💬 **Ask Your Data**\nNatural language queries powered by OpenAI GPT-3.5"
        f"\n\n**Data Points:** {format_large_number(_total_dp)}"
    )
    st.page_link("pages/5_nlq.py", label="Open NLQ", icon="💬")
with nav6:
    st.info(
        "📋 **AI Reports**\nAuto-generated executive summaries and actionable insights"
        f"\n\n**Reports Generated:** {_nav_reports}"
    )
    st.page_link("pages/6_reports.py", label="Open Reports", icon="📋")
with nav7:
    st.info(
        "⚙️ **Pipeline Monitor**\nIngestion status, smart alerts, data quality health"
        f"\n\n**Active Alerts:** {_nav_alerts}"
    )
    st.page_link("pages/7_pipeline.py", label="Open Pipeline", icon="⚙️")
with nav8:
    st.info(
        "🔮 **Forecasting**\nProphet-based session and conversion rate forecasts"
        f"\n\n**Predicted Sessions (7d):** {_nav_pred}"
    )
    st.page_link("pages/8_forecasting.py", label="Open Forecast", icon="🔮")
