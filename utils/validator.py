"""Reusable data validation helpers for ingestion pipelines.

Each function returns True for a valid value, False otherwise. For bulk
validation use validate_dataframe() which applies named rules to a DataFrame
and returns (valid_df, invalid_df, summary_dict).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

log = logging.getLogger(__name__)

_VAL_SUMMARY = (
    Path(__file__).resolve().parent.parent / "data" / "processed" / "validation_summary.json"
)
_LOG_DIR = Path(__file__).resolve().parent.parent / "data" / "processed" / "logs"

_URL_RE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)


# ── Scalar validators ──────────────────────────────────────────────────────────

def is_valid_date(value) -> bool:
    """Return True if value can be parsed as a date."""
    if value is None:
        return False
    try:
        pd.to_datetime(value)
        return True
    except Exception:
        return False


def is_valid_url(value) -> bool:
    """Return True if value is a non-empty string with valid scheme and host."""
    if not value or not isinstance(value, str):
        return False
    parsed = urlparse(value.strip())
    return bool(parsed.scheme) and bool(parsed.netloc)


def is_positive_number(value) -> bool:
    """Return True if value is numeric and strictly > 0."""
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def is_valid_percentage(value) -> bool:
    """Return True if value is numeric and within [0.0, 1.0]."""
    try:
        f = float(value)
        return 0.0 <= f <= 1.0
    except (TypeError, ValueError):
        return False


def is_not_empty(value) -> bool:
    """Return True if value is not None, NaN, or blank string."""
    if value is None:
        return False
    if isinstance(value, float):
        import math
        return not math.isnan(value)
    return str(value).strip() not in ("", "nan", "None", "NaN")


# ── Bulk DataFrame validator ───────────────────────────────────────────────────

def validate_dataframe(
    df: pd.DataFrame,
    rules: dict[str, pd.Series],
    source: str = "unknown",
    log_invalid: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Apply named boolean masks (True = FAIL) to df.

    Parameters
    ----------
    df       : Input DataFrame (unmodified).
    rules    : Mapping of rule_name → boolean Series (True where the row fails).
    source   : Label used for log file naming and the validation summary JSON.
    log_invalid : If True, save invalid rows to data/processed/logs/.

    Returns
    -------
    valid_df   : Rows passing all checks.
    invalid_df : Rows failing at least one check (with "_errors" column).
    summary    : Dict with keys: passed, failed, error_counts, last_run.
    """
    flags = pd.DataFrame(rules)
    fail_mask = flags.any(axis=1)

    invalid_df = pd.DataFrame()
    if fail_mask.any():
        invalid_df = df[fail_mask].copy()
        invalid_df["_errors"] = flags[fail_mask].apply(
            lambda r: ", ".join(r.index[r].tolist()), axis=1
        )
        if log_invalid:
            _LOG_DIR.mkdir(parents=True, exist_ok=True)
            ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
            path = _LOG_DIR / f"{source}_invalid_{ts}.csv"
            invalid_df.to_csv(path, index=False)
            log.warning("Saved %d invalid rows → %s", fail_mask.sum(), path.name)

    summary: dict = {
        "passed": int((~fail_mask).sum()),
        "failed": int(fail_mask.sum()),
        "error_counts": {k: int(v) for k, v in flags.sum().items() if v > 0},
        "last_run": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    _save_summary(source, summary)
    return df[~fail_mask].copy(), invalid_df, summary


# ── Summary persistence ────────────────────────────────────────────────────────

def _save_summary(source: str, summary: dict) -> None:
    data: dict = {}
    if _VAL_SUMMARY.exists():
        try:
            data = json.loads(_VAL_SUMMARY.read_text())
        except Exception:
            pass
    data[source] = summary
    _VAL_SUMMARY.write_text(json.dumps(data, indent=2))


def load_validation_summary() -> dict:
    """Return the latest validation summary dict (keyed by source name)."""
    if not _VAL_SUMMARY.exists():
        return {}
    try:
        return json.loads(_VAL_SUMMARY.read_text())
    except Exception:
        return {}


def latest_invalid_file(source: str) -> Path | None:
    """Return the most recent invalid-rows CSV path for a given source, or None."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(_LOG_DIR.glob(f"{source}_invalid_*.csv"), reverse=True)
    return files[0] if files else None
