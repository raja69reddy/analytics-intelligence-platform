"""Generate mock GA4 session data — CSV export or direct DB load."""
import argparse
import os
import random
import sys
import uuid
from datetime import date, timedelta

import pandas as pd
from faker import Faker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.db import get_engine

CSV_OUT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "raw", "ga4_sessions.csv"))

CSV_CHANNELS = [
    ("Organic Search", "google",     "organic"),
    ("Direct",         "direct",     "(none)"),
    ("Referral",       "facebook",   "referral"),
    ("Social",         "twitter",    "social"),
    ("Email",          "newsletter", "email"),
    ("Paid Search",    "bing",       "cpc"),
]

CSV_DEVICES = ["desktop", "mobile", "tablet"]
CSV_COUNTRIES = ["US", "UK", "India", "Canada", "Australia"]
CSV_LANDING_PAGES = [
    "/home", "/about", "/products", "/blog",
    "/pricing", "/contact", "/blog/post-1", "/blog/post-2",
]


def generate_csv(n: int = 2000, days: int = 90) -> pd.DataFrame:
    """Generate n simplified GA4 rows with aggregated daily metrics."""
    end = date.today()
    start = end - timedelta(days=days - 1)
    rows = []
    for _ in range(n):
        d = start + timedelta(days=random.randint(0, days - 1))
        channel, source, medium = random.choice(CSV_CHANNELS)
        sessions = random.randint(1, 50)
        users = random.randint(1, sessions)
        rows.append({
            "session_date":         d,
            "source":               source,
            "medium":               medium,
            "channel":              channel,
            "sessions":             sessions,
            "users":                users,
            "new_users":            random.randint(0, users),
            "pageviews":            sessions * random.randint(1, 8),
            "bounce_rate":          round(random.uniform(0.2, 0.8), 4),
            "avg_session_duration": round(random.uniform(30, 600), 2),
            "device_category":      random.choice(CSV_DEVICES),
            "country":              random.choice(CSV_COUNTRIES),
            "landing_page":         random.choice(CSV_LANDING_PAGES),
        })
    return pd.DataFrame(rows).sort_values("session_date").reset_index(drop=True)

fake = Faker()

CHANNELS = [
    ("Organic Search",  "google",      "organic"),
    ("Organic Search",  "bing",        "organic"),
    ("Paid Search",     "google",      "cpc"),
    ("Direct",          "(direct)",    "(none)"),
    ("Referral",        "reddit.com",  "referral"),
    ("Social",          "twitter.com", "social"),
    ("Email",           "newsletter",  "email"),
]

DEVICES = ["desktop", "mobile", "tablet"]
COUNTRIES = ["United States", "United Kingdom", "Canada", "Germany", "Australia", "India"]
BROWSERS = ["Chrome", "Safari", "Firefox", "Edge"]
OS_LIST  = ["Windows", "macOS", "iOS", "Android", "Linux"]

PAGES = [
    "https://example.com/",
    "https://example.com/blog/",
    "https://example.com/pricing/",
    "https://example.com/about/",
    "https://example.com/contact/",
    "https://example.com/blog/post-1/",
    "https://example.com/blog/post-2/",
    "https://example.com/products/",
]


def _make_row(d: date) -> dict:
    channel, source, medium = random.choice(CHANNELS)
    pv = random.randint(1, 12)
    duration = 0 if random.random() < 0.35 else random.gauss(180, 90)
    bounced = pv == 1 and duration < 10
    converted = random.random() < 0.03
    return {
        "session_date":       d,
        "session_id":         str(uuid.uuid4())[:16],
        "user_pseudo_id":     str(uuid.uuid4())[:16],
        "user_id":            None,
        "country":            random.choice(COUNTRIES),
        "city":               fake.city(),
        "device_category":    random.choice(DEVICES),
        "operating_system":   random.choice(OS_LIST),
        "browser":            random.choice(BROWSERS),
        "channel_grouping":   channel,
        "source":             source,
        "medium":             medium,
        "campaign":           "(not set)" if medium not in ("cpc", "email") else fake.slug(),
        "landing_page":       random.choice(PAGES),
        "sessions":           1,
        "new_users":          int(random.random() < 0.55),
        "pageviews":          pv,
        "bounce":             bounced,
        "session_duration_s": max(0.0, round(duration, 2)),
        "conversions":        int(converted),
        "revenue":            round(random.uniform(10, 250), 2) if converted else 0.0,
    }


def generate(days: int = 90, sessions_per_day: int = 200) -> pd.DataFrame:
    rows = []
    end = date.today()
    start = end - timedelta(days=days - 1)
    for n in range(days):
        d = start + timedelta(days=n)
        count = max(1, int(random.gauss(sessions_per_day, sessions_per_day * 0.15)))
        for _ in range(count):
            rows.append(_make_row(d))
    return pd.DataFrame(rows)


def load(df: pd.DataFrame, mode: str = "full") -> None:
    engine = get_engine()
    with engine.begin() as conn:
        if mode == "full":
            conn.execute(__import__("sqlalchemy").text("TRUNCATE raw_ga4_sessions RESTART IDENTITY"))
    df.to_sql("raw_ga4_sessions", engine, if_exists="append", index=False, method="multi", chunksize=500)
    print(f"Loaded {len(df):,} rows into raw_ga4_sessions ({mode} mode).")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["csv", "full", "incremental"], default="csv")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--rows", type=int, default=2000)
    parser.add_argument("--sessions-per-day", type=int, default=200)
    args = parser.parse_args()

    if args.mode == "csv":
        df = generate_csv(n=args.rows, days=args.days)
        os.makedirs(os.path.dirname(CSV_OUT), exist_ok=True)
        df.to_csv(CSV_OUT, index=False)
        print(f"Generated {len(df)} rows saved to data/raw/ga4_sessions.csv")
    else:
        df = generate(days=args.days, sessions_per_day=args.sessions_per_day)
        load(df, mode=args.mode)


if __name__ == "__main__":
    main()
