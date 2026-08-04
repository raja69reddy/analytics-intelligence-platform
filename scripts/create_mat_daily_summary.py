"""Day 54 — Apply mat_daily_summary materialized view to PostgreSQL.

Reads sql/views/mat_daily_summary.sql, executes it, then creates
covering indexes and verifies row count.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.db import get_engine, query_df
from sqlalchemy import text

SQL_FILE = Path(__file__).resolve().parent.parent / "sql" / "views" / "mat_daily_summary.sql"

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_mat_daily_date     ON mat_daily_summary (report_date)",
    "CREATE INDEX IF NOT EXISTS idx_mat_daily_yr_mo    ON mat_daily_summary (year, month)",
    "CREATE INDEX IF NOT EXISTS idx_mat_daily_weekend  ON mat_daily_summary (is_weekend)",
]


def run() -> None:
    engine = get_engine()
    ddl = SQL_FILE.read_text(encoding="utf-8")

    print("=" * 60)
    print("  Day 54 — Creating mat_daily_summary")
    print("=" * 60)

    t0 = time.perf_counter()
    with engine.begin() as conn:
        conn.execute(text(ddl))
    elapsed_create = (time.perf_counter() - t0) * 1000
    print(f"  Materialized view created  ({elapsed_create:.0f} ms)")

    print("  Adding indexes...")
    with engine.begin() as conn:
        for idx_sql in INDEXES:
            conn.execute(text(idx_sql))
            name = idx_sql.split("EXISTS")[1].split("ON")[0].strip()
            print(f"    OK  {name}")

    # Verify
    t1 = time.perf_counter()
    df = query_df("SELECT * FROM mat_daily_summary")
    query_ms = (time.perf_counter() - t1) * 1000
    print(f"\n  Verification:")
    print(f"    Rows           : {len(df)}")
    print(f"    Columns        : {len(df.columns)}")
    print(f"    Date range     : {df['report_date'].min()} to {df['report_date'].max()}")
    print(f"    Total sessions : {int(df['total_sessions'].sum()):,}")
    print(f"    Total revenue  : ${df['total_revenue'].sum():,.2f}")
    print(f"    Query time     : {query_ms:.1f} ms")
    print("=" * 60)
    print("\nmat_daily_summary created and ready.")


if __name__ == "__main__":
    run()
