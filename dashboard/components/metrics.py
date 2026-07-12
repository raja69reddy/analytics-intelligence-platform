"""
KPI card and formatting helpers for the Web Analytics Dashboard.
"""

from typing import Literal

import streamlit as st


def format_number(n: int | float) -> str:
    """Format large numbers: 1234567 → '1.2M', 12345 → '12.3K', 999 → '999'."""
    n = float(n or 0)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{int(n):,}"


def format_percentage(p: float | None) -> str:
    """Format a percentage value: 0.234 → '23.4%', 23.4 → '23.4%'."""
    if p is None:
        return "—"
    p = float(p)
    if p <= 1.0 and p >= 0.0:
        p = p * 100
    return f"{p:.1f}%"


def format_duration(seconds: int | float | None) -> str:
    """Format seconds into a human-readable duration: 125 → '2m 5s', 45 → '45s'."""
    if seconds is None:
        return "—"
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
