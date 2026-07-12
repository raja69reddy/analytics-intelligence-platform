"""
Unit tests for the server logs ingestion pipeline (ingestion/server_logs.py).
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CSV_PATH = ROOT / "data" / "raw" / "server_logs.csv"
EXPECTED_COLUMNS = {
    "log_timestamp",
    "ip_address",
    "request_method",
    "url",
    "status_code",
    "response_size",
    "user_agent",
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
        from ingestion.server_logs import load_csv

        df = load_csv()
        assert df is not None
        assert len(df) > 0

    def test_load_csv_converts_log_time(self):
        import pandas as pd
        from ingestion.server_logs import load_csv

        df = load_csv()
        assert pd.api.types.is_datetime64_any_dtype(
            df["log_time"]
        ), "log_time column should be a datetime type"

    def test_load_csv_no_null_timestamps(self):
        from ingestion.server_logs import load_csv

        df = load_csv()
        assert df["log_time"].isna().sum() == 0, "log_time should have no null values"

    def test_full_mode_row_count_matches_csv(self):
        from ingestion.server_logs import ingest
        from utils.db import query_df

        ingest("full")
        csv_count = len(pd.read_csv(CSV_PATH))
        db_df = query_df("SELECT COUNT(*) AS n FROM raw_server_logs")
        db_count = int(db_df["n"].iloc[0])
        assert (
            db_count == csv_count
        ), f"DB row count ({db_count}) does not match CSV row count ({csv_count})"

    def test_no_null_timestamps_in_db(self):
        from utils.db import query_df

        df = query_df(
            "SELECT COUNT(*) AS n FROM raw_server_logs WHERE log_time IS NULL"
        )
        assert (
            int(df["n"].iloc[0]) == 0
        ), "raw_server_logs should have no null log_time values"
