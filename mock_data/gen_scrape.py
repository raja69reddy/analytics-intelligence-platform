"""Generate mock scraped page metadata — CSV export or direct DB load."""
import argparse
import os
import random
import sys
from datetime import datetime, timezone

import pandas as pd
from faker import Faker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.db import get_engine

CSV_OUT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "raw", "scrape_pages.csv"))

BASE_PAGES = [
    ("https://example.com/",          "Home"),
    ("https://example.com/about",     "About Us"),
    ("https://example.com/contact",   "Contact"),
    ("https://example.com/pricing",   "Pricing"),
    ("https://example.com/products",  "Products"),
    ("https://example.com/faq",       "FAQ"),
    ("https://example.com/careers",   "Careers"),
    ("https://example.com/blog",      "Blog"),
    ("https://example.com/terms",     "Terms of Service"),
    ("https://example.com/privacy",   "Privacy Policy"),
]


def generate_csv(n: int = 50) -> pd.DataFrame:
    """Generate n simplified scraped-page rows for CSV export."""
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for i in range(n):
        if i < len(BASE_PAGES):
            url, title = BASE_PAGES[i]
        else:
            slug = fake.slug()
            url = f"https://example.com/blog/{slug}"
            title = " ".join(fake.words(nb=5)).title()
        rows.append({
            "url":              url,
            "title":            title,
            "meta_description": fake.sentence(nb_words=20)[:160],
            "word_count":       random.randint(300, 3000),
            "scraped_at":       now,
        })
    return pd.DataFrame(rows)

fake = Faker()

PAGES = [
    ("https://example.com/",              "Home"),
    ("https://example.com/blog/",         "Blog Index"),
    ("https://example.com/pricing/",      "Pricing"),
    ("https://example.com/about/",        "About Us"),
    ("https://example.com/contact/",      "Contact"),
    ("https://example.com/blog/post-1/",  "How to Get Started"),
    ("https://example.com/blog/post-2/",  "10 Tips for Growth"),
    ("https://example.com/products/",     "Products"),
]


def _make_row(url: str, title: str) -> dict:
    word_count = random.randint(200, 3500) if "blog" in url else random.randint(50, 600)
    return {
        "scraped_at":       datetime.now(tz=timezone.utc),
        "url":              url,
        "canonical_url":    url,
        "title":            title,
        "meta_description": fake.sentence(nb_words=20)[:160],
        "h1":               title,
        "word_count":       word_count,
        "internal_links":   random.randint(2, 20),
        "external_links":   random.randint(0, 8),
        "images_count":     random.randint(0, 12),
        "has_schema_org":   random.random() < 0.4,
        "page_size_kb":     round(random.uniform(20, 500), 2),
        "load_time_ms":     random.randint(150, 4000),
        "http_status":      200,
    }


def generate() -> pd.DataFrame:
    return pd.DataFrame([_make_row(url, title) for url, title in PAGES])


def load(df: pd.DataFrame, mode: str = "full") -> None:
    engine = get_engine()
    with engine.begin() as conn:
        if mode == "full":
            conn.execute(__import__("sqlalchemy").text("TRUNCATE raw_scrape_pages RESTART IDENTITY"))
    df.to_sql("raw_scrape_pages", engine, if_exists="append", index=False, method="multi", chunksize=500)
    print(f"Loaded {len(df):,} rows into raw_scrape_pages ({mode} mode).")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["csv", "full", "incremental"], default="csv")
    parser.add_argument("--rows", type=int, default=50)
    args = parser.parse_args()

    if args.mode == "csv":
        df = generate_csv(n=args.rows)
        os.makedirs(os.path.dirname(CSV_OUT), exist_ok=True)
        df.to_csv(CSV_OUT, index=False)
        print(f"Generated {len(df)} rows saved to data/raw/scrape_pages.csv")
    else:
        df = generate()
        load(df, mode=args.mode)


if __name__ == "__main__":
    main()
