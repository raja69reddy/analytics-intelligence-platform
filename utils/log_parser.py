"""
Log parsing utilities for web server access log fields.

Functions:
    parse_ip              - validate and clean an IP address string
    parse_timestamp       - convert a log timestamp to a datetime object
    parse_status_code     - map an HTTP status code to a human-readable category
    parse_response_size   - convert response bytes to kilobytes
    extract_page_from_url - extract the clean path component from a URL
"""
import ipaddress
from datetime import datetime
from urllib.parse import urlparse


def parse_ip(ip: str) -> str | None:
    """Validate and return a clean IP address string.

    Args:
        ip: Raw IP address string from a log entry.

    Returns:
        Normalised IP string if valid, or None for invalid/missing values.
    """
    if not ip:
        return None
    try:
        return str(ipaddress.ip_address(str(ip).strip()))
    except ValueError:
        return None


def parse_timestamp(ts: str | datetime) -> datetime | None:
    """Convert a log timestamp string or datetime to a datetime object.

    Accepts ISO-8601 strings, common log format strings, and existing
    datetime objects (which are returned as-is).

    Args:
        ts: Timestamp string (e.g. '2024-03-15 14:23:01') or datetime.

    Returns:
        A datetime object, or None if the value cannot be parsed.
    """
    if isinstance(ts, datetime):
        return ts
    if not ts:
        return None
    import pandas as pd
    parsed = pd.to_datetime(ts, errors="coerce")
    return None if parsed is pd.NaT else parsed.to_pydatetime()


def parse_status_code(code: int | str) -> str:
    """Map an HTTP status code to a human-readable category string.

    Args:
        code: HTTP status code as an int or string (e.g. 200, '404').

    Returns:
        One of: '2xx Success', '3xx Redirect', '4xx Client Error',
        '5xx Server Error', or 'Unknown' for codes outside those ranges.
    """
    try:
        code = int(code)
    except (TypeError, ValueError):
        return "Unknown"

    if 200 <= code < 300:
        return "2xx Success"
    elif 300 <= code < 400:
        return "3xx Redirect"
    elif 400 <= code < 500:
        return "4xx Client Error"
    elif 500 <= code < 600:
        return "5xx Server Error"
    return "Unknown"


def parse_response_size(size: int | float | str) -> float:
    """Convert a response size in bytes to kilobytes, rounded to 2 decimal places.

    Args:
        size: Response size in bytes (int, float, or numeric string).

    Returns:
        Size in KB as a float. Returns 0.0 for missing or non-numeric values.
    """
    try:
        return round(float(size) / 1024, 2)
    except (TypeError, ValueError):
        return 0.0


def extract_page_from_url(url: str) -> str:
    """Extract the clean path component from a full URL or a bare path string.

    Strips scheme, host, and query string. Normalises an empty path to '/'.

    Args:
        url: Full URL (e.g. 'https://example.com/blog/post-1?ref=tw')
             or a bare path (e.g. '/blog/post-1').

    Returns:
        The path component only (e.g. '/blog/post-1').
    """
    if not url:
        return "/"
    parsed = urlparse(str(url))
    return parsed.path or "/"
