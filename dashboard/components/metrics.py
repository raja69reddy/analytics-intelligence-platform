"""
KPI card and formatting helpers for the Analytics Intelligence Platform.
"""

from typing import Literal

import streamlit as st


# ── Number formatters ─────────────────────────────────────────────────────────

def format_number(n: int | float) -> str:
    """Format large numbers: 1234567 → '1.2M', 12345 → '12.3K', 999 → '999'."""
    n = float(n or 0)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{int(n):,}"


def format_large_number(n: int | float) -> str:
    """Format large numbers with K/M suffix: 1234567 → '1.2M', 12345 → '12.3K'."""
    n = float(n or 0)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{int(n):,}"


def format_currency(n: float | None) -> str:
    """Format a value as currency: 1234.5 → '$1,235', None → '$0'."""
    if n is None:
        return "$0"
    return f"${float(n):,.0f}"


def format_percentage(p: float | None) -> str:
    """Format a percentage value: 0.234 → '23.4%', 23.4 → '23.4%'."""
    if p is None:
        return "--"
    p = float(p)
    if 0.0 <= p <= 1.0:
        p = p * 100
    return f"{p:.1f}%"


def format_duration(seconds: int | float | None) -> str:
    """Format seconds into a human-readable duration: 125 → '2m 5s', 45 → '45s'."""
    if seconds is None:
        return "--"
    seconds = int(seconds or 0)
    if seconds >= 3600:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h {m}m"
    if seconds >= 60:
        m = seconds // 60
        s = seconds % 60
        return f"{m}m {s}s"
    return f"{seconds}s"


# ── Delta helpers ─────────────────────────────────────────────────────────────

def calculate_period_change(current: float, previous: float) -> str:
    """Calculate % change between two periods. Returns a signed string like '+12.5%'."""
    if previous == 0:
        return "+100%" if current > 0 else "0%"
    change = (current - previous) / abs(previous) * 100
    return f"{change:+.1f}%"


def display_trend_indicator(value: float, threshold: float) -> str:
    """Return an ASCII trend indicator vs a threshold: UP, DOWN, or FLAT."""
    if value > threshold:
        return "UP"
    if value < threshold:
        return "DOWN"
    return "FLAT"


# ── KPI card renderers ────────────────────────────────────────────────────────

def display_kpi_card(
    title: str,
    value: str | int | float,
    delta: str | int | float | None = None,
    delta_color: Literal["normal", "inverse", "off"] = "normal",
    col=None,
) -> None:
    """
    Render a single KPI metric card using st.metric.
    Pass col=st.columns(...)[i] to place inside a column.
    """
    target = col if col is not None else st
    target.metric(
        label=title,
        value=str(value),
        delta=str(delta) if delta is not None else None,
        delta_color=delta_color,
    )


def display_metric_card(
    title: str,
    value: str | int | float,
    delta: str | int | float | None = None,
    icon: str = "",
    color: Literal["normal", "inverse", "off"] = "normal",
    col=None,
) -> None:
    """
    Render a KPI metric card with an optional icon prefix and delta color.
    Pass col=st.columns(...)[i] to place inside a specific column.
    """
    label = f"{icon} {title}".strip() if icon else title
    target = col if col is not None else st
    target.metric(
        label=label,
        value=str(value),
        delta=str(delta) if delta is not None else None,
        delta_color=color,
    )


def display_kpi_row(metrics: list[dict]) -> None:
    """
    Render a row of KPI cards from a list of dicts.
    Each dict: {"title": str, "value": any, "delta": any (opt), "delta_color": str (opt)}
    """
    cols = st.columns(len(metrics))
    for col, m in zip(cols, metrics):
        display_kpi_card(
            title=m["title"],
            value=m["value"],
            delta=m.get("delta"),
            delta_color=m.get("delta_color", "normal"),
            col=col,
        )


def display_4_kpi_row(
    m1: dict,
    m2: dict,
    m3: dict,
    m4: dict,
) -> None:
    """
    Render exactly 4 KPI metric cards in a single row using display_metric_card.
    Each dict: {"title": str, "value": any, "delta": any (opt), "icon": str (opt), "color": str (opt)}
    """
    c1, c2, c3, c4 = st.columns(4)
    for col, m in zip([c1, c2, c3, c4], [m1, m2, m3, m4]):
        display_metric_card(
            title=m["title"],
            value=m["value"],
            delta=m.get("delta"),
            icon=m.get("icon", ""),
            color=m.get("color", "normal"),
            col=col,
        )
