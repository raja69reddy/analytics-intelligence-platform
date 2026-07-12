"""
Unit tests for the GA4 ingestion pipeline (ingestion/ga4.py).
"""

import sys
from pathlib import Path

import pandas as pd

# Make project root importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CSV_PATH = ROOT / "data" / "raw" / "ga4_sessions.csv"
EXPECTED_COLUMNS = {
    "session_date",
    "source",
    "medium",
    "channel",
    "sessions",
    "users",
    "new_users",
    "pageviews",
    "bounce_rate",
    "avg_session_duration",
}


class TestCsvFile:
    def test_csv_exists(self):
        assert CSV_PATH.exists(), f"CSV not found: {CSV_PATH}"

    def test_csv_has_correct_columns(self):
        df = pd.read_csv(CSV_PATH, nrows=1)
        missing = EXPECTED_COLUMNS - set(df.columns)
        assert not missing, f"Missing columns in CSV: {missing}"

    def test_csv_has_rows(self):
        df = pd.read_csv(CSV_PATH)
        assert len(df) > 0, "CSV is empty"


class TestIngestionScript:
    def test_load_csv_runs_without_error(self):
        from ingestion.ga4 import load_csv

        df = load_csv()
        assert df is not None
        assert len(df) > 0

    def test_load_csv_converts_session_date(self):
        import datetime
        from ingestion.ga4 import load_csv

        df = load_csv()
        assert all(
            isinstance(d, datetime.date) for d in df["session_date"]
        ), "session_date column should contain datetime.date objects"

    def test_load_csv_no_nulls_in_numeric_cols(self):
        from ingestion.ga4 import load_csv

        df = load_csv()
        num_cols = df.select_dtypes(include="number").columns
        for col in num_cols:
            assert df[col].isna().sum() == 0, f"Nulls found in numeric column: {col}"

    def test_load_csv_columns_mapped(self):
        from ingestion.ga4 import load_csv

        df = load_csv()
        assert (
            "channel_grouping" in df.columns
        ), "channel should be renamed to channel_grouping"
        assert (
            "session_duration_s" in df.columns
        ), "avg_session_duration should be renamed to session_duration_s"
        assert "bounce" in df.columns, "bounce column should be derived"

    def test_full_mode_row_count_matches_csv(self):
        from ingestion.ga4 import ingest
        from utils.db import query_df

        ingest("full")
        csv_count = len(pd.read_csv(CSV_PATH))
        db_df = query_df("SELECT COUNT(*) AS n FROM raw_ga4_sessions")
        db_count = int(db_df["n"].iloc[0])
        assert (
            db_count == csv_count
        ), f"DB row count ({db_count}) does not match CSV row count ({csv_count})"
