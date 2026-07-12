"""Print row counts and a 5-row preview for each CSV in data/raw/."""

import os
import sys

import pandas as pd

DATA_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "raw")
)

CSVS = [
    "ga4_sessions.csv",
    "server_logs.csv",
    "scrape_pages.csv",
    "clickstream_events.csv",
]


def verify():
    all_ok = True
    for fname in CSVS:
        path = os.path.join(DATA_DIR, fname)
        if not os.path.exists(path):
            print(f"  MISSING: {fname}")
            all_ok = False
            continue
        df = pd.read_csv(path)
        print(f"\n{fname}  —  {df.shape[0]:,} rows x {df.shape[1]} columns")
        print(df.head(5).to_string(index=False))
    return all_ok


if __name__ == "__main__":
    ok = verify()
    sys.exit(0 if ok else 1)
