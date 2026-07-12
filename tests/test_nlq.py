"""Unit tests for ai/nlq/safety.py and ai/nlq/cache.py."""

import pandas as pd

from ai.nlq.safety import (
    has_dangerous_keywords,
    is_safe_query,
    sanitize_input,
    validate_table_names,
)
from ai.nlq.cache import QueryCache

# ── is_safe_query ──────────────────────────────────────────────────────────────


def test_is_safe_query_select_allowed():
    assert is_safe_query("SELECT * FROM raw_ga4_sessions") is True


def test_is_safe_query_select_with_where():
    sql = "SELECT channel_grouping, COUNT(*) FROM raw_ga4_sessions WHERE session_date > '2024-01-01' GROUP BY 1"
    assert is_safe_query(sql) is True


def test_is_safe_query_drop_rejected():
    assert is_safe_query("DROP TABLE raw_ga4_sessions") is False


def test_is_safe_query_delete_rejected():
    assert is_safe_query("DELETE FROM raw_ga4_sessions") is False


def test_is_safe_query_update_rejected():
    assert is_safe_query("UPDATE raw_ga4_sessions SET sessions = 0") is False


def test_is_safe_query_insert_rejected():
    assert is_safe_query("INSERT INTO raw_ga4_sessions VALUES (1)") is False


def test_is_safe_query_non_select_first_word():
    assert is_safe_query("TRUNCATE TABLE raw_ga4_sessions") is False


# ── has_dangerous_keywords ────────────────────────────────────────────────────


def test_has_dangerous_keywords_drop():
    assert has_dangerous_keywords("DROP TABLE users") is True


def test_has_dangerous_keywords_delete():
    assert has_dangerous_keywords("DELETE FROM sessions WHERE id=1") is True


def test_has_dangerous_keywords_update():
    assert has_dangerous_keywords("UPDATE sessions SET col=1") is True


def test_has_dangerous_keywords_truncate():
    assert has_dangerous_keywords("TRUNCATE sessions") is True


def test_has_dangerous_keywords_clean_select():
    assert has_dangerous_keywords("SELECT * FROM raw_ga4_sessions LIMIT 10") is False


def test_has_dangerous_keywords_case_insensitive():
    assert has_dangerous_keywords("drop table users") is True


# ── sanitize_input ─────────────────────────────────────────────────────────────


def test_sanitize_input_removes_double_dash():
    result = sanitize_input("top sessions -- DROP TABLE")
    assert "--" not in result


def test_sanitize_input_removes_semicolons():
    result = sanitize_input("show sessions; DROP TABLE users")
    assert ";" not in result


def test_sanitize_input_collapses_whitespace():
    result = sanitize_input("  top   5  channels  ")
    assert result == "top 5 channels"


def test_sanitize_input_truncates_long_input():
    long_question = "a" * 600
    result = sanitize_input(long_question)
    assert len(result) <= 500


def test_sanitize_input_normal_question_unchanged():
    q = "What are the top 5 channels by sessions?"
    assert sanitize_input(q) == q


# ── validate_table_names ───────────────────────────────────────────────────────


def test_validate_table_names_valid_raw():
    sql = "SELECT * FROM raw_ga4_sessions"
    assert validate_table_names(sql) is True


def test_validate_table_names_valid_view():
    sql = "SELECT * FROM vw_channel_performance"
    assert validate_table_names(sql) is True


def test_validate_table_names_valid_join():
    sql = "SELECT s.*, d.full_date FROM fct_sessions s JOIN dim_dates d ON s.date_id = d.date_id"
    assert validate_table_names(sql) is True


def test_validate_table_names_invalid_table():
    sql = "SELECT * FROM secret_passwords"
    assert validate_table_names(sql) is False


def test_validate_table_names_invalid_in_join():
    sql = "SELECT * FROM raw_ga4_sessions JOIN hacked_table ON 1=1"
    assert validate_table_names(sql) is False


# ── QueryCache ────────────────────────────────────────────────────────────────


def test_cache_miss_returns_none():
    cache = QueryCache()
    assert cache.get_cached_query("unknown question") is None


def test_cache_hit_returns_entry():
    cache = QueryCache()
    df = pd.DataFrame({"col": [1, 2]})
    cache.cache_query("top channels", "SELECT * FROM raw_ga4_sessions", df)
    entry = cache.get_cached_query("top channels")
    assert entry is not None
    assert entry["sql"] == "SELECT * FROM raw_ga4_sessions"


def test_cache_hit_is_case_insensitive():
    cache = QueryCache()
    df = pd.DataFrame({"x": [1]})
    cache.cache_query("Top Channels", "SELECT 1", df)
    assert cache.get_cached_query("top channels") is not None


def test_cache_clear_empties_store():
    cache = QueryCache()
    cache.cache_query("q", "SELECT 1", pd.DataFrame())
    cache.clear_cache()
    assert cache.get_cached_query("q") is None


def test_cache_stats_hit_rate():
    cache = QueryCache()
    df = pd.DataFrame({"n": [1]})
    cache.cache_query("q1", "SELECT 1", df)
    cache.get_cached_query("q1")  # hit
    cache.get_cached_query("q2")  # miss
    stats = cache.get_cache_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["total_queries"] == 2
    assert stats["hit_rate_pct"] == 50.0


def test_cache_stats_initial_zero():
    cache = QueryCache()
    stats = cache.get_cache_stats()
    assert stats["total_queries"] == 0
    assert stats["hit_rate_pct"] == 0.0
    assert stats["cached_entries"] == 0
