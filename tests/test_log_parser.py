"""
Unit tests for utils/log_parser.py — 15 tests covering all 5 parsing functions.
"""
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.log_parser import (
    extract_page_from_url,
    parse_ip,
    parse_response_size,
    parse_status_code,
    parse_timestamp,
)


# ── parse_ip ──────────────────────────────────────────────────────────────

class TestParseIp:
    def test_valid_ipv4(self):
        assert parse_ip("192.168.1.1") == "192.168.1.1"

    def test_valid_public_ip(self):
        assert parse_ip("8.8.8.8") == "8.8.8.8"

    def test_strips_whitespace(self):
        assert parse_ip("  10.0.0.1  ") == "10.0.0.1"

    def test_invalid_ip_returns_none(self):
        assert parse_ip("999.999.999.999") is None

    def test_empty_string_returns_none(self):
        assert parse_ip("") is None


# ── parse_timestamp ───────────────────────────────────────────────────────

class TestParseTimestamp:
    def test_string_iso_format(self):
        result = parse_timestamp("2024-03-15 14:23:01")
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 3
        assert result.day == 15

    def test_datetime_passthrough(self):
        dt = datetime(2024, 6, 1, 12, 0, 0)
        assert parse_timestamp(dt) is dt

    def test_invalid_string_returns_none(self):
        assert parse_timestamp("not-a-date") is None

    def test_none_returns_none(self):
        assert parse_timestamp(None) is None

    def test_date_only_string(self):
        result = parse_timestamp("2024-01-01")
        assert isinstance(result, datetime)
        assert result.year == 2024


# ── parse_status_code ─────────────────────────────────────────────────────

class TestParseStatusCode:
    def test_200_is_success(self):
        assert parse_status_code(200) == "2xx Success"

    def test_301_is_redirect(self):
        assert parse_status_code(301) == "3xx Redirect"

    def test_404_is_client_error(self):
        assert parse_status_code(404) == "4xx Client Error"

    def test_500_is_server_error(self):
        assert parse_status_code(500) == "5xx Server Error"

    def test_string_code_works(self):
        assert parse_status_code("200") == "2xx Success"


# ── parse_response_size ───────────────────────────────────────────────────

class TestParseResponseSize:
    def test_1024_bytes_is_1_kb(self):
        assert parse_response_size(1024) == 1.0

    def test_5120_bytes_is_5_kb(self):
        assert parse_response_size(5120) == 5.0

    def test_rounding(self):
        assert parse_response_size(1500) == 1.46

    def test_zero_bytes(self):
        assert parse_response_size(0) == 0.0

    def test_invalid_returns_zero(self):
        assert parse_response_size(None) == 0.0


# ── extract_page_from_url ─────────────────────────────────────────────────

class TestExtractPageFromUrl:
    def test_full_url_strips_host(self):
        assert extract_page_from_url("https://example.com/blog/post-1") == "/blog/post-1"

    def test_url_with_query_string(self):
        assert extract_page_from_url("https://example.com/search?q=hello") == "/search"

    def test_bare_path_unchanged(self):
        assert extract_page_from_url("/home") == "/home"

    def test_root_path(self):
        assert extract_page_from_url("/") == "/"

    def test_empty_string_returns_root(self):
        assert extract_page_from_url("") == "/"
