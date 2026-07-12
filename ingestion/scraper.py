"""
Scrape pages CSV ingestion pipeline: data/raw/scrape_pages.csv -> raw_scrape_pages

Performs an upsert: existing URLs are updated in-place; new URLs are inserted.

Usage:
    python ingestion/scraper.py
    python ingestion/scraper.py --mode full
"""

import argparse
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
REQUIRED_COLUMNS = {"url", "title", "meta_description", "word_count", "scraped_at"}


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
