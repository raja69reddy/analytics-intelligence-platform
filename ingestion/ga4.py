"""
GA4 CSV ingestion pipeline: data/raw/ga4_sessions.csv -> raw_ga4_sessions

Usage:
    python ingestion/ga4.py --mode full
    python ingestion/ga4.py --mode incremental --since 2024-01-01
"""

import argparse
import logging
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.db import get_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ga4_ingestion")

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "raw" / "ga4_sessions.csv"
TABLE = "raw_ga4_sessions"


def load_csv() -> pd.DataFrame:
    try:
        log.info("Reading %s", CSV_PATH)
        df = pd.read_csv(CSV_PATH, dtype_backend="numpy_nullable")
    except FileNotFoundError:
        log.error("CSV file not found: %s", CSV_PATH)
        print(f"Error: CSV file not found at {CSV_PATH}")
        raise
    except Exception as exc:
        log.error("Failed to read CSV: %s", exc)
        print(f"Error reading CSV: {exc}")
        raise

    # Strip whitespace from string/object columns
    str_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()
    for col in str_cols:
        df[col] = df[col].astype(str).str.strip().replace("nan", None)

    # Convert session_date to proper DATE
    df["session_date"] = pd.to_datetime(df["session_date"]).dt.date

    # Fill nulls with 0 for numeric columns
    num_cols = df.select_dtypes(include="number").columns
    df[num_cols] = df[num_cols].fillna(0)

    # Map CSV columns to DB column names
    df = df.rename(
        columns={
            "channel": "channel_grouping",
            "avg_session_duration": "session_duration_s",
        }
    )

    # Derive boolean bounce from bounce_rate float
    df["bounce"] = df["bounce_rate"] > 0.5

    # Drop columns with no matching DB column
    df = df.drop(columns=["bounce_rate", "users"], errors="ignore")

    log.info("Loaded %d rows from CSV", len(df))
    return df


def _existing_dates(engine) -> set:
    with engine.connect() as conn:
        rows = conn.execute(text(f"SELECT DISTINCT session_date FROM {TABLE}"))
        return {r[0] for r in rows}


def ingest(mode: str, since: date | None = None) -> int:
    _start = time.perf_counter()
    log.info("START ga4 ingest mode=%s since=%s", mode, since)
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        log.info("Database connection established")
    except Exception as exc:
        log.error("Cannot connect to database: %s", exc)
        print(f"Error: Cannot connect to database - {exc}")
        raise

    df = load_csv()

    try:
        if mode == "incremental":
            if since is not None:
                # Filter CSV rows to only those on or after the since date
                df = df[df["session_date"] >= since]
                log.info("Since filter applied: %d rows from %s onward", len(df), since)

            # Also skip dates already in the database
            existing = _existing_dates(engine)
            df = df[~df["session_date"].isin(existing)]
            log.info("After dedup: %d new rows to insert", len(df))

            if df.empty:
                since_str = str(since) if since else "existing dates"
                print(f"No new rows to insert since {since_str}.")
                return 0

        with engine.begin() as conn:
            if mode == "full":
                conn.execute(text(f"TRUNCATE {TABLE} RESTART IDENTITY"))
                log.info("Truncated %s", TABLE)

        df.to_sql(
            TABLE,
            engine,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=500,
        )

    except Exception as exc:
        log.error("Insert failed: %s", exc)
        print(f"Error inserting into {TABLE}: {exc}")
        raise

    count = len(df)
    elapsed = time.perf_counter() - _start
    if mode == "incremental" and since is not None:
        log.info("Incremental load: inserted %d rows since %s", count, since)
        print(f"Incremental load: inserted {count} rows since {since}")
    else:
        log.info("Inserted %d rows into %s", count, TABLE)
        print(f"Inserted {count} rows into {TABLE}")
    log.info("END ga4 ingest: %d rows in %.2fs", count, elapsed)
    return count


def main():
    parser = argparse.ArgumentParser(description="Ingest GA4 CSV into raw_ga4_sessions")
    parser.add_argument(
        "--mode",
        choices=["full", "incremental"],
        default="full",
        help="full: truncate and reload; incremental: only insert new dates",
    )
    parser.add_argument(
        "--since",
        default=None,
        metavar="YYYY-MM-DD",
        help="Start date for incremental load (e.g. 2024-01-01)",
    )
    args = parser.parse_args()
    since = date.fromisoformat(args.since) if args.since else None
    try:
        ingest(args.mode, since)
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
