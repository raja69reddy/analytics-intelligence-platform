"""Conversion Tracking — loads from vw_conversions and vw_funnel."""

import os
import sys
from datetime import timedelta

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd

from dashboard.components.filters import (
    build_where_clause,
    get_channel_filter,
    get_date_filter,
    get_plotly_template,
    show_active_filters,
)
from dashboard.components.metrics import (
    calculate_period_change,
    display_4_kpi_row,
    format_currency,
    format_large_number,
)
from utils.db import query_df
from utils.query_runner import run_view

st.set_page_config(page_title="Conversion Tracking", page_icon="🎯", layout="wide")
st.title("🎯 Conversion Tracking")


# ── Cached data loaders — date-filtered at DB level ───────────────────────────
@st.cache_data(ttl=300)
def _load_conversions(start_date=None, end_date=None, channels: tuple = ()):
    where, params = build_where_clause(start_date, end_date, channels=list(channels) or None)
    return query_df(f"SELECT * FROM vw_conversions {where}", params=params or None)


@st.cache_data(ttl=300)
def _load_funnel():
    return run_view("vw_funnel")


# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")
    start_date, end_date = get_date_filter()
    channels = get_channel_filter()
    st.divider()
    _active = sum([bool(channels)])
    st.caption(f"Date: {start_date} → {end_date}")
    if _active:
        st.success(f"{_active} filter(s) active")
        if channels:
            st.caption(f"Channels: {', '.join(channels)}")
    else:
        st.caption("No extra filters — showing all channels")
    if st.button("Clear data cache", key="conv_clear_cache"):
        st.cache_data.clear()
        st.success("Cache cleared — reloading…")
    st.caption("Cache TTL: 5 min · All queries cached")
    from datetime import datetime as _dt
    st.caption(f"Last loaded: {_dt.now().strftime('%Y-%m-%d %H:%M:%S')}")

_plotly_tpl = get_plotly_template()

# ── Load data ─────────────────────────────────────────────────────────────────
with st.spinner("Loading conversion data…"):
    try:
        df_conv = _load_conversions(start_date, end_date, tuple(channels))
        df_funnel = _load_funnel()
    except Exception as _load_exc:
        st.error(f"Failed to load data from the database: {_load_exc}")
        if st.button("Retry", key="retry_conv_load"):
            st.cache_data.clear()
            st.rerun()
        st.stop()

if df_conv.empty:
    st.info(
        f"No conversion data found for the selected filters "
        f"({start_date} → {end_date}"
        + (f", channels: {', '.join(channels)}" if channels else "")
        + "). Try adjusting the date range or channel filter."
    )

# Date and channel filters applied at DB level

# ── KPI cards — 4 metrics with % change vs previous period ───────────────────
_cv_period_days = (end_date - start_date).days + 1
_cv_prev_start = start_date - timedelta(days=_cv_period_days)
_cv_prev_end = start_date - timedelta(days=1)

df_prev_conv = _load_conversions(_cv_prev_start, _cv_prev_end, tuple(channels))

total_sessions = int(df_conv["sessions"].sum()) if not df_conv.empty else 0
total_completions = int(df_conv["goal_completions"].sum()) if not df_conv.empty else 0
total_revenue = float(df_conv["revenue"].sum()) if not df_conv.empty else 0.0
overall_cvr = (total_completions / total_sessions * 100) if total_sessions else 0.0
avg_rev_per_session = (total_revenue / total_sessions) if total_sessions else 0.0

prev_sessions = int(df_prev_conv["sessions"].sum()) if not df_prev_conv.empty else 0
prev_completions = int(df_prev_conv["goal_completions"].sum()) if not df_prev_conv.empty else 0
prev_revenue = float(df_prev_conv["revenue"].sum()) if not df_prev_conv.empty else 0.0
prev_cvr = (prev_completions / prev_sessions * 100) if prev_sessions else 0.0
prev_avg_rev = (prev_revenue / prev_sessions) if prev_sessions else 0.0

display_4_kpi_row(
    {
        "title": "Overall CVR",
        "value": f"{overall_cvr:.2f}%",
        "delta": calculate_period_change(overall_cvr, prev_cvr),
        "icon": "🎯",
    },
    {
        "title": "Total Goal Completions",
        "value": format_large_number(total_completions),
        "delta": calculate_period_change(total_completions, prev_completions),
        "icon": "✅",
    },
    {
        "title": "Total Revenue",
        "value": format_currency(total_revenue),
        "delta": calculate_period_change(total_revenue, prev_revenue),
        "icon": "💰",
    },
    {
        "title": "Avg Revenue Per Session",
        "value": format_currency(avg_rev_per_session),
        "delta": calculate_period_change(avg_rev_per_session, prev_avg_rev),
        "icon": "💵",
    },
)
st.caption(
    f"Period: {start_date} to {end_date} vs {_cv_prev_start} to {_cv_prev_end}. "
    "Green = improved performance."
)

st.divider()

# ── CVR over time ──────────────────────────────────────────────────────────────
st.subheader("Conversion Rate Over Time")
CVR_TARGET = 3.5  # target CVR % for reference line

if not df_conv.empty:
    daily_cvr = (
        df_conv.groupby("session_date")
        .apply(
            lambda g: pd.Series(
                {
                    "sessions": g["sessions"].sum(),
                    "goal_completions": g["goal_completions"].sum(),
                }
            )
        )
        .reset_index()
    )
    daily_cvr["cvr_pct"] = (
        daily_cvr["goal_completions"] / daily_cvr["sessions"].replace(0, None) * 100
    ).round(4)
    daily_cvr = daily_cvr.sort_values("session_date")
    daily_cvr["cvr_7day_avg"] = (
        daily_cvr["cvr_pct"].rolling(7, min_periods=1).mean().round(4)
    )

    fig_cvr = go.Figure()
    # Color bars green/red depending on target
    colors = [
        "#2ca02c" if v >= CVR_TARGET else "#d62728"
        for v in daily_cvr["cvr_pct"].fillna(0)
    ]
    fig_cvr.add_trace(
        go.Bar(
            x=daily_cvr["session_date"],
            y=daily_cvr["cvr_pct"],
            name="Daily CVR",
            marker_color=colors,
            opacity=0.6,
        )
    )
    fig_cvr.add_trace(
        go.Scatter(
            x=daily_cvr["session_date"],
            y=daily_cvr["cvr_7day_avg"],
            name="7-Day Avg",
            line={"color": "#1f77b4", "width": 2},
        )
    )
    fig_cvr.add_hline(
        y=CVR_TARGET,
        line_dash="dash",
        line_color="orange",
        annotation_text=f"Target {CVR_TARGET}%",
        annotation_position="bottom right",
    )
    fig_cvr.update_layout(
        title="Conversion Rate % — Daily with 7-Day Rolling Average",
        xaxis_title="Date",
        yaxis_title="CVR (%)",
        template="plotly_white",
        legend=dict(orientation="h"),
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
        df_src,
        x="source_medium",
        y="goal_completions",
        color="channel_grouping",
        title="Goal Completions by Source / Medium (Top 15)",
        labels={
            "source_medium": "Source / Medium",
            "goal_completions": "Completions",
            "channel_grouping": "Channel",
        },
        template="plotly_white",
    )
    fig_src.update_xaxes(tickangle=30)
    st.plotly_chart(fig_src, use_container_width=True)
else:
    st.info("No source/medium data available.")

st.divider()

# ── Revenue by channel ─────────────────────────────────────────────────────────
st.subheader("Revenue by Channel")
if not df_conv.empty:
    df_rev = (
        df_conv.groupby("channel_grouping")["revenue"]
        .sum()
        .reset_index()
        .sort_values("revenue", ascending=True)
    )
    fig_rev = go.Figure(
        go.Bar(
            x=df_rev["revenue"],
            y=df_rev["channel_grouping"],
            orientation="h",
            text=[f"${v:,.0f}" for v in df_rev["revenue"]],
            textposition="outside",
            marker_color="#636EFA",
        )
    )
    fig_rev.update_layout(
        title="Total Revenue by Channel",
        xaxis_title="Revenue ($)",
        yaxis_title="Channel",
        template="plotly_white",
    )
    st.plotly_chart(fig_rev, use_container_width=True)
else:
    st.info("No revenue data available.")

st.divider()

# ── Drop-off waterfall chart ───────────────────────────────────────────────────
st.subheader("Funnel Drop-off Analysis")
if not df_funnel.empty:
    stages = df_funnel["stage_name"].tolist()
    reached = df_funnel["users_reached"].tolist()
    dropoffs = df_funnel["drop_off_count"].tolist()

    # Waterfall: first bar absolute (total), then each stage = -dropoff
    wf_x = [stages[0]] + stages[1:]
    wf_measure = ["absolute"] + ["relative"] * (len(stages) - 1)
    wf_y = [reached[0]] + [-d for d in dropoffs[:-1]] + [0]
    wf_colors = (
        ["#636EFA"]
        + ["#d62728" if d > 0 else "#2ca02c" for d in dropoffs[:-1]]
        + ["#2ca02c"]
    )

    fig_wf = go.Figure(
        go.Waterfall(
            name="Funnel",
            orientation="v",
            measure=wf_measure,
            x=wf_x,
            y=wf_y,
            text=[f"{v:,}" for v in ([reached[0]] + [-d for d in dropoffs[:-1]] + [0])],
            textposition="outside",
            connector={"line": {"color": "rgba(63,63,63,0.3)"}},
            increasing={"marker": {"color": "#2ca02c"}},
            decreasing={"marker": {"color": "#d62728"}},
            totals={"marker": {"color": "#636EFA"}},
        )
    )
    fig_wf.update_layout(
        title="Users Entering vs Dropping Off at Each Stage",
        xaxis_title="Funnel Stage",
        yaxis_title="Users",
        template="plotly_white",
        waterfallgap=0.3,
    )
    st.plotly_chart(fig_wf, use_container_width=True)
else:
    st.info("No funnel data available.")

st.divider()

# ── Conversion funnel visualization ───────────────────────────────────────────
st.subheader("Conversion Funnel")
if not df_funnel.empty:
    df_f = df_funnel.copy()
    df_f["label"] = (
        df_f["stage_name"]
        + "<br>"
        + df_f["users_reached"].apply(lambda v: f"{int(v):,}")
        + " ("
        + df_f["completion_rate_pct"].apply(lambda v: f"{v:.1f}%")
        + ")"
    )

    # Identify the stage with the biggest drop-off (excluding last stage)
    max_drop_idx = int(df_f.iloc[:-1]["drop_off_count"].idxmax())

    colors = []
    for i, row in df_f.iterrows():
        if i == max_drop_idx:
            colors.append("#d62728")  # red = biggest drop-off stage
        else:
            colors.append("#636EFA")

    fig_funnel = go.Figure(
        go.Funnel(
            y=df_f["stage_name"].tolist(),
            x=df_f["users_reached"].tolist(),
            text=df_f["label"].tolist(),
            textinfo="text",
            marker={"color": colors},
            connector={"line": {"color": "rgba(100,100,100,0.3)", "width": 2}},
        )
    )
    biggest_stage = df_f.loc[max_drop_idx, "stage_name"]
    fig_funnel.update_layout(
        title=f"Funnel — Biggest drop-off at: {biggest_stage}",
        template="plotly_white",
    )
    st.plotly_chart(fig_funnel, use_container_width=True)
else:
    st.info("No funnel data available.")

st.divider()

# ── Channel contribution table ─────────────────────────────────────────────────
st.subheader("Channel Contribution")
if not df_conv.empty:
    df_ch = (
        df_conv.groupby("channel_grouping")
        .agg(
            sessions=("sessions", "sum"),
            goal_completions=("goal_completions", "sum"),
            revenue=("revenue", "sum"),
        )
        .reset_index()
        .sort_values("goal_completions", ascending=False)
    )
    df_ch["cvr_pct"] = (
        df_ch["goal_completions"] / df_ch["sessions"].replace(0, None) * 100
    ).round(2)
    df_ch["revenue"] = df_ch["revenue"].round(2)
    df_ch.rename(
        columns={
            "channel_grouping": "Channel",
            "sessions": "Sessions",
            "goal_completions": "Conversions",
            "cvr_pct": "CVR (%)",
            "revenue": "Revenue ($)",
        },
        inplace=True,
    )

    st.dataframe(df_ch, use_container_width=True, hide_index=True)
    st.download_button(
        label="Download channel table as CSV",
        data=df_ch.to_csv(index=False).encode("utf-8"),
        file_name="channel_contribution.csv",
        mime="text/csv",
    )
else:
    st.info("No channel data available.")

st.divider()

# ── Conversion trend by day of week ───────────────────────────────────────────
st.subheader("Conversion Trend by Day of Week")
if not df_conv.empty:
    df_dow = df_conv.copy()
    df_dow["session_date"] = pd.to_datetime(df_dow["session_date"])
    df_dow["dow"] = df_dow["session_date"].dt.dayofweek  # 0=Mon … 6=Sun
    df_dow["day_name"] = df_dow["session_date"].dt.strftime("%A")

    dow_agg = (
        df_dow.groupby(["dow", "day_name"])["goal_completions"]
        .mean()
        .reset_index()
        .sort_values("dow")
    )
    best_dow = int(dow_agg.loc[dow_agg["goal_completions"].idxmax(), "dow"])
    dow_colors = ["#2ca02c" if d == best_dow else "#636EFA" for d in dow_agg["dow"]]

    fig_dow = go.Figure(
        go.Bar(
            x=dow_agg["day_name"],
            y=dow_agg["goal_completions"].round(1),
            text=dow_agg["goal_completions"].round(1),
            textposition="outside",
            marker_color=dow_colors,
        )
    )
    best_day_name = dow_agg.loc[dow_agg["dow"] == best_dow, "day_name"].iloc[0]
    fig_dow.update_layout(
        title=f"Avg Goal Completions by Day of Week — Best day: {best_day_name}",
        xaxis_title="Day of Week",
        yaxis_title="Avg Completions",
        template="plotly_white",
    )
    st.plotly_chart(fig_dow, use_container_width=True)
else:
    st.info("No data available for day-of-week analysis.")
