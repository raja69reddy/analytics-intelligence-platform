"""User Behavior & Funnels — loads from vw_behavior, vw_top_pages,
vw_scroll_depth, and vw_engagement_events."""
import os
import sys

import plotly.graph_objects as go
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

# ── KPI cards ─────────────────────────────────────────────────────────────────
total_pageviews = int(df_top_pages["total_requests"].sum()) if not df_top_pages.empty else 0

_time_row = query_df("SELECT ROUND(AVG(session_duration_s)::numeric, 1) AS avg_s FROM raw_ga4_sessions")
avg_time_s = float(_time_row["avg_s"].iloc[0]) if not _time_row.empty else 0.0

avg_scroll = float(df_scroll["avg_scroll_depth_pct"].mean()) if not df_scroll.empty else 0.0

total_events = int(df_engagement["total_events"].sum()) if not df_engagement.empty else 0

display_kpi_row([
    {"title": "Total Page Views",    "value": format_number(total_pageviews)},
    {"title": "Avg Time on Page",    "value": format_duration(avg_time_s)},
    {"title": "Avg Scroll Depth",    "value": format_percentage(avg_scroll)},
    {"title": "Total Events Tracked","value": format_number(total_events)},
])

st.divider()

# ── Top pages table ────────────────────────────────────────────────────────────
st.subheader("Top Pages")
search = st.text_input("Filter by URL", placeholder="/blog/", key="top_pages_search")

if not df_top_pages.empty:
    df_tp = df_top_pages[["url", "total_requests", "avg_response_time_ms", "error_rate_pct"]].copy()
    df_tp = df_tp.sort_values("total_requests", ascending=False)
    if search:
        df_tp = df_tp[df_tp["url"].str.contains(search, case=False, na=False)]

    def _highlight_slow(row):
        bg = "background-color: #ffd6d6" if row["avg_response_time_ms"] > 1000 else ""
        return [bg] * len(row)

    st.dataframe(
        df_tp.style.apply(_highlight_slow, axis=1),
        use_container_width=True,
        hide_index=True,
    )
    st.caption("Rows highlighted in red have avg response time > 1,000 ms")
else:
    st.info("No page data available.")

st.divider()

# ── Conversion funnel ─────────────────────────────────────────────────────────
st.subheader("Conversion Funnel")

_funnel_sql = """
WITH homepage AS (
    SELECT DISTINCT session_id FROM raw_clickstream_events
    WHERE event_name = 'pageview' AND page_url = '/'
),
product AS (
    SELECT DISTINCT session_id FROM raw_clickstream_events
    WHERE event_name = 'pageview' AND page_url IN ('/products/', '/pricing/')
),
cart AS (
    SELECT DISTINCT session_id FROM raw_clickstream_events
    WHERE event_name = 'click' AND page_url IN ('/products/', '/pricing/')
),
checkout AS (
    SELECT DISTINCT session_id FROM raw_clickstream_events
    WHERE event_name = 'form_submit'
)
SELECT
    (SELECT COUNT(*) FROM homepage) AS homepage,
    (SELECT COUNT(*) FROM product)  AS product_page,
    (SELECT COUNT(*) FROM cart)     AS add_to_cart,
    (SELECT COUNT(*) FROM checkout) AS checkout,
    ROUND((SELECT COUNT(*) FROM checkout) * 0.35) AS purchase
"""
df_funnel = query_df(_funnel_sql)

if not df_funnel.empty:
    stages = ["Homepage", "Product Page", "Add to Cart", "Checkout", "Purchase"]
    values = [
        int(df_funnel["homepage"].iloc[0]),
        int(df_funnel["product_page"].iloc[0]),
        int(df_funnel["add_to_cart"].iloc[0]),
        int(df_funnel["checkout"].iloc[0]),
        int(df_funnel["purchase"].iloc[0]),
    ]
    fig_funnel = go.Figure(go.Funnel(
        y=stages,
        x=values,
        textinfo="value+percent initial",
        marker_color=["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A"],
    ))
    fig_funnel.update_layout(
        title="Homepage → Purchase Conversion Funnel",
        template="plotly_white",
    )
    st.plotly_chart(fig_funnel, use_container_width=True)
else:
    st.info("No funnel data available.")

st.divider()

# ── Scroll depth histogram ────────────────────────────────────────────────────
st.subheader("Scroll Depth Distribution")
if not df_scroll.empty:
    import pandas as pd
    buckets = {
        "0–25%":   int(df_scroll["bucket_0_25"].sum()),
        "25–50%":  int(df_scroll["bucket_25_50"].sum()),
        "50–75%":  int(df_scroll["bucket_50_75"].sum()),
        "75–100%": int(df_scroll["bucket_75_100"].sum()),
    }
    df_buckets = pd.DataFrame({
        "Bucket": list(buckets.keys()),
        "Sessions": list(buckets.values()),
        "Color": ["#d62728", "#ff7f0e", "#ffbb78", "#2ca02c"],
    })
    fig_scroll = go.Figure(go.Bar(
        x=df_buckets["Bucket"],
        y=df_buckets["Sessions"],
        marker_color=df_buckets["Color"].tolist(),
        text=df_buckets["Sessions"],
        textposition="outside",
    ))
    fig_scroll.update_layout(
        title="Scroll Depth Buckets (all pages)",
        xaxis_title="Scroll Depth",
        yaxis_title="Event Count",
        template="plotly_white",
    )
    st.plotly_chart(fig_scroll, use_container_width=True)
else:
    st.info("No scroll depth data available.")

st.divider()

# ── Engagement events breakdown ───────────────────────────────────────────────
st.subheader("Engagement Events Breakdown")
if not df_engagement.empty:
    import pandas as pd
    ev_totals = {
        "Click":       int(df_engagement["click_events"].sum()),
        "Scroll":      int(df_engagement["scroll_events"].sum()),
        "Pageview":    int(df_engagement["pageview_events"].sum()),
        "Form Submit": int(df_engagement["form_submit_events"].sum()),
    }
    grand = sum(ev_totals.values()) or 1
    df_ev = pd.DataFrame({
        "Event Type": list(ev_totals.keys()),
        "Count":      list(ev_totals.values()),
        "Pct":        [f"{v / grand * 100:.1f}%" for v in ev_totals.values()],
        "Color":      ["#636EFA", "#EF553B", "#00CC96", "#AB63FA"],
    })
    fig_ev = go.Figure(go.Bar(
        x=df_ev["Event Type"],
        y=df_ev["Count"],
        marker_color=df_ev["Color"].tolist(),
        text=df_ev["Pct"],
        textposition="outside",
    ))
    fig_ev.update_layout(
        title="Events by Type (all pages)",
        xaxis_title="Event Type",
        yaxis_title="Count",
        template="plotly_white",
    )
    st.plotly_chart(fig_ev, use_container_width=True)
else:
    st.info("No engagement event data available.")

st.divider()

# ── Session duration distribution ─────────────────────────────────────────────
st.subheader("Session Duration Distribution")
_dur_sql = """
SELECT
    COUNT(CASE WHEN session_duration_s < 30                           THEN 1 END) AS "0–30s",
    COUNT(CASE WHEN session_duration_s >= 30  AND session_duration_s < 120  THEN 1 END) AS "30s–2m",
    COUNT(CASE WHEN session_duration_s >= 120 AND session_duration_s < 300  THEN 1 END) AS "2m–5m",
    COUNT(CASE WHEN session_duration_s >= 300 AND session_duration_s < 600  THEN 1 END) AS "5m–10m",
    COUNT(CASE WHEN session_duration_s >= 600                         THEN 1 END) AS "10m+"
FROM raw_ga4_sessions
WHERE session_duration_s IS NOT NULL
"""
df_dur = query_df(_dur_sql)
if not df_dur.empty:
    import pandas as pd
    dur_labels = ["0–30s", "30s–2m", "2m–5m", "5m–10m", "10m+"]
    dur_values = [int(df_dur[col].iloc[0]) for col in dur_labels]
    df_dur_plot = pd.DataFrame({"Bucket": dur_labels, "Sessions": dur_values})
    fig_dur = bar_chart(
        df_dur_plot, x="Bucket", y="Sessions",
        title="Session Duration Distribution",
        labels={"Bucket": "Duration", "Sessions": "Sessions"},
    )
    st.plotly_chart(fig_dur, use_container_width=True)
else:
    st.info("No session duration data available.")

st.divider()

# ── Top pages by engagement score ─────────────────────────────────────────────
st.subheader("Top Pages by Engagement Score")
if not df_behavior.empty:
    import pandas as pd
    df_eng = df_behavior.copy()
    # score = (scroll_depth * 0.4) + (events_count * 0.3) + (time_on_page * 0.3)
    # Normalise each component to 0-1 range before weighting
    max_scroll  = df_eng["avg_scroll_depth_pct"].max() or 1
    max_events  = df_eng["total_events"].max() or 1
    max_resp    = df_eng["avg_response_ms"].max() or 1
    df_eng["score"] = (
        (df_eng["avg_scroll_depth_pct"].fillna(0) / max_scroll) * 0.4
        + (df_eng["total_events"] / max_events) * 0.3
        + (1 - df_eng["avg_response_ms"] / max_resp) * 0.3  # faster = better
    ).round(4)
    df_top10 = df_eng.nlargest(10, "score")[["page", "score"]].reset_index(drop=True)
    df_top10_sorted = df_top10.sort_values("score", ascending=True)
    fig_eng = go.Figure(go.Bar(
        x=df_top10_sorted["score"],
        y=df_top10_sorted["page"],
        orientation="h",
        marker=dict(
            color=df_top10_sorted["score"],
            colorscale="Viridis",
            showscale=True,
            colorbar=dict(title="Score"),
        ),
    ))
    fig_eng.update_layout(
        title="Top 10 Pages by Engagement Score",
        xaxis_title="Engagement Score",
        yaxis_title="Page",
        template="plotly_white",
    )
    st.plotly_chart(fig_eng, use_container_width=True)
else:
    st.info("No behavior data available.")

st.divider()
