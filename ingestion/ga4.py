"""
GA4 CSV ingestion pipeline: data/raw/ga4_sessions.csv -> raw_ga4_sessions

Usage:
    python ingestion/ga4.py --mode full
    python ingestion/ga4.py --mode incremental --since 2024-01-01
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ga4_ingestion")

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "raw" / "ga4_sessions.csv"
TABLE = "raw_ga4_sessions"
_EXPECTED_SCHEMA: dict[str, str] = {
    "session_date": "str",
    "source": "str",
    "medium": "str",
    "channel": "str",
    "sessions": "numeric",
    "users": "numeric",
    "new_users": "numeric",
    "pageviews": "numeric",
    "bounce_rate": "numeric",
    "avg_session_duration": "numeric",
}
_LOG_DIR = Path(__file__).resolve().parent.parent / "data" / "processed" / "logs"
_VAL_SUMMARY = Path(__file__).resolve().parent.parent / "data" / "processed" / "validation_summary.json"


def _validate_schema(df: pd.DataFrame) -> bool:
    """Check CSV columns match expected schema. Returns True if schema is valid."""
    missing = [c for c in _EXPECTED_SCHEMA if c not in df.columns]
    extra = [c for c in df.columns if c not in _EXPECTED_SCHEMA]
    type_errors = []
    for col, expected_type in _EXPECTED_SCHEMA.items():
        if col not in df.columns:
            continue
        if expected_type == "numeric" and not pd.api.types.is_numeric_dtype(df[col]):
            type_errors.append(f"{col} expected numeric, got {df[col].dtype}")
    ok = not missing and not type_errors
    if missing:
        log.error("Schema mismatch — missing columns: %s", missing)
    if extra:
        log.warning("Schema mismatch — unexpected columns: %s", extra)
    if type_errors:
        log.error("Schema mismatch — type errors: %s", type_errors)
    if ok:
        log.info("Schema validation PASSED (%d expected columns present)", len(_EXPECTED_SCHEMA))
    else:
        log.error("Schema validation FAILED")
    return ok


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
    br = pd.to_numeric(df["bounce_rate"], errors="coerce")
    checks = {
        "invalid_session_date": pd.to_datetime(df["session_date"], errors="coerce").isna(),
        "sessions_not_positive": pd.to_numeric(df["sessions"], errors="coerce").fillna(0) < 1,
        "users_not_positive": pd.to_numeric(df["users"], errors="coerce").fillna(0) < 1,
        "bounce_rate_out_of_range": br.notna() & ((br < 0) | (br > 1)),
        "channel_empty": df["channel"].isna() | (df["channel"].astype(str).str.strip() == ""),
    }
    flags = pd.DataFrame(checks)
    fail_mask = flags.any(axis=1)
    if fail_mask.any():
        bad = df[fail_mask].copy()
        bad["_errors"] = flags[fail_mask].apply(
            lambda r: ", ".join(r.index[r].tolist()), axis=1
        )
        ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        bad.to_csv(_LOG_DIR / f"ga4_invalid_{ts}.csv", index=False)
        log.warning("Saved %d invalid rows → ga4_invalid_%s.csv", fail_mask.sum(), ts)
    summary = {
        "passed": int((~fail_mask).sum()),
        "failed": int(fail_mask.sum()),
        "error_counts": {k: int(v) for k, v in flags.sum().items() if v > 0},
        "last_run": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    _update_val_summary("ga4", summary)
    return df[~fail_mask].copy(), summary


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

    # Schema validation — check columns and types match expected schema
    _validate_schema(df)

    # Strip whitespace from string/object columns
    str_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()
    for col in str_cols:
        df[col] = df[col].astype(str).str.strip().replace("nan", None)

    # Validate raw CSV values before transforms
    df, _val = _validate(df)
    log.info("Validation: %d passed, %d failed", _val["passed"], _val["failed"])
    if _val["error_counts"]:
        log.warning("Error breakdown: %s", _val["error_counts"])

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
    print(f"Validation: {_val['passed']} rows passed, {_val['failed']} failed")
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
