"""
Server logs CSV ingestion pipeline: data/raw/server_logs.csv -> raw_server_logs

Usage:
    python ingestion/server_logs.py --mode full
    python ingestion/server_logs.py --mode incremental --since 2024-01-01
"""
import argparse
import logging
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.db import get_engine
from utils.log_parser import (
    extract_page_from_url,
    parse_response_size,
    parse_status_code,
    parse_timestamp,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("server_logs_ingestion")

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "raw" / "server_logs.csv"
TABLE = "raw_server_logs"
REQUIRED_COLUMNS = {"log_timestamp", "ip_address", "request_method",
                    "url", "status_code", "response_size", "user_agent"}


def load_csv() -> pd.DataFrame:
    try:
        log.info("Reading %s", CSV_PATH)
        df = pd.read_csv(CSV_PATH)
    except FileNotFoundError:
        log.error("CSV file not found: %s", CSV_PATH)
        print(f"Error: CSV file not found at {CSV_PATH}")
        raise
    except Exception as exc:
        log.error("Failed to read CSV: %s", exc)
        print(f"Error reading CSV: {exc}")
        raise

    # Validate required columns are present
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        log.error("CSV is missing required columns: %s", missing)
        print(f"Error: CSV is missing required columns: {missing}")
        raise ValueError(f"Missing columns: {missing}")

    # Strip whitespace from string columns
    str_cols = df.select_dtypes(include="str").columns.tolist() or \
               df.select_dtypes(include="object").columns.tolist()
    for col in str_cols:
        df[col] = df[col].str.strip()

    # Use parse_timestamp() for timestamp cleaning
    df["log_timestamp"] = df["log_timestamp"].apply(parse_timestamp)
    dropped = df["log_timestamp"].isna().sum()
    if dropped:
        log.warning("Dropped %d rows with unparseable timestamps", dropped)
    df = df.dropna(subset=["log_timestamp"])

    # Use extract_page_from_url() to clean URL paths and split query strings
    from urllib.parse import urlparse
    df["query_string"] = df["url"].fillna("").apply(lambda u: urlparse(u).query or None)
    df["url"] = df["url"].fillna("").apply(extract_page_from_url)

    # Use parse_status_code() to add status_category column (for logging/reporting)
    df["status_category"] = df["status_code"].apply(parse_status_code)
    log.info("Status breakdown: %s", df["status_category"].value_counts().to_dict())

    # Use parse_response_size() to log KB equivalent (raw bytes still stored in DB)
    total_mb = df["response_size"].apply(parse_response_size).sum() / 1024
    log.info("Total response data: %.1f MB", total_mb)

    # Fill nulls with 0 for numeric columns
    num_cols = df.select_dtypes(include="number").columns
    df[num_cols] = df[num_cols].fillna(0)

    # Rename CSV columns to match DB column names
    df = df.rename(columns={
        "log_timestamp":  "log_time",
        "request_method": "method",
        "response_size":  "response_bytes",
    })

    # Keep only columns that exist in raw_server_logs
    keep = ["log_time", "ip_address", "method", "url", "query_string",
            "status_code", "response_bytes", "referrer", "user_agent", "response_time_ms"]
    df = df[[c for c in keep if c in df.columns]]

    log.info("Loaded %d rows from CSV", len(df))
    return df


def _existing_dates(engine) -> set:
    with engine.connect() as conn:
        rows = conn.execute(text(f"SELECT DISTINCT log_time::date FROM {TABLE}"))
        return {r[0] for r in rows}


def ingest(mode: str, since: date | None = None) -> int:
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
                df = df[df["log_time"].dt.date >= since]
                log.info("Since filter applied: %d rows from %s onward", len(df), since)

            existing = _existing_dates(engine)
            df = df[~df["log_time"].dt.date.isin(existing)]
            log.info("After dedup: %d new rows to insert", len(df))

            if df.empty:
                since_str = str(since) if since else "existing dates"
                print(f"No new rows to insert since {since_str}.")
                return 0

        with engine.begin() as conn:
            if mode == "full":
                conn.execute(text(f"TRUNCATE {TABLE} RESTART IDENTITY"))
                log.info("Truncated %s", TABLE)

        # Build INSERT columns dynamically based on what's in the DataFrame
        db_cols = ["log_time", "ip_address", "method", "url", "query_string",
                   "status_code", "response_bytes", "referrer", "user_agent", "response_time_ms"]
        present = [c for c in db_cols if c in df.columns]
        values_clause = ", ".join(
            f"CAST(:ip_address AS INET)" if c == "ip_address" else f":{c}"
            for c in present
        )
        insert_sql = text(
            f"INSERT INTO {TABLE} ({', '.join(present)}) VALUES ({values_clause})"
        )
        records = df[present].to_dict("records")
        with engine.begin() as conn:
            conn.execute(insert_sql, records)

    except Exception as exc:
        log.error("Insert failed: %s", exc)
        print(f"Error inserting into {TABLE}: {exc}")
        raise

    count = len(df)
    if mode == "incremental" and since is not None:
        log.info("Incremental load: inserted %d rows since %s", count, since)
        print(f"Incremental load: inserted {count} rows since {since}")
    else:
        log.info("Inserted %d rows into %s", count, TABLE)
        print(f"Inserted {count} rows into {TABLE}")
    return count


def main():
    parser = argparse.ArgumentParser(description="Ingest server logs CSV into raw_server_logs")
    parser.add_argument("--mode", choices=["full", "incremental"], default="full",
                        help="full: truncate and reload; incremental: only insert new dates")
    parser.add_argument("--since", default=None, metavar="YYYY-MM-DD",
                        help="Start date for incremental load (e.g. 2024-01-01)")
    args = parser.parse_args()
    since = date.fromisoformat(args.since) if args.since else None
    try:
        ingest(args.mode, since)
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
