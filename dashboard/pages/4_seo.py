"""SEO & Content Performance dashboard page."""
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dashboard.components.filters import get_date_filter, get_page_filter
from utils.db import query_df

st.set_page_config(page_title="SEO & Content", page_icon="🔍", layout="wide")
st.title("🔍 SEO & Content Performance")

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("SEO Filters")
    start_date, end_date = get_date_filter()
    page_search = get_page_filter()

start_str = start_date.isoformat()
end_str   = end_date.isoformat()

# ── KPI cards ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def _load_kpis():
    organic = query_df(
        "SELECT SUM(organic_sessions) AS total_organic_sessions, "
        "ROUND(AVG(word_count)) AS avg_word_count, "
        "COUNT(CASE WHEN missing_meta_description THEN 1 END) AS missing_meta "
        "FROM vw_seo"
    )
    load_time = query_df(
        "SELECT ROUND(AVG(load_time_ms)) AS avg_load_ms FROM raw_scrape_pages WHERE http_status = 200"
    )
    return organic, load_time

with st.spinner("Loading KPIs..."):
    try:
        _organic_kpi, _load_kpi = _load_kpis()
        total_organic = int(_organic_kpi["total_organic_sessions"].iloc[0] or 0)
        avg_word_count = int(_organic_kpi["avg_word_count"].iloc[0] or 0)
        missing_meta = int(_organic_kpi["missing_meta"].iloc[0] or 0)
        avg_load_ms = int(_load_kpi["avg_load_ms"].iloc[0] or 0)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Organic Sessions", f"{total_organic:,}")
        col2.metric("Avg Page Load Time", f"{avg_load_ms:,} ms",
                    delta=None,
                    help="Average load time across all crawled pages (200 status only)")
        col3.metric("Pages Missing Meta Description", f"{missing_meta}")
        col4.metric("Avg Word Count per Page", f"{avg_word_count:,}")
    except Exception as exc:
        st.error(f"Could not load KPIs: {exc}")

st.divider()
