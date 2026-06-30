"""
Web Analytics Dashboard — main Streamlit entry point.

Run:
    streamlit run dashboard/app.py
"""
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dashboard.components.filters import (  # noqa: E402
    get_channel_filter,
    get_date_filter,
    get_device_filter,
    get_page_filter,
)

st.set_page_config(
    page_title="Web Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📊 Web Analytics")
    st.caption("Full-stack analytics: PostgreSQL + Python + Streamlit")
    st.divider()

    st.subheader("Navigation")
    st.page_link("pages/1_traffic.py",     label="Traffic & Sessions",  icon="📈")
    st.page_link("pages/2_behavior.py",    label="User Behavior",       icon="🖱️")
    st.page_link("pages/3_conversions.py", label="Conversions",         icon="🎯")
    st.page_link("pages/4_seo.py",         label="SEO & Content",       icon="🔍")
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
st.title("Welcome to Web Analytics Dashboard")
st.markdown("""
A full-stack analytics project powered by **PostgreSQL**, **Python**, and **Streamlit**.

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
