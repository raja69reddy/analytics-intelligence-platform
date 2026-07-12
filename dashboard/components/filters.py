"""
Sidebar filter components for the Web Analytics Dashboard.
Each function renders its own widget and returns the selected value(s).
apply_filters() applies all active filters to a pandas DataFrame.
"""

from datetime import date, timedelta

import pandas as pd
import streamlit as st


def get_date_filter() -> tuple[date, date]:
    """Render a date range picker. Returns (start_date, end_date)."""
    today = date.today()
    default_start = today - timedelta(days=29)
    date_range = st.sidebar.date_input(
        "Date range",
        value=(default_start, today),
        min_value=date(2020, 1, 1),
        max_value=today,
    )
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        return date_range[0], date_range[1]
    return date_range, date_range


def get_channel_filter() -> list[str]:
    """Render a multiselect for traffic channels. Returns list of selected channels (empty = all)."""
    return st.sidebar.multiselect(
        "Channel",
        options=[
            "Direct",
            "Email",
            "Organic Search",
            "Paid Search",
            "Referral",
            "Social",
        ],
        default=[],
        placeholder="All channels",
    )


def get_page_filter() -> str:
    """Render a text input for page URL search. Returns the search string (empty = no filter)."""
    return st.sidebar.text_input(
        "Page URL contains",
        value="",
        placeholder="/blog/",
    ).strip()


def get_device_filter() -> list[str]:
    """Render a multiselect for device types. Returns list of selected devices (empty = all)."""
    return st.sidebar.multiselect(
        "Device",
        options=["desktop", "mobile", "tablet"],
        default=[],
        placeholder="All devices",
    )


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
                mask &= (
                    df[col].fillna("").str.contains(page_search, case=False, na=False)
                )
                break

    if devices:
        if "device_category" in df.columns:
            mask &= df["device_category"].isin(devices)

    return df[mask].reset_index(drop=True)


# Legacy helpers kept for backward compatibility with existing page files
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
