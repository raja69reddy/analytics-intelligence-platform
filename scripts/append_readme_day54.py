"""Append Day 54 entry to the README.md progress log (bottom, never reorder)."""
from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"

DAY54 = """
### Day 54 - PostgreSQL Indexes + Query Optimization
- Added 7 composite indexes to all raw/dim/fact tables via `scripts/add_composite_indexes.py`
- Ran `EXPLAIN ANALYZE` on all 8 SQL views; top 3 slowest: vw_traffic 331ms, vw_top_pages 25ms, vw_behavior 14ms
- Optimized top 3 slowest views: `mv_traffic_fast` materialized view -97% (284ms to 8.6ms); vw_top_pages -36%; vw_behavior -13%
- Created `sql/views/mat_daily_summary.sql`: pre-aggregated daily KPIs across all 4 sources, 22 columns, 90-day coverage
- Added Step 5 to `ingestion/run_all.py`: `REFRESH MATERIALIZED VIEW` for both materialized views after each full pipeline run
- Enhanced `utils/db.py`: `pool_timeout=30`, `pool_recycle=3600`, new `pool_status()` function with live metrics
"""

text = README.read_text(encoding="utf-8")
README.write_text(text.rstrip("\n") + "\n" + DAY54, encoding="utf-8")
print("README.md updated with Day 54 progress entry.")
