"""
populate_dim_pages.py
Populates dim_pages from raw_server_logs (all distinct URL paths)
enriched with metadata from raw_scrape_pages.
Uses ON CONFLICT (url) DO UPDATE for safe upsert.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from utils.db import get_engine, query_df


def _get_all_paths() -> list[str]:
    """Union distinct paths from server logs, GA4 landing pages, and clickstream."""
    df = query_df("""
        SELECT DISTINCT url AS path FROM raw_server_logs WHERE url IS NOT NULL
        UNION
        SELECT DISTINCT landing_page AS path FROM raw_ga4_sessions WHERE landing_page IS NOT NULL
        UNION
        SELECT DISTINCT
            CASE
                WHEN page_url = '/' OR page_url = '' THEN '/'
                ELSE regexp_replace(page_url, '/$', '')
            END AS path
        FROM raw_clickstream_events
        WHERE page_url IS NOT NULL
        ORDER BY path
    """)
    return df["path"].tolist()


def _get_scrape_metadata() -> dict:
    """
    Return dict keyed by path → {title, word_count, first_seen, last_seen}
    extracted from raw_scrape_pages by stripping the domain from the URL.
    """
    df = query_df("""
        SELECT
            CASE
                WHEN regexp_replace(url, 'https://[^/]+', '') IN ('', '/')
                     THEN '/'
                ELSE regexp_replace(regexp_replace(url, 'https://[^/]+', ''), '/$', '')
            END                                         AS path,
            MAX(title)                                  AS page_title,
            MAX(word_count)                             AS word_count,
            MIN(scraped_at::date)                       AS first_seen,
            MAX(scraped_at::date)                       AS last_seen
        FROM raw_scrape_pages
        WHERE url IS NOT NULL
        GROUP BY 1
        ORDER BY 1
    """)
    result: dict = {}
    for _, row in df.iterrows():
        result[row["path"]] = {
            "page_title": row["page_title"],
            "word_count": int(row["word_count"]) if row["word_count"] is not None else None,
            "first_seen": row["first_seen"],
            "last_seen":  row["last_seen"],
        }
    return result


def _extract_domain(url: str) -> str:
    """Extract domain from a path (no domain for path-only entries)."""
    return "example.com"


def _extract_section(path: str) -> str | None:
    """First path segment: /blog/post-1 → 'blog'."""
    parts = [p for p in path.strip("/").split("/") if p]
    return parts[0] if parts else None


def run(verbose: bool = True) -> int:
    paths    = _get_all_paths()
    metadata = _get_scrape_metadata()
    today    = date.today()

    engine   = get_engine()
    inserted = 0
    updated  = 0

    with engine.begin() as conn:
        for path in paths:
            meta  = metadata.get(path, {})
            title = meta.get("page_title")
            wc    = meta.get("word_count")
            fs    = meta.get("first_seen") or today
            ls    = meta.get("last_seen")  or today

            # Determine if this is a landing page
            is_lp_result = query_df(
                "SELECT COUNT(*) AS n FROM raw_ga4_sessions WHERE landing_page = :p",
                params={"p": path},
            )
            is_lp = int(is_lp_result["n"].iloc[0]) > 0

            result = conn.execute(text("""
                INSERT INTO dim_pages
                    (url, url_path, url_domain, page_title, page_section,
                     is_landing_page, word_count, first_seen, last_seen, updated_at)
                VALUES
                    (:url, :url_path, :domain, :title, :section,
                     :is_lp, :wc, :fs, :ls, NOW())
                ON CONFLICT (url) DO UPDATE SET
                    page_title      = COALESCE(EXCLUDED.page_title, dim_pages.page_title),
                    word_count      = COALESCE(EXCLUDED.word_count, dim_pages.word_count),
                    last_seen       = GREATEST(EXCLUDED.last_seen, dim_pages.last_seen),
                    is_landing_page = EXCLUDED.is_landing_page OR dim_pages.is_landing_page,
                    updated_at      = NOW()
                RETURNING (xmax = 0) AS is_insert
            """), {
                "url":     path,
                "url_path": path,
                "domain":  "example.com",
                "title":   title,
                "section": _extract_section(path),
                "is_lp":   is_lp,
                "wc":      wc,
                "fs":      fs,
                "ls":      ls,
            })
            row = result.fetchone()
            if row and row[0]:
                inserted += 1
            else:
                updated += 1

    if verbose:
        print(f"Inserted/Updated {inserted + updated} rows in dim_pages "
              f"({inserted} new, {updated} updated).")
    return inserted + updated


if __name__ == "__main__":
    run(verbose=True)
    # Verify
    df = query_df("SELECT COUNT(*) AS n FROM dim_pages")
    print(f"dim_pages now has {df['n'].iloc[0]} rows.")
    sample = query_df("SELECT page_id, url, page_title, word_count, is_landing_page FROM dim_pages LIMIT 5")
    print("\nSample rows:")
    print(sample.to_string(index=False))
