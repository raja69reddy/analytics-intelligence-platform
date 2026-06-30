"""
Clickstream CSV ingestion pipeline: data/raw/clickstream_events.csv -> raw_clickstream_events

Usage:
    python ingestion/clickstream.py --mode full
    python ingestion/clickstream.py --mode incremental --since 2024-01-01
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
from utils.helpers import parse_url

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("clickstream_ingestion")

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "raw" / "clickstream_events.csv"
TABLE = "raw_clickstream_events"
VALID_EVENT_TYPES = {"click", "scroll", "pageview", "form_submit"}
REQUIRED_COLUMNS = {"event_timestamp", "session_id", "user_id", "event_type", "page_url"}


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

    # Validate required columns
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        log.error("CSV is missing required columns: %s", missing)
        raise ValueError(f"Missing columns: {missing}")

    # Strip whitespace from string columns
    str_cols = df.select_dtypes(include="object").columns
    for col in str_cols:
        df[col] = df[col].str.strip()

    # Convert event_timestamp to proper TIMESTAMP format
    df["event_timestamp"] = pd.to_datetime(df["event_timestamp"], errors="coerce")
    dropped = df["event_timestamp"].isna().sum()
    if dropped:
        log.warning("Dropped %d rows with unparseable timestamps", dropped)
    df = df.dropna(subset=["event_timestamp"])

    # Validate event_type — log invalid values and drop them
    invalid_mask = ~df["event_type"].isin(VALID_EVENT_TYPES)
    if invalid_mask.sum():
        invalid_vals = df.loc[invalid_mask, "event_type"].value_counts().to_dict()
        log.error(
            "Found %d rows with invalid event_type values (dropping): %s  "
            "— valid types are: %s",
            invalid_mask.sum(), invalid_vals, sorted(VALID_EVENT_TYPES),
        )
        df = df[~invalid_mask]
    log.info("Event type counts after validation: %s",
             df["event_type"].value_counts().to_dict())

    # Clean page_url using parse_url() — keep just the path
    df["page_url"] = df["page_url"].fillna("").apply(lambda u: parse_url(u)["path"] if u else None)

    # Validate scroll_depth is between 0.0 and 1.0, then convert to 0-100 integer
    if "scroll_depth" in df.columns:
        invalid_scroll = df["scroll_depth"].notna() & (
            (df["scroll_depth"] < 0.0) | (df["scroll_depth"] > 1.0)
        )
        if invalid_scroll.sum():
            log.warning("Clamping %d scroll_depth values outside [0, 1]", invalid_scroll.sum())
            df.loc[invalid_scroll, "scroll_depth"] = df.loc[invalid_scroll, "scroll_depth"].clip(0.0, 1.0)
        df["scroll_depth_pct"] = (df["scroll_depth"] * 100).round().astype("Int64")
        df = df.drop(columns=["scroll_depth"])

    # Fill nulls with 0 for numeric columns
    num_cols = df.select_dtypes(include="number").columns
    df[num_cols] = df[num_cols].fillna(0)

    # Rename CSV columns to match DB column names
    df = df.rename(columns={
        "event_timestamp": "event_time",
        "user_id":         "user_pseudo_id",
        "event_type":      "event_name",
    })

    # Keep only columns that exist in raw_clickstream_events
    keep = ["event_time", "session_id", "user_pseudo_id", "event_name",
            "page_url", "scroll_depth_pct"]
    df = df[[c for c in keep if c in df.columns]]

    log.info("Loaded %d rows from CSV", len(df))
    return df


def _existing_dates(engine) -> set:
    with engine.connect() as conn:
        rows = conn.execute(text(f"SELECT DISTINCT event_time::date FROM {TABLE}"))
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
                df = df[df["event_time"].dt.date >= since]
                log.info("Since filter: %d rows from %s onward", len(df), since)
            existing = _existing_dates(engine)
            df = df[~df["event_time"].dt.date.isin(existing)]
            log.info("After dedup: %d new rows to insert", len(df))
            if df.empty:
                print(f"No new rows to insert.")
                return 0

        with engine.begin() as conn:
            if mode == "full":
                conn.execute(text(f"TRUNCATE {TABLE} RESTART IDENTITY"))
                log.info("Truncated %s", TABLE)

        df.to_sql(TABLE, engine, if_exists="append", index=False, method="multi", chunksize=500)

    except Exception as exc:
        log.error("Insert failed: %s", exc)
        print(f"Error inserting into {TABLE}: {exc}")
        raise

    count = len(df)
    log.info("Inserted %d rows into %s", count, TABLE)
    print(f"Inserted {count} rows into {TABLE}")
    return count


def main():
    parser = argparse.ArgumentParser(description="Ingest clickstream CSV into raw_clickstream_events")
    parser.add_argument("--mode", choices=["full", "incremental"], default="full")
    parser.add_argument("--since", default=None, metavar="YYYY-MM-DD")
    args = parser.parse_args()
    since = date.fromisoformat(args.since) if args.since else None
    try:
        ingest(args.mode, since)
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
