"""User Behavior & Funnels — loads from vw_behavior, vw_top_pages,
vw_scroll_depth, and vw_engagement_events."""

import os
import sys
from datetime import timedelta

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dashboard.components.charts import bar_chart, line_chart
from dashboard.components.filters import (
    build_where_clause,
    get_date_filter,
    get_device_filter,
    get_page_filter,
    get_plotly_template,
    show_active_filters,
)
from dashboard.components.metrics import (
    calculate_period_change,
    display_4_kpi_row,
    format_duration,
    format_large_number,
    format_percentage,
)
from utils.db import query_df
from utils.query_runner import run_view

st.set_page_config(page_title="User Behavior & Funnels", page_icon="🖱️", layout="wide")
st.title("🖱️ User Behavior & Funnels")
show_active_filters()


# ── Cached loaders (TTL = 5 minutes) ─────────────────────────────────────────
@st.cache_data(ttl=300)
def _load_behavior():
    return run_view("vw_behavior")


@st.cache_data(ttl=300)
def _load_top_pages():
    return run_view("vw_top_pages")


@st.cache_data(ttl=300)
def _load_scroll():
    return run_view("vw_scroll_depth")


@st.cache_data(ttl=300)
def _load_engagement():
    return run_view("vw_engagement_events")


@st.cache_data(ttl=300)
def _load_avg_time(start_date=None, end_date=None, devices: tuple = ()):
    where, params = build_where_clause(start_date, end_date, devices=list(devices) or None)
    return query_df(
        f"SELECT ROUND(AVG(session_duration_s)::numeric, 1) AS avg_s FROM raw_ga4_sessions {where}",
        params=params or None,
    )


@st.cache_data(ttl=300)
def _load_behavior_kpis_period(start_date=None, end_date=None, devices: tuple = ()):
    """Load the 4 behavior KPI metrics for a given date period."""
    where, params = build_where_clause(start_date, end_date, devices=list(devices) or None)
    df_sess = query_df(
        f"""SELECT COALESCE(SUM(pageviews), 0) AS total_pageviews,
                   ROUND(AVG(session_duration_s)::numeric, 1) AS avg_duration_s
            FROM raw_ga4_sessions {where}""",
        params=params or None,
    )
    if start_date and end_date:
        df_ev = query_df(
            """SELECT ROUND(AVG(scroll_depth_pct)::numeric, 1) AS avg_scroll,
                      COUNT(*) AS total_events
               FROM raw_clickstream_events
               WHERE DATE(timestamp) BETWEEN :s AND :e""",
            params={"s": str(start_date), "e": str(end_date)},
        )
    else:
        df_ev = query_df(
            """SELECT ROUND(AVG(scroll_depth_pct)::numeric, 1) AS avg_scroll,
                      COUNT(*) AS total_events
               FROM raw_clickstream_events"""
        )
    return {
        "pageviews": int(df_sess["total_pageviews"].iloc[0] or 0),
        "avg_duration_s": float(df_sess["avg_duration_s"].iloc[0] or 0),
        "avg_scroll": float(df_ev["avg_scroll"].iloc[0] or 0),
        "total_events": int(df_ev["total_events"].iloc[0] or 0),
    }


@st.cache_data(ttl=300)
def _load_funnel():
    return query_df("""
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
""")


@st.cache_data(ttl=300)
def _load_duration(start_date=None, end_date=None, devices: tuple = ()):
    date_where, params = build_where_clause(start_date, end_date, devices=list(devices) or None)
    base_cond = date_where + " AND session_duration_s IS NOT NULL" if date_where else "WHERE session_duration_s IS NOT NULL"
    return query_df(f"""
SELECT
    COUNT(CASE WHEN session_duration_s < 30                                   THEN 1 END) AS "0-30s",
    COUNT(CASE WHEN session_duration_s >= 30  AND session_duration_s < 120    THEN 1 END) AS "30s-2m",
    COUNT(CASE WHEN session_duration_s >= 120 AND session_duration_s < 300    THEN 1 END) AS "2m-5m",
    COUNT(CASE WHEN session_duration_s >= 300 AND session_duration_s < 600    THEN 1 END) AS "5m-10m",
    COUNT(CASE WHEN session_duration_s >= 600                                 THEN 1 END) AS "10m+"
FROM raw_ga4_sessions {base_cond}
""", params=params or None)


@st.cache_data(ttl=300)
def _load_duration_clickstream(start_date=None, end_date=None):
    _conds = []
    _params: dict = {}
    if start_date and end_date:
        _conds.append("DATE(timestamp) BETWEEN :s AND :e")
        _params.update({"s": str(start_date), "e": str(end_date)})
    _where = ("WHERE " + " AND ".join(_conds)) if _conds else ""
    return query_df(
        f"""SELECT
                SUM(CASE WHEN dur < 30 THEN 1 ELSE 0 END)                      AS "0-30s",
                SUM(CASE WHEN dur >= 30  AND dur < 120 THEN 1 ELSE 0 END)      AS "30s-2m",
                SUM(CASE WHEN dur >= 120 AND dur < 300 THEN 1 ELSE 0 END)      AS "2m-5m",
                SUM(CASE WHEN dur >= 300 AND dur < 600 THEN 1 ELSE 0 END)      AS "5m-10m",
                SUM(CASE WHEN dur >= 600 THEN 1 ELSE 0 END)                    AS "10m+"
           FROM (
               SELECT session_id,
                      EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp))) AS dur
               FROM raw_clickstream_events {_where}
               GROUP BY session_id
               HAVING COUNT(*) > 1
           ) sess""",
        params=_params or None,
    )


@st.cache_data(ttl=300)
def _load_heatmap():
    return query_df("""
SELECT EXTRACT(DOW FROM log_time)::int AS dow,
       EXTRACT(HOUR FROM log_time)::int AS hour_of_day,
       COUNT(*) AS total_requests
FROM raw_server_logs GROUP BY 1, 2 ORDER BY 1, 2
""")


@st.cache_data(ttl=300)
def _load_heatmap_dated(start_date=None, end_date=None):
    _conds = []
    _params: dict = {}
    if start_date and end_date:
        _conds.append("DATE(log_time) BETWEEN :s AND :e")
        _params.update({"s": str(start_date), "e": str(end_date)})
    _where = ("WHERE " + " AND ".join(_conds)) if _conds else ""
    return query_df(
        f"""SELECT EXTRACT(DOW FROM log_time)::int AS dow,
                   EXTRACT(HOUR FROM log_time)::int AS hour_of_day,
                   COUNT(*) AS total_requests
            FROM raw_server_logs {_where}
            GROUP BY 1, 2
            ORDER BY 1, 2""",
        params=_params or None,
    )


@st.cache_data(ttl=300)
def _load_retention(start_date=None, end_date=None, devices: tuple = ()):
    where, params = build_where_clause(start_date, end_date, devices=list(devices) or None)
    return query_df(f"""
        SELECT
            DATE_TRUNC('week', session_date)::DATE AS week_start,
            SUM(sessions)  AS weekly_sessions,
            SUM(new_users) AS new_users,
            SUM(sessions) - SUM(new_users) AS returning_users,
            ROUND((SUM(sessions) - SUM(new_users))::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2)
                AS retention_rate_pct
        FROM raw_ga4_sessions {where}
        GROUP BY week_start
        ORDER BY week_start
    """, params=params or None)


@st.cache_data(ttl=300)
def _load_session_quality(start_date=None, end_date=None, devices: tuple = ()):
    where, params = build_where_clause(start_date, end_date, devices=list(devices) or None)
    return query_df(f"""
        WITH quality AS (
            SELECT
                channel_grouping,
                COUNT(*) AS total_sessions,
                COUNT(CASE WHEN session_duration_s > 180 AND NOT bounce THEN 1 END) AS high_quality,
                COUNT(CASE WHEN session_duration_s < 30 OR bounce THEN 1 END) AS low_quality
            FROM raw_ga4_sessions {where}
            GROUP BY channel_grouping
        )
        SELECT channel_grouping, total_sessions, high_quality, low_quality,
               ROUND(high_quality::NUMERIC / NULLIF(total_sessions, 0) * 100, 2) AS high_quality_pct,
               ROUND(low_quality::NUMERIC  / NULLIF(total_sessions, 0) * 100, 2) AS low_quality_pct
        FROM quality ORDER BY high_quality_pct DESC
    """, params=params or None)


@st.cache_data(ttl=300)
def _load_quality_heatmap():
    return query_df("""
        SELECT EXTRACT(DOW FROM session_date)::INT AS dow,
               EXTRACT(HOUR FROM (session_date + interval '12 hours'))::INT AS hour_of_day,
               COUNT(CASE WHEN session_duration_s > 180 AND NOT bounce THEN 1 END) AS high_quality
        FROM raw_ga4_sessions
        GROUP BY dow, hour_of_day
        ORDER BY dow, hour_of_day
    """)


@st.cache_data(ttl=300)
def _load_top_pages_events(start_date=None, end_date=None):
    _conds = []
    _params: dict = {}
    if start_date and end_date:
        _conds.append("DATE(timestamp) BETWEEN :s AND :e")
        _params.update({"s": str(start_date), "e": str(end_date)})
    _where = ("WHERE " + " AND ".join(_conds)) if _conds else ""
    return query_df(
        f"""SELECT page,
                   COUNT(*) AS total_events,
                   SUM(CASE WHEN event_type = 'click' THEN 1 ELSE 0 END)       AS clicks,
                   SUM(CASE WHEN event_type = 'scroll' THEN 1 ELSE 0 END)      AS scrolls,
                   SUM(CASE WHEN event_type = 'form_submit' THEN 1 ELSE 0 END) AS form_submits
            FROM raw_clickstream_events {_where}
            GROUP BY page
            ORDER BY total_events DESC
            LIMIT 50""",
        params=_params or None,
    )


@st.cache_data(ttl=300)
def _load_event_trend(start_date=None, end_date=None):
    _conds = []
    _params: dict = {}
    if start_date and end_date:
        _conds.append("DATE(timestamp) BETWEEN :s AND :e")
        _params.update({"s": str(start_date), "e": str(end_date)})
    _where = ("WHERE " + " AND ".join(_conds)) if _conds else ""
    return query_df(
        f"""SELECT DATE(timestamp) AS event_date,
                   event_type,
                   COUNT(*) AS event_count
            FROM raw_clickstream_events {_where}
            GROUP BY DATE(timestamp), event_type
            ORDER BY event_date, event_type""",
        params=_params or None,
    )


@st.cache_data(ttl=300)
def _load_new_vs_ret_dated(start_date=None, end_date=None):
    _conds = []
    _params: dict = {}
    if start_date and end_date:
        _conds.append("session_date BETWEEN :s AND :e")
        _params.update({"s": str(start_date), "e": str(end_date)})
    _where = ("WHERE " + " AND ".join(_conds)) if _conds else ""
    return query_df(
        f"""SELECT
                COALESCE(SUM(new_users), 0)                            AS new_users,
                COALESCE(SUM(sessions) - SUM(new_users), 0)            AS returning_users,
                COALESCE(SUM(sessions), 0)                             AS total_sessions
           FROM raw_ga4_sessions {_where}""",
        params=_params or None,
    )


@st.cache_data(ttl=300)
def _load_dau_mau():
    return query_df("""
        WITH dau AS (
            SELECT session_date, SUM(sessions) AS daily_s FROM raw_ga4_sessions GROUP BY session_date
        ),
        mau AS (
            SELECT DATE_TRUNC('month', session_date)::DATE AS mo,
                   SUM(sessions) ms, COUNT(DISTINCT session_date) active_days
            FROM raw_ga4_sessions GROUP BY mo
        )
        SELECT m.mo AS month_start, m.ms AS monthly_sessions, m.active_days,
               ROUND(m.ms::NUMERIC / NULLIF(m.active_days, 0), 1) AS avg_dau
        FROM mau m ORDER BY m.mo
    """)


@st.cache_data(ttl=300)
def _load_funnel_dated(start_date=None, end_date=None):
    _conds = []
    _params: dict = {}
    if start_date and end_date:
        _conds.append("DATE(timestamp) BETWEEN :s AND :e")
        _params.update({"s": str(start_date), "e": str(end_date)})
    _dflt = (" AND " + " AND ".join(_conds)) if _conds else ""
    return query_df(
        f"""WITH homepage AS (
            SELECT DISTINCT session_id FROM raw_clickstream_events
            WHERE event_name = 'pageview' AND page_url = '/' {_dflt}
        ),
        product AS (
            SELECT DISTINCT session_id FROM raw_clickstream_events
            WHERE event_name = 'pageview' AND page_url IN ('/products/', '/pricing/') {_dflt}
        ),
        cart AS (
            SELECT DISTINCT session_id FROM raw_clickstream_events
            WHERE event_name = 'click' AND page_url IN ('/products/', '/pricing/') {_dflt}
        ),
        checkout AS (
            SELECT DISTINCT session_id FROM raw_clickstream_events
            WHERE event_name = 'form_submit' {_dflt}
        )
        SELECT
            (SELECT COUNT(*) FROM homepage) AS homepage,
            (SELECT COUNT(*) FROM product)  AS product_page,
            (SELECT COUNT(*) FROM cart)     AS add_to_cart,
            (SELECT COUNT(*) FROM checkout) AS checkout,
            ROUND((SELECT COUNT(*) FROM checkout) * 0.35) AS purchase""",
        params=_params or None,
    )


@st.cache_data(ttl=300)
def _load_top_pages_dated(start_date=None, end_date=None):
    if start_date and end_date:
        return query_df(
            """SELECT url,
                      COUNT(*) AS total_requests,
                      ROUND(AVG(response_time_ms)::numeric, 1) AS avg_response_time_ms,
                      ROUND(100.0 * SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END)
                          / NULLIF(COUNT(*), 0), 2) AS error_rate_pct,
                      MAX(log_time) AS last_visited
               FROM raw_server_logs
               WHERE DATE(log_time) BETWEEN :s AND :e
               GROUP BY url
               ORDER BY total_requests DESC
               LIMIT 50""",
            params={"s": str(start_date), "e": str(end_date)},
        )
    return run_view("vw_top_pages")


@st.cache_data(ttl=300)
def _load_scroll_dated(start_date=None, end_date=None, page_search: str = ""):
    _conds = []
    _params: dict = {}
    if start_date and end_date:
        _conds.append("DATE(timestamp) BETWEEN :s AND :e")
        _params.update({"s": str(start_date), "e": str(end_date)})
    if page_search:
        _conds.append("page ILIKE :pg")
        _params["pg"] = f"%{page_search}%"
    _where = ("WHERE " + " AND ".join(_conds)) if _conds else ""
    return query_df(
        f"""SELECT
                SUM(CASE WHEN scroll_depth_pct IS NOT NULL AND scroll_depth_pct <= 25 THEN 1 ELSE 0 END) AS bucket_0_25,
                SUM(CASE WHEN scroll_depth_pct > 25 AND scroll_depth_pct <= 50 THEN 1 ELSE 0 END) AS bucket_25_50,
                SUM(CASE WHEN scroll_depth_pct > 50 AND scroll_depth_pct <= 75 THEN 1 ELSE 0 END) AS bucket_50_75,
                SUM(CASE WHEN scroll_depth_pct > 75 THEN 1 ELSE 0 END) AS bucket_75_100
           FROM raw_clickstream_events {_where}""",
        params=_params,
    )


@st.cache_data(ttl=300)
def _load_engagement_dated(start_date=None, end_date=None, page_search: str = ""):
    _conds = []
    _params: dict = {}
    if start_date and end_date:
        _conds.append("DATE(timestamp) BETWEEN :s AND :e")
        _params.update({"s": str(start_date), "e": str(end_date)})
    if page_search:
        _conds.append("page ILIKE :pg")
        _params["pg"] = f"%{page_search}%"
    _where = ("WHERE " + " AND ".join(_conds)) if _conds else ""
    return query_df(
        f"""SELECT
                SUM(CASE WHEN event_type = 'click' THEN 1 ELSE 0 END) AS click_events,
                SUM(CASE WHEN event_type = 'scroll' THEN 1 ELSE 0 END) AS scroll_events,
                SUM(CASE WHEN event_type = 'pageview' THEN 1 ELSE 0 END) AS pageview_events,
                SUM(CASE WHEN event_type = 'form_submit' THEN 1 ELSE 0 END) AS form_submit_events
           FROM raw_clickstream_events {_where}""",
        params=_params,
    )


# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")
    start_date, end_date = get_date_filter()
    devices = get_device_filter()
    page_search = get_page_filter()
    st.divider()
    active = sum([bool(devices), bool(page_search)])
    if active:
        st.success(f"{active} filter(s) active")
    if st.button("Clear data cache"):
        st.cache_data.clear()
        st.success("Cache cleared — reloading…")
    st.caption("Cache TTL: 5 min")

# ── Load data — device filter applied at DB level for session queries ──────────
_dev = tuple(devices)
_plotly_tpl = get_plotly_template()
try:
    with st.spinner("Loading behavior data from PostgreSQL…"):
        df_behavior = _load_behavior()
        df_top_pages = _load_top_pages()
        df_scroll = _load_scroll()
        df_engagement = _load_engagement()
except Exception as exc:
    st.error(
        f"Could not load behavior data from the database. "
        f"Check your PostgreSQL connection and try again.\n\n**Error:** {exc}"
    )
    st.stop()

# Apply page URL filter
if page_search:
    df_behavior = df_behavior[
        df_behavior["page"].str.contains(page_search, case=False, na=False)
    ].reset_index(drop=True)
    df_top_pages = df_top_pages[
        df_top_pages["url"].str.contains(page_search, case=False, na=False)
    ].reset_index(drop=True)
    df_scroll = df_scroll[
        df_scroll["page_url"].str.contains(page_search, case=False, na=False)
    ].reset_index(drop=True)
    df_engagement = df_engagement[
        df_engagement["page_url"].str.contains(page_search, case=False, na=False)
    ].reset_index(drop=True)

with st.expander("Debug: data shapes", expanded=False):
    st.write(
        {
            "vw_behavior": df_behavior.shape,
            "vw_top_pages": df_top_pages.shape,
            "vw_scroll_depth": df_scroll.shape,
            "vw_engagement_events": df_engagement.shape,
        }
    )

# ── KPI cards — 4 metrics with % change vs previous period ───────────────────
_period_days = (end_date - start_date).days + 1
_prev_start = start_date - timedelta(days=_period_days)
_prev_end = start_date - timedelta(days=1)

_curr_kpis = _load_behavior_kpis_period(start_date, end_date, _dev)
_prev_kpis = _load_behavior_kpis_period(_prev_start, _prev_end, _dev)

display_4_kpi_row(
    {
        "title": "Total Page Views",
        "value": format_large_number(_curr_kpis["pageviews"]),
        "delta": calculate_period_change(_curr_kpis["pageviews"], _prev_kpis["pageviews"]),
        "icon": "📄",
    },
    {
        "title": "Avg Time on Page",
        "value": format_duration(_curr_kpis["avg_duration_s"]),
        "delta": calculate_period_change(
            _curr_kpis["avg_duration_s"], _prev_kpis["avg_duration_s"]
        ),
        "icon": "⏱️",
    },
    {
        "title": "Avg Scroll Depth",
        "value": format_percentage(_curr_kpis["avg_scroll"]),
        "delta": calculate_period_change(_curr_kpis["avg_scroll"], _prev_kpis["avg_scroll"]),
        "icon": "📜",
    },
    {
        "title": "Total Events Tracked",
        "value": format_large_number(_curr_kpis["total_events"]),
        "delta": calculate_period_change(
            _curr_kpis["total_events"], _prev_kpis["total_events"]
        ),
        "icon": "🖱️",
    },
)
st.caption(
    f"Period: {start_date} to {end_date} vs {_prev_start} to {_prev_end}. "
    "Green = improved performance."
)

st.divider()

# ── Top pages table ────────────────────────────────────────────────────────────
st.subheader("Top Pages by Requests")
search = st.text_input("Search by URL", placeholder="/blog/", key="top_pages_search")

df_tp_dated = _load_top_pages_dated(start_date, end_date)
if page_search:
    df_tp_dated = df_tp_dated[
        df_tp_dated["url"].str.contains(page_search, case=False, na=False)
    ].reset_index(drop=True)

if not df_tp_dated.empty:
    _tp_cols = ["url", "total_requests", "avg_response_time_ms", "error_rate_pct"]
    if "last_visited" in df_tp_dated.columns:
        _tp_cols.append("last_visited")
    df_tp = df_tp_dated[_tp_cols].sort_values("total_requests", ascending=False).copy()
    if search:
        df_tp = df_tp[df_tp["url"].str.contains(search, case=False, na=False)]

    def _style_page_perf(row):
        ms = row["avg_response_time_ms"]
        if ms > 1000:
            return ["background-color: #ffd6d6"] * len(row)
        if ms < 200:
            return ["background-color: #d4edda"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df_tp.style.apply(_style_page_perf, axis=1),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        f"{len(df_tp):,} pages shown · Green = fast (<200 ms) · Red = slow (>1,000 ms)"
    )
else:
    st.info("No page data available.")

st.divider()

# ── Page performance bar chart ────────────────────────────────────────────────
st.subheader("Page Performance — Top 10 by Requests")
if not df_tp_dated.empty:
    _perf_top10 = df_tp_dated.nlargest(10, "total_requests").sort_values(
        "total_requests", ascending=True
    )

    def _ms_color(ms):
        if ms > 1000:
            return "#d62728"
        if ms > 200:
            return "#ff7f0e"
        return "#2ca02c"

    _bar_colors = [_ms_color(v) for v in _perf_top10["avg_response_time_ms"]]
    fig_perf = go.Figure(
        go.Bar(
            x=_perf_top10["total_requests"],
            y=_perf_top10["url"],
            orientation="h",
            marker_color=_bar_colors,
            text=_perf_top10["avg_response_time_ms"].apply(lambda v: f"{v:.0f} ms"),
            textposition="outside",
            customdata=_perf_top10[["avg_response_time_ms"]].values,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Requests: %{x:,}<br>"
                "Avg Response: %{customdata[0]:.0f} ms"
                "<extra></extra>"
            ),
        )
    )
    fig_perf.update_layout(
        title="Top 10 Pages by Request Volume",
        xaxis_title="Total Requests",
        yaxis_title=None,
        template=_plotly_tpl,
        height=420,
    )
    st.plotly_chart(fig_perf, use_container_width=True)
    st.caption(
        "Color: green = fast (<200 ms) · orange = medium (200–1,000 ms) · red = slow (>1,000 ms)"
    )
else:
    st.info("No page performance data available.")

st.divider()

# ── Conversion funnel ─────────────────────────────────────────────────────────
st.subheader("Conversion Funnel")

df_funnel = _load_funnel_dated(start_date, end_date)
if df_funnel.empty:
    df_funnel = _load_funnel()

if not df_funnel.empty:
    _f_stages = ["Landing Page", "Product Page", "Add to Cart", "Checkout", "Purchase"]
    _f_cols = ["homepage", "product_page", "add_to_cart", "checkout", "purchase"]
    _f_vals = [int(df_funnel[c].iloc[0]) for c in _f_cols]

    # Drop-off % between consecutive stages
    _f_drops: list = []
    for _fi in range(1, len(_f_vals)):
        _fp = _f_vals[_fi - 1]
        _f_drops.append(round((_fp - _f_vals[_fi]) / _fp * 100, 1) if _fp else 0.0)

    # Stage with biggest drop-off gets a red bar
    _worst_idx = (_f_drops.index(max(_f_drops)) + 1) if _f_drops else 0
    _f_colors = ["#636EFA"] * len(_f_stages)
    if _worst_idx:
        _f_colors[_worst_idx] = "#d62728"

    # Custom text: show count + stage-to-stage drop-off %
    _f_text = [f"{_f_vals[0]:,}"]
    for _fi, _fd in enumerate(_f_drops):
        _f_text.append(f"{_f_vals[_fi + 1]:,}  (-{_fd}%)")

    fig_funnel = go.Figure(
        go.Funnel(
            y=_f_stages,
            x=_f_vals,
            text=_f_text,
            textinfo="text+percent initial",
            marker_color=_f_colors,
            connector=dict(line=dict(color="rgba(120,120,120,0.3)", width=1)),
        )
    )
    fig_funnel.update_layout(
        title="Conversion Funnel: Landing Page to Purchase"
        + (f" ({start_date} to {end_date})" if start_date and end_date else ""),
        template=_plotly_tpl,
        height=400,
    )
    st.plotly_chart(fig_funnel, use_container_width=True)
    _f_overall_cvr = round(_f_vals[-1] / _f_vals[0] * 100, 2) if _f_vals[0] else 0
    st.caption(
        f"Biggest drop-off: {_f_stages[_worst_idx]} "
        f"({_f_drops[_worst_idx - 1]}% lost from previous stage) — highlighted in red.  "
        f"Overall conversion: {_f_overall_cvr}%"
    )
else:
    st.info("No funnel data available.")

st.divider()

# ── Funnel drop-off analysis table ───────────────────────────────────────────
st.subheader("Funnel Drop-off Analysis")
if not df_funnel.empty:
    import pandas as pd

    _drop_rows = []
    for _di, _ds in enumerate(_f_stages):
        _entered = _f_vals[_di]
        _dropped = _f_vals[_di - 1] - _entered if _di > 0 else 0
        _drop_pct = _f_drops[_di - 1] if _di > 0 else 0.0
        _compl_pct = round(_entered / _f_vals[0] * 100, 1) if _f_vals[0] else 0.0
        _drop_rows.append(
            {
                "Stage": _ds,
                "Users Entered": _entered,
                "Users Dropped": _dropped,
                "Drop-off %": _drop_pct,
                "Completion Rate %": _compl_pct,
            }
        )

    df_drop_tbl = pd.DataFrame(_drop_rows)
    st.dataframe(
        df_drop_tbl.style.background_gradient(
            subset=["Drop-off %"], cmap="RdYlGn_r", vmin=0, vmax=100
        )
        .background_gradient(
            subset=["Completion Rate %"], cmap="RdYlGn", vmin=0, vmax=100
        )
        .format(
            {
                "Drop-off %": "{:.1f}%",
                "Completion Rate %": "{:.1f}%",
                "Users Entered": "{:,}",
                "Users Dropped": "{:,}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )
    _needs_attn = df_drop_tbl.loc[df_drop_tbl["Drop-off %"].idxmax(), "Stage"]
    _max_drop_pct = df_drop_tbl["Drop-off %"].max()
    st.caption(
        f"Stage needing most attention: {_needs_attn} "
        f"(highest drop-off: {_max_drop_pct}%) — "
        "Red = high drop-off, Green = low drop-off / high completion."
    )
else:
    st.info("No funnel data available for drop-off analysis.")

st.divider()

# ── Scroll depth histogram ────────────────────────────────────────────────────
st.subheader("Scroll Depth Distribution")
import pandas as pd

df_scroll_d = _load_scroll_dated(start_date, end_date, page_search or "")
_scroll_src = df_scroll_d if not df_scroll_d.empty else df_scroll
if not _scroll_src.empty:
    buckets = {
        "0-25%": int(_scroll_src["bucket_0_25"].sum()),
        "25-50%": int(_scroll_src["bucket_25_50"].sum()),
        "50-75%": int(_scroll_src["bucket_50_75"].sum()),
        "75-100%": int(_scroll_src["bucket_75_100"].sum()),
    }
    _total_scroll = sum(buckets.values()) or 1
    df_scroll_plot = pd.DataFrame(
        {
            "Bucket": list(buckets.keys()),
            "Sessions": list(buckets.values()),
            "Pct": [f"{v / _total_scroll * 100:.1f}%" for v in buckets.values()],
            "Color": ["#d62728", "#ff7f0e", "#ffbb78", "#2ca02c"],
        }
    )
    fig_scroll = go.Figure(
        go.Bar(
            x=df_scroll_plot["Bucket"],
            y=df_scroll_plot["Sessions"],
            marker_color=df_scroll_plot["Color"].tolist(),
            text=df_scroll_plot["Pct"],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Sessions: %{y:,}<extra></extra>",
        )
    )
    fig_scroll.update_layout(
        title="Scroll Depth Distribution"
        + (f" — {start_date} to {end_date}" if start_date and end_date else ""),
        xaxis_title="Scroll Depth",
        yaxis_title="Event Count",
        template=_plotly_tpl,
    )
    st.plotly_chart(fig_scroll, use_container_width=True)
    st.caption(
        "Red = low engagement (0-25%) · Yellow = medium · Green = high (75-100%)"
    )
else:
    st.info("No scroll depth data available.")

st.divider()

# ── Engagement events breakdown ───────────────────────────────────────────────
st.subheader("Engagement Events Breakdown")
df_ev_d = _load_engagement_dated(start_date, end_date, page_search or "")
_ev_src = df_ev_d if not df_ev_d.empty else df_engagement
if not _ev_src.empty:
    ev_totals = {
        "Click": int(_ev_src["click_events"].sum()),
        "Scroll": int(_ev_src["scroll_events"].sum()),
        "Pageview": int(_ev_src["pageview_events"].sum()),
        "Form Submit": int(_ev_src["form_submit_events"].sum()),
    }
    _ev_grand = sum(ev_totals.values()) or 1
    df_ev_plot = pd.DataFrame(
        {
            "Event Type": list(ev_totals.keys()),
            "Count": list(ev_totals.values()),
            "Pct": [f"{v / _ev_grand * 100:.1f}%" for v in ev_totals.values()],
            "Color": ["#636EFA", "#EF553B", "#00CC96", "#AB63FA"],
        }
    )
    fig_ev = go.Figure(
        go.Bar(
            x=df_ev_plot["Event Type"],
            y=df_ev_plot["Count"],
            marker_color=df_ev_plot["Color"].tolist(),
            text=df_ev_plot["Pct"],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Count: %{y:,}<extra></extra>",
        )
    )
    fig_ev.update_layout(
        title="Events by Type"
        + (f" — {start_date} to {end_date}" if start_date and end_date else ""),
        xaxis_title="Event Type",
        yaxis_title="Count",
        template=_plotly_tpl,
    )
    st.plotly_chart(fig_ev, use_container_width=True)
    st.caption(
        f"Total events: {_ev_grand:,} · "
        + " · ".join(f"{k}: {v / _ev_grand * 100:.1f}%" for k, v in ev_totals.items())
    )
else:
    st.info("No engagement event data available.")

st.divider()

# ── Time on page distribution ─────────────────────────────────────────────────
st.subheader("Time on Page Distribution")
# Primary: session duration derived from raw_clickstream_events (per-event timestamps)
# Fallback: pre-aggregated raw_ga4_sessions buckets
df_dur = _load_duration_clickstream(start_date, end_date)
if df_dur.empty:
    df_dur = _load_duration(start_date, end_date, _dev)
if not df_dur.empty:
    # Column names from SQL use ASCII hyphens — use them directly
    _dur_cols = ["0-30s", "30s-2m", "2m-5m", "5m-10m", "10m+"]
    _dur_display = ["0-30s", "30s-2m", "2m-5m", "5m-10m", "10m+"]
    _dur_colors = ["#d62728", "#ff7f0e", "#ffbb78", "#9dc183", "#2ca02c"]
    _dur_values = []
    for col in _dur_cols:
        try:
            _dur_values.append(int(df_dur[col].iloc[0]))
        except (KeyError, IndexError):
            _dur_values.append(0)
    _dur_total = sum(_dur_values) or 1
    fig_dur = go.Figure(
        go.Bar(
            x=_dur_display,
            y=_dur_values,
            marker_color=_dur_colors,
            text=[f"{v:,}<br>({v / _dur_total * 100:.1f}%)" for v in _dur_values],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Sessions: %{y:,}<extra></extra>",
        )
    )
    fig_dur.update_layout(
        title="Session Duration Distribution (Time on Page)",
        xaxis_title="Duration Bucket",
        yaxis_title="Sessions",
        template=_plotly_tpl,
    )

    # Avg session duration reference annotation
    _avg_s = float(_curr_kpis.get("avg_duration_s") or 0)
    if _avg_s > 0:
        def _avg_dur_bucket(s):
            if s < 30:
                return "0-30s"
            if s < 120:
                return "30s-2m"
            if s < 300:
                return "2m-5m"
            if s < 600:
                return "5m-10m"
            return "10m+"

        _avg_buck = _avg_dur_bucket(_avg_s)
        try:
            fig_dur.add_vline(
                x=_avg_buck,
                line_dash="dash",
                line_color="#ffd700",
                line_width=2,
                annotation_text=f"Avg: {format_duration(_avg_s)}",
                annotation_position="top",
                annotation=dict(
                    font=dict(color="#ffd700", size=12),
                    bgcolor="rgba(0,0,0,0.1)",
                ),
            )
        except Exception:
            fig_dur.add_annotation(
                xref="paper", yref="paper",
                x=0.01, y=0.97,
                text=f"Avg session: {format_duration(_avg_s)}",
                showarrow=False,
                bgcolor="rgba(255,215,0,0.15)",
                bordercolor="#ffd700",
                borderwidth=1,
                font=dict(size=11),
                align="left",
            )

    st.plotly_chart(fig_dur, use_container_width=True)
    st.caption(
        f"Total sessions: {_dur_total:,} · "
        "Color: red = short sessions, green = long sessions"
        + (f" · Dashed line = avg ({format_duration(_avg_s)})" if _avg_s > 0 else "")
    )
else:
    st.info("No session duration data available.")

st.divider()

# ── Top pages by engagement score ─────────────────────────────────────────────
st.subheader("Top Pages by Engagement Score")
if not df_behavior.empty:
    df_eng = df_behavior.copy()
    _max_scroll_e = df_eng["avg_scroll_depth_pct"].max() or 1
    _max_events_e = df_eng["total_events"].max() or 1
    _max_resp_e = df_eng["avg_response_ms"].max() or 1

    # Compute normalised component scores
    df_eng["c_scroll"] = (df_eng["avg_scroll_depth_pct"].fillna(0) / _max_scroll_e * 0.4).round(4)
    df_eng["c_events"] = (df_eng["total_events"] / _max_events_e * 0.3).round(4)
    df_eng["c_speed"] = ((1 - df_eng["avg_response_ms"] / _max_resp_e) * 0.3).round(4)
    df_eng["score"] = (df_eng["c_scroll"] + df_eng["c_events"] + df_eng["c_speed"]).round(4)

    _eng_cols = [
        "page", "score", "c_scroll", "c_events", "c_speed",
        "avg_scroll_depth_pct", "total_events", "avg_response_ms",
    ]
    df_top10 = df_eng.nlargest(10, "score")[_eng_cols].reset_index(drop=True)
    df_top10_sorted = df_top10.sort_values("score", ascending=True)

    fig_eng = go.Figure(
        go.Bar(
            x=df_top10_sorted["score"],
            y=df_top10_sorted["page"],
            orientation="h",
            marker=dict(
                color=df_top10_sorted["score"],
                colorscale="Viridis",
                showscale=True,
                colorbar=dict(title="Score"),
            ),
            customdata=df_top10_sorted[[
                "c_scroll", "c_events", "c_speed",
                "avg_scroll_depth_pct", "total_events", "avg_response_ms",
            ]].values,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Total Score: %{x:.4f}<br>"
                "<br>Score Breakdown:<br>"
                "  Scroll Depth (40%): %{customdata[0]:.4f}<br>"
                "  Events (30%): %{customdata[1]:.4f}<br>"
                "  Speed (30%): %{customdata[2]:.4f}<br>"
                "<br>Raw Metrics:<br>"
                "  Avg Scroll Depth: %{customdata[3]:.1f}%<br>"
                "  Total Events: %{customdata[4]:,}<br>"
                "  Avg Response: %{customdata[5]:.0f} ms"
                "<extra></extra>"
            ),
        )
    )
    fig_eng.update_layout(
        title="Top 10 Pages by Engagement Score",
        xaxis_title="Engagement Score (0-1)",
        yaxis_title=None,
        template=_plotly_tpl,
        height=420,
    )
    st.plotly_chart(fig_eng, use_container_width=True)
    st.caption(
        "Score = Scroll Depth (40%) + Events (30%) + Page Speed (30%) — hover for breakdown"
    )

    # Engagement score table with CSV download
    st.markdown("**Engagement Score Table — Top 10 Pages**")
    df_eng_tbl = df_top10[["page", "score", "c_scroll", "c_events", "c_speed",
                            "avg_scroll_depth_pct", "total_events", "avg_response_ms"]].copy()
    df_eng_tbl.columns = [
        "Page", "Total Score", "Scroll (40%)", "Events (30%)", "Speed (30%)",
        "Avg Scroll %", "Total Events", "Avg Response ms",
    ]
    df_eng_tbl = df_eng_tbl.sort_values("Total Score", ascending=False).reset_index(drop=True)
    st.dataframe(
        df_eng_tbl.style.background_gradient(
            subset=["Total Score"], cmap="viridis", vmin=0, vmax=1
        ).format(
            {
                "Total Score": "{:.4f}",
                "Scroll (40%)": "{:.4f}",
                "Events (30%)": "{:.4f}",
                "Speed (30%)": "{:.4f}",
                "Avg Scroll %": "{:.1f}%",
                "Total Events": "{:,.0f}",
                "Avg Response ms": "{:.0f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        label="Download engagement scores as CSV",
        data=df_eng_tbl.to_csv(index=False).encode("utf-8"),
        file_name="engagement_scores.csv",
        mime="text/csv",
    )
else:
    st.info("No behavior data available.")

st.divider()

# ── Page views over time ───────────────────────────────────────────────────────
st.subheader("Page Views Over Time")
pv_url = st.text_input(
    "Filter by page URL (optional)", placeholder="/blog/", key="pv_url_filter"
)
_pv_where = "AND url ILIKE :url_pat" if pv_url else ""
_pv_params = {"url_pat": f"%{pv_url}%"} if pv_url else {}
_pv_sql = f"""
SELECT DATE(log_time) AS log_date, COUNT(*) AS total_requests
FROM raw_server_logs
WHERE 1=1 {_pv_where}
GROUP BY DATE(log_time)
ORDER BY log_date
"""
df_pv = query_df(_pv_sql, _pv_params)
if not df_pv.empty:
    fig_pv = line_chart(
        df_pv,
        x="log_date",
        y="total_requests",
        title="Daily Page Requests" + (f" — {pv_url}" if pv_url else ""),
        labels={"log_date": "Date", "total_requests": "Requests"},
    )
    st.plotly_chart(fig_pv, use_container_width=True)
else:
    st.info("No page view data for the selected URL.")

st.divider()

# ── Retention Analysis ────────────────────────────────────────────────────────
st.subheader("Retention Analysis")

import pandas as pd

df_dau_mau = _load_dau_mau()
df_retention = _load_retention(start_date, end_date, _dev)

# KPI cards: DAU, WAU, MAU, stickiness
if not df_retention.empty:
    last_week_row = df_retention.iloc[-1]
    dau_approx = int(last_week_row.get("weekly_sessions", 0) / 7 or 0)
    wau = int(last_week_row.get("weekly_sessions", 0) or 0)
    mau = int(df_dau_mau["monthly_sessions"].iloc[-1]) if not df_dau_mau.empty else 0
    stickiness = round(dau_approx / mau * 100, 1) if mau else 0
    ret_rate = float(last_week_row.get("retention_rate_pct", 0) or 0)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("DAU (last week avg)", f"{dau_approx:,}")
    with k2:
        st.metric("WAU (last week)", f"{wau:,}")
    with k3:
        st.metric("MAU (last month)", f"{mau:,}")
    with k4:
        st.metric("Stickiness (DAU/MAU)", f"{stickiness}%")

    # Retention trend chart
    fig_ret = go.Figure()
    fig_ret.add_trace(
        go.Scatter(
            x=df_retention["week_start"].astype(str),
            y=df_retention["retention_rate_pct"],
            mode="lines+markers",
            name="Retention Rate %",
            line=dict(color="#00CC96", width=2),
        )
    )
    fig_ret.add_trace(
        go.Bar(
            x=df_retention["week_start"].astype(str),
            y=df_retention["weekly_sessions"],
            name="Weekly Sessions",
            yaxis="y2",
            opacity=0.3,
            marker_color="#636EFA",
        )
    )
    fig_ret.update_layout(
        title="Weekly Retention Rate & Session Volume",
        xaxis_title="Week",
        yaxis=dict(title="Retention Rate %", range=[0, 100]),
        yaxis2=dict(title="Sessions", overlaying="y", side="right"),
        template="plotly_white",
        legend=dict(orientation="h", y=1.1),
    )
    st.plotly_chart(fig_ret, use_container_width=True)

    # Re-engagement rate by channel
    df_reeng = query_df("""
        SELECT channel_grouping,
               ROUND((SUM(sessions) - SUM(new_users))::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2) AS re_engagement_pct
        FROM raw_ga4_sessions
        GROUP BY channel_grouping ORDER BY re_engagement_pct DESC
    """)
    if not df_reeng.empty:
        fig_re = go.Figure(
            go.Bar(
                x=df_reeng["channel_grouping"],
                y=df_reeng["re_engagement_pct"],
                marker_color="#AB63FA",
                text=df_reeng["re_engagement_pct"].apply(lambda v: f"{v}%"),
                textposition="outside",
            )
        )
        fig_re.update_layout(
            title="Re-engagement Rate by Channel (Returning Users %)",
            xaxis_title="Channel",
            yaxis_title="Re-engagement %",
            template="plotly_white",
        )
        st.plotly_chart(fig_re, use_container_width=True)
else:
    st.info("No retention data available.")

st.divider()

# ── Session Quality ───────────────────────────────────────────────────────────
st.subheader("Session Quality")

df_sq = _load_session_quality(start_date, end_date, _dev)

if not df_sq.empty:
    total_all = int(df_sq["total_sessions"].sum())
    high_all = int(df_sq["high_quality"].sum())
    low_all = int(df_sq["low_quality"].sum())
    mid_all = total_all - high_all - low_all

    sq1, sq2, sq3 = st.columns(3)
    with sq1:
        st.metric(
            "High Quality Sessions",
            f"{high_all:,}",
            delta=(
                f"{round(high_all / total_all * 100, 1)}% of total"
                if total_all
                else None
            ),
        )
    with sq2:
        st.metric("Medium Quality Sessions", f"{mid_all:,}")
    with sq3:
        st.metric(
            "Low Quality Sessions",
            f"{low_all:,}",
            delta=(
                f"-{round(low_all / total_all * 100, 1)}% bounce/quick-exit"
                if total_all
                else None
            ),
            delta_color="inverse",
        )

    # High / low quality pie
    pie_col, bar_col = st.columns(2)
    with pie_col:
        fig_pie = go.Figure(
            go.Pie(
                labels=["High Quality", "Medium Quality", "Low Quality"],
                values=[high_all, mid_all, low_all],
                marker_colors=["#2ca02c", "#ffbb78", "#d62728"],
                hole=0.35,
            )
        )
        fig_pie.update_layout(
            title="Session Quality Distribution", template="plotly_white"
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with bar_col:
        fig_bar = go.Figure()
        fig_bar.add_trace(
            go.Bar(
                name="High Quality %",
                x=df_sq["channel_grouping"],
                y=df_sq["high_quality_pct"],
                marker_color="#2ca02c",
            )
        )
        fig_bar.add_trace(
            go.Bar(
                name="Low Quality %",
                x=df_sq["channel_grouping"],
                y=df_sq["low_quality_pct"],
                marker_color="#d62728",
            )
        )
        fig_bar.update_layout(
            barmode="group",
            title="Session Quality by Channel",
            xaxis_title="Channel",
            yaxis_title="% of Sessions",
            template="plotly_white",
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # Best time heatmap — high quality sessions by day-of-week
    df_qheat = _load_quality_heatmap()
    if not df_qheat.empty:
        _day_map2 = {
            0: "Sun",
            1: "Mon",
            2: "Tue",
            3: "Wed",
            4: "Thu",
            5: "Fri",
            6: "Sat",
        }
        df_qheat["day_name"] = df_qheat["dow"].map(_day_map2)
        pivot_q = df_qheat.pivot_table(
            index="day_name",
            columns="hour_of_day",
            values="high_quality",
            fill_value=0,
        )
        day_order2 = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        pivot_q = pivot_q.reindex([d for d in day_order2 if d in pivot_q.index])
        fig_qheat = go.Figure(
            go.Heatmap(
                z=pivot_q.values.tolist(),
                x=[str(h) for h in pivot_q.columns.tolist()],
                y=pivot_q.index.tolist(),
                colorscale="Greens",
                hoverongaps=False,
                colorbar=dict(title="High Quality"),
            )
        )
        fig_qheat.update_layout(
            title="Best Time for High Quality Sessions (Day × Hour)",
            xaxis_title="Hour of Day",
            yaxis_title="Day of Week",
            template="plotly_white",
        )
        st.plotly_chart(fig_qheat, use_container_width=True)
else:
    st.info("No session quality data available.")

st.divider()

# ── Traffic heatmap by day and hour ───────────────────────────────────────────
st.subheader("Traffic Heatmap — Day × Hour")
df_heat = _load_heatmap_dated(start_date, end_date)
if df_heat.empty:
    df_heat = _load_heatmap()
if not df_heat.empty:
    _day_map = {0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat"}
    df_heat["day_name"] = df_heat["dow"].map(_day_map)
    pivot = df_heat.pivot_table(
        index="day_name",
        columns="hour_of_day",
        values="total_requests",
        fill_value=0,
    )
    day_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    pivot = pivot.reindex([d for d in day_order if d in pivot.index])
    fig_heat = go.Figure(
        go.Heatmap(
            z=pivot.values.tolist(),
            x=[str(h) for h in pivot.columns.tolist()],
            y=pivot.index.tolist(),
            colorscale="YlOrRd",
            hoverongaps=False,
            colorbar=dict(title="Requests"),
            hovertemplate="Day: %{y}<br>Hour: %{x}:00<br>Requests: %{z:,}<extra></extra>",
        )
    )
    fig_heat.update_layout(
        title="Request Volume by Day of Week and Hour"
        + (f" ({start_date} to {end_date})" if start_date and end_date else ""),
        xaxis_title="Hour of Day (0–23)",
        yaxis_title="Day of Week",
        template=_plotly_tpl,
    )
    st.plotly_chart(fig_heat, use_container_width=True)
    st.caption("Color intensity = request volume · Brightest cells = peak traffic hours")
else:
    st.info("No hourly traffic data available.")

st.divider()

# ── New vs Returning Users ────────────────────────────────────────────────────
st.subheader("New vs Returning Users")
df_nvr = _load_new_vs_ret_dated(start_date, end_date)
if not df_nvr.empty:
    _new_u = int(df_nvr["new_users"].iloc[0])
    _ret_u = int(df_nvr["returning_users"].iloc[0])
    _total_u = int(df_nvr["total_sessions"].iloc[0]) or 1
    _new_pct = round(_new_u / _total_u * 100, 1)
    _ret_pct = round(_ret_u / _total_u * 100, 1)

    _nvr_col1, _nvr_col2 = st.columns([1, 2])
    with _nvr_col1:
        st.metric("New Users", f"{_new_u:,}", delta=f"{_new_pct}% of sessions")
        st.metric("Returning Users", f"{_ret_u:,}", delta=f"{_ret_pct}% of sessions")
        st.metric("Total Sessions", f"{_total_u:,}")

    with _nvr_col2:
        fig_nvr = go.Figure(
            go.Pie(
                labels=["New Users", "Returning Users"],
                values=[_new_u, _ret_u],
                hole=0.45,
                marker_colors=["#636EFA", "#EF553B"],
                textinfo="label+percent",
                hovertemplate=(
                    "<b>%{label}</b><br>Sessions: %{value:,}<br>Share: %{percent}<extra></extra>"
                ),
            )
        )
        fig_nvr.add_annotation(
            text=f"{_total_u:,}<br>sessions",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=14),
        )
        fig_nvr.update_layout(
            title="New vs Returning Users"
            + (f" ({start_date} to {end_date})" if start_date and end_date else ""),
            template=_plotly_tpl,
            showlegend=True,
            legend=dict(orientation="h", y=-0.1),
        )
        st.plotly_chart(fig_nvr, use_container_width=True)
    st.caption(
        f"New: {_new_pct}% · Returning: {_ret_pct}% "
        f"· Period: {start_date} to {end_date}" if start_date and end_date
        else f"New: {_new_pct}% · Returning: {_ret_pct}%"
    )
else:
    st.info("No new vs returning data available.")

st.divider()

# ── Event type trends ─────────────────────────────────────────────────────────
st.subheader("Event Type Trends Over Time")
import pandas as pd

df_event_trend = _load_event_trend(start_date, end_date)
if not df_event_trend.empty:
    df_event_trend["event_date"] = pd.to_datetime(df_event_trend["event_date"])
    df_ev_pivot = df_event_trend.pivot_table(
        index="event_date",
        columns="event_type",
        values="event_count",
        fill_value=0,
    ).reset_index()

    _et_colors = {
        "click": "#636EFA",
        "scroll": "#EF553B",
        "pageview": "#00CC96",
        "form_submit": "#AB63FA",
    }
    fig_trend = go.Figure()
    for _et in ["click", "scroll", "pageview", "form_submit"]:
        if _et in df_ev_pivot.columns:
            fig_trend.add_trace(
                go.Scatter(
                    x=df_ev_pivot["event_date"],
                    y=df_ev_pivot[_et],
                    mode="lines",
                    name=_et.replace("_", " ").title(),
                    line=dict(color=_et_colors.get(_et, "#888888"), width=2),
                    hovertemplate=(
                        f"<b>{_et.replace('_', ' ').title()}</b><br>"
                        "Date: %{x|%Y-%m-%d}<br>"
                        "Count: %{y:,}<extra></extra>"
                    ),
                )
            )
    fig_trend.update_xaxes(
        rangeselector=dict(
            buttons=[
                dict(count=7, label="7D", step="day", stepmode="backward"),
                dict(count=30, label="30D", step="day", stepmode="backward"),
                dict(count=90, label="90D", step="day", stepmode="backward"),
                dict(step="all", label="All"),
            ]
        )
    )
    fig_trend.update_layout(
        title="Event Count by Type Over Time",
        xaxis_title="Date",
        yaxis_title="Event Count",
        template=_plotly_tpl,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.1),
    )
    st.plotly_chart(fig_trend, use_container_width=True)
    st.caption("Use the range selector above the chart to zoom into 7D / 30D / 90D windows")
else:
    st.info("No event trend data available.")

st.divider()

# ── Top pages by event count ──────────────────────────────────────────────────
st.subheader("Top Pages by Event Count")
_evt_search = st.text_input("Filter by page URL", placeholder="/blog/", key="evt_page_search")
df_top_events = _load_top_pages_events(start_date, end_date)
if not df_top_events.empty:
    if _evt_search:
        df_top_events = df_top_events[
            df_top_events["page"].str.contains(_evt_search, case=False, na=False)
        ].reset_index(drop=True)
    df_top_events.columns = ["Page", "Total Events", "Clicks", "Scrolls", "Form Submits"]

    st.dataframe(
        df_top_events.style.background_gradient(
            subset=["Form Submits"], cmap="Greens", vmin=0
        ).format(
            {
                "Total Events": "{:,}",
                "Clicks": "{:,}",
                "Scrolls": "{:,}",
                "Form Submits": "{:,}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        label="Download table as CSV",
        data=df_top_events.to_csv(index=False).encode("utf-8"),
        file_name="top_pages_events.csv",
        mime="text/csv",
    )
    st.caption(
        f"{len(df_top_events):,} pages shown · "
        "Green = high form submission volume · Sorted by total events"
    )
else:
    st.info("No page event data available.")
