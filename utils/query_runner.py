"""
Utility for running SQL files or query strings against the web_analytics database.
Prints execution time and returns a DataFrame.
"""
import time
from pathlib import Path

import pandas as pd

from utils.db import get_engine, query_df


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
