"""
Sidebar filter components for the Analytics Intelligence Platform.

Each get_*_filter() function renders its widget and returns the selected value(s).
Filter values are stored in st.session_state under the keys in FILTER_KEYS so
they persist across page navigation within the same Streamlit session.

DB-option loaders (get_available_*, get_date_range) are cached for 10 minutes so
filter widgets always show real data without hammering the database on every render.
"""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

DARK_MODE_KEY = "dark_mode"

FILTER_KEYS = {
    "date_range": "gf_date_range",
    "channels": "gf_channels",
    "page_search": "gf_page_search",
    "devices": "gf_devices",
}


def get_plotly_template() -> str:
    """Return the Plotly chart template matching the current dark mode preference."""
    if st.session_state.get(DARK_MODE_KEY, False):
        return "plotly_dark"
    return "plotly_white"


# ── DB option loaders — TTL 600s ──────────────────────────────────────────────

@st.cache_data(ttl=600)
def get_date_range() -> tuple[date, date]:
    """Load min and max session dates from PostgreSQL. Cached 10 minutes."""
    from utils.db import query_df as _qdf

    try:
        df = _qdf(
            "SELECT MIN(session_date)::date AS mn, MAX(session_date)::date AS mx "
            "FROM raw_ga4_sessions"
        )
        mn, mx = df["mn"].iloc[0], df["mx"].iloc[0]
        if mn is not None and mx is not None:
            mn_d = mn.date() if hasattr(mn, "date") else date.fromisoformat(str(mn)[:10])
            mx_d = mx.date() if hasattr(mx, "date") else date.fromisoformat(str(mx)[:10])
            return mn_d, mx_d
    except Exception:
        pass
    return date(2020, 1, 1), date.today()


@st.cache_data(ttl=600)
def get_available_channels() -> list[str]:
    """Load distinct channel names from PostgreSQL. Cached 10 minutes."""
    from utils.db import query_df as _qdf

    try:
        df = _qdf(
            "SELECT DISTINCT channel_grouping FROM raw_ga4_sessions "
            "WHERE channel_grouping IS NOT NULL ORDER BY 1"
        )
        return list(df["channel_grouping"])
    except Exception:
        return ["Direct", "Email", "Organic Search", "Paid Search", "Referral", "Social"]


@st.cache_data(ttl=600)
def get_available_devices() -> list[str]:
    """Load distinct device types from PostgreSQL. Cached 10 minutes."""
    from utils.db import query_df as _qdf

    try:
        df = _qdf(
            "SELECT DISTINCT device_category FROM raw_ga4_sessions "
            "WHERE device_category IS NOT NULL ORDER BY 1"
        )
        return list(df["device_category"])
    except Exception:
        return ["desktop", "mobile", "tablet"]


@st.cache_data(ttl=600)
def get_available_pages() -> list[str]:
    """Load top 50 page URLs from PostgreSQL. Cached 10 minutes."""
    from utils.db import query_df as _qdf

    try:
        df = _qdf("SELECT url FROM vw_top_pages LIMIT 50")
        return list(df["url"])
    except Exception:
        return []


# ── SQL WHERE clause builder ──────────────────────────────────────────────────

def build_where_clause(
    start_date=None,
    end_date=None,
    channels: list[str] | None = None,
    devices: list[str] | None = None,
    date_col: str = "session_date",
    channel_col: str = "channel_grouping",
    device_col: str = "device_category",
) -> tuple[str, dict]:
    """
    Build a SQL WHERE clause string and named-params dict for DB-level filtering.

    Returns (where_str, params_dict). where_str is "" when no filters are active.
    Use :filter_start / :filter_end for dates, :ch0 / :ch1 … for channels,
    :dev0 / :dev1 … for devices — all bound safely via SQLAlchemy text().
    """
    clauses: list[str] = []
    params: dict = {}

    if start_date:
        clauses.append(f"{date_col} >= :filter_start")
        params["filter_start"] = str(start_date)
    if end_date:
        clauses.append(f"{date_col} <= :filter_end")
        params["filter_end"] = str(end_date)

    if channels:
        phs = ", ".join(f":ch{i}" for i in range(len(channels)))
        clauses.append(f"{channel_col} IN ({phs})")
        params.update({f"ch{i}": ch for i, ch in enumerate(channels)})

    if devices:
        phs = ", ".join(f":dev{i}" for i in range(len(devices)))
        clauses.append(f"{device_col} IN ({phs})")
        params.update({f"dev{i}": dev for i, dev in enumerate(devices)})

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


# ── Filter widgets ────────────────────────────────────────────────────────────

def get_date_filter() -> tuple[date, date]:
    """Render a date range picker bounded by actual DB dates. Returns (start_date, end_date)."""
    today = date.today()
    default_start = today - timedelta(days=29)
    db_min, _db_max = get_date_range()
    date_range = st.sidebar.date_input(
        "Date range",
        value=(default_start, today),
        min_value=db_min,
        max_value=today,
        key=FILTER_KEYS["date_range"],
    )
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        return date_range[0], date_range[1]
    return date_range, date_range


def get_channel_filter() -> list[str]:
    """Render a multiselect with channels loaded from DB. Returns selected channels (empty = all)."""
    return st.sidebar.multiselect(
        "Channel",
        options=get_available_channels(),
        default=[],
        placeholder="All channels",
        key=FILTER_KEYS["channels"],
    )


def get_page_filter() -> str:
    """Render a text input for page URL search. Returns the search string (empty = no filter)."""
    return st.sidebar.text_input(
        "Page URL contains",
        value="",
        placeholder="/blog/",
        key=FILTER_KEYS["page_search"],
    ).strip()


def get_device_filter() -> list[str]:
    """Render a multiselect with device types loaded from DB. Returns selected devices (empty = all)."""
    return st.sidebar.multiselect(
        "Device",
        options=get_available_devices(),
        default=[],
        placeholder="All devices",
        key=FILTER_KEYS["devices"],
    )


# ── DataFrame-level filtering ─────────────────────────────────────────────────

def apply_date_filter(
    df: pd.DataFrame,
    start_date: date | None,
    end_date: date | None,
) -> pd.DataFrame:
    """Apply only the date range filter to a DataFrame."""
    return apply_filters(df, start_date=start_date, end_date=end_date)


def apply_all_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Apply all active filters from st.session_state to a DataFrame."""
    dr = st.session_state.get(FILTER_KEYS["date_range"])
    if isinstance(dr, (tuple, list)) and len(dr) == 2:
        start, end = dr[0], dr[1]
    else:
        start = end = None

    channels = list(st.session_state.get(FILTER_KEYS["channels"], []))
    page_search = str(st.session_state.get(FILTER_KEYS["page_search"], "")).strip()
    devices = list(st.session_state.get(FILTER_KEYS["devices"], []))

    return apply_filters(df, start, end, channels, page_search, devices)


def apply_filters(
    df: pd.DataFrame,
    start_date: date | None = None,
    end_date: date | None = None,
    channels: list[str] | None = None,
    page_search: str = "",
    devices: list[str] | None = None,
) -> pd.DataFrame:
    """
    Apply active filters to a DataFrame.
    Looks for columns: session_date, channel_grouping, page_url/url, device_category.
    Unrecognised columns are silently ignored.
    """
    mask = pd.Series([True] * len(df), index=df.index)

    if start_date is not None and "session_date" in df.columns:
        mask &= pd.to_datetime(df["session_date"]).dt.date >= start_date
    if end_date is not None and "session_date" in df.columns:
        mask &= pd.to_datetime(df["session_date"]).dt.date <= end_date

    if channels:
        if "channel_grouping" in df.columns:
            mask &= df["channel_grouping"].isin(channels)

    if page_search:
        for col in ("page_url", "url"):
            if col in df.columns:
                mask &= df[col].fillna("").str.contains(page_search, case=False, na=False)
                break

    if devices:
        if "device_category" in df.columns:
            mask &= df["device_category"].isin(devices)

    return df[mask].reset_index(drop=True)


# ── Active filter display ─────────────────────────────────────────────────────

def show_active_filters() -> None:
    """Render an info box summarising every active filter."""
    parts = []

    dr = st.session_state.get(FILTER_KEYS["date_range"])
    if isinstance(dr, (tuple, list)) and len(dr) == 2:
        parts.append(f"Date: {dr[0]} to {dr[1]}")

    channels = list(st.session_state.get(FILTER_KEYS["channels"], []))
    if channels:
        parts.append(f"Channel: {', '.join(channels)}")

    page_search = str(st.session_state.get(FILTER_KEYS["page_search"], "")).strip()
    if page_search:
        parts.append(f"Page: *{page_search}*")

    devices = list(st.session_state.get(FILTER_KEYS["devices"], []))
    if devices:
        parts.append(f"Device: {', '.join(devices)}")

    if parts:
        st.info("**Active filters:** " + " | ".join(parts))


# ── Legacy helpers (backward compatibility) ───────────────────────────────────

def render_filters(include_channel: bool = True, include_page: bool = True) -> dict:
    start_date, end_date = get_date_filter()
    filters: dict = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "start_id": int(start_date.strftime("%Y%m%d")),
        "end_id": int(end_date.strftime("%Y%m%d")),
    }
    if include_channel:
        sel = get_channel_filter()
        filters["channel"] = sel[0] if len(sel) == 1 else None
    if include_page:
        filters["page_filter"] = get_page_filter() or None
    return filters


def date_clause(alias: str = "d") -> str:
    return f"{alias}.date_id BETWEEN :start_id AND :end_id"


def channel_clause(alias: str = "s") -> str:
    return f"(:channel IS NULL OR {alias}.channel_grouping = :channel)"


def page_clause(alias: str = "p") -> str:
    return f"(:page_filter IS NULL OR {alias}.url ILIKE '%' || :page_filter || '%')"
