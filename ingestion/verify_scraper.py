"""
Verification script for raw_scrape_pages data quality.

Usage:
    python ingestion/verify_scraper.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.db import query_df

TABLE = "raw_scrape_pages"


def run_verification() -> None:
    print(f"\n{'='*50}")
    print("  raw_scrape_pages Verification Report")
    print(f"{'='*50}")

    # Total row count
    total = int(query_df(f"SELECT COUNT(*) AS n FROM {TABLE}")["n"].iloc[0])
    print(f"\nTotal rows: {total:,}")

    # Average word count
    df_avg = query_df(
        f"SELECT ROUND(AVG(word_count)) AS avg_wc, MIN(word_count) AS min_wc, MAX(word_count) AS max_wc FROM {TABLE}"
    )
    r = df_avg.iloc[0]
    print(f"Word count — avg: {r['avg_wc']}  min: {r['min_wc']}  max: {r['max_wc']}")

    # Pages missing meta descriptions
    df_no_meta = query_df(f"""
        SELECT COUNT(*) AS n FROM {TABLE}
        WHERE meta_description IS NULL OR meta_description = ''
    """)
    n_no_meta = int(df_no_meta["n"].iloc[0])
    print(f"\nPages missing meta description: {n_no_meta}")
    if n_no_meta > 0:
        df_urls = query_df(f"""
            SELECT url FROM {TABLE}
            WHERE meta_description IS NULL OR meta_description = ''
            LIMIT 5
        """)
        for _, r in df_urls.iterrows():
            print(f"  {r['url']}")

    # Top 5 longest pages by word count
    df_top = query_df(f"""
        SELECT url, word_count FROM {TABLE}
        ORDER BY word_count DESC LIMIT 5
    """)
    print("\nTop 5 longest pages by word count:")
    for _, r in df_top.iterrows():
        print(f"  {str(r['url']):<50} {int(r['word_count']):>5,} words")

    # Null check on key columns
    key_cols = ["scraped_at", "url", "title", "word_count"]
    print("\nNull value check:")
    found_nulls = False
    for col in key_cols:
        n_null = int(
            query_df(f"SELECT COUNT(*) AS n FROM {TABLE} WHERE {col} IS NULL")[
                "n"
            ].iloc[0]
        )
        status = "OK" if n_null == 0 else f"WARN: {n_null} nulls"
        print(f"  {col:<25} {status}")
        if n_null > 0:
            found_nulls = True

    print(f"\n{'='*50}")
    print(
        "Result:",
        "WARNING - nulls found" if found_nulls else "PASS - all checks passed",
    )
    print(f"{'='*50}\n")


if __name__ == "__main__":
    run_verification()
