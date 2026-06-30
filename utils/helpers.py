"""Shared helpers used across ingestion scripts."""
import os
import re
from datetime import date, timedelta
from urllib.parse import urlparse, parse_qs


def date_to_id(d: date) -> int:
    """Convert a date object to an integer key in YYYYMMDD format."""
    return int(d.strftime("%Y%m%d"))


def populate_dim_dates(start: date, end: date) -> None:
    """Insert missing rows into dim_dates for [start, end]."""
    import pandas as pd
    from utils.db import get_engine

    dates = pd.date_range(start, end, freq="D")
    rows = []
    for d in dates:
        rows.append({
            "date_id":        int(d.strftime("%Y%m%d")),
            "full_date":      d.date(),
            "year":           d.year,
            "quarter":        d.quarter,
            "month":          d.month,
            "month_name":     d.strftime("%B"),
            "week":           int(d.strftime("%V")),
            "day_of_week":    d.isoweekday(),
            "day_name":       d.strftime("%A"),
            "is_weekend":     d.isoweekday() >= 6,
            "is_month_start": d.day == 1,
            "is_month_end":   (d + timedelta(days=1)).month != d.month,
        })
    df = pd.DataFrame(rows)
    engine = get_engine()
    # upsert — skip existing
    from sqlalchemy import text
    with engine.begin() as conn:
        for row in df.itertuples(index=False):
            conn.execute(
                text("""
                    INSERT INTO dim_dates
                        (date_id, full_date, year, quarter, month, month_name,
                         week, day_of_week, day_name, is_weekend, is_month_start, is_month_end)
                    VALUES
                        (:date_id, :full_date, :year, :quarter, :month, :month_name,
                         :week, :day_of_week, :day_name, :is_weekend, :is_month_start, :is_month_end)
                    ON CONFLICT (date_id) DO NOTHING
                """),
                row._asdict(),
            )


def parse_url_parts(url: str) -> dict:
    """Return url_path, url_domain, and page_section extracted from a URL."""
    parsed = urlparse(url)
    path = parsed.path or "/"
    section = path.strip("/").split("/")[0] if path.strip("/") else "home"
    return {"url_path": path, "url_domain": parsed.netloc, "page_section": section}


def parse_url(url: str) -> dict:
    """Extract path, domain, and query params from a URL."""
    parsed = urlparse(url)
    return {
        "domain": parsed.netloc,
        "path": parsed.path or "/",
        "query_params": parse_qs(parsed.query),
    }


def get_date_id(d: date) -> int:
    """Convert a date to YYYYMMDD integer format."""
    return int(d.strftime("%Y%m%d"))


def clean_user_agent(ua: str) -> dict:
    """Extract browser and OS from a user agent string."""
    ua = ua or ""

    if "Edg/" in ua or "Edge/" in ua:
        browser = "Edge"
    elif "OPR/" in ua or "Opera" in ua:
        browser = "Opera"
    elif "Chrome/" in ua:
        browser = "Chrome"
    elif "Firefox/" in ua:
        browser = "Firefox"
    elif "Safari/" in ua:
        browser = "Safari"
    else:
        browser = "Other"

    if "Windows" in ua:
        os_name = "Windows"
    elif "Mac OS X" in ua:
        os_name = "macOS"
    elif "Linux" in ua:
        os_name = "Linux"
    elif "Android" in ua:
        os_name = "Android"
    elif "iPhone" in ua or "iPad" in ua:
        os_name = "iOS"
    else:
        os_name = "Other"

    return {"browser": browser, "os": os_name}


def clean_url(url: str) -> str:
    """Normalise a URL: strip trailing slash, lowercase scheme+host."""
    url = url.strip()
    parsed = urlparse(url)
    clean = parsed._replace(scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower())
    return clean.geturl().rstrip("/")
