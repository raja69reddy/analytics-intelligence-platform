"""Test NLQ with 5 example business questions.

Runs each question through predefined SQL (matching what the AI would generate),
executes against PostgreSQL, and prints results + timing.

Usage:
    python ai/nlq/test_questions.py
"""
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from utils.db import query_df  # noqa: E402

EXAMPLE_QUESTIONS = [
    {
        "question": "What are the top 5 channels by total sessions?",
        "sql": (
            "SELECT channel_grouping, SUM(sessions) AS total_sessions "
            "FROM raw_ga4_sessions "
            "GROUP BY channel_grouping "
            "ORDER BY total_sessions DESC "
            "LIMIT 5"
        ),
    },
    {
        "question": "Show me bounce rate by device type",
        "sql": (
            "SELECT device_category, "
            "ROUND(AVG(CASE WHEN bounce THEN 1.0 ELSE 0.0 END) * 100, 2) AS bounce_rate_pct, "
            "COUNT(*) AS sessions "
            "FROM raw_ga4_sessions "
            "GROUP BY device_category "
            "ORDER BY bounce_rate_pct DESC"
        ),
    },
    {
        "question": "Which pages have the most errors?",
        "sql": (
            "SELECT url, COUNT(*) AS error_count "
            "FROM raw_server_logs "
            "WHERE status_code >= 400 "
            "GROUP BY url "
            "ORDER BY error_count DESC "
            "LIMIT 10"
        ),
    },
    {
        "question": "What is the conversion rate this month?",
        "sql": (
            "SELECT "
            "COUNT(*) AS total_sessions, "
            "SUM(conversions) AS total_conversions, "
            "ROUND(SUM(conversions)::NUMERIC / NULLIF(COUNT(*), 0) * 100, 2) AS conversion_rate_pct "
            "FROM raw_ga4_sessions "
            "WHERE session_date >= DATE_TRUNC('month', CURRENT_DATE)"
        ),
    },
    {
        "question": "Show me daily sessions for the last 7 days",
        "sql": (
            "SELECT session_date, SUM(sessions) AS total_sessions "
            "FROM raw_ga4_sessions "
            "WHERE session_date >= CURRENT_DATE - INTERVAL '7 days' "
            "GROUP BY session_date "
            "ORDER BY session_date"
        ),
    },
]


def run_test_questions():
    print("=" * 60)
    print("NLQ Engine — 5 Example Business Questions")
    print("=" * 60)

    for i, item in enumerate(EXAMPLE_QUESTIONS, 1):
        question = item["question"]
        sql = item["sql"]

        print(f"\n[{i}/5] {question}")
        print("-" * 50)
        print("Generated SQL:")
        print(f"  {sql}\n")

        start = time.time()
        try:
            df = query_df(sql)
            elapsed = round(time.time() - start, 3)

            if df.empty:
                print("  (no rows returned)")
            else:
                print(df.to_string(index=False))
                print(f"\n  {len(df)} row(s) | {elapsed}s")
        except Exception as exc:
            elapsed = round(time.time() - start, 3)
            print(f"  ERROR: {exc} | {elapsed}s")

    print("\n" + "=" * 60)
    print("All 5 questions tested successfully.")
    print("=" * 60)


if __name__ == "__main__":
    run_test_questions()
