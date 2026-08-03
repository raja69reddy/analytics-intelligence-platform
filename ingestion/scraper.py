"""
Scrape pages CSV ingestion pipeline: data/raw/scrape_pages.csv -> raw_scrape_pages

Performs an upsert: existing URLs are updated in-place; new URLs are inserted.

Usage:
    python ingestion/scraper.py
    python ingestion/scraper.py --mode full
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.db import get_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("scraper_ingestion")

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "raw" / "scrape_pages.csv"
TABLE = "raw_scrape_pages"
_LOG_DIR = Path(__file__).resolve().parent.parent / "data" / "processed" / "logs"
_VAL_SUMMARY = Path(__file__).resolve().parent.parent / "data" / "processed" / "validation_summary.json"
_EXPECTED_SCHEMA: dict[str, str] = {
    "url": "str",
    "title": "str",
    "meta_description": "str",
    "word_count": "numeric",
    "scraped_at": "str",
}
REQUIRED_COLUMNS = {"url", "title", "meta_description", "word_count", "scraped_at"}


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
    parsed_urls = df["url"].fillna("").astype(str).apply(urlparse)
    title_col = df["title"].fillna("").astype(str).str.strip()
    checks = {
        "invalid_url": parsed_urls.apply(lambda p: not p.scheme or not p.netloc),
        "word_count_not_positive": pd.to_numeric(df["word_count"], errors="coerce").fillna(0) < 1,
        "title_empty": title_col.isin(["", "nan", "None"]),
        "invalid_scraped_at": pd.to_datetime(df["scraped_at"], errors="coerce").isna(),
    }
    flags = pd.DataFrame(checks)
    fail_mask = flags.any(axis=1)
    if fail_mask.any():
        bad = df[fail_mask].copy()
        bad["_errors"] = flags[fail_mask].apply(
            lambda r: ", ".join(r.index[r].tolist()), axis=1
        )
        ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        bad.to_csv(_LOG_DIR / f"scraper_invalid_{ts}.csv", index=False)
        log.warning("Saved %d invalid rows → scraper_invalid_%s.csv", fail_mask.sum(), ts)
    summary = {
        "passed": int((~fail_mask).sum()),
        "failed": int(fail_mask.sum()),
        "error_counts": {k: int(v) for k, v in flags.sum().items() if v > 0},
        "last_run": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    _update_val_summary("scraper", summary)
    return df[~fail_mask].copy(), summary


def _normalize_url(url: str) -> str:
    """Lowercase scheme+host, strip trailing slash."""
    if not url:
        return url
    parsed = urlparse(str(url).strip())
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
    )
    return normalized.geturl().rstrip("/")


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

    # Schema validation — check columns and types match expected schema
    _validate_schema(df)

    # Validate raw CSV values before transforms
    df, _val = _validate(df)
    log.info("Validation: %d passed, %d failed", _val["passed"], _val["failed"])
    if _val["error_counts"]:
        log.warning("Error breakdown: %s", _val["error_counts"])

    # Normalize URLs — lowercase, strip trailing slash; log and drop invalid entries
    invalid_urls = df["url"].isna() | (df["url"].astype(str).str.strip() == "")
    if invalid_urls.sum():
        log.error("Dropping %d rows with missing/empty URLs", invalid_urls.sum())
        df = df[~invalid_urls]
    df["url"] = df["url"].apply(_normalize_url)
    # Log any URLs that fail basic validation (no scheme or host)
    bad_urls = df["url"].apply(
        lambda u: not urlparse(u).scheme or not urlparse(u).netloc
    )
    if bad_urls.sum():
        log.error(
            "Dropping %d rows with malformed URLs (missing scheme or host): %s",
            bad_urls.sum(),
            df.loc[bad_urls, "url"].tolist(),
        )
        df = df[~bad_urls]

    # Clean title and meta_description — strip whitespace
    for col in ["title", "meta_description"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace("nan", None)

    # Validate word_count is a positive integer
    df["word_count"] = (
        pd.to_numeric(df["word_count"], errors="coerce").fillna(0).astype(int)
    )
    neg_mask = df["word_count"] < 0
    if neg_mask.sum():
        log.warning("Setting %d negative word_count values to 0", neg_mask.sum())
        df.loc[neg_mask, "word_count"] = 0

    # Convert scraped_at to proper TIMESTAMP
    df["scraped_at"] = pd.to_datetime(df["scraped_at"], errors="coerce")
    bad_ts = df["scraped_at"].isna().sum()
    if bad_ts:
        log.warning("Filling %d unparseable scraped_at values with NOW()", bad_ts)
        df["scraped_at"] = df["scraped_at"].fillna(pd.Timestamp.now())

    keep = ["scraped_at", "url", "title", "meta_description", "word_count"]
    df = df[[c for c in keep if c in df.columns]]

    log.info("Loaded %d rows from CSV", len(df))
    print(f"Validation: {_val['passed']} rows passed, {_val['failed']} failed")
    return df


def _ensure_unique_constraint(engine) -> None:
    """Add UNIQUE constraint on url if it doesn't already exist."""
    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT COUNT(*) FROM pg_constraint
            WHERE conname = 'uq_scrape_pages_url'
        """))
        if result.scalar() == 0:
            conn.execute(
                text(
                    "ALTER TABLE raw_scrape_pages ADD CONSTRAINT uq_scrape_pages_url UNIQUE (url)"
                )
            )
            log.info("Added UNIQUE constraint on raw_scrape_pages.url")


def ingest(mode: str = "full") -> int:
    _start = time.perf_counter()
    log.info("START scraper ingest mode=%s", mode)
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
        _ensure_unique_constraint(engine)

        if mode == "full":
            # Upsert each row — insert or update on URL conflict
            upsert_sql = text(f"""
                INSERT INTO {TABLE} (scraped_at, url, title, meta_description, word_count)
                VALUES (:scraped_at, :url, :title, :meta_description, :word_count)
                ON CONFLICT (url) DO UPDATE SET
                    scraped_at       = EXCLUDED.scraped_at,
                    title            = EXCLUDED.title,
                    meta_description = EXCLUDED.meta_description,
                    word_count       = EXCLUDED.word_count
            """)
            records = df.to_dict("records")
            with engine.begin() as conn:
                conn.execute(upsert_sql, records)

    except Exception as exc:
        log.error("Insert/update failed: %s", exc)
        print(f"Error inserting into {TABLE}: {exc}")
        raise

    count = len(df)
    elapsed = time.perf_counter() - _start
    log.info("Inserted/Updated %d rows into %s", count, TABLE)
    print(f"Inserted/Updated {count} rows into {TABLE}")
    log.info("END scraper ingest: %d rows in %.2fs", count, elapsed)
    return count


def main():
    parser = argparse.ArgumentParser(
        description="Ingest scrape pages CSV into raw_scrape_pages"
    )
    parser.add_argument(
        "--mode", choices=["full"], default="full", help="full: upsert all rows by URL"
    )
    args = parser.parse_args()
    try:
        ingest(args.mode)
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
