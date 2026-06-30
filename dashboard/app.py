"""
Analytics Intelligence Platform — main Streamlit entry point.

Run:
    streamlit run dashboard/app.py
"""
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai.anomaly_detection.detector import AnomalyDetector  # noqa: E402
from ai.anomaly_detection.train import load_model           # noqa: E402
from ai.anomaly_detection.utils import load_traffic_data    # noqa: E402
from dashboard.components.filters import (                  # noqa: E402
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

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📊 Analytics Intelligence")
    st.caption("PostgreSQL + Python + Streamlit + AI/ML")
    st.divider()

    st.subheader("Navigation")
    st.page_link("pages/1_traffic.py",     label="Traffic & Sessions",  icon="📈")
    st.page_link("pages/2_behavior.py",    label="User Behavior",       icon="🖱️")
    st.page_link("pages/3_conversions.py", label="Conversions",         icon="🎯")
    st.page_link("pages/4_seo.py",         label="SEO & Content",       icon="🔍")
    st.divider()

    # ── AI Anomaly Alerts ─────────────────────────────────────────────────────
    st.subheader("🤖 AI Anomaly Alerts")

    @st.cache_data(ttl=300)
    def _sidebar_anomaly_summary():
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
        high  = alert_summary.severity_counts.get("high", 0)
        med   = alert_summary.severity_counts.get("medium", 0)

        st.metric("Anomalies Detected", total)

        if alert_summary.anomaly_dates:
            most_recent = alert_summary.anomaly_dates[-1]
            # find severity of most recent
            recent_df = None
            if alert_summary.anomalies_df is not None and not alert_summary.anomalies_df.empty:
                row = alert_summary.anomalies_df[
                    alert_summary.anomalies_df["session_date"].astype(str) == most_recent
                ]
                recent_sev = row["severity"].values[0] if len(row) else "low"
            else:
                recent_sev = "low"
            st.caption(f"Most recent: {most_recent} — {recent_sev.upper()}")

        if high > 0:
            st.error(f"🔴 {high} high-severity anomaly(s) detected!")
        if med > 0:
            st.warning(f"🟡 {med} medium-severity anomaly(s) — review recommended.")
        if total == 0:
            st.success("🟢 No anomalies detected — traffic looks healthy.")

        if st.button("View All Anomalies", key="sidebar_anomalies"):
            st.switch_page("pages/1_traffic.py")

    st.divider()

    st.subheader("Global Filters")
    start_date, end_date = get_date_filter()
    channels   = get_channel_filter()
    page_search = get_page_filter()
    devices    = get_device_filter()

    st.divider()
    active = sum([bool(channels), bool(page_search), bool(devices)])
    if active:
        st.success(f"Filters applied: {active}")
    else:
        st.caption("No filters active — showing all data")

# ── Main page ────────────────────────────────────────────────────────────────
st.title("Welcome to Analytics Intelligence Platform")
st.markdown("""
A production-grade analytics platform powered by **PostgreSQL**, **Python**, **Streamlit**, and **AI/ML**.

Use the **sidebar** to filter by date range, channel, and page URL.
Use the **navigation links** to explore each section.
""")

st.divider()

# Project stats
from utils.db import query_df  # noqa: E402

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
    df = query_df("SELECT MIN(session_date) AS mn, MAX(session_date) AS mx FROM raw_ga4_sessions")
    mn, mx = str(df["mn"].iloc[0])[:10], str(df["mx"].iloc[0])[:10]
    st.metric("Data Range", f"{mn} → {mx}")

st.divider()

st.subheader("Dashboard Pages")
c1, c2, c3, c4 = st.columns(4)
c1.info("📈 **Traffic & Sessions**\nSessions over time, channels, new vs returning, device split")
c2.info("🖱️ **User Behavior**\nTop pages, scroll depth, event types, response times")
c3.info("🎯 **Conversions**\nFunnel, form submissions, bounce rates by channel")
c4.info("🔍 **SEO & Content**\nOrganic pages, word count vs engagement, content health")
