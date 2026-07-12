"""
Unit tests for the clickstream ingestion pipeline (ingestion/clickstream.py).
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CSV_PATH = ROOT / "data" / "raw" / "clickstream_events.csv"
EXPECTED_COLUMNS = {
    "event_timestamp",
    "session_id",
    "user_id",
    "event_type",
    "page_url",
}
VALID_EVENT_TYPES = {"click", "scroll", "pageview", "form_submit"}


class TestCsvFile:
    def test_csv_exists(self):
        assert CSV_PATH.exists(), f"CSV not found: {CSV_PATH}"

    def test_csv_has_correct_columns(self):
        df = pd.read_csv(CSV_PATH, nrows=1)
        missing = EXPECTED_COLUMNS - set(df.columns)
        assert not missing, f"Missing columns: {missing}"

    def test_csv_has_rows(self):
        df = pd.read_csv(CSV_PATH)
        assert len(df) > 0, "CSV is empty"


class TestIngestionScript:
    def test_load_csv_runs_without_error(self):
        from ingestion.clickstream import load_csv

        df = load_csv()
        assert df is not None and len(df) > 0

    def test_full_mode_row_count_matches_csv(self):
        from ingestion.clickstream import ingest
        from utils.db import query_df

        ingest("full")
        csv_count = len(pd.read_csv(CSV_PATH))
        db_count = int(
            query_df("SELECT COUNT(*) AS n FROM raw_clickstream_events")["n"].iloc[0]
        )
        assert db_count == csv_count, f"DB {db_count} != CSV {csv_count}"

    def test_no_invalid_event_types_in_db(self):
        from utils.db import query_df

        df = query_df("""
            SELECT COUNT(*) AS n FROM raw_clickstream_events
            WHERE event_name NOT IN ('click', 'scroll', 'pageview', 'form_submit')
        """)
        assert int(df["n"].iloc[0]) == 0, "Invalid event_types found in DB"

    def test_scroll_depth_values_between_0_and_100(self):
        from utils.db import query_df

        df = query_df("""
            SELECT COUNT(*) AS n FROM raw_clickstream_events
            WHERE scroll_depth_pct IS NOT NULL
              AND (scroll_depth_pct < 0 OR scroll_depth_pct > 100)
        """)
        assert (
            int(df["n"].iloc[0]) == 0
        ), "scroll_depth_pct values outside [0, 100] found"
