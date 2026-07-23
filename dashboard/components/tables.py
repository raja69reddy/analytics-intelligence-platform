"""Reusable table formatting and styling utilities for the analytics dashboard."""

from __future__ import annotations

import pandas as pd


def display_styled_table(df: pd.DataFrame, **kwargs) -> None:
    """Render df with automatic numeric formatting via Streamlit."""
    import streamlit as st
    st.dataframe(
        format_table_numbers(df),
        use_container_width=True,
        hide_index=True,
        **kwargs,
    )


def highlight_slow_pages(
    df: pd.DataFrame,
    col: str = "avg_response_time_ms",
    threshold: float = 1000,
) -> pd.Styler:
    """Row colors: red when col > threshold, green when col < threshold * 0.2."""
    def _style(row):
        v = row.get(col, 0) or 0
        if v > threshold:
            return ["background-color: #ffd6d6"] * len(row)
        if v < threshold * 0.2:
            return ["background-color: #d4edda"] * len(row)
        return [""] * len(row)

    return df.style.apply(_style, axis=1)


def highlight_top_performers(
    df: pd.DataFrame,
    col: str,
    top_n: int = 3,
) -> pd.Styler:
    """Green background for the top_n rows ranked by col (descending)."""
    if df.empty or col not in df.columns:
        return df.style
    threshold = df[col].nlargest(top_n).min()

    def _style(row):
        return (
            ["background-color: #d4edda"] * len(row)
            if row[col] >= threshold
            else [""] * len(row)
        )

    return df.style.apply(_style, axis=1)


def add_rank_column(
    df: pd.DataFrame,
    col: str | None = None,
    ascending: bool = False,
) -> pd.DataFrame:
    """Prepend a '#' rank column.  Optionally re-sort by col first."""
    df = df.copy()
    if col and col in df.columns:
        df = df.sort_values(col, ascending=ascending).reset_index(drop=True)
    df.insert(0, "#", range(1, len(df) + 1))
    return df


def format_table_numbers(df: pd.DataFrame) -> pd.Styler:
    """Auto-format int columns with comma thousands, float columns to 2 dp."""
    fmt: dict[str, str] = {}
    for c in df.columns:
        if pd.api.types.is_integer_dtype(df[c]):
            fmt[c] = "{:,}"
        elif pd.api.types.is_float_dtype(df[c]):
            fmt[c] = "{:,.2f}"
    return df.style.format(fmt)
