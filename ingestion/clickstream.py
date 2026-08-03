"""
Clickstream CSV ingestion pipeline: data/raw/clickstream_events.csv -> raw_clickstream_events

Usage:
    python ingestion/clickstream.py --mode full
    python ingestion/clickstream.py --mode incremental --since 2024-01-01
"""

import argparse
import json
import logging
import sys
import time
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

CSV_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "raw" / "clickstream_events.csv"
)
TABLE = "raw_clickstream_events"
_LOG_DIR = Path(__file__).resolve().parent.parent / "data" / "processed" / "logs"
_VAL_SUMMARY = Path(__file__).resolve().parent.parent / "data" / "processed" / "validation_summary.json"
VALID_EVENT_TYPES = {"click", "scroll", "pageview", "form_submit"}
REQUIRED_COLUMNS = {
    "event_timestamp",
    "session_id",
    "user_id",
    "event_type",
    "page_url",
}


def _update_val_summary(source: str, summary: dict) -> None:
    data: dict = {}
    if _VAL_SUMMARY.exists():
        try:
            data = json.loads(_VAL_SUMMARY.read_text())
        except Exception:
            pass
    data[source] = summary
    _VAL_SUMMARY.write_text(json.dumps(data, indent=2))


def _validate(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Check row-level constraints before transforms. Returns (valid_df, summary)."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    sd = pd.to_numeric(df["scroll_depth"], errors="coerce") if "scroll_depth" in df.columns else None
    checks = {
        "invalid_event_timestamp": pd.to_datetime(df["event_timestamp"], errors="coerce").isna(),
        "scroll_depth_out_of_range": (
            sd.notna() & ((sd < 0.0) | (sd > 1.0))
            if sd is not None
            else pd.Series(False, index=df.index)
        ),
        "invalid_event_type": ~df["event_type"].isin(VALID_EVENT_TYPES),
        "page_url_empty": df["page_url"].isna() | (df["page_url"].astype(str).str.strip() == ""),
    }
    flags = pd.DataFrame(checks)
    fail_mask = flags.any(axis=1)
    if fail_mask.any():
        bad = df[fail_mask].copy()
        bad["_errors"] = flags[fail_mask].apply(
            lambda r: ", ".join(r.index[r].tolist()), axis=1
        )
        ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        bad.to_csv(_LOG_DIR / f"clickstream_invalid_{ts}.csv", index=False)
        log.warning("Saved %d invalid rows → clickstream_invalid_%s.csv", fail_mask.sum(), ts)
    summary = {
        "passed": int((~fail_mask).sum()),
        "failed": int(fail_mask.sum()),
        "error_counts": {k: int(v) for k, v in flags.sum().items() if v > 0},
        "last_run": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    _update_val_summary("clickstream", summary)
    return df[~fail_mask].copy(), summary


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

    # Validate raw CSV values before transforms
    df, _val = _validate(df)
    log.info("Validation: %d passed, %d failed", _val["passed"], _val["failed"])
    if _val["error_counts"]:
        log.warning("Error breakdown: %s", _val["error_counts"])

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
            invalid_mask.sum(),
            invalid_vals,
            sorted(VALID_EVENT_TYPES),
        )
        df = df[~invalid_mask]
    log.info(
        "Event type counts after validation: %s",
        df["event_type"].value_counts().to_dict(),
    )

    # Clean page_url using parse_url() — keep just the path
    df["page_url"] = (
        df["page_url"].fillna("").apply(lambda u: parse_url(u)["path"] if u else None)
    )

    # Validate scroll_depth is between 0.0 and 1.0, then convert to 0-100 integer
    if "scroll_depth" in df.columns:
        invalid_scroll = df["scroll_depth"].notna() & (
            (df["scroll_depth"] < 0.0) | (df["scroll_depth"] > 1.0)
        )
        if invalid_scroll.sum():
            log.warning(
                "Clamping %d scroll_depth values outside [0, 1]", invalid_scroll.sum()
            )
            df.loc[invalid_scroll, "scroll_depth"] = df.loc[
                invalid_scroll, "scroll_depth"
            ].clip(0.0, 1.0)
        df["scroll_depth_pct"] = (df["scroll_depth"] * 100).round().astype("Int64")
        df = df.drop(columns=["scroll_depth"])

    # Fill nulls with 0 for numeric columns
    num_cols = df.select_dtypes(include="number").columns
    df[num_cols] = df[num_cols].fillna(0)

    # Rename CSV columns to match DB column names
    df = df.rename(
        columns={
            "event_timestamp": "event_time",
            "user_id": "user_pseudo_id",
            "event_type": "event_name",
            "device_type": "device_category",
        }
    )

    # Keep only columns that exist in raw_clickstream_events
    keep = [
        "event_time",
        "session_id",
        "user_pseudo_id",
        "event_name",
        "page_url",
        "scroll_depth_pct",
        "device_category",
    ]
    df = df[[c for c in keep if c in df.columns]]

    log.info("Loaded %d rows from CSV", len(df))
    print(f"Validation: {_val['passed']} rows passed, {_val['failed']} failed")
    return df


def _existing_dates(engine) -> set:
    with engine.connect() as conn:
        rows = conn.execute(text(f"SELECT DISTINCT event_time::date FROM {TABLE}"))
        return {r[0] for r in rows}


def ingest(mode: str, since: date | None = None) -> int:
    _start = time.perf_counter()
    log.info("START clickstream ingest mode=%s since=%s", mode, since)
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
                print("No new rows to insert.")
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
    log.info("Inserted %d rows into %s", count, TABLE)
    print(f"Inserted {count} rows into {TABLE}")
    log.info("END clickstream ingest: %d rows in %.2fs", count, elapsed)
    return count


def main():
    parser = argparse.ArgumentParser(
        description="Ingest clickstream CSV into raw_clickstream_events"
    )
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
