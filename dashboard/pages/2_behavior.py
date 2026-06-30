"""User Behavior & Funnels — loads from vw_behavior, vw_top_pages,
vw_scroll_depth, and vw_engagement_events."""
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dashboard.components.charts import bar_chart, line_chart
from dashboard.components.filters import get_date_filter, get_page_filter
from dashboard.components.metrics import (
    display_kpi_row,
    format_duration,
    format_number,
    format_percentage,
)
from utils.db import query_df
from utils.query_runner import run_view

st.set_page_config(
    page_title="User Behavior & Funnels", page_icon="🖱️", layout="wide"
)
st.title("🖱️ User Behavior & Funnels")

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")
    start_date, end_date = get_date_filter()
    page_search = get_page_filter()
    if page_search:
        st.success("Page filter applied")

# ── Load data ─────────────────────────────────────────────────────────────────
df_behavior   = run_view("vw_behavior")
df_top_pages  = run_view("vw_top_pages")
df_scroll     = run_view("vw_scroll_depth")
df_engagement = run_view("vw_engagement_events")

# Apply page URL filter
if page_search:
    df_behavior   = df_behavior[df_behavior["page"].str.contains(page_search, case=False, na=False)].reset_index(drop=True)
    df_top_pages  = df_top_pages[df_top_pages["url"].str.contains(page_search, case=False, na=False)].reset_index(drop=True)
    df_scroll     = df_scroll[df_scroll["page_url"].str.contains(page_search, case=False, na=False)].reset_index(drop=True)
    df_engagement = df_engagement[df_engagement["page_url"].str.contains(page_search, case=False, na=False)].reset_index(drop=True)

with st.expander("Debug: data shapes", expanded=False):
    st.write({
        "vw_behavior":          df_behavior.shape,
        "vw_top_pages":         df_top_pages.shape,
        "vw_scroll_depth":      df_scroll.shape,
        "vw_engagement_events": df_engagement.shape,
    })

st.info("Dashboard sections loading below…")
