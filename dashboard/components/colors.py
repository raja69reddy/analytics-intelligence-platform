"""Shared color palette and theme helpers for all dashboard pages."""

from __future__ import annotations

import plotly.graph_objects as go

# Primary sequential palette — used for channel / source breakdowns
CHANNEL_PALETTE: list[str] = [
    "#636EFA",  # blue
    "#EF553B",  # red-orange
    "#00CC96",  # teal
    "#AB63FA",  # purple
    "#FFA15A",  # orange
    "#19D3F3",  # cyan
    "#FF6692",  # pink
    "#B6E880",  # lime
]

# Semantic colors
COLOR_GOOD = "#2ca02c"       # green — improvement / high quality
COLOR_BAD = "#d62728"        # red   — degradation / drop-off
COLOR_WARN = "#ff7f0e"       # orange — medium / borderline
COLOR_NEUTRAL = "#636EFA"    # blue  — default / neutral
COLOR_ACCENT = "#ffd700"     # gold  — reference lines / average markers

# Gradient color-scales
CMAP_QUALITY = "RdYlGn"      # low→high quality (red/yellow/green)
CMAP_HEATMAP = "YlOrRd"      # heatmap (yellow/orange/red)
CMAP_SPEED = "RdYlGn_r"     # response time (green = fast, red = slow)

# Standard font applied to every chart
CHART_FONT = dict(family="Inter, Arial, sans-serif", size=13)


def channel_color(index: int) -> str:
    """Return a color from CHANNEL_PALETTE cycling by index."""
    return CHANNEL_PALETTE[index % len(CHANNEL_PALETTE)]


def apply_theme(fig: go.Figure, *, template: str | None = None) -> go.Figure:
    """Apply consistent font and optional template to a Plotly figure in-place.

    Returns the same figure for chaining.
    """
    kwargs: dict = {"font": CHART_FONT}
    if template:
        kwargs["template"] = template
    fig.update_layout(**kwargs)
    return fig
