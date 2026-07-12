"""SQL safety validation for NLQ queries."""

import re

DANGEROUS_KEYWORDS = {
    "DROP",
    "DELETE",
    "UPDATE",
    "INSERT",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "REPLACE",
    "EXEC",
    "EXECUTE",
    "GRANT",
    "REVOKE",
    "COMMIT",
    "ROLLBACK",
    "MERGE",
    "CALL",
    "COPY",
}

VALID_TABLES = {
    "raw_ga4_sessions",
    "raw_server_logs",
    "raw_scrape_pages",
    "raw_clickstream_events",
    "dim_pages",
    "dim_dates",
    "fct_sessions",
    "fct_events",
    "vw_traffic",
    "vw_daily_traffic",
    "vw_channel_performance",
    "vw_new_vs_returning",
    "vw_device_breakdown",
    "vw_geo_performance",
    "vw_top_pages",
    "vw_page_performance",
    "vw_error_pages",
    "vw_traffic_by_hour",
    "vw_user_agents",
    "vw_scroll_depth",
    "vw_engagement_events",
    "vw_behavior",
    "vw_conversions",
    "vw_seo",
    "vw_funnel",
}


def is_safe_query(sql: str) -> bool:
    """Check the query is SELECT-only and contains no dangerous keywords."""
    stripped = sql.strip().upper()
    if not stripped.startswith("SELECT"):
        return False
    if has_dangerous_keywords(sql):
        return False
    return True


def has_dangerous_keywords(sql: str) -> bool:
    """Return True if the SQL contains DROP, DELETE, UPDATE, or similar keywords."""
    tokens = set(re.findall(r"\b\w+\b", sql.upper()))
    return bool(tokens & DANGEROUS_KEYWORDS)


def sanitize_input(question: str) -> str:
    """Remove potential injection characters and truncate to safe length."""
    # Strip SQL comment sequences and semicolons
    question = re.sub(r"(--|;|/\*|\*/)", "", question)
    # Collapse whitespace
    question = " ".join(question.split())
    # Hard limit to prevent prompt injection via very long inputs
    return question[:500]


def validate_table_names(sql: str) -> bool:
    """Return True only if every table referenced after FROM/JOIN is in the allowed set."""
    tables_found = re.findall(r"(?:FROM|JOIN)\s+(\w+)", sql.upper())
    for table in tables_found:
        if table.lower() not in VALID_TABLES:
            return False
    return True
