"""High-level metric accessors for the analytics dashboard.

Each function queries the web_analytics database and returns a scalar value.
All functions are cached with functools.lru_cache so repeated calls within
the same process (e.g. multiple page renders) hit the DB only once per
unique (start, end) argument pair.
"""

from __future__ import annotations

from functools import lru_cache

from utils.db import query_df


@lru_cache(maxsize=256)
def get_total_sessions(start: str | None = None, end: str | None = None) -> int:
    """Return total session count in [start, end] (inclusive, YYYY-MM-DD strings)."""
    _where, _p = _date_where("session_date", start, end)
    df = query_df(f"SELECT COALESCE(SUM(sessions), 0) AS v FROM raw_ga4_sessions {_where}", _p)
    return int(df["v"].iloc[0])


@lru_cache(maxsize=256)
def get_total_users(start: str | None = None, end: str | None = None) -> int:
    """Return total unique users in [start, end]."""
    _where, _p = _date_where("session_date", start, end)
    df = query_df(f"SELECT COALESCE(SUM(users), 0) AS v FROM raw_ga4_sessions {_where}", _p)
    return int(df["v"].iloc[0])


@lru_cache(maxsize=256)
def get_overall_cvr(start: str | None = None, end: str | None = None) -> float:
    """Return overall conversion rate (%) in [start, end]. Returns 0.0 if no data."""
    _where, _p = _date_where("session_date", start, end)
    df = query_df(
        f"""
        SELECT
            CASE WHEN SUM(sessions) = 0 THEN 0.0
                 ELSE ROUND(SUM(conversions)::numeric / SUM(sessions) * 100, 2)
            END AS v
        FROM raw_ga4_sessions
        {_where}
        """,
        _p,
    )
    return float(df["v"].iloc[0])


@lru_cache(maxsize=256)
def get_avg_bounce_rate(start: str | None = None, end: str | None = None) -> float:
    """Return average bounce rate (%) across all sessions in [start, end]."""
    _where, _p = _date_where("session_date", start, end)
    df = query_df(
        f"""
        SELECT COALESCE(
            ROUND(AVG(bounce_rate) * 100, 2), 0.0
        ) AS v
        FROM raw_ga4_sessions
        {_where}
        """,
        _p,
    )
    return float(df["v"].iloc[0])


@lru_cache(maxsize=256)
def get_top_channel(start: str | None = None, end: str | None = None) -> str:
    """Return the channel with the most sessions in [start, end]."""
    _where, _p = _date_where("session_date", start, end)
    df = query_df(
        f"""
        SELECT channel, SUM(sessions) AS total
        FROM raw_ga4_sessions
        {_where}
        GROUP BY channel
        ORDER BY total DESC
        LIMIT 1
        """,
        _p,
    )
    if df.empty:
        return "N/A"
    return str(df["channel"].iloc[0])


@lru_cache(maxsize=256)
def get_top_page(start: str | None = None, end: str | None = None) -> str:
    """Return the URL with the most requests in [start, end]."""
    _p: dict = {}
    _conds: list[str] = []
    if start:
        _conds.append("DATE(log_time) >= :s")
        _p["s"] = start
    if end:
        _conds.append("DATE(log_time) <= :e")
        _p["e"] = end
    _where = ("WHERE " + " AND ".join(_conds)) if _conds else ""
    df = query_df(
        f"""
        SELECT url, COUNT(*) AS total
        FROM raw_server_logs
        {_where}
        GROUP BY url
        ORDER BY total DESC
        LIMIT 1
        """,
        _p,
    )
    if df.empty:
        return "N/A"
    return str(df["url"].iloc[0])


# ── internal helper ────────────────────────────────────────────────────────────

def _date_where(col: str, start: str | None, end: str | None) -> tuple[str, dict]:
    """Build a WHERE clause and params dict for a date-range filter on col."""
    conds: list[str] = []
    params: dict = {}
    if start:
        conds.append(f"{col} >= :s")
        params["s"] = start
    if end:
        conds.append(f"{col} <= :e")
        params["e"] = end
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    return where, params
