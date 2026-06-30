"""Shared utility helpers used across ingestion and mock-data scripts.

Functions cover three areas:
  - Date utilities  : date_to_id, get_date_id, populate_dim_dates
  - URL parsing     : parse_url, parse_url_parts, clean_url
  - UA parsing      : clean_user_agent
"""
import os
import re
from datetime import date, timedelta
from urllib.parse import urlparse, parse_qs


def date_to_id(d: date) -> int:
    """Convert a date object to an integer primary key in YYYYMMDD format.

    Used to join fact tables to dim_dates without storing full DATE objects
    in every fact row. Example: date(2024, 3, 15) → 20240315.

    Args:
        d: A Python date object.

    Returns:
        An integer of the form YYYYMMDD.
    """
    return int(d.strftime("%Y%m%d"))


def populate_dim_dates(start: date, end: date) -> None:
    """Insert missing rows into dim_dates for every date in [start, end].

    Safe to run multiple times — uses ON CONFLICT DO NOTHING so existing
    rows are never overwritten. Computes all calendar attributes (week,
    quarter, is_weekend, is_month_start, is_month_end) from the date itself.

    Args:
        start: First date to insert (inclusive).
        end:   Last date to insert (inclusive).
    """
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
    """Extract path, domain, and top-level section from a URL.

    Used by ingestion scripts to populate dim_pages with structured
    fields derived from raw URL strings.

    Args:
        url: A full URL string, e.g. 'https://example.com/blog/post-1/'.

    Returns:
        A dict with keys: url_path (str), url_domain (str), page_section (str).
        page_section is the first non-empty path segment, or 'home' for '/'.
    """
    parsed = urlparse(url)
    path = parsed.path or "/"
    section = path.strip("/").split("/")[0] if path.strip("/") else "home"
    return {"url_path": path, "url_domain": parsed.netloc, "page_section": section}


def parse_url(url: str) -> dict:
    """Parse a URL into its domain, path, and decoded query parameters.

    Args:
        url: A full URL string.

    Returns:
        A dict with keys: domain (str), path (str), query_params (dict of lists).
    """
    parsed = urlparse(url)
    return {
        "domain": parsed.netloc,
        "path": parsed.path or "/",
        "query_params": parse_qs(parsed.query),
    }


def get_date_id(d: date) -> int:
    """Convert a date to YYYYMMDD integer format.

    Alias of date_to_id — use either name; both return the same value.

    Args:
        d: A Python date object.

    Returns:
        An integer of the form YYYYMMDD.
    """
    return int(d.strftime("%Y%m%d"))


def clean_user_agent(ua: str) -> dict:
    """Classify a raw user-agent string into browser and OS labels.

    Applies a priority-ordered substring match. Edge/OPR must be checked
    before Chrome/Safari because those browsers include 'Chrome' or 'Safari'
    in their UA strings.

    Args:
        ua: A raw HTTP User-Agent header value. None-safe (treats None as '').

    Returns:
        A dict with keys: browser (str), os (str).
        Unknown values default to 'Other'.
    """
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
    """Normalise a URL by lowercasing scheme+host and stripping trailing slashes.

    Args:
        url: Any URL string.

    Returns:
        A normalised URL string suitable for use as a deduplication key.
    """
    url = url.strip()
    parsed = urlparse(url)
    clean = parsed._replace(scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower())
    return clean.geturl().rstrip("/")
