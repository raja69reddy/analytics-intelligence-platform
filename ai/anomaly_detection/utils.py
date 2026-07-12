"""Utility functions for anomaly detection data loading and feature engineering."""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# ── Feature column definitions by metric type ─────────────────────────────────
_TRAFFIC_FEATURES = [
    "total_sessions",
    "total_pageviews",
    "avg_bounce_rate",
    "avg_session_duration",
]
_CONVERSION_FEATURES = ["conversion_rate", "goal_completions", "revenue"]
_BOUNCE_FEATURES = ["avg_bounce_rate", "total_sessions"]


def load_traffic_data() -> pd.DataFrame:
    """Load daily traffic data from the vw_daily_traffic view.

    Falls back to an empty DataFrame with the expected schema if the DB
    is unreachable, so callers can always rely on the column contract.
    """
    try:
        from utils.query_runner import run_view

        df = run_view("vw_daily_traffic")
        logger.info("Loaded %d rows from vw_daily_traffic.", len(df))
        return df
    except Exception as exc:
        logger.warning("Could not load traffic data from DB: %s", exc)
        return pd.DataFrame(
            columns=[
                "session_date",
                "total_sessions",
                "total_pageviews",
                "avg_bounce_rate",
                "avg_session_duration",
                "sessions_7day_avg",
            ]
        )


def load_conversion_data() -> pd.DataFrame:
    """Load conversion data from the vw_conversions view.

    Falls back to an empty DataFrame with the expected schema on DB failure.
    """
    try:
        from utils.query_runner import run_view

        df = run_view("vw_conversions")
        logger.info("Loaded %d rows from vw_conversions.", len(df))
        return df
    except Exception as exc:
        logger.warning("Could not load conversion data from DB: %s", exc)
        return pd.DataFrame(
            columns=["session_date", "conversion_rate", "goal_completions", "revenue"]
        )


def prepare_features(df: pd.DataFrame, metric_type: str = "traffic") -> list[str]:
    """Return the feature column names available in df for the given metric type.

    Only columns that are both defined for the metric type AND present in df
    are returned, so the caller can safely index df with the result.
    """
    candidates: list[str] = {
        "traffic": _TRAFFIC_FEATURES,
        "conversion": _CONVERSION_FEATURES,
        "bounce": _BOUNCE_FEATURES,
    }.get(metric_type, _TRAFFIC_FEATURES)

    available = [c for c in candidates if c in df.columns]
    if not available:
        logger.warning(
            "No recognised feature columns found in df for metric_type='%s'. "
            "Available columns: %s",
            metric_type,
            list(df.columns),
        )
    return available


def score_anomaly(score: float) -> str:
    """Convert an IsolationForest anomaly score to a human-readable severity.

    IsolationForest.decision_function() returns values roughly in [-0.5, 0.5].
    We negate them in detector.py so that higher values mean more anomalous.

    Thresholds (tuned empirically on web analytics data):
      ≥ 0.15  →  high
      ≥ 0.05  →  medium
      < 0.05  →  low
    """
    if score >= 0.15:
        return "high"
    if score >= 0.05:
        return "medium"
    return "low"
