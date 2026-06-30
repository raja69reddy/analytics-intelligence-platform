"""
Unit tests for the scrape pages ingestion pipeline (ingestion/scraper.py).
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CSV_PATH = ROOT / "data" / "raw" / "scrape_pages.csv"
EXPECTED_COLUMNS = {"url", "title", "meta_description", "word_count", "scraped_at"}


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
        from ingestion.scraper import load_csv
        df = load_csv()
        assert df is not None and len(df) > 0

    def test_full_mode_row_count_matches_csv(self):
        from ingestion.scraper import ingest
        from utils.db import query_df
        ingest("full")
        csv_count = len(pd.read_csv(CSV_PATH))
        db_count = int(query_df("SELECT COUNT(*) AS n FROM raw_scrape_pages")["n"].iloc[0])
        # scraper uses UPSERT — DB accumulates rows; at minimum every CSV URL is present
        assert db_count >= csv_count, f"DB {db_count} < CSV {csv_count}"

    def test_no_null_urls_in_db(self):
        from utils.db import query_df
        df = query_df("SELECT COUNT(*) AS n FROM raw_scrape_pages WHERE url IS NULL OR url = ''")
        assert int(df["n"].iloc[0]) == 0, "NULL or empty URLs found in DB"

    def test_all_word_counts_are_positive(self):
        from utils.db import query_df
        df = query_df("SELECT COUNT(*) AS n FROM raw_scrape_pages WHERE word_count < 0")
        assert int(df["n"].iloc[0]) == 0, "Negative word_count values found in DB"
