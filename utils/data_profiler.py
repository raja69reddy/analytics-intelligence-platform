"""DataFrame statistical profiler for ingestion quality monitoring.

Public API:
    profile_dataframe(df, name)   — full statistical profile dict
    get_null_summary(df)          — null counts and percentages per column
    get_duplicate_summary(df)     — fully-duplicate row counts
    get_outlier_summary(df)       — IQR-based outlier detection per numeric column
    get_data_types(df)            — dtype and unique counts per column
    save_profile_report(df, name) — save JSON report to data/processed/profiles/
    load_profile(name)            — load a saved profile by source name
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

_PROFILES_DIR = (
    Path(__file__).resolve().parent.parent / "data" / "processed" / "profiles"
)


def get_null_summary(df: pd.DataFrame) -> dict[str, dict]:
    """Return null count and percentage per column."""
    total = len(df)
    return {
        col: {
            "null_count": int(df[col].isna().sum()),
            "null_pct": round(df[col].isna().sum() / max(total, 1) * 100, 2),
        }
        for col in df.columns
    }


def get_duplicate_summary(df: pd.DataFrame) -> dict:
    """Return fully-duplicate row counts for df."""
    n_dup = int(df.duplicated().sum())
    total = len(df)
    return {
        "duplicate_count": n_dup,
        "duplicate_pct": round(n_dup / max(total, 1) * 100, 2),
        "unique_count": total - n_dup,
    }


def get_outlier_summary(df: pd.DataFrame) -> dict[str, dict]:
    """Detect outliers per numeric column using the IQR method (1.5×IQR fence)."""
    result: dict[str, dict] = {}
    for col in df.select_dtypes(include="number").columns:
        series = df[col].dropna()
        if len(series) < 4:
            continue
        q1, q3 = float(series.quantile(0.25)), float(series.quantile(0.75))
        iqr = q3 - q1
        if iqr == 0:
            continue
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        n_out = int(((series < lower) | (series > upper)).sum())
        result[col] = {
            "outlier_count": n_out,
            "outlier_pct": round(n_out / max(len(series), 1) * 100, 2),
            "lower_fence": round(lower, 4),
            "upper_fence": round(upper, 4),
        }
    return result


def get_data_types(df: pd.DataFrame) -> dict[str, dict]:
    """Return dtype string, unique count, and 3 sample values per column."""
    return {
        col: {
            "dtype": str(df[col].dtype),
            "unique_count": int(df[col].nunique()),
            "sample_values": [str(v) for v in df[col].dropna().head(3).tolist()],
        }
        for col in df.columns
    }


def profile_dataframe(df: pd.DataFrame, name: str = "unnamed") -> dict:
    """Return a full statistical profile of df as a serialisable dict."""
    null_summary = get_null_summary(df)
    dup_summary = get_duplicate_summary(df)
    outlier_summary = get_outlier_summary(df)

    # Numeric describe stats
    num_df = df.select_dtypes(include="number")
    statistics: dict = {}
    if not num_df.empty:
        desc = num_df.describe().to_dict()
        statistics = {
            col: {k: round(float(v), 4) for k, v in vals.items()}
            for col, vals in desc.items()
        }

    # Aggregate quality metrics
    avg_null_pct = round(
        sum(v["null_pct"] for v in null_summary.values()) / max(len(null_summary), 1), 2
    )
    cols_with_nulls = sum(1 for v in null_summary.values() if v["null_count"] > 0)
    avg_outlier_pct = round(
        sum(v["outlier_pct"] for v in outlier_summary.values())
        / max(len(outlier_summary), 1),
        2,
    ) if outlier_summary else 0.0

    quality_score = max(
        0,
        round(
            100
            - avg_null_pct
            - dup_summary["duplicate_pct"]
            - avg_outlier_pct * 0.5,
            1,
        ),
    )

    return {
        "name": name,
        "profiled_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "row_count": len(df),
        "column_count": len(df.columns),
        "columns": list(df.columns),
        "null_summary": null_summary,
        "duplicate_summary": dup_summary,
        "outlier_summary": outlier_summary,
        "data_types": get_data_types(df),
        "statistics": statistics,
        "quality": {
            "score": quality_score,
            "avg_null_pct": avg_null_pct,
            "cols_with_nulls": cols_with_nulls,
            "duplicate_pct": dup_summary["duplicate_pct"],
            "avg_outlier_pct": avg_outlier_pct,
        },
    }


def save_profile_report(df: pd.DataFrame, name: str) -> Path:
    """Profile df and save a JSON report to data/processed/profiles/{name}_profile.json."""
    _PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    profile = profile_dataframe(df, name=name)
    out_path = _PROFILES_DIR / f"{name}_profile.json"
    out_path.write_text(json.dumps(profile, indent=2, default=str))
    return out_path


def load_profile(name: str) -> dict | None:
    """Load a saved profile by source name. Returns None if not found."""
    path = _PROFILES_DIR / f"{name}_profile.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None
