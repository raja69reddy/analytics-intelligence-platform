"""Pure-Python conversion metric helpers — no DB or Streamlit dependencies."""

from __future__ import annotations


def calculate_cvr(sessions: int | float, conversions: int | float) -> float:
    """Return conversion rate as a fraction 0.0–1.0.

    Returns 0.0 when sessions is zero to avoid division by zero.
    """
    if sessions <= 0:
        return 0.0
    return max(0.0, min(1.0, conversions / sessions))


def calculate_revenue_per_session(revenue: float, sessions: int | float) -> float:
    """Return average revenue generated per session.

    Returns 0.0 when sessions is zero.
    """
    if sessions <= 0:
        return 0.0
    return max(0.0, revenue / sessions)


def calculate_goal_value(completions: int | float, avg_value: float) -> float:
    """Return total goal value (completions × avg_value per completion).

    Returns 0.0 for negative inputs.
    """
    if completions < 0 or avg_value < 0:
        return 0.0
    return completions * avg_value


def calculate_roas(revenue: float, ad_spend: float) -> float:
    """Return Return On Ad Spend (revenue / ad_spend).

    Returns 0.0 when ad_spend is zero or negative.
    """
    if ad_spend <= 0:
        return 0.0
    return max(0.0, revenue / ad_spend)


def format_conversion_metrics(metrics: dict) -> dict:
    """Return a display-ready copy of a metrics dict with formatted strings.

    Recognised keys (all optional):
        sessions, conversions, revenue, ad_spend, avg_goal_value
    Adds formatted_* keys for each recognised key found.
    """
    out: dict = dict(metrics)

    sessions = float(metrics.get("sessions", 0) or 0)
    conversions = float(metrics.get("conversions", 0) or 0)
    revenue = float(metrics.get("revenue", 0) or 0)
    ad_spend = float(metrics.get("ad_spend", 0) or 0)
    avg_goal_value = float(metrics.get("avg_goal_value", 0) or 0)

    cvr = calculate_cvr(sessions, conversions)
    rps = calculate_revenue_per_session(revenue, sessions)
    goal_val = calculate_goal_value(conversions, avg_goal_value)
    roas = calculate_roas(revenue, ad_spend)

    out["cvr"] = cvr
    out["revenue_per_session"] = rps
    out["total_goal_value"] = goal_val
    out["roas"] = roas

    out["formatted_cvr"] = f"{cvr * 100:.2f}%"
    out["formatted_revenue_per_session"] = f"${rps:,.2f}"
    out["formatted_total_goal_value"] = f"${goal_val:,.2f}"
    out["formatted_roas"] = f"{roas:.2f}x" if ad_spend > 0 else "N/A"
    out["formatted_sessions"] = f"{int(sessions):,}"
    out["formatted_conversions"] = f"{int(conversions):,}"
    out["formatted_revenue"] = f"${revenue:,.2f}"

    return out
