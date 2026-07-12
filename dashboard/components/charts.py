"""
Reusable Plotly chart components for the Analytics Intelligence Platform.
Each function returns a Plotly figure that can be passed to st.plotly_chart().
Pass template=get_plotly_template() from filters.py to apply dark/light theming.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def line_chart(
    df: pd.DataFrame,
    x: str,
    y: str | list[str],
    title: str = "",
    labels: dict | None = None,
    color: str | None = None,
    template: str = "plotly_white",
) -> go.Figure:
    """Plotly line chart. y can be a single column name or a list for multi-line."""
    return px.line(
        df,
        x=x,
        y=y,
        title=title,
        labels=labels or {},
        color=color,
        template=template,
    )


def bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str = "",
    orientation: str = "v",
    labels: dict | None = None,
    color: str | None = None,
    template: str = "plotly_white",
) -> go.Figure:
    """Plotly bar chart. orientation='h' for horizontal."""
    return px.bar(
        df,
        x=x,
        y=y,
        title=title,
        orientation=orientation,
        labels=labels or {},
        color=color,
        template=template,
    )


def pie_chart(
    df: pd.DataFrame,
    names: str,
    values: str,
    title: str = "",
    hole: float = 0.35,
    template: str = "plotly_white",
) -> go.Figure:
    """Plotly donut/pie chart. hole=0 for pie, hole>0 for donut."""
    return px.pie(
        df,
        names=names,
        values=values,
        title=title,
        hole=hole,
        template=template,
    )


def funnel_chart(
    stages: list[str],
    values: list[int | float],
    title: str = "",
    template: str = "plotly_white",
) -> go.Figure:
    """Plotly funnel chart."""
    fig = go.Figure(
        go.Funnel(
            y=stages,
            x=values,
            textinfo="value+percent initial",
        )
    )
    fig.update_layout(title=title, template=template)
    return fig


def scatter_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str = "",
    color: str | None = None,
    size: str | None = None,
    hover_name: str | None = None,
    labels: dict | None = None,
    template: str = "plotly_white",
) -> go.Figure:
    """Plotly scatter chart with optional color, size, and hover label."""
    return px.scatter(
        df,
        x=x,
        y=y,
        title=title,
        color=color,
        size=size,
        hover_name=hover_name,
        labels=labels or {},
        template=template,
    )
