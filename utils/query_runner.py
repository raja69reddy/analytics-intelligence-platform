"""
Utility for running SQL files or query strings against the web_analytics database.
Prints execution time and returns a DataFrame.
"""

import time
from pathlib import Path

import pandas as pd

from utils.db import query_df

_PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"


def run_query(sql_file: str | Path, params: dict | None = None) -> pd.DataFrame:
    """Execute a SQL file and return results as a DataFrame. Prints execution time."""
    path = Path(sql_file)
    sql = path.read_text(encoding="utf-8")
    start = time.perf_counter()
    df = query_df(sql, params=params)
    elapsed = time.perf_counter() - start
    print(f"[query_runner] {path.name}: {len(df)} rows in {elapsed:.3f}s")
    return df


def run_query_string(sql: str, params: dict | None = None) -> pd.DataFrame:
    """Execute a SQL string and return results as a DataFrame. Prints execution time."""
    start = time.perf_counter()
    df = query_df(sql, params=params)
    elapsed = time.perf_counter() - start
    print(f"[query_runner] inline query: {len(df)} rows in {elapsed:.3f}s")
    return df


def run_view(view_name: str) -> pd.DataFrame:
    """Query a database view by name and return results as a DataFrame. Prints execution time."""
    start = time.perf_counter()
    df = query_df(f"SELECT * FROM {view_name}")
    elapsed = time.perf_counter() - start
    print(f"[query_runner] {view_name}: {len(df)} rows in {elapsed:.3f}s")
    return df


def get_view_columns(view_name: str) -> list[str]:
    """Return the list of column names for a database view."""
    df = query_df(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = :view AND table_schema = 'public' "
        "ORDER BY ordinal_position",
        params={"view": view_name},
    )
    return list(df["column_name"])


def save_results_to_csv(df: pd.DataFrame, filename: str) -> Path:
    """Save a DataFrame to data/processed/<filename>. Returns the written path."""
    _PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out = _PROCESSED_DIR / filename
    df.to_csv(out, index=False)
    print(f"[query_runner] saved {len(df)} rows -> {out}")
    return out
