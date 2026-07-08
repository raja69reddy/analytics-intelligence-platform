"""
Data validation script for the Analytics Intelligence Platform.
Checks all 4 raw tables for expected columns, row counts, date ranges,
null values, and duplicate primary keys. Prints PASS/FAIL for each check
and returns an overall health score (0-100).
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.db import query_df

# ── Expected schemas ──────────────────────────────────────────────────────────

EXPECTED_COLUMNS = {
    "raw_ga4_sessions": [
        "id", "session_date", "channel_grouping", "device_category",
        "landing_page", "sessions", "new_users", "pageviews",
        "bounce", "session_duration_s", "conversions", "revenue", "ingested_at",
    ],
    "raw_server_logs": [
        "id", "log_time", "ip_address", "method", "url",
        "status_code", "response_time_ms", "ingested_at",
    ],
    "raw_clickstream_events": [
        "id", "event_time", "event_name", "page_url",
        "scroll_depth_pct", "device_category", "ingested_at",
    ],
    "raw_scrape_pages": [
        "id", "scraped_at", "url", "title", "word_count",
        "load_time_ms", "http_status", "ingested_at",
    ],
}

MIN_ROW_COUNTS = {
    "raw_ga4_sessions":       100,
    "raw_server_logs":        500,
    "raw_clickstream_events": 500,
    "raw_scrape_pages":        10,
}

NOT_NULL_CHECKS = {
    "raw_ga4_sessions":       ["session_date", "sessions", "channel_grouping"],
    "raw_server_logs":        ["log_time", "url", "status_code"],
    "raw_clickstream_events": ["event_time", "event_name"],
    "raw_scrape_pages":       ["url", "http_status"],
}

DATE_COLUMNS = {
    "raw_ga4_sessions":       "session_date",
    "raw_server_logs":        "log_time",
    "raw_clickstream_events": "event_time",
    "raw_scrape_pages":       "scraped_at",
}


# ── Check runners ─────────────────────────────────────────────────────────────

class CheckResult:
    def __init__(self, name: str, passed: bool, detail: str = ""):
        self.name   = name
        self.passed = passed
        self.detail = detail

    def __repr__(self):
        status = "PASS" if self.passed else "FAIL"
        detail = f" — {self.detail}" if self.detail else ""
        return f"  [{status}] {self.name}{detail}"


def _check_columns(table: str) -> list[CheckResult]:
    results = []
    try:
        df = query_df(f"SELECT * FROM {table} LIMIT 0")
        actual = set(df.columns)
        for col in EXPECTED_COLUMNS[table]:
            if col in actual:
                results.append(CheckResult(f"{table}.{col} exists", True))
            else:
                results.append(CheckResult(f"{table}.{col} exists", False, "column missing"))
    except Exception as exc:
        results.append(CheckResult(f"{table} column check", False, str(exc)))
    return results


def _check_row_count(table: str) -> CheckResult:
    try:
        df = query_df(f"SELECT COUNT(*) n FROM {table}")
        n  = int(df["n"].iloc[0])
        mn = MIN_ROW_COUNTS[table]
        if n >= mn:
            return CheckResult(f"{table} row count >= {mn:,}", True, f"{n:,} rows")
        return CheckResult(f"{table} row count >= {mn:,}", False, f"only {n:,} rows")
    except Exception as exc:
        return CheckResult(f"{table} row count", False, str(exc))


def _check_date_range(table: str) -> list[CheckResult]:
    col = DATE_COLUMNS[table]
    results = []
    try:
        df = query_df(f"SELECT MIN({col})::DATE mn, MAX({col})::DATE mx FROM {table}")
        mn = df["mn"].iloc[0]
        mx = df["mx"].iloc[0]
        if mn is None or mx is None:
            results.append(CheckResult(f"{table} date range not null", False, "min or max is NULL"))
        else:
            results.append(CheckResult(f"{table} date range not null", True, f"{mn} to {mx}"))
            if str(mn) <= str(mx):
                results.append(CheckResult(f"{table} date range valid (min <= max)", True))
            else:
                results.append(CheckResult(f"{table} date range valid (min <= max)", False,
                                           f"min {mn} > max {mx}"))
    except Exception as exc:
        results.append(CheckResult(f"{table} date range", False, str(exc)))
    return results


def _check_nulls(table: str) -> list[CheckResult]:
    results = []
    for col in NOT_NULL_CHECKS.get(table, []):
        try:
            df = query_df(f"SELECT COUNT(*) n FROM {table} WHERE {col} IS NULL")
            nulls = int(df["n"].iloc[0])
            if nulls == 0:
                results.append(CheckResult(f"{table}.{col} no nulls", True))
            else:
                results.append(CheckResult(f"{table}.{col} no nulls", False,
                                           f"{nulls:,} null rows"))
        except Exception as exc:
            results.append(CheckResult(f"{table}.{col} null check", False, str(exc)))
    return results


def _check_pk_duplicates(table: str) -> CheckResult:
    try:
        df = query_df(f"""
            SELECT COUNT(*) - COUNT(DISTINCT id) AS dups FROM {table}
        """)
        dups = int(df["dups"].iloc[0])
        if dups == 0:
            return CheckResult(f"{table} no duplicate PKs", True)
        return CheckResult(f"{table} no duplicate PKs", False, f"{dups:,} duplicates")
    except Exception as exc:
        return CheckResult(f"{table} PK duplicates", False, str(exc))


def _check_views_accessible() -> list[CheckResult]:
    VIEWS = [
        "vw_daily_traffic", "vw_channel_performance", "vw_conversions",
        "vw_top_pages", "vw_scroll_depth", "vw_engagement_events",
    ]
    results = []
    for v in VIEWS:
        try:
            query_df(f"SELECT * FROM {v} LIMIT 1")
            results.append(CheckResult(f"view {v} accessible", True))
        except Exception as exc:
            results.append(CheckResult(f"view {v} accessible", False, str(exc)[:80]))
    return results


def _check_dim_dates() -> CheckResult:
    try:
        df = query_df("SELECT COUNT(*) n FROM dim_dates")
        n = int(df["n"].iloc[0])
        if n == 1096:
            return CheckResult("dim_dates has 1096 rows", True)
        return CheckResult("dim_dates has 1096 rows", False, f"got {n}")
    except Exception as exc:
        return CheckResult("dim_dates row count", False, str(exc))


# ── Main validation runner ────────────────────────────────────────────────────

def run_validation() -> dict:
    all_checks: list[CheckResult] = []
    sections: dict[str, list[CheckResult]] = {}

    for table in EXPECTED_COLUMNS:
        sec = []
        sec.extend(_check_columns(table))
        sec.append(_check_row_count(table))
        sec.extend(_check_date_range(table))
        sec.extend(_check_nulls(table))
        sec.append(_check_pk_duplicates(table))
        sections[table] = sec
        all_checks.extend(sec)

    view_checks = _check_views_accessible()
    sections["sql_views"] = view_checks
    all_checks.extend(view_checks)

    dim_check = _check_dim_dates()
    sections["dim_tables"] = [dim_check]
    all_checks.append(dim_check)

    total  = len(all_checks)
    passed = sum(1 for c in all_checks if c.passed)
    score  = round(passed / total * 100) if total else 0

    return {
        "sections":     sections,
        "all_checks":   all_checks,
        "total_checks": total,
        "passed":       passed,
        "failed":       total - passed,
        "health_score": score,
        "generated_at": datetime.now().isoformat(),
    }


def print_report(result: dict) -> None:
    sep = "=" * 60
    print(sep)
    print("  DATA VALIDATION REPORT")
    print(f"  Generated: {result['generated_at'][:19]}")
    print(sep)

    for section, checks in result["sections"].items():
        print(f"\n[{section.upper()}]")
        for c in checks:
            print(repr(c))

    print()
    print(sep)
    n_pass = result["passed"]
    n_fail = result["failed"]
    score  = result["health_score"]
    print(f"  Total checks:  {result['total_checks']}")
    print(f"  Passed:        {n_pass}")
    print(f"  Failed:        {n_fail}")
    print(f"  Health Score:  {score}/100")
    if score == 100:
        print("  Status:        ALL CHECKS PASSED")
    elif score >= 80:
        print("  Status:        HEALTHY (minor issues)")
    elif score >= 60:
        print("  Status:        DEGRADED (review failures)")
    else:
        print("  Status:        CRITICAL (immediate action needed)")
    print(sep)


if __name__ == "__main__":
    result = run_validation()
    print_report(result)
    sys.exit(0 if result["failed"] == 0 else 1)
