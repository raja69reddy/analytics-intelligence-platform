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
with st.spinner("Loading KPI metrics…"):
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

with st.spinner("Loading CVR trend…"):
    if not df_conv.empty:
        daily_cvr = (
            df_conv.groupby("session_date")
            .agg(sessions=("sessions", "sum"), goal_completions=("goal_completions", "sum"))
            .reset_index()
            .sort_values("session_date")
        )
        daily_cvr["cvr_pct"] = (
            daily_cvr["goal_completions"] / daily_cvr["sessions"].replace(0, None) * 100
        ).round(4)
        daily_cvr["cvr_7day_avg"] = daily_cvr["cvr_pct"].rolling(7, min_periods=1).mean().round(4)
        _above = daily_cvr[daily_cvr["cvr_pct"] >= CVR_TARGET]
        _below = daily_cvr[daily_cvr["cvr_pct"] < CVR_TARGET]

        fig_cvr = go.Figure()
        fig_cvr.add_trace(
            go.Scatter(
                x=_above["session_date"],
                y=_above["cvr_pct"],
                mode="markers",
                name="Above Target",
                marker=dict(color="#2ca02c", size=6),
                hovertemplate="<b>%{x|%Y-%m-%d}</b><br>CVR: %{y:.2f}%<extra></extra>",
            )
        )
        fig_cvr.add_trace(
            go.Scatter(
                x=_below["session_date"],
                y=_below["cvr_pct"],
                mode="markers",
                name="Below Target",
                marker=dict(color="#d62728", size=6),
                hovertemplate="<b>%{x|%Y-%m-%d}</b><br>CVR: %{y:.2f}%<extra></extra>",
            )
        )
        fig_cvr.add_trace(
            go.Scatter(
                x=daily_cvr["session_date"],
                y=daily_cvr["cvr_7day_avg"],
                name="7-Day Rolling Avg",
                mode="lines",
                line=dict(color="#1f77b4", width=2),
                hovertemplate="<b>%{x|%Y-%m-%d}</b><br>7d Avg: %{y:.2f}%<extra></extra>",
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
            template=_plotly_tpl,
            legend=dict(orientation="h"),
            hovermode="x unified",
        )
        fig_cvr.update_xaxes(
            rangeselector=dict(
                buttons=[
                    dict(count=7, label="7D", step="day", stepmode="backward"),
                    dict(count=30, label="30D", step="day", stepmode="backward"),
                    dict(count=90, label="90D", step="day", stepmode="backward"),
                    dict(step="all", label="All"),
                ]
            ),
            rangeslider=dict(visible=False),
        )
        st.plotly_chart(fig_cvr, use_container_width=True)
        _period_avg = daily_cvr["cvr_pct"].mean()
        st.caption(
            f"Period avg CVR: {_period_avg:.2f}% · Target: {CVR_TARGET}% · "
            f"Green = above target · Red = below target"
            + (f" · Channels: {', '.join(channels)}" if channels else "")
        )
    else:
        st.info("No conversion data available for the selected filters.")

st.divider()

# ── Goal completions by source / medium ───────────────────────────────────────
st.subheader("Goal Completions by Source / Medium")
with st.spinner("Loading goal completions by source…"):
    if not df_conv.empty:
        import plotly.express as px

        df_src = (
            df_conv.groupby(["source", "medium", "channel_grouping"])["goal_completions"]
            .sum()
            .reset_index()
            .sort_values("goal_completions", ascending=False)
            .head(15)
        )
        df_src["source_medium"] = df_src["source"] + " / " + df_src["medium"]
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
            template=_plotly_tpl,
        )
        fig_src.update_xaxes(tickangle=30)
        fig_src.update_layout(hovermode="x unified", legend=dict(orientation="h"))
        st.plotly_chart(fig_src, use_container_width=True)
        _src_dl = df_src[["source_medium", "channel_grouping", "goal_completions"]].copy()
        _src_dl.columns = ["Source / Medium", "Channel", "Goal Completions"]
        st.download_button(
            "Download as CSV",
            data=_src_dl.to_csv(index=False).encode("utf-8"),
            file_name="goal_completions_by_source.csv",
            mime="text/csv",
            key="dl_src_csv",
        )
        st.caption(f"Top 15 sources sorted by goal completions · {len(df_src)} rows shown")
    else:
        st.info("No source/medium data available.")

st.divider()

# ── Revenue by channel ─────────────────────────────────────────────────────────
st.subheader("Revenue by Channel")
with st.spinner("Loading revenue by channel…"):
    if not df_conv.empty:
        _CHANNEL_COLORS = [
            "#636EFA", "#EF553B", "#00CC96", "#AB63FA",
            "#FFA15A", "#19D3F3", "#FF6692", "#B6E880",
        ]
        df_rev = (
            df_conv.groupby("channel_grouping")["revenue"]
            .sum()
            .reset_index()
            .sort_values("revenue", ascending=True)
        )
        _rev_colors = [
            _CHANNEL_COLORS[i % len(_CHANNEL_COLORS)]
            for i in range(len(df_rev))
        ]
        fig_rev = go.Figure(
            go.Bar(
                x=df_rev["revenue"],
                y=df_rev["channel_grouping"],
                orientation="h",
                text=[f"${v:,.0f}" for v in df_rev["revenue"]],
                textposition="outside",
                marker_color=_rev_colors,
                hovertemplate="<b>%{y}</b><br>Revenue: $%{x:,.0f}<extra></extra>",
            )
        )
        fig_rev.update_layout(
            title="Total Revenue by Channel",
            xaxis_title="Revenue ($)",
            yaxis_title="Channel",
            template=_plotly_tpl,
        )
        st.plotly_chart(fig_rev, use_container_width=True)
        st.caption(
            f"Total revenue: ${df_rev['revenue'].sum():,.0f} · "
            f"{len(df_rev)} channels · Sorted by revenue ascending"
        )
    else:
        st.info("No revenue data available.")

st.divider()

# ── Drop-off waterfall chart ───────────────────────────────────────────────────
st.subheader("Funnel Drop-off Analysis")
with st.spinner("Loading drop-off waterfall…"):
    if not df_funnel.empty:
        stages = df_funnel["stage_name"].tolist()
        reached = df_funnel["users_reached"].tolist()
        dropoffs = df_funnel["drop_off_count"].tolist()

        # Build drop-off % labels: pct of previous stage that dropped
        def _dropoff_label(idx):
            if idx == 0:
                return f"{reached[0]:,} entered"
            d = dropoffs[idx - 1]
            prev = reached[idx - 1]
            pct = (d / prev * 100) if prev else 0
            return f"-{d:,} ({pct:.1f}% dropped)"

        wf_x = [stages[0]] + stages[1:]
        wf_measure = ["absolute"] + ["relative"] * (len(stages) - 1)
        wf_y = [reached[0]] + [-d for d in dropoffs[:-1]] + [0]
        wf_text = [_dropoff_label(i) for i in range(len(wf_x))]

        fig_wf = go.Figure(
            go.Waterfall(
                name="Funnel",
                orientation="v",
                measure=wf_measure,
                x=wf_x,
                y=wf_y,
                text=wf_text,
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
            template=_plotly_tpl,
            waterfallgap=0.3,
        )
        st.plotly_chart(fig_wf, use_container_width=True)
        _total_drop = reached[0] - reached[-1]
        _total_drop_pct = (_total_drop / reached[0] * 100) if reached[0] else 0
        st.caption(
            f"Total drop-off: {_total_drop:,} users ({_total_drop_pct:.1f}%) · "
            f"Green bars = users continuing · Red bars = drop-offs"
        )
    else:
        st.info("No funnel data available.")

st.divider()

# ── Conversion funnel visualization ───────────────────────────────────────────
st.subheader("Conversion Funnel")
with st.spinner("Loading conversion funnel…"):
    if not df_funnel.empty:
        df_f = df_funnel.copy()

        # Stage-by-stage CVR: pct of the FIRST stage (overall) and pct of previous stage
        first_val = df_f["users_reached"].iloc[0]
        df_f["cvr_vs_first"] = (df_f["users_reached"] / first_val * 100).round(1)
        df_f["cvr_vs_prev"] = (
            df_f["users_reached"] / df_f["users_reached"].shift(1) * 100
        ).round(1)

        df_f["label"] = df_f.apply(
            lambda r: (
                f"<b>{r['stage_name']}</b><br>"
                f"{int(r['users_reached']):,} users<br>"
                f"Overall: {r['cvr_vs_first']:.1f}%"
                + (
                    f"<br>vs prev: {r['cvr_vs_prev']:.1f}%"
                    if pd.notna(r["cvr_vs_prev"])
                    else ""
                )
            ),
            axis=1,
        )

        # Biggest drop-off stage highlighted in red
        max_drop_idx = int(df_f.iloc[:-1]["drop_off_count"].idxmax())
        colors = [
            "#d62728" if i == max_drop_idx else "#636EFA"
            for i in range(len(df_f))
        ]

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
        biggest_drop_pct = 100 - df_f.loc[max_drop_idx, "cvr_vs_prev"]
        fig_funnel.update_layout(
            title=(
                f"Conversion Funnel — Biggest drop-off: {biggest_stage} "
                f"({biggest_drop_pct:.1f}% lost)"
            ),
            template=_plotly_tpl,
        )
        st.plotly_chart(fig_funnel, use_container_width=True)
        st.caption(
            f"Red = biggest drop-off stage ({biggest_stage}) · "
            f"Overall funnel CVR: {df_f['cvr_vs_first'].iloc[-1]:.1f}%"
        )
    else:
        st.info("No funnel data available.")

st.divider()

# ── Channel contribution table ─────────────────────────────────────────────────
st.subheader("Channel Contribution")
from dashboard.components.tables import add_rank_column  # noqa: E402

with st.spinner("Loading channel contribution table…"):
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
        df_ch = add_rank_column(df_ch)

        # Color-code CVR column: green gradient (higher = better)
        _cvr_max = df_ch["CVR (%)"].max() or 1
        styled_ch = df_ch.style.background_gradient(
            subset=["CVR (%)"], cmap="RdYlGn", vmin=0, vmax=_cvr_max
        ).format(
            {
                "Sessions": "{:,}",
                "Conversions": "{:,}",
                "CVR (%)": "{:.2f}",
                "Revenue ($)": "${:,.2f}",
            }
        )
        st.dataframe(styled_ch, use_container_width=True, hide_index=True)
        st.download_button(
            label="Download channel table as CSV",
            data=df_ch.to_csv(index=False).encode("utf-8"),
            file_name="channel_contribution.csv",
            mime="text/csv",
            key="dl_channel_csv",
        )
        st.caption("CVR column color-coded: green = high conversion rate · Sorted by conversions")
    else:
        st.info("No channel data available.")

st.divider()

# ── Conversion trend by day of week ───────────────────────────────────────────
st.subheader("Conversion Trend by Day of Week")
with st.spinner("Loading conversions by day of week…"):
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
        worst_dow = int(dow_agg.loc[dow_agg["goal_completions"].idxmin(), "dow"])
        dow_colors = [
            "#2ca02c" if d == best_dow
            else "#d62728" if d == worst_dow
            else "#636EFA"
            for d in dow_agg["dow"]
        ]

        fig_dow = go.Figure(
            go.Bar(
                x=dow_agg["day_name"],
                y=dow_agg["goal_completions"].round(1),
                text=dow_agg["goal_completions"].round(1),
                textposition="outside",
                marker_color=dow_colors,
                hovertemplate="<b>%{x}</b><br>Avg completions: %{y:.1f}<extra></extra>",
            )
        )
        best_day_name = dow_agg.loc[dow_agg["dow"] == best_dow, "day_name"].iloc[0]
        worst_day_name = dow_agg.loc[dow_agg["dow"] == worst_dow, "day_name"].iloc[0]
        fig_dow.update_layout(
            title=(
                f"Avg Goal Completions by Day of Week — "
                f"Best: {best_day_name} · Worst: {worst_day_name}"
            ),
            xaxis_title="Day of Week",
            yaxis_title="Avg Completions",
            template=_plotly_tpl,
        )
        st.plotly_chart(fig_dow, use_container_width=True)
        st.caption(
            f"Green = best day ({best_day_name}) · "
            f"Red = worst day ({worst_day_name}) · "
            "Based on average daily goal completions"
        )
    else:
        st.info("No data available for day-of-week analysis.")
