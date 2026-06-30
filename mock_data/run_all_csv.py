"""Run all 4 mock data generators in CSV mode and print row counts."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mock_data.gen_ga4 import generate_csv as ga4_csv, CSV_OUT as GA4_OUT
from mock_data.gen_server_logs import generate_csv as logs_csv, CSV_OUT as LOGS_OUT
from mock_data.gen_scrape import generate_csv as scrape_csv, CSV_OUT as SCRAPE_OUT
from mock_data.gen_clickstream import generate_csv as click_csv, CSV_OUT as CLICK_OUT

DATA_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "raw"))


def run_all():
    os.makedirs(DATA_DIR, exist_ok=True)

    jobs = [
        ("ga4_sessions.csv",        lambda: ga4_csv(n=1000),    GA4_OUT),
        ("server_logs.csv",         lambda: logs_csv(n=2000),   LOGS_OUT),
        ("scrape_pages.csv",        lambda: scrape_csv(n=50),   SCRAPE_OUT),
        ("clickstream_events.csv",  lambda: click_csv(n=5000),  CLICK_OUT),
    ]

    for fname, gen_fn, out_path in jobs:
        df = gen_fn()
        df.to_csv(out_path, index=False)
        print(f"  {fname:<30} {len(df):>6,} rows")

    print("\nAll 4 CSVs generated in data/raw/")


if __name__ == "__main__":
    print("Generating all mock data CSVs...\n")
    run_all()
