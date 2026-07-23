"""
Reusable Plotly chart components for the Analytics Intelligence Platform.
Each function returns a Plotly figure that can be passed to st.plotly_chart().
Pass template=get_plotly_template() from filters.py to apply dark/light theming.
"""

from __future__ import annotations

import os

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


def add_chart_theme(fig: go.Figure, *, title: str | None = None) -> go.Figure:
    """Apply consistent layout theme: margins, font, gridlines, legend."""
    fig.update_layout(
        margin=dict(l=40, r=20, t=50, b=40),
        font=dict(family="Inter, sans-serif", size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor="rgba(128,128,128,0.15)"),
    )
    if title:
        fig.update_layout(title=dict(text=title, font=dict(size=16)))
    return fig


def add_hover_template(
    fig: go.Figure,
    x_fmt: str = "%{x}",
    y_fmt: str = "%{y:,.0f}",
    name_fmt: str = "%{fullData.name}",
) -> go.Figure:
    """Apply a unified hover template to all traces in fig."""
    hover = f"<b>{name_fmt}</b><br>{x_fmt}<br>Value: {y_fmt}<extra></extra>"
    fig.update_traces(hovertemplate=hover)
    fig.update_layout(hovermode="x unified")
    return fig


def add_range_selector(fig: go.Figure) -> go.Figure:
    """Add 7D / 30D / 90D / All range-selector buttons to the x-axis."""
    fig.update_xaxes(
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
    return fig


def add_reference_line(
    fig: go.Figure,
    value: float,
    label: str = "",
    color: str = "red",
    dash: str = "dash",
) -> go.Figure:
    """Add a horizontal dashed reference line at value with an annotation."""
    fig.add_hline(
        y=value,
        line_dash=dash,
        line_color=color,
        annotation_text=label,
        annotation_position="top right",
    )
    return fig


def save_chart_as_png(fig: go.Figure, filename: str) -> str:
    """Save fig as PNG to the processed/ directory. Returns the saved path."""
    out_dir = os.path.join(os.getcwd(), "processed")
    os.makedirs(out_dir, exist_ok=True)
    if not filename.endswith(".png"):
        filename += ".png"
    path = os.path.join(out_dir, filename)
    fig.write_image(path)
    return path


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
