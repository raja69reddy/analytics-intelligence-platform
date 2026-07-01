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
