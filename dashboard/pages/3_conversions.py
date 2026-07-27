"""Conversion Tracking — loads from vw_conversions and vw_funnel."""

import os
import sys
from datetime import timedelta

import plotly.express as px
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
st.markdown(
    "Track goal completions, revenue attribution, and conversion rates across channels. "
    "Use sidebar filters to narrow by date range or acquisition channel."
)
show_active_filters()

_FONT = dict(family="Inter, Arial, sans-serif", size=13)


# ── Cached data loaders — date-filtered at DB level ───────────────────────────
@st.cache_data(ttl=300)
def _load_conversions(start_date=None, end_date=None, channels: tuple = ()):
    where, params = build_where_clause(start_date, end_date, channels=list(channels) or None)
    return query_df(f"SELECT * FROM vw_conversions {where}", params=params or None)


@st.cache_data(ttl=300)
def _load_funnel():
    return run_view("vw_funnel")


@st.cache_data(ttl=300)
def _load_cvr_trend(start_date=None, end_date=None, channels: tuple = ()):
    """Daily CVR time-series — aggregated directly from vw_conversions."""
    where, params = build_where_clause(start_date, end_date, channels=list(channels) or None)
    return query_df(
        f"""SELECT session_date,
                   SUM(sessions) AS sessions,
                   SUM(goal_completions) AS goal_completions,
                   ROUND(SUM(goal_completions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 4) AS cvr_pct
            FROM vw_conversions {where}
            GROUP BY session_date
            ORDER BY session_date""",
        params=params or None,
    )


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
    try:
        daily_cvr = _load_cvr_trend(start_date, end_date, tuple(channels))
    except Exception as _cvr_exc:
        st.warning(f"Could not load CVR trend data: {_cvr_exc}")
        if st.button("Retry", key="retry_cvr_trend"):
            st.cache_data.clear()
            st.rerun()
        daily_cvr = pd.DataFrame()

if not daily_cvr.empty:
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
        title="Conversion Rate % — Daily (green = above target, red = below) with 7-Day Rolling Average",
        xaxis_title="Date",
        yaxis_title="CVR (%)",
        template=_plotly_tpl,
        legend=dict(orientation="h"),
        hovermode="x unified",
        font=_FONT,
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
    _period_avg = daily_cvr["cvr_pct"].mean()
    _best_day = daily_cvr.loc[daily_cvr["cvr_pct"].idxmax()]
    fig_cvr.add_annotation(
        x=str(_best_day["session_date"]),
        y=float(_best_day["cvr_pct"]),
        text=f"Best day: {float(_best_day['cvr_pct']):.2f}%",
        showarrow=True,
        arrowhead=2,
        arrowcolor="#2ca02c",
        font=dict(size=11, color="#2ca02c"),
        bgcolor="rgba(0,0,0,0.25)",
        borderpad=4,
        ay=-40,
    )
    st.plotly_chart(fig_cvr, use_container_width=True)
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
    try:
        if not df_conv.empty:
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
                labels={
                    "source_medium": "Source / Medium",
                    "goal_completions": "Completions",
                    "channel_grouping": "Channel",
                },
                template=_plotly_tpl,
            )
            fig_src.update_xaxes(tickangle=30)
            fig_src.update_layout(
                title="Goal Completions by Source / Medium — top 15 traffic sources",
                hovermode="x unified",
                legend=dict(orientation="h"),
                font=_FONT,
            )
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
            st.info("No source/medium data available for the selected filters.")
    except Exception as _exc:
        st.warning(f"Could not render goal completions chart: {_exc}")
        if st.button("Retry", key="retry_src"):
            st.cache_data.clear()
            st.rerun()

st.divider()

# ── Revenue by channel ─────────────────────────────────────────────────────────
st.subheader("Revenue by Channel")
with st.spinner("Loading revenue by channel…"):
    try:
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
                title="Total Revenue by Channel — sorted ascending to highlight top earner",
                xaxis_title="Revenue (USD)",
                yaxis_title="Acquisition Channel",
                template=_plotly_tpl,
                font=_FONT,
            )
            st.plotly_chart(fig_rev, use_container_width=True)
            st.caption(
                f"Total revenue: ${df_rev['revenue'].sum():,.0f} · "
                f"{len(df_rev)} channels · Sorted by revenue ascending"
            )
        else:
            st.info("No revenue data available for the selected filters.")
    except Exception as _exc:
        st.warning(f"Could not render revenue by channel chart: {_exc}")
        if st.button("Retry", key="retry_rev_ch"):
            st.cache_data.clear()
            st.rerun()

st.divider()

# ── Drop-off waterfall chart ───────────────────────────────────────────────────
st.subheader("Funnel Drop-off Analysis")
with st.spinner("Loading drop-off waterfall…"):
    try:
        if not df_funnel.empty:
            stages = df_funnel["stage_name"].tolist()
            reached = df_funnel["users_reached"].tolist()
            dropoffs = df_funnel["drop_off_count"].tolist()
            n = len(stages)

            # Build interleaved x/measure/y: Stage bar (green) → Drop bar (red) → …
            wf_x, wf_measure, wf_y, wf_text = [], [], [], []
            for i in range(n):
                # Stage bar — how many users are at this stage
                wf_x.append(stages[i])
                if i == 0:
                    wf_measure.append("absolute")
                    wf_y.append(reached[i])
                    wf_text.append(f"{reached[i]:,} entered")
                else:
                    # relative negative delta from previous stage to this one
                    drop = reached[i - 1] - reached[i]
                    drop_pct = (drop / reached[i - 1] * 100) if reached[i - 1] else 0
                    wf_measure.append("relative")
                    wf_y.append(-drop)
                    wf_text.append(f"−{drop:,} ({drop_pct:.1f}% dropped)")

            fig_wf = go.Figure(
                go.Waterfall(
                    name="Funnel",
                    orientation="v",
                    measure=wf_measure,
                    x=wf_x,
                    y=wf_y,
                    text=wf_text,
                    textposition="outside",
                    connector={"line": {"color": "rgba(100,100,100,0.4)", "width": 1.5}},
                    increasing={"marker": {"color": "#2ca02c"}},
                    decreasing={"marker": {"color": "#d62728"}},
                    totals={"marker": {"color": "#2ca02c"}},
                )
            )
            _total_drop = reached[0] - reached[-1]
            _total_drop_pct = (_total_drop / reached[0] * 100) if reached[0] else 0
            _best_drop_idx = int(df_funnel.iloc[:-1]["drop_off_count"].idxmax()) if n > 1 else 0
            _worst_stage = stages[_best_drop_idx + 1] if _best_drop_idx + 1 < n else stages[-1]
            fig_wf.update_layout(
                title=(
                    f"Funnel Drop-off Waterfall — "
                    f"green = users at stage, red = users lost · "
                    f"Biggest drop: → {_worst_stage}"
                ),
                xaxis_title="Funnel Stage",
                yaxis_title="Users",
                template=_plotly_tpl,
                waterfallgap=0.3,
                height=460,
                font=_FONT,
            )
            st.plotly_chart(fig_wf, use_container_width=True)

            # Stage detail table
            _wf_detail = df_funnel.copy()
            _wf_detail["drop_pct"] = (
                _wf_detail["drop_off_count"]
                / _wf_detail["users_reached"].replace(0, None)
                * 100
            ).round(1)
            _wf_detail["overall_cvr_pct"] = (
                _wf_detail["users_reached"] / (reached[0] or 1) * 100
            ).round(1)
            _wf_detail.rename(columns={
                "stage_name": "Stage",
                "users_reached": "Users Reached",
                "drop_off_count": "Dropped Off",
                "drop_pct": "Drop Rate (%)",
                "overall_cvr_pct": "vs Entry (%)",
            }, inplace=True)
            st.dataframe(
                _wf_detail.style.background_gradient(subset=["Drop Rate (%)"], cmap="RdYlGn_r"),
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                f"Total funnel drop-off: {_total_drop:,} users ({_total_drop_pct:.1f}%) · "
                f"Green bar = stage entry · Red bar = users lost at that transition · "
                f"Biggest leak: → {_worst_stage}"
            )
        else:
            st.info("No funnel data available.")
    except Exception as _exc:
        st.error(f"Could not render drop-off waterfall: {_exc}")
        if st.button("Retry", key="retry_waterfall"):
            st.cache_data.clear()
            st.rerun()

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
                f"({biggest_drop_pct:.1f}% lost) — red = highest drop-off stage"
            ),
            template=_plotly_tpl,
            font=_FONT,
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
    try:
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
            st.info("No channel data available for the selected filters.")
    except Exception as _exc:
        st.warning(f"Could not render channel contribution table: {_exc}")
        if st.button("Retry", key="retry_ch_tbl"):
            st.cache_data.clear()
            st.rerun()

st.divider()

# ── Conversion trend by day of week ───────────────────────────────────────────
st.subheader("Conversion Trend by Day of Week")
with st.spinner("Loading conversions by day of week…"):
    try:
        if not df_conv.empty:
            df_dow = df_conv.copy()
            df_dow["session_date"] = pd.to_datetime(df_dow["session_date"])
            df_dow["dow"] = df_dow["session_date"].dt.dayofweek
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
                    f"Avg Daily Goal Completions by Day of Week — "
                    f"Best: {best_day_name} (green) · Worst: {worst_day_name} (red)"
                ),
                xaxis_title="Day of Week",
                yaxis_title="Avg Goal Completions",
                template=_plotly_tpl,
                font=_FONT,
            )
            st.plotly_chart(fig_dow, use_container_width=True)
            st.caption(
                f"Green = best day ({best_day_name}) · "
                f"Red = worst day ({worst_day_name}) · "
                "Based on average daily goal completions"
            )
        else:
            st.info("No data available for day-of-week analysis.")
    except Exception as _exc:
        st.warning(f"Could not render day-of-week chart: {_exc}")
        if st.button("Retry", key="retry_dow"):
            st.cache_data.clear()
            st.rerun()

st.divider()

# ── A/B Test Results ──────────────────────────────────────────────────────────
st.subheader("A/B Test Results")
st.caption("Mock data — in production, load from your experiments tracking table.")

import numpy as np  # noqa: E402

_ab_df = pd.DataFrame({
    "Variant": ["Control (A)", "Variant B", "Variant C"],
    "Sessions": [4250, 4180, 4320],
    "Conversions": [148, 172, 164],
})
_ab_df["CVR (%)"] = (_ab_df["Conversions"] / _ab_df["Sessions"] * 100).round(3)
_control_cvr = float(_ab_df.loc[0, "CVR (%)"])
_ab_df["Uplift vs Control"] = ((_ab_df["CVR (%)"] / _control_cvr - 1) * 100).round(2)
_ab_df.loc[0, "Uplift vs Control"] = 0.0


def _wilson_ci(n: int, k: int, z: float = 1.96):
    p = k / n if n > 0 else 0.0
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * (p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5 / denom
    return round((centre - margin) * 100, 3), round((centre + margin) * 100, 3)


_ab_df[["CI Lower (%)", "CI Upper (%)"]] = pd.DataFrame(
    [_wilson_ci(int(r.Sessions), int(r.Conversions)) for r in _ab_df.itertuples()],
    index=_ab_df.index,
)


def _is_significant(n1: int, k1: int, n2: int, k2: int) -> bool:
    if n1 == 0 or n2 == 0:
        return False
    p1, p2 = k1 / n1, k2 / n2
    p_pool = (k1 + k2) / (n1 + n2)
    se = (p_pool * (1 - p_pool) * (1 / n1 + 1 / n2)) ** 0.5
    return se > 0 and abs(p1 - p2) / se > 1.96


_ctrl_n = int(_ab_df.loc[0, "Sessions"])
_ctrl_k = int(_ab_df.loc[0, "Conversions"])
_ab_df["Significant?"] = [
    "—" if i == 0
    else (
        "✅ Yes (p<0.05)"
        if _is_significant(_ctrl_n, _ctrl_k, int(r.Sessions), int(r.Conversions))
        else "❌ No"
    )
    for i, r in enumerate(_ab_df.itertuples())
]

_winner_idx = int(_ab_df["CVR (%)"].idxmax())


def _color_ab_row(row):
    return (
        ["background-color: #d4edda"] * len(row)
        if row.name == _winner_idx
        else [""] * len(row)
    )


st.dataframe(
    _ab_df.style.apply(_color_ab_row, axis=1).format({
        "CVR (%)": "{:.3f}%",
        "Uplift vs Control": "{:+.2f}%",
        "CI Lower (%)": "{:.3f}%",
        "CI Upper (%)": "{:.3f}%",
        "Sessions": "{:,}",
        "Conversions": "{:,}",
    }),
    use_container_width=True,
    hide_index=True,
)
_winner_name = _ab_df.loc[_winner_idx, "Variant"]
_winner_uplift = float(_ab_df.loc[_winner_idx, "Uplift vs Control"])
st.success(f"Winner: **{_winner_name}** — {_winner_uplift:+.2f}% uplift vs Control")

fig_ab = go.Figure()
for _i, _row in _ab_df.iterrows():
    fig_ab.add_trace(
        go.Bar(
            name=_row["Variant"],
            x=[_row["Variant"]],
            y=[_row["CVR (%)"]],
            error_y=dict(
                type="data",
                symmetric=False,
                array=[_row["CI Upper (%)"] - _row["CVR (%)"]],
                arrayminus=[_row["CVR (%)"] - _row["CI Lower (%)"]],
                color="#888888",
            ),
            marker_color="#2ca02c" if _i == _winner_idx else "#636EFA",
            hovertemplate=(
                f"<b>{_row['Variant']}</b><br>"
                f"CVR: {_row['CVR (%)']:.3f}%<br>"
                f"95% CI: [{_row['CI Lower (%)']:.3f}%, {_row['CI Upper (%)']:.3f}%]"
                "<extra></extra>"
            ),
        )
    )
fig_ab.add_hline(
    y=_control_cvr,
    line_dash="dash",
    line_color="gray",
    annotation_text="Control CVR",
    annotation_position="bottom right",
)
fig_ab.update_layout(
    title="A/B Test CVR Comparison — bars show 95% confidence intervals",
    xaxis_title="Variant",
    yaxis_title="CVR (%)",
    template=_plotly_tpl,
    showlegend=False,
    font=_FONT,
)
st.plotly_chart(fig_ab, use_container_width=True)
st.caption(
    "Error bars = 95% Wilson confidence intervals · "
    "Green bar = winning variant · Dashed line = Control CVR · "
    "✅ = statistically significant at p<0.05"
)

st.divider()

# ── Revenue Trend Over Time ───────────────────────────────────────────────────
st.subheader("Revenue Trend Over Time")
_REVENUE_TARGET = 5000.0  # daily target in USD


@st.cache_data(ttl=300)
def _load_revenue_trend(start_date=None, end_date=None, channels: tuple = ()):
    where, params = build_where_clause(start_date, end_date, channels=list(channels) or None)
    return query_df(
        f"""SELECT session_date,
                   ROUND(SUM(revenue)::NUMERIC, 2) AS daily_revenue
            FROM vw_conversions {where}
            GROUP BY session_date
            ORDER BY session_date""",
        params=params or None,
    )


with st.spinner("Loading revenue trend…"):
    try:
        df_rev_trend = _load_revenue_trend(start_date, end_date, tuple(channels))
    except Exception as _exc:
        st.warning(f"Could not load revenue trend data: {_exc}")
        if st.button("Retry", key="retry_rev_trend"):
            st.cache_data.clear()
            st.rerun()
        df_rev_trend = pd.DataFrame()

if not df_rev_trend.empty:
    df_rev_trend["rev_7day_avg"] = (
        df_rev_trend["daily_revenue"].rolling(7, min_periods=1).mean().round(2)
    )
    _total_rev_trend = float(df_rev_trend["daily_revenue"].sum())
    _period_days_rv = len(df_rev_trend)
    _avg_daily_rev = _total_rev_trend / _period_days_rv if _period_days_rv else 0.0

    fig_rev_trend = go.Figure()
    fig_rev_trend.add_trace(
        go.Bar(
            x=df_rev_trend["session_date"],
            y=df_rev_trend["daily_revenue"],
            name="Daily Revenue",
            marker_color="#636EFA",
            opacity=0.6,
            hovertemplate="<b>%{x|%Y-%m-%d}</b><br>Revenue: $%{y:,.2f}<extra></extra>",
        )
    )
    fig_rev_trend.add_trace(
        go.Scatter(
            x=df_rev_trend["session_date"],
            y=df_rev_trend["rev_7day_avg"],
            name="7-Day Rolling Avg",
            mode="lines",
            line=dict(color="#EF553B", width=2.5),
            hovertemplate="<b>%{x|%Y-%m-%d}</b><br>7d Avg: $%{y:,.2f}<extra></extra>",
        )
    )
    fig_rev_trend.add_hline(
        y=_REVENUE_TARGET,
        line_dash="dash",
        line_color="#ffd700",
        annotation_text=f"Daily Target ${_REVENUE_TARGET:,.0f}",
        annotation_position="bottom right",
        annotation=dict(font=dict(color="#ffd700", size=11)),
    )
    fig_rev_trend.update_xaxes(
        rangeselector=dict(
            buttons=[
                dict(count=7, label="7D", step="day", stepmode="backward"),
                dict(count=30, label="30D", step="day", stepmode="backward"),
                dict(count=90, label="90D", step="day", stepmode="backward"),
                dict(step="all", label="All"),
            ]
        )
    )
    fig_rev_trend.update_layout(
        title=f"Daily Revenue Over Time — Total: ${_total_rev_trend:,.0f} · Avg: ${_avg_daily_rev:,.0f}/day",
        xaxis_title="Date",
        yaxis_title="Revenue (USD)",
        template=_plotly_tpl,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.1),
        font=_FONT,
    )
    st.plotly_chart(fig_rev_trend, use_container_width=True)
    _above_target = int((df_rev_trend["daily_revenue"] >= _REVENUE_TARGET).sum())
    st.caption(
        f"Total: ${_total_rev_trend:,.0f} · "
        f"Daily avg: ${_avg_daily_rev:,.0f} · "
        f"Days above ${_REVENUE_TARGET:,.0f} target: {_above_target}/{_period_days_rv}"
    )
else:
    st.info("No revenue data available for the selected filters.")

st.divider()

# ── Conversion Rate by Device ─────────────────────────────────────────────────
st.subheader("Conversion Rate by Device")


@st.cache_data(ttl=300)
def _load_device_conv(start_date=None, end_date=None):
    """Estimate device-level CVR by distributing conversions proportionally."""
    _conds: list = []
    _params: dict = {}
    if start_date and end_date:
        _conds.append("session_date BETWEEN :s AND :e")
        _params.update({"s": str(start_date), "e": str(end_date)})
    _where = ("WHERE " + " AND ".join(_conds)) if _conds else ""
    return query_df(
        f"""WITH device_agg AS (
                SELECT device_type,
                       SUM(sessions)              AS total_sessions,
                       ROUND(AVG(session_duration_s), 1) AS avg_duration_s
                FROM raw_ga4_sessions {_where}
                GROUP BY device_type
            ),
            total_conv AS (
                SELECT COALESCE(SUM(sessions), 0)         AS t_sessions,
                       COALESCE(SUM(goal_completions), 0) AS t_completions
                FROM vw_conversions {_where}
            )
            SELECT da.device_type,
                   da.total_sessions                   AS sessions,
                   da.avg_duration_s,
                   ROUND(
                       da.total_sessions::NUMERIC / NULLIF(tc.t_sessions, 0)
                       * tc.t_completions
                   )::INT                              AS estimated_conversions,
                   ROUND(
                       da.total_sessions::NUMERIC / NULLIF(tc.t_sessions, 0)
                       * tc.t_completions
                       / NULLIF(da.total_sessions, 0) * 100,
                   2)                                 AS cvr_pct
            FROM device_agg da
            CROSS JOIN total_conv tc
            ORDER BY da.total_sessions DESC""",
        params=_params or None,
    )


with st.spinner("Loading device conversion data…"):
    try:
        df_dev = _load_device_conv(start_date, end_date)
    except Exception as _exc:
        st.warning(f"Could not load device conversion data: {_exc}")
        if st.button("Retry", key="retry_dev_conv"):
            st.cache_data.clear()
            st.rerun()
        df_dev = pd.DataFrame()

if not df_dev.empty:
    _dev_colors = {"desktop": "#636EFA", "mobile": "#EF553B", "tablet": "#00CC96"}
    _bar_colors = [_dev_colors.get(str(d).lower(), "#AB63FA") for d in df_dev["device_type"]]

    fig_dev = go.Figure(
        go.Bar(
            x=df_dev["device_type"],
            y=df_dev["cvr_pct"],
            marker_color=_bar_colors,
            text=[
                f"{v:.2f}%<br>({s:,} sessions)"
                for v, s in zip(df_dev["cvr_pct"], df_dev["sessions"])
            ],
            textposition="outside",
            customdata=df_dev[["sessions", "estimated_conversions", "avg_duration_s"]].values,
            hovertemplate=(
                "<b>%{x}</b><br>"
                "CVR: %{y:.2f}%<br>"
                "Sessions: %{customdata[0]:,}<br>"
                "Est. Conversions: %{customdata[1]:,}<br>"
                "Avg Duration: %{customdata[2]:.0f}s"
                "<extra></extra>"
            ),
        )
    )
    fig_dev.update_layout(
        title="Estimated Conversion Rate by Device Type — desktop / mobile / tablet",
        xaxis_title="Device Type",
        yaxis_title="Estimated CVR (%)",
        template=_plotly_tpl,
        font=_FONT,
    )
    st.plotly_chart(fig_dev, use_container_width=True)
    st.caption(
        "CVR estimated by distributing total conversions proportionally to each device's session share. "
        "Desktop = blue · Mobile = red · Tablet = teal"
    )
else:
    st.info("No device data available for the selected filters.")

st.divider()

# ── Top Converting Pages ──────────────────────────────────────────────────────
st.subheader("Top Converting Pages")


@st.cache_data(ttl=300)
def _load_top_conv_pages(start_date=None, end_date=None):
    _conds: list = []
    _params: dict = {}
    if start_date and end_date:
        _conds.append("DATE(timestamp) BETWEEN :s AND :e")
        _params.update({"s": str(start_date), "e": str(end_date)})
    _where = ("WHERE " + " AND ".join(_conds)) if _conds else ""
    return query_df(
        f"""SELECT page                                                            AS page_url,
                   COUNT(DISTINCT session_id)                                     AS sessions,
                   COUNT(CASE WHEN event_type = 'form_submit' THEN 1 END)         AS conversions,
                   ROUND(
                       100.0 * COUNT(CASE WHEN event_type = 'form_submit' THEN 1 END)::NUMERIC
                       / NULLIF(COUNT(DISTINCT session_id), 0),
                   2)                                                             AS cvr_pct
            FROM raw_clickstream_events {_where}
            GROUP BY page
            HAVING COUNT(DISTINCT session_id) >= 5
            ORDER BY cvr_pct DESC
            LIMIT 20""",
        params=_params or None,
    )


with st.spinner("Loading top converting pages…"):
    try:
        df_top_conv = _load_top_conv_pages(start_date, end_date)
    except Exception as _exc:
        st.warning(f"Could not load top converting pages: {_exc}")
        if st.button("Retry", key="retry_top_conv"):
            st.cache_data.clear()
            st.rerun()
        df_top_conv = pd.DataFrame()

if not df_top_conv.empty:
    # Estimate revenue using avg revenue per conversion from already-loaded KPI data
    _apc = (total_revenue / total_completions) if total_completions > 0 else 0.0
    df_top_conv["Estimated Revenue ($)"] = (df_top_conv["conversions"] * _apc).round(2)
    df_top_conv.rename(
        columns={
            "page_url": "Page URL",
            "sessions": "Sessions",
            "conversions": "Conversions",
            "cvr_pct": "CVR (%)",
        },
        inplace=True,
    )

    _cvr_col_max = df_top_conv["CVR (%)"].max() or 1
    styled_top_conv = df_top_conv.style.background_gradient(
        subset=["CVR (%)"], cmap="RdYlGn", vmin=0, vmax=_cvr_col_max
    ).format(
        {
            "Sessions": "{:,}",
            "Conversions": "{:,}",
            "CVR (%)": "{:.2f}%",
            "Estimated Revenue ($)": "${:,.2f}",
        }
    )
    st.dataframe(styled_top_conv, use_container_width=True, hide_index=True)
    st.download_button(
        label="Download top converting pages as CSV",
        data=df_top_conv.to_csv(index=False).encode("utf-8"),
        file_name="top_converting_pages.csv",
        mime="text/csv",
        key="dl_top_conv_csv",
    )
    st.caption(
        f"{len(df_top_conv)} pages shown · CVR = form_submit events / unique sessions · "
        f"Revenue estimated at ${_apc:.2f}/conversion · Sorted by CVR descending"
    )
else:
    st.info("No page conversion data available for the selected filters.")

st.divider()

# ── Conversion Cohort Analysis ────────────────────────────────────────────────
st.subheader("Conversion Cohort Analysis")
st.caption(
    "CVR by acquisition channel × weekly cohort — "
    "darker cells indicate higher conversion rates for that channel in that week."
)


@st.cache_data(ttl=300)
def _load_conv_cohorts(start_date=None, end_date=None, channels: tuple = ()):
    where, params = build_where_clause(start_date, end_date, channels=list(channels) or None)
    return query_df(
        f"""SELECT channel_grouping,
                   DATE_TRUNC('week', session_date)::DATE                          AS cohort_week,
                   ROUND(SUM(goal_completions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2)
                                                                                   AS cvr_pct,
                   SUM(sessions)                                                   AS sessions
            FROM vw_conversions {where}
            GROUP BY channel_grouping, cohort_week
            ORDER BY cohort_week, channel_grouping""",
        params=params or None,
    )


with st.spinner("Loading cohort data…"):
    try:
        df_cohort = _load_conv_cohorts(start_date, end_date, tuple(channels))
    except Exception as _exc:
        st.warning(f"Could not load cohort data: {_exc}")
        if st.button("Retry", key="retry_cohort"):
            st.cache_data.clear()
            st.rerun()
        df_cohort = pd.DataFrame()

if not df_cohort.empty:
    df_cohort["cohort_week"] = df_cohort["cohort_week"].astype(str)
    pivot_cohort = df_cohort.pivot_table(
        index="channel_grouping",
        columns="cohort_week",
        values="cvr_pct",
        fill_value=0,
    )
    fig_cohort = go.Figure(
        go.Heatmap(
            z=pivot_cohort.values.tolist(),
            x=[str(c) for c in pivot_cohort.columns],
            y=pivot_cohort.index.tolist(),
            colorscale="Blues",
            hoverongaps=False,
            colorbar=dict(title="CVR %"),
            hovertemplate=(
                "Channel: %{y}<br>"
                "Week: %{x}<br>"
                "CVR: %{z:.2f}%"
                "<extra></extra>"
            ),
        )
    )
    fig_cohort.update_layout(
        title="Conversion Rate Cohort Heatmap — Acquisition Channel × Week",
        xaxis_title="Cohort Week",
        yaxis_title="Acquisition Channel",
        template=_plotly_tpl,
        height=max(300, len(pivot_cohort) * 55 + 120),
        font=_FONT,
    )
    fig_cohort.update_xaxes(tickangle=45)
    st.plotly_chart(fig_cohort, use_container_width=True)
    _ch_avg = df_cohort.groupby("channel_grouping")["cvr_pct"].mean()
    _best_ch = str(_ch_avg.idxmax())
    _best_ch_cvr = float(_ch_avg.max())
    st.caption(
        f"Best-performing channel: {_best_ch} (avg CVR {_best_ch_cvr:.2f}%) · "
        "Darker blue = higher CVR · Rows = channels, columns = weekly cohorts"
    )
else:
    st.info("No cohort data available for the selected filters.")

st.divider()

# ── Micro conversion tracking ──────────────────────────────────────────────────
st.subheader("Micro Conversion Tracking")
st.caption(
    "Counts of smaller conversion goals (newsletter signups, downloads, video plays, "
    "contact form submits) derived from raw_clickstream_events event types."
)

_MICRO_LABELS = {
    "newsletter_signup": "Newsletter Signup",
    "pdf_download": "PDF Download",
    "video_play": "Video Play",
    "contact_form": "Contact Form Submit",
    "form_submit": "Form Submit",
    "button_click": "Button Click",
    "scroll": "Scroll",
    "page_view": "Page View",
}


@st.cache_data(ttl=300)
def _load_micro_conversions(start_date=None, end_date=None):
    _conds: list = []
    _params: dict = {}
    if start_date and end_date:
        _conds.append("DATE(timestamp) BETWEEN :s AND :e")
        _params.update({"s": str(start_date), "e": str(end_date)})
    _where = ("WHERE " + " AND ".join(_conds)) if _conds else ""
    return query_df(
        f"""SELECT event_type,
                   COUNT(*)                     AS event_count,
                   COUNT(DISTINCT session_id)   AS unique_sessions
            FROM raw_clickstream_events {_where}
            GROUP BY event_type
            ORDER BY event_count DESC""",
        params=_params or None,
    )


@st.cache_data(ttl=300)
def _load_total_sessions_micro(start_date=None, end_date=None):
    _conds: list = []
    _params: dict = {}
    if start_date and end_date:
        _conds.append("DATE(timestamp) BETWEEN :s AND :e")
        _params.update({"s": str(start_date), "e": str(end_date)})
    _where = ("WHERE " + " AND ".join(_conds)) if _conds else ""
    return query_df(
        f"SELECT COUNT(DISTINCT session_id) AS total_sessions FROM raw_clickstream_events {_where}",
        params=_params or None,
    )


with st.spinner("Loading micro conversion data…"):
    try:
        df_micro = _load_micro_conversions(start_date, end_date)
        df_micro_total = _load_total_sessions_micro(start_date, end_date)
        _total_sess_micro = int(df_micro_total["total_sessions"].iloc[0]) if not df_micro_total.empty else 1

        if df_micro.empty:
            st.info("No event data found in raw_clickstream_events for the selected period.")
        else:
            df_micro["display_label"] = df_micro["event_type"].map(_MICRO_LABELS).fillna(
                df_micro["event_type"].str.replace("_", " ").str.title()
            )
            df_micro["micro_cvr_pct"] = (
                df_micro["unique_sessions"] / max(_total_sess_micro, 1) * 100
            ).round(2)

            _col_micro_bar, _col_micro_tbl = st.columns([2, 1])

            with _col_micro_bar:
                fig_micro = go.Figure()
                fig_micro.add_trace(
                    go.Bar(
                        name="Event Count",
                        x=df_micro["display_label"],
                        y=df_micro["event_count"],
                        marker_color="#636EFA",
                        text=df_micro["event_count"],
                        textposition="outside",
                        hovertemplate=(
                            "<b>%{x}</b><br>Events: %{y:,}<extra></extra>"
                        ),
                        yaxis="y",
                    )
                )
                fig_micro.add_trace(
                    go.Scatter(
                        name="Micro CVR %",
                        x=df_micro["display_label"],
                        y=df_micro["micro_cvr_pct"],
                        mode="lines+markers",
                        marker=dict(color="#EF553B", size=8),
                        line=dict(color="#EF553B", width=2),
                        hovertemplate=(
                            "<b>%{x}</b><br>CVR: %{y:.2f}%<extra></extra>"
                        ),
                        yaxis="y2",
                    )
                )
                fig_micro.update_layout(
                    title="Micro Conversion Event Counts with CVR % (sessions that triggered each event)",
                    xaxis_title="Event Type",
                    yaxis=dict(title="Event Count", showgrid=False),
                    yaxis2=dict(
                        title="Micro CVR (%)",
                        overlaying="y",
                        side="right",
                        showgrid=False,
                        tickformat=".1f",
                    ),
                    template=_plotly_tpl,
                    legend=dict(orientation="h", y=1.1),
                    hovermode="x unified",
                    height=420,
                    font=_FONT,
                )
                st.plotly_chart(fig_micro, use_container_width=True)

            with _col_micro_tbl:
                _micro_display = df_micro[["display_label", "event_count", "unique_sessions", "micro_cvr_pct"]].copy()
                _micro_display.columns = ["Event Type", "Count", "Unique Sessions", "CVR (%)"]
                st.dataframe(
                    _micro_display.style.background_gradient(subset=["CVR (%)"], cmap="Blues"),
                    use_container_width=True,
                    hide_index=True,
                )

            _top_micro = df_micro.loc[df_micro["event_count"].idxmax(), "display_label"]
            st.caption(
                f"{len(df_micro)} event types · {_total_sess_micro:,} total sessions · "
                f"Top micro-conversion: {_top_micro} · "
                "CVR = unique sessions with event / total sessions"
            )
            st.download_button(
                "Download micro conversions CSV",
                data=df_micro[["display_label", "event_count", "unique_sessions", "micro_cvr_pct"]].to_csv(index=False).encode("utf-8"),
                file_name="micro_conversions.csv",
                mime="text/csv",
                key="dl_micro_csv",
            )
    except Exception as _exc:
        st.error(f"Could not load micro conversion data: {_exc}")
        if st.button("Retry", key="retry_micro"):
            st.cache_data.clear()
            st.rerun()

st.divider()

# ── Conversion attribution comparison ─────────────────────────────────────────
st.subheader("Conversion Attribution — First / Last / Linear Touch")
st.caption(
    "Compares how many goal completions each channel gets credit for under "
    "three attribution models: first-touch (credit to earliest-session channel), "
    "last-touch (direct from vw_conversions), and linear (equal split)."
)


@st.cache_data(ttl=300)
def _load_channel_sessions_attr(start_date=None, end_date=None):
    """Channel session share — used to compute first-touch attribution proxy."""
    _conds: list = []
    _params: dict = {}
    if start_date and end_date:
        _conds.append("session_date BETWEEN :s AND :e")
        _params.update({"s": str(start_date), "e": str(end_date)})
    _where = ("WHERE " + " AND ".join(_conds)) if _conds else ""
    return query_df(
        f"SELECT channel_grouping, SUM(sessions) AS sessions FROM raw_ga4_sessions {_where} GROUP BY channel_grouping",
        params=_params or None,
    )


@st.cache_data(ttl=300)
def _load_last_touch_attr(start_date=None, end_date=None, channels: tuple = ()):
    """Last-touch attribution — directly from vw_conversions."""
    where, params = build_where_clause(start_date, end_date, channels=list(channels) or None)
    return query_df(
        f"""SELECT channel_grouping,
                   SUM(goal_completions) AS last_touch_conversions
            FROM vw_conversions {where}
            GROUP BY channel_grouping
            ORDER BY last_touch_conversions DESC""",
        params=params or None,
    )


with st.spinner("Loading attribution data…"):
    try:
        df_last = _load_last_touch_attr(start_date, end_date, tuple(channels))
        df_sess_attr = _load_channel_sessions_attr(start_date, end_date)

        if df_last.empty:
            st.info("No attribution data available for the selected filters.")
        else:
            _total_conv_attr = int(df_last["last_touch_conversions"].sum())

            # First-touch: redistribute total conversions by session share
            _total_sess_attr = df_sess_attr["sessions"].sum() if not df_sess_attr.empty else 1
            df_sess_attr["first_touch_conversions"] = (
                df_sess_attr["sessions"] / max(_total_sess_attr, 1) * _total_conv_attr
            ).round(0).astype(int)

            # Merge into one frame
            df_attr = df_last.merge(
                df_sess_attr[["channel_grouping", "first_touch_conversions"]],
                on="channel_grouping", how="outer",
            ).fillna(0)
            df_attr["first_touch_conversions"] = df_attr["first_touch_conversions"].astype(int)
            df_attr["last_touch_conversions"] = df_attr["last_touch_conversions"].astype(int)

            # Linear: equal share of total conversions per channel
            _n_channels = max(len(df_attr), 1)
            df_attr["linear_conversions"] = round(_total_conv_attr / _n_channels)

            df_attr = df_attr.sort_values("last_touch_conversions", ascending=True)

            _CH_COLORS = ["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A", "#19D3F3", "#FF6692", "#B6E880"]
            fig_attr = go.Figure()
            _models = [
                ("first_touch_conversions", "First Touch", "#00CC96"),
                ("last_touch_conversions", "Last Touch", "#636EFA"),
                ("linear_conversions", "Linear", "#FFA15A"),
            ]
            for col, label, color in _models:
                fig_attr.add_trace(
                    go.Bar(
                        name=label,
                        x=df_attr[col],
                        y=df_attr["channel_grouping"],
                        orientation="h",
                        marker_color=color,
                        hovertemplate=(
                            f"<b>%{{y}}</b><br>{label}: %{{x:,}}<extra></extra>"
                        ),
                    )
                )
            fig_attr.update_layout(
                title=(
                    f"Attribution Comparison — {_total_conv_attr:,} total conversions · "
                    "Green = first touch · Blue = last touch · Orange = linear"
                ),
                xaxis_title="Attributed Conversions",
                yaxis_title="Channel",
                barmode="group",
                template=_plotly_tpl,
                legend=dict(orientation="h", y=1.1),
                height=max(380, len(df_attr) * 60 + 120),
                font=_FONT,
            )
            st.plotly_chart(fig_attr, use_container_width=True)

            # Attribution table
            _attr_tbl = df_attr[["channel_grouping", "first_touch_conversions",
                                   "last_touch_conversions", "linear_conversions"]].copy()
            _attr_tbl.columns = ["Channel", "First Touch", "Last Touch", "Linear"]
            _attr_tbl = _attr_tbl.sort_values("Last Touch", ascending=False).reset_index(drop=True)
            st.dataframe(_attr_tbl, use_container_width=True, hide_index=True)
            st.caption(
                "First touch: credit to channel with highest session share (proxy) · "
                "Last touch: credit to channel that drove direct conversion · "
                "Linear: equal credit per channel"
            )
            st.download_button(
                "Download attribution table CSV",
                data=_attr_tbl.to_csv(index=False).encode("utf-8"),
                file_name="conversion_attribution.csv",
                mime="text/csv",
                key="dl_attr_csv",
            )
    except Exception as _exc:
        st.error(f"Could not load attribution data: {_exc}")
        if st.button("Retry", key="retry_attr"):
            st.cache_data.clear()
            st.rerun()

st.divider()

# ── Conversion time analysis ───────────────────────────────────────────────────
st.subheader("Conversion Time Analysis")
st.caption(
    "When do users convert? Best hour of day, day of week, "
    "and daily conversion distribution from raw_clickstream_events form_submit events."
)


@st.cache_data(ttl=300)
def _load_conv_by_hour(start_date=None, end_date=None):
    _conds = ["event_type = 'form_submit'"]
    _params: dict = {}
    if start_date and end_date:
        _conds.append("DATE(timestamp) BETWEEN :s AND :e")
        _params.update({"s": str(start_date), "e": str(end_date)})
    _where = "WHERE " + " AND ".join(_conds)
    return query_df(
        f"""SELECT EXTRACT(HOUR FROM timestamp)::INT AS hour_of_day,
                   COUNT(*)                          AS conversions,
                   COUNT(DISTINCT session_id)        AS unique_sessions
            FROM raw_clickstream_events {_where}
            GROUP BY hour_of_day
            ORDER BY hour_of_day""",
        params=_params or None,
    )


@st.cache_data(ttl=300)
def _load_conv_by_dow(start_date=None, end_date=None):
    _conds = ["event_type = 'form_submit'"]
    _params: dict = {}
    if start_date and end_date:
        _conds.append("DATE(timestamp) BETWEEN :s AND :e")
        _params.update({"s": str(start_date), "e": str(end_date)})
    _where = "WHERE " + " AND ".join(_conds)
    return query_df(
        f"""SELECT EXTRACT(DOW FROM timestamp)::INT AS dow,
                   TO_CHAR(timestamp, 'Day')        AS day_name,
                   COUNT(*)                          AS conversions
            FROM raw_clickstream_events {_where}
            GROUP BY dow, day_name
            ORDER BY dow""",
        params=_params or None,
    )


@st.cache_data(ttl=300)
def _load_daily_conv_dist(start_date=None, end_date=None, channels: tuple = ()):
    """Daily goal completions from vw_conversions — for day-to-convert histogram."""
    where, params = build_where_clause(start_date, end_date, channels=list(channels) or None)
    return query_df(
        f"""SELECT session_date,
                   SUM(goal_completions) AS goal_completions
            FROM vw_conversions {where}
            GROUP BY session_date
            ORDER BY session_date""",
        params=params or None,
    )


with st.spinner("Loading conversion time data…"):
    try:
        df_by_hour = _load_conv_by_hour(start_date, end_date)
        df_by_dow = _load_conv_by_dow(start_date, end_date)
        df_daily_dist = _load_daily_conv_dist(start_date, end_date, tuple(channels))

        _col_h, _col_d = st.columns(2)

        # ── Best time of day ──
        with _col_h:
            if not df_by_hour.empty:
                _best_hour = int(df_by_hour.loc[df_by_hour["conversions"].idxmax(), "hour_of_day"])
                _hour_colors = [
                    "#2ca02c" if h == _best_hour else "#636EFA"
                    for h in df_by_hour["hour_of_day"]
                ]
                fig_hour = go.Figure(
                    go.Bar(
                        x=df_by_hour["hour_of_day"],
                        y=df_by_hour["conversions"],
                        marker_color=_hour_colors,
                        text=df_by_hour["conversions"],
                        textposition="outside",
                        hovertemplate="<b>%{x}:00</b><br>Conversions: %{y:,}<extra></extra>",
                    )
                )
                _best_hour_label = f"{_best_hour:02d}:00–{_best_hour:02d}:59"
                fig_hour.update_layout(
                    title=f"Conversions by Hour of Day — peak: {_best_hour_label}",
                    xaxis_title="Hour (24h)",
                    yaxis_title="Form Submits",
                    template=_plotly_tpl,
                    showlegend=False,
                    height=350,
                    font=_FONT,
                )
                fig_hour.update_xaxes(dtick=2)
                st.plotly_chart(fig_hour, use_container_width=True)
                st.caption(f"Green = peak conversion hour ({_best_hour_label}) · Based on form_submit events")
            else:
                st.info("No hourly conversion data available.")

        # ── Best day of week ──
        with _col_d:
            if not df_by_dow.empty:
                df_by_dow["day_name"] = df_by_dow["day_name"].str.strip()
                _best_dow = int(df_by_dow.loc[df_by_dow["conversions"].idxmax(), "dow"])
                _worst_dow = int(df_by_dow.loc[df_by_dow["conversions"].idxmin(), "dow"])
                _dow_colors = [
                    "#2ca02c" if d == _best_dow
                    else "#d62728" if d == _worst_dow
                    else "#636EFA"
                    for d in df_by_dow["dow"]
                ]
                fig_dow2 = go.Figure(
                    go.Bar(
                        x=df_by_dow["day_name"],
                        y=df_by_dow["conversions"],
                        marker_color=_dow_colors,
                        text=df_by_dow["conversions"],
                        textposition="outside",
                        hovertemplate="<b>%{x}</b><br>Conversions: %{y:,}<extra></extra>",
                    )
                )
                _best_day_nm = df_by_dow.loc[df_by_dow["dow"] == _best_dow, "day_name"].iloc[0]
                _worst_day_nm = df_by_dow.loc[df_by_dow["dow"] == _worst_dow, "day_name"].iloc[0]
                fig_dow2.update_layout(
                    title=f"Conversions by Day of Week — best: {_best_day_nm}, worst: {_worst_day_nm}",
                    xaxis_title="Day",
                    yaxis_title="Form Submits",
                    template=_plotly_tpl,
                    showlegend=False,
                    height=350,
                    font=_FONT,
                )
                st.plotly_chart(fig_dow2, use_container_width=True)
                st.caption(f"Green = best ({_best_day_nm}) · Red = worst ({_worst_day_nm}) · Form submits by day")
            else:
                st.info("No day-of-week conversion data available.")

        # ── Daily goal completions distribution histogram ──
        if not df_daily_dist.empty:
            _avg_daily = float(df_daily_dist["goal_completions"].mean())
            _median_daily = float(df_daily_dist["goal_completions"].median())
            fig_dist = go.Figure(
                go.Histogram(
                    x=df_daily_dist["goal_completions"],
                    nbinsx=20,
                    marker_color="#636EFA",
                    opacity=0.8,
                    hovertemplate="Completions: %{x}<br>Days: %{y}<extra></extra>",
                )
            )
            fig_dist.add_vline(
                x=_avg_daily,
                line_dash="dash",
                line_color="#EF553B",
                annotation_text=f"Avg: {_avg_daily:.1f}",
                annotation_position="top right",
            )
            fig_dist.add_vline(
                x=_median_daily,
                line_dash="dot",
                line_color="#ffd700",
                annotation_text=f"Median: {_median_daily:.1f}",
                annotation_position="top left",
            )
            fig_dist.update_layout(
                title="Daily Goal Completions Distribution — how many days hit each conversion count",
                xaxis_title="Goal Completions per Day",
                yaxis_title="Number of Days",
                template=_plotly_tpl,
                height=340,
                font=_FONT,
            )
            st.plotly_chart(fig_dist, use_container_width=True)
            st.caption(
                f"{len(df_daily_dist)} days in period · "
                f"Avg: {_avg_daily:.1f} conversions/day · "
                f"Median: {_median_daily:.1f} · "
                f"Max: {int(df_daily_dist['goal_completions'].max())}"
            )
    except Exception as _exc:
        st.error(f"Could not load conversion time analysis: {_exc}")
        if st.button("Retry", key="retry_time_analysis"):
            st.cache_data.clear()
            st.rerun()

st.divider()

# ── Conversion page flow sankey ────────────────────────────────────────────────
st.subheader("Conversion Page Flow")
st.caption(
    "Sankey diagram showing user paths that lead to a conversion (form_submit). "
    "Source node = entry page, target node = conversion page, "
    "link width = number of converting sessions."
)


@st.cache_data(ttl=300)
def _load_conv_page_flow(start_date=None, end_date=None):
    """Entry page → conversion page flows from raw_clickstream_events."""
    _conds: list = []
    _params: dict = {}
    if start_date and end_date:
        _conds.append("DATE(ce.timestamp) BETWEEN :s AND :e")
        _params.update({"s": str(start_date), "e": str(end_date)})
    _date_where = ("AND " + " AND ".join(_conds)) if _conds else ""
    return query_df(
        f"""WITH entry_pages AS (
                SELECT session_id,
                       page AS entry_page,
                       ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY timestamp ASC) AS rn
                FROM raw_clickstream_events
            ),
            conv_pages AS (
                SELECT session_id,
                       page AS conv_page
                FROM raw_clickstream_events ce
                WHERE event_type = 'form_submit' {_date_where}
            )
            SELECT ep.entry_page AS source_page,
                   cp.conv_page  AS target_page,
                   COUNT(*)      AS conversions
            FROM entry_pages ep
            JOIN conv_pages cp ON cp.session_id = ep.session_id
            WHERE ep.rn = 1
              AND ep.entry_page != cp.conv_page
            GROUP BY ep.entry_page, cp.conv_page
            ORDER BY conversions DESC
            LIMIT 25""",
        params=_params or None,
    )


with st.spinner("Loading page flow data…"):
    try:
        df_flow = _load_conv_page_flow(start_date, end_date)

        if df_flow.empty:
            st.info("No page flow data found — no form_submit events for the selected period.")
        else:
            # Build Sankey node list
            _all_pages = pd.unique(df_flow[["source_page", "target_page"]].values.ravel())
            _page_idx = {p: i for i, p in enumerate(_all_pages)}

            def _short(url: str, max_len: int = 40) -> str:
                return url if len(url) <= max_len else "…" + url[-max_len + 1:]

            _node_labels = [_short(p) for p in _all_pages]

            _source_idx = df_flow["source_page"].map(_page_idx).tolist()
            _target_idx = df_flow["target_page"].map(_page_idx).tolist()
            _values = df_flow["conversions"].tolist()

            # Color: entry pages green, conversion pages blue
            _entry_set = set(df_flow["source_page"])
            _conv_set = set(df_flow["target_page"])
            _node_colors = [
                "rgba(44,160,44,0.7)" if p in _entry_set and p not in _conv_set
                else "rgba(99,110,250,0.7)" if p in _conv_set and p not in _entry_set
                else "rgba(255,127,14,0.7)"
                for p in _all_pages
            ]

            fig_sankey = go.Figure(
                go.Sankey(
                    arrangement="snap",
                    node=dict(
                        pad=20,
                        thickness=18,
                        line=dict(color="rgba(0,0,0,0.3)", width=0.5),
                        label=_node_labels,
                        color=_node_colors,
                        hovertemplate="<b>%{label}</b><br>Flow: %{value}<extra></extra>",
                    ),
                    link=dict(
                        source=_source_idx,
                        target=_target_idx,
                        value=_values,
                        color="rgba(150,150,150,0.35)",
                        hovertemplate=(
                            "From: %{source.label}<br>"
                            "To: %{target.label}<br>"
                            "Converting sessions: %{value:,}"
                            "<extra></extra>"
                        ),
                    ),
                )
            )
            fig_sankey.update_layout(
                title="Conversion Page Flow — entry pages (green) → conversion pages (blue)",
                template=_plotly_tpl,
                height=max(450, len(df_flow) * 18 + 100),
                font=_FONT,
            )
            st.plotly_chart(fig_sankey, use_container_width=True)
            _total_conv_flow = int(df_flow["conversions"].sum())
            _top_path = df_flow.iloc[0]
            st.caption(
                f"{len(df_flow)} unique paths · {_total_conv_flow:,} total converting sessions · "
                f"Top path: {_short(_top_path['source_page'], 30)} → "
                f"{_short(_top_path['target_page'], 30)} ({int(_top_path['conversions']):,} sessions)"
            )
            st.download_button(
                "Download page flow CSV",
                data=df_flow.to_csv(index=False).encode("utf-8"),
                file_name="conversion_page_flow.csv",
                mime="text/csv",
                key="dl_flow_csv",
            )
    except Exception as _exc:
        st.error(f"Could not load page flow data: {_exc}")
        if st.button("Retry", key="retry_sankey"):
            st.cache_data.clear()
            st.rerun()
