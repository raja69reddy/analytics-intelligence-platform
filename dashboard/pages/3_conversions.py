"""Conversion Tracking — loads from vw_conversions and vw_funnel."""
import os
import sys

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dashboard.components.charts import bar_chart, line_chart, pie_chart
from dashboard.components.filters import get_channel_filter, get_date_filter
from dashboard.components.metrics import (
    display_kpi_row,
    format_number,
    format_percentage,
)
from utils.query_runner import run_view

st.set_page_config(
    page_title="Conversion Tracking", page_icon="🎯", layout="wide"
)
st.title("🎯 Conversion Tracking")

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")
    start_date, end_date = get_date_filter()
    channels = get_channel_filter()
    if channels:
        st.success(f"Channel filter: {len(channels)} selected")

# ── Load data ─────────────────────────────────────────────────────────────────
df_conv  = run_view("vw_conversions")
df_funnel = run_view("vw_funnel")

# Apply date and channel filters to vw_conversions
from dashboard.components.filters import apply_filters  # noqa: E402
import pandas as pd                                     # noqa: E402

df_conv = apply_filters(df_conv, start_date, end_date, channels)

with st.expander("Debug: data shapes", expanded=False):
    st.write({
        "vw_conversions": df_conv.shape,
        "vw_funnel":      df_funnel.shape,
    })

# ── KPI cards ─────────────────────────────────────────────────────────────────
total_sessions      = int(df_conv["sessions"].sum())        if not df_conv.empty else 0
total_completions   = int(df_conv["goal_completions"].sum()) if not df_conv.empty else 0
total_revenue       = float(df_conv["revenue"].sum())        if not df_conv.empty else 0.0
overall_cvr         = (total_completions / total_sessions * 100) if total_sessions else 0.0
avg_rev_per_session = (total_revenue / total_sessions) if total_sessions else 0.0

display_kpi_row([
    {"title": "Overall Conversion Rate", "value": f"{overall_cvr:.2f}%"},
    {"title": "Total Goal Completions",  "value": format_number(total_completions)},
    {"title": "Total Revenue",           "value": f"${total_revenue:,.2f}"},
    {"title": "Avg Revenue Per Session", "value": f"${avg_rev_per_session:.2f}"},
])

st.divider()

# ── CVR over time ──────────────────────────────────────────────────────────────
st.subheader("Conversion Rate Over Time")
CVR_TARGET = 3.5  # target CVR % for reference line

if not df_conv.empty:
    daily_cvr = (
        df_conv.groupby("session_date")
        .apply(lambda g: pd.Series({
            "sessions":        g["sessions"].sum(),
            "goal_completions": g["goal_completions"].sum(),
        }))
        .reset_index()
    )
    daily_cvr["cvr_pct"] = (
        daily_cvr["goal_completions"] / daily_cvr["sessions"].replace(0, None) * 100
    ).round(4)
    daily_cvr = daily_cvr.sort_values("session_date")
    daily_cvr["cvr_7day_avg"] = (
        daily_cvr["cvr_pct"]
        .rolling(7, min_periods=1)
        .mean()
        .round(4)
    )

    fig_cvr = go.Figure()
    # Color bars green/red depending on target
    colors = [
        "#2ca02c" if v >= CVR_TARGET else "#d62728"
        for v in daily_cvr["cvr_pct"].fillna(0)
    ]
    fig_cvr.add_trace(go.Bar(
        x=daily_cvr["session_date"],
        y=daily_cvr["cvr_pct"],
        name="Daily CVR",
        marker_color=colors,
        opacity=0.6,
    ))
    fig_cvr.add_trace(go.Scatter(
        x=daily_cvr["session_date"],
        y=daily_cvr["cvr_7day_avg"],
        name="7-Day Avg",
        line={"color": "#1f77b4", "width": 2},
    ))
    fig_cvr.add_hline(
        y=CVR_TARGET, line_dash="dash", line_color="orange",
        annotation_text=f"Target {CVR_TARGET}%",
        annotation_position="bottom right",
    )
    fig_cvr.update_layout(
        title="Conversion Rate % — Daily with 7-Day Rolling Average",
        xaxis_title="Date", yaxis_title="CVR (%)",
        template="plotly_white", legend=dict(orientation="h"),
    )
    st.plotly_chart(fig_cvr, use_container_width=True)
else:
    st.info("No conversion data available for the selected filters.")

st.divider()

# ── Goal completions by source / medium ───────────────────────────────────────
st.subheader("Goal Completions by Source / Medium")
if not df_conv.empty:
    df_src = (
        df_conv.groupby(["source", "medium", "channel_grouping"])["goal_completions"]
        .sum()
        .reset_index()
        .sort_values("goal_completions", ascending=False)
        .head(15)
    )
    df_src["source_medium"] = df_src["source"] + " / " + df_src["medium"]

    import plotly.express as px
    fig_src = px.bar(
        df_src, x="source_medium", y="goal_completions",
        color="channel_grouping",
        title="Goal Completions by Source / Medium (Top 15)",
        labels={"source_medium": "Source / Medium", "goal_completions": "Completions",
                "channel_grouping": "Channel"},
        template="plotly_white",
    )
    fig_src.update_xaxes(tickangle=30)
    st.plotly_chart(fig_src, use_container_width=True)
else:
    st.info("No source/medium data available.")

st.divider()
