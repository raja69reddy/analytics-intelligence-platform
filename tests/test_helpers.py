"""Unit tests for utils/helpers.py — parse_url, get_date_id, clean_user_agent."""
import sys
import os
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.helpers import parse_url, get_date_id, clean_user_agent


# ── parse_url ──────────────────────────────────────────────────────────────

def test_parse_url_basic():
    result = parse_url("https://example.com/blog/post-1/")
    assert result["domain"] == "example.com"
    assert result["path"] == "/blog/post-1/"
    assert result["query_params"] == {}


def test_parse_url_with_query_string():
    result = parse_url("https://example.com/search?q=python&page=2")
    assert result["domain"] == "example.com"
    assert result["path"] == "/search"
    assert result["query_params"]["q"] == ["python"]
    assert result["query_params"]["page"] == ["2"]


def test_parse_url_root_path():
    result = parse_url("https://example.com/")
    assert result["domain"] == "example.com"
    assert result["path"] == "/"
    assert result["query_params"] == {}


# ── get_date_id ────────────────────────────────────────────────────────────

def test_get_date_id_regular():
    assert get_date_id(date(2024, 3, 15)) == 20240315


def test_get_date_id_start_of_year():
    assert get_date_id(date(2023, 1, 1)) == 20230101


def test_get_date_id_end_of_year():
    assert get_date_id(date(2025, 12, 31)) == 20251231


# ── clean_user_agent ───────────────────────────────────────────────────────

def test_clean_user_agent_chrome_windows():
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    result = clean_user_agent(ua)
    assert result["browser"] == "Chrome"
    assert result["os"] == "Windows"


def test_clean_user_agent_firefox_linux():
    ua = "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0"
    result = clean_user_agent(ua)
    assert result["browser"] == "Firefox"
    assert result["os"] == "Linux"


def test_clean_user_agent_unknown():
    result = clean_user_agent("")
    assert result["browser"] == "Other"
    assert result["os"] == "Other"
