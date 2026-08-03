"""Tests for utils/validator.py and utils/data_profiler.py."""

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.validator import (
    is_valid_date,
    is_valid_url,
    is_positive_number,
    is_valid_percentage,
    is_not_empty,
    validate_dataframe,
)
from utils.data_profiler import (
    profile_dataframe,
    get_null_summary,
    get_duplicate_summary,
    get_outlier_summary,
    get_data_types,
)


# ── is_valid_date ─────────────────────────────────────────────────────────────


class TestIsValidDate:
    def test_iso_format(self):
        assert is_valid_date("2024-01-15") is True

    def test_us_format(self):
        assert is_valid_date("01/15/2024") is True

    def test_datetime_string(self):
        assert is_valid_date("2024-01-15 10:30:00") is True

    def test_invalid_string(self):
        assert is_valid_date("not-a-date") is False

    def test_none(self):
        assert is_valid_date(None) is False

    def test_empty_string(self):
        assert is_valid_date("") is False

    def test_partial_date(self):
        assert is_valid_date("2024-13-40") is False

    def test_timestamp_object(self):
        assert is_valid_date(pd.Timestamp("2024-06-01")) is True


# ── is_valid_url ──────────────────────────────────────────────────────────────


class TestIsValidUrl:
    def test_https_url(self):
        assert is_valid_url("https://example.com/page") is True

    def test_http_url(self):
        assert is_valid_url("http://example.com") is True

    def test_url_with_path(self):
        assert is_valid_url("https://example.com/blog/post-1/") is True

    def test_url_with_query(self):
        assert is_valid_url("https://example.com/search?q=test") is True

    def test_no_scheme(self):
        assert is_valid_url("example.com/page") is False

    def test_path_only(self):
        assert is_valid_url("/blog/post") is False

    def test_empty_string(self):
        assert is_valid_url("") is False

    def test_none(self):
        assert is_valid_url(None) is False

    def test_just_scheme(self):
        assert is_valid_url("https://") is False


# ── is_positive_number ────────────────────────────────────────────────────────


class TestIsPositiveNumber:
    def test_positive_int(self):
        assert is_positive_number(5) is True

    def test_positive_float(self):
        assert is_positive_number(0.001) is True

    def test_zero(self):
        assert is_positive_number(0) is False

    def test_negative(self):
        assert is_positive_number(-1) is False

    def test_numeric_string(self):
        assert is_positive_number("10") is True

    def test_zero_string(self):
        assert is_positive_number("0") is False

    def test_none(self):
        assert is_positive_number(None) is False

    def test_non_numeric_string(self):
        assert is_positive_number("abc") is False


# ── is_valid_percentage ───────────────────────────────────────────────────────


class TestIsValidPercentage:
    def test_zero(self):
        assert is_valid_percentage(0) is True

    def test_half(self):
        assert is_valid_percentage(0.5) is True

    def test_one(self):
        assert is_valid_percentage(1) is True

    def test_above_one(self):
        assert is_valid_percentage(1.5) is False

    def test_negative(self):
        assert is_valid_percentage(-0.1) is False

    def test_none(self):
        assert is_valid_percentage(None) is False

    def test_string_valid(self):
        assert is_valid_percentage("0.75") is True

    def test_string_invalid(self):
        assert is_valid_percentage("abc") is False


# ── is_not_empty ──────────────────────────────────────────────────────────────


class TestIsNotEmpty:
    def test_normal_string(self):
        assert is_not_empty("hello") is True

    def test_empty_string(self):
        assert is_not_empty("") is False

    def test_whitespace(self):
        assert is_not_empty("  ") is False

    def test_none(self):
        assert is_not_empty(None) is False

    def test_nan_string(self):
        assert is_not_empty("nan") is False

    def test_nan_float(self):
        import math
        assert is_not_empty(float("nan")) is False

    def test_integer(self):
        assert is_not_empty(42) is True

    def test_zero(self):
        assert is_not_empty(0) is True


# ── validate_dataframe ────────────────────────────────────────────────────────


class TestValidateDataframe:
    def _sample_df(self):
        return pd.DataFrame({
            "name": ["Alice", "Bob", None, "Dave", "Eve"],
            "score": [95, -5, 80, 0, 100],
            "rate": [0.5, 0.8, 0.3, 0.0, 1.5],  # row 2 has null name, row 4 has rate > 1
        })

    def test_returns_three_values(self):
        df = self._sample_df()
        result = validate_dataframe(df, {}, log_invalid=False)
        assert len(result) == 3

    def test_no_rules_all_pass(self):
        df = self._sample_df()
        valid, invalid, summary = validate_dataframe(df, {}, log_invalid=False)
        assert len(valid) == len(df)
        assert summary["failed"] == 0

    def test_null_rule(self):
        df = self._sample_df()
        rules = {"name_null": df["name"].isna()}
        valid, invalid, summary = validate_dataframe(df, rules, log_invalid=False)
        assert summary["failed"] == 1
        assert summary["passed"] == 4
        assert "_errors" in invalid.columns
        assert "name_null" in invalid["_errors"].iloc[0]

    def test_negative_score_rule(self):
        df = self._sample_df()
        rules = {"score_not_positive": df["score"] <= 0}
        valid, invalid, summary = validate_dataframe(df, rules, log_invalid=False)
        assert summary["failed"] == 2  # Bob (-5) and Dave (0)

    def test_combined_rules(self):
        df = self._sample_df()
        rules = {
            "name_null": df["name"].isna(),
            "rate_out_of_range": (df["rate"] < 0) | (df["rate"] > 1),
        }
        valid, invalid, summary = validate_dataframe(df, rules, log_invalid=False)
        # row 2 has null name, row 4 has rate > 1 — two distinct rows
        assert summary["failed"] == 2

    def test_error_counts_in_summary(self):
        df = self._sample_df()
        rules = {"score_not_positive": df["score"] <= 0}
        _, _, summary = validate_dataframe(df, rules, log_invalid=False)
        assert "score_not_positive" in summary["error_counts"]
        assert summary["error_counts"]["score_not_positive"] == 2


# ── data_profiler ─────────────────────────────────────────────────────────────


class TestGetNullSummary:
    def test_no_nulls(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        result = get_null_summary(df)
        assert result["a"]["null_count"] == 0
        assert result["b"]["null_pct"] == 0.0

    def test_with_nulls(self):
        df = pd.DataFrame({"a": [1, None, 3, None, 5]})
        result = get_null_summary(df)
        assert result["a"]["null_count"] == 2
        assert result["a"]["null_pct"] == 40.0

    def test_all_null(self):
        df = pd.DataFrame({"a": [None, None]})
        result = get_null_summary(df)
        assert result["a"]["null_pct"] == 100.0


class TestGetDuplicateSummary:
    def test_no_duplicates(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        result = get_duplicate_summary(df)
        assert result["duplicate_count"] == 0
        assert result["unique_count"] == 3

    def test_with_duplicates(self):
        df = pd.DataFrame({"a": [1, 2, 2, 3, 3, 3]})
        result = get_duplicate_summary(df)
        assert result["duplicate_count"] == 3

    def test_empty_df(self):
        df = pd.DataFrame({"a": pd.Series([], dtype=int)})
        result = get_duplicate_summary(df)
        assert result["duplicate_count"] == 0


class TestGetOutlierSummary:
    def test_detects_outliers(self):
        # Normal cluster with one far outlier
        data = [10, 11, 10, 12, 11, 10, 500]
        df = pd.DataFrame({"val": data})
        result = get_outlier_summary(df)
        assert result["val"]["outlier_count"] >= 1

    def test_no_outliers(self):
        df = pd.DataFrame({"val": [1, 2, 3, 4, 5, 6, 7, 8]})
        result = get_outlier_summary(df)
        assert result.get("val", {}).get("outlier_count", 0) == 0

    def test_skips_non_numeric(self):
        df = pd.DataFrame({"text": ["a", "b", "c", "d", "e"]})
        result = get_outlier_summary(df)
        assert "text" not in result


class TestGetDataTypes:
    def test_returns_all_columns(self):
        df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
        result = get_data_types(df)
        assert "a" in result
        assert "b" in result

    def test_unique_count(self):
        df = pd.DataFrame({"a": [1, 1, 2, 3]})
        result = get_data_types(df)
        assert result["a"]["unique_count"] == 3

    def test_sample_values_not_empty(self):
        df = pd.DataFrame({"a": [10, 20, 30]})
        result = get_data_types(df)
        assert len(result["a"]["sample_values"]) > 0


class TestProfileDataframe:
    def _make_df(self):
        return pd.DataFrame({
            "session": range(100),
            "duration": [float(i) for i in range(100)],
            "channel": (["organic"] * 60 + ["paid"] * 40),
            "missing": ([None] * 10 + list(range(90))),
        })

    def test_keys_present(self):
        df = self._make_df()
        profile = profile_dataframe(df, name="test")
        for key in ("name", "row_count", "column_count", "null_summary",
                    "duplicate_summary", "outlier_summary", "data_types",
                    "statistics", "quality"):
            assert key in profile, f"Missing key: {key}"

    def test_row_count(self):
        df = self._make_df()
        profile = profile_dataframe(df, name="test")
        assert profile["row_count"] == 100

    def test_quality_score_range(self):
        df = self._make_df()
        profile = profile_dataframe(df, name="test")
        assert 0 <= profile["quality"]["score"] <= 100

    def test_null_detected(self):
        df = self._make_df()
        profile = profile_dataframe(df, name="test")
        assert profile["null_summary"]["missing"]["null_count"] == 10

    def test_name_stored(self):
        df = self._make_df()
        profile = profile_dataframe(df, name="mytest")
        assert profile["name"] == "mytest"
