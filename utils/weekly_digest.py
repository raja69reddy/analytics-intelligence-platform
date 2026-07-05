"""
Weekly performance digest generator.
Queries the database, builds a markdown report, and saves it to
data/processed/digests/weekly_YYYY-MM-DD.md.
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Ensure project root is on sys.path when run as a script
_ROOT_PATH = str(Path(__file__).resolve().parent.parent)
if _ROOT_PATH not in sys.path:
    sys.path.insert(0, _ROOT_PATH)

logger = logging.getLogger(__name__)

ROOT    = Path(__file__).resolve().parent.parent
DIGESTS = ROOT / "data" / "processed" / "digests"
DIGESTS.mkdir(parents=True, exist_ok=True)


def _qdf(sql: str):
    from utils.db import query_df
    return query_df(sql)


def _safe(df, col, default="N/A"):
    try:
        v = df[col].iloc[0]
        return v if v is not None else default
    except Exception:
        return default


# ── Section builders ──────────────────────────────────────────────────────────

def _traffic_section(today: datetime) -> str:
    week_start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    week_end   = today.strftime("%Y-%m-%d")
    try:
        df = _qdf(f"""
            SELECT
                SUM(sessions)   AS total_sessions,
                SUM(new_users)  AS new_users,
                ROUND(SUM(bounce::INT)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2) AS bounce_rate_pct,
                ROUND(AVG(session_duration_s), 1) AS avg_duration_s
            FROM raw_ga4_sessions
            WHERE session_date BETWEEN '{week_start}' AND '{week_end}'
        """)
        sessions   = _safe(df, "total_sessions", 0)
        new_users  = _safe(df, "new_users", 0)
        bounce     = _safe(df, "bounce_rate_pct", 0)
        duration   = _safe(df, "avg_duration_s", 0)
    except Exception as exc:
        return f"## Traffic\n\n_Error loading traffic data: {exc}_\n"

    try:
        prev_start = (today - timedelta(days=14)).strftime("%Y-%m-%d")
        prev_end   = (today - timedelta(days=8)).strftime("%Y-%m-%d")
        prev_df = _qdf(f"""
            SELECT SUM(sessions) AS prev_sessions FROM raw_ga4_sessions
            WHERE session_date BETWEEN '{prev_start}' AND '{prev_end}'
        """)
        prev_sessions = _safe(prev_df, "prev_sessions", 0) or 0
        wow_pct = round((float(sessions or 0) - float(prev_sessions)) / float(prev_sessions) * 100, 1) if prev_sessions else 0
        wow_str = f"+{wow_pct}%" if wow_pct >= 0 else f"{wow_pct}%"
    except Exception:
        wow_str = "N/A"

    return f"""## Traffic Summary

| Metric | Value |
|--------|-------|
| Total Sessions | {int(sessions or 0):,} |
| New Users | {int(new_users or 0):,} |
| Bounce Rate | {bounce}% |
| Avg Session Duration | {duration}s |
| Week-over-Week Change | {wow_str} |
"""


def _channel_section(today: datetime) -> str:
    week_start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    week_end   = today.strftime("%Y-%m-%d")
    try:
        df = _qdf(f"""
            SELECT channel_grouping,
                   SUM(sessions) AS sessions,
                   ROUND(SUM(bounce::INT)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 1) AS bounce_pct,
                   ROUND(AVG(session_duration_s), 0) AS avg_s
            FROM raw_ga4_sessions
            WHERE session_date BETWEEN '{week_start}' AND '{week_end}'
            GROUP BY channel_grouping
            ORDER BY sessions DESC
            LIMIT 6
        """)
    except Exception as exc:
        return f"## Channel Breakdown\n\n_Error: {exc}_\n"

    rows = "| Channel | Sessions | Bounce % | Avg Duration |\n|---------|----------|----------|--------------|\n"
    for _, row in df.iterrows():
        rows += f"| {row.get('channel_grouping','?')} | {int(row.get('sessions',0) or 0):,} | {row.get('bounce_pct',0)}% | {int(row.get('avg_s',0) or 0)}s |\n"
    return f"## Channel Breakdown\n\n{rows}"


def _top_pages_section(today: datetime) -> str:
    week_start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    week_end   = today.strftime("%Y-%m-%d")
    try:
        df = _qdf(f"""
            SELECT landing_page,
                   SUM(sessions) AS sessions,
                   ROUND(AVG(session_duration_s), 0) AS avg_s
            FROM raw_ga4_sessions
            WHERE session_date BETWEEN '{week_start}' AND '{week_end}'
            GROUP BY landing_page
            ORDER BY sessions DESC
            LIMIT 5
        """)
    except Exception as exc:
        return f"## Top Pages\n\n_Error: {exc}_\n"

    rows = "| Page | Sessions | Avg Duration |\n|------|----------|--------------|\n"
    for _, row in df.iterrows():
        page = str(row.get("landing_page", "?"))
        page = page if len(page) <= 50 else page[:47] + "..."
        rows += f"| {page} | {int(row.get('sessions', 0) or 0):,} | {int(row.get('avg_s', 0) or 0)}s |\n"
    return f"## Top Pages\n\n{rows}"


def _device_section(today: datetime) -> str:
    week_start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    week_end   = today.strftime("%Y-%m-%d")
    try:
        df = _qdf(f"""
            SELECT device_category,
                   SUM(sessions) AS sessions,
                   ROUND(SUM(sessions)::NUMERIC / NULLIF(SUM(SUM(sessions)) OVER (), 0) * 100, 1) AS share_pct
            FROM raw_ga4_sessions
            WHERE session_date BETWEEN '{week_start}' AND '{week_end}'
            GROUP BY device_category
            ORDER BY sessions DESC
        """)
    except Exception as exc:
        return f"## Device Breakdown\n\n_Error: {exc}_\n"

    rows = "| Device | Sessions | Share |\n|--------|----------|-------|\n"
    for _, row in df.iterrows():
        rows += f"| {row.get('device_category','?')} | {int(row.get('sessions',0) or 0):,} | {row.get('share_pct',0)}% |\n"
    return f"## Device Breakdown\n\n{rows}"


def _alerts_section() -> str:
    try:
        from utils.alerts import generate_alert_summary
        s = generate_alert_summary()
        status = "All Clear" if s["all_clear"] else f"{s['active_alerts']} alert(s) firing"
        lines = [f"## Alert Status\n\n**Status:** {status}  "]
        for a in s.get("alerts", []):
            icon = "🔴" if a.get("severity") == "critical" else "🟡"
            lines.append(f"- {icon} [{a.get('severity','?').upper()}] {a.get('message','')}")
        if not s.get("alerts"):
            lines.append("- No active alerts")
        return "\n".join(lines) + "\n"
    except Exception as exc:
        return f"## Alert Status\n\n_Error: {exc}_\n"


# ── Main digest function ──────────────────────────────────────────────────────

def generate_weekly_digest(reference_date: datetime | None = None) -> Path:
    """Build and save the weekly digest markdown file. Returns the path."""
    today = reference_date or datetime.now()
    week_start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    week_end   = today.strftime("%Y-%m-%d")
    generated  = today.strftime("%Y-%m-%d %H:%M")

    header = f"""# Weekly Analytics Digest

**Period:** {week_start} to {week_end}
**Generated:** {generated}

---

"""

    sections = [
        header,
        _traffic_section(today),
        "\n---\n\n",
        _channel_section(today),
        "\n---\n\n",
        _top_pages_section(today),
        "\n---\n\n",
        _device_section(today),
        "\n---\n\n",
        _alerts_section(),
        "\n---\n\n",
        f"_Generated by Analytics Intelligence Platform — {generated}_\n",
    ]

    content = "".join(sections)
    filename = DIGESTS / f"weekly_{today.strftime('%Y-%m-%d')}.md"
    filename.write_text(content, encoding="utf-8")
    logger.info(f"Weekly digest saved to {filename}")
    return filename


if __name__ == "__main__":
    path = generate_weekly_digest()
    print(f"Digest saved: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    print("\n--- First 20 lines ---")
    for line in lines[:20]:
        print(line)
