"""Prepend Day 55 entry to CHANGELOG.md (top of file, after heading)."""
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"

DAY55 = """## Day 55 - Query Profiling + DB Maintenance
- Created sql/optimization/query_profiler.py with profile_query(), get_execution_plan(), identify_bottlenecks(), suggest_optimizations(), benchmark_query(), save_profile_results() — full EXPLAIN ANALYZE profiling toolkit
- Profiled all 20 dashboard page queries (5 per page: traffic, behavior, conversions, SEO) via scripts/profile_dashboard_queries.py; ranked slowest to fastest; top slowest: traffic/daily_sessions 270ms, behavior/event_breakdown 37ms, conversions/vw_conversions 25ms; results saved to data/processed/query_profiles.csv
- Created sql/optimization/index_advisor.py with analyze_missing_indexes(), analyze_unused_indexes(), get_index_usage_stats(), recommend_indexes(), apply_recommended_indexes() — pulls pg_stat_user_indexes and compares against known filter-column patterns
- Ran index advisor on all 7 tracked tables via scripts/run_index_advisor.py: found 7 missing indexes across 5 tables; applied top 3 (raw_ga4_sessions.source, raw_server_logs.ip_address, raw_scrape_pages.http_status)
- Created sql/optimization/vacuum_analyzer.py with run_vacuum_analyze(), get_table_bloat(), get_dead_tuples(), run_full_maintenance(), print_maintenance_report() — AUTOCOMMIT VACUUM, bloat estimation via pg_stat_user_tables
- Ran full VACUUM ANALYZE on all 8 tracked tables via scripts/run_db_maintenance.py: raw_scrape_pages bloat 28% to 0%, dim_pages bloat 67% to 0%, 99 dead tuples cleared; all 8 tables OK in 444ms; maintenance log saved to data/processed/pipeline_logs/maintenance_*.json

"""

text = CHANGELOG.read_text(encoding="utf-8")
if text.startswith("# Changelog\n"):
    new_text = "# Changelog\n\n" + DAY55 + text[len("# Changelog\n"):].lstrip("\n")
else:
    new_text = DAY55 + text

CHANGELOG.write_text(new_text, encoding="utf-8")
print("CHANGELOG.md updated with Day 55 entry.")
