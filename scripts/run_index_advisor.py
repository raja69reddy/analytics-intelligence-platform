"""Day 55 — Run index advisor on all tables.

Analyzes missing + unused indexes, prints top 5 recommendations,
and applies the top 3.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sql.optimization.index_advisor import (
    _TABLE_FILTER_COLS,
    analyze_missing_indexes,
    analyze_unused_indexes,
    get_index_usage_stats,
    recommend_indexes,
    apply_recommended_indexes,
)

ALL_TABLES = list(_TABLE_FILTER_COLS.keys())


def run() -> None:
    print("=" * 68)
    print("  Day 55 - Index Advisor")
    print("=" * 68)

    # ── Index usage stats ─────────────────────────────────────────────────────
    print("\n  [1] Index Usage Stats (pg_stat_user_indexes)")
    stats = get_index_usage_stats()
    print(f"  {'Table':<30} {'Index':<35} {'Scans':>6}")
    print("  " + "-" * 73)
    for r in sorted(stats, key=lambda x: -x["idx_scan"])[:15]:
        print(f"  {r['tablename']:<30} {r['indexname']:<35} {r['idx_scan']:>6}")

    # ── Missing indexes per table ─────────────────────────────────────────────
    print("\n  [2] Missing Index Analysis (per table)")
    all_missing: list[dict] = []
    for table in ALL_TABLES:
        recs = analyze_missing_indexes(table)
        all_missing.extend(recs)
        if recs:
            for r in recs:
                print(f"  [{r['priority']}] {r['table']}.{r['column']} — {r['reason'][:60]}")
        else:
            print(f"  [OK]  {table} — no missing indexes detected")

    # ── Unused indexes per table ──────────────────────────────────────────────
    print("\n  [3] Unused Index Analysis (idx_scan < 5)")
    any_unused = False
    for table in ALL_TABLES:
        unused = analyze_unused_indexes(table)
        for u in unused:
            print(f"  [{u['idx_scan']} scans]  {u['tablename']}.{u['indexname']}")
            any_unused = True
    if not any_unused:
        print("  All tracked indexes have adequate usage.")

    # ── Top 5 recommendations ─────────────────────────────────────────────────
    print("\n  [4] Top 5 Prioritised Recommendations")
    recs = recommend_indexes()
    if not recs:
        print("  No missing indexes found — schema is well-indexed.")
    else:
        for i, r in enumerate(recs[:5], 1):
            print(f"  #{i} [{r['priority']}] {r['table']}.{r['column']}")
            print(f"       {r['ddl']}")

    # ── Apply top 3 ───────────────────────────────────────────────────────────
    print("\n  [5] Applying Top 3 Recommended Indexes")
    applied = apply_recommended_indexes(limit=3)
    if not applied:
        print("  Nothing to apply — all recommendations already exist.")
    for a in applied:
        tag = "OK" if a["status"] == "created" else "ERR"
        print(f"  [{tag}] {a['table']}.{a['column']} ({a['elapsed_ms']:.0f} ms)  {a['status']}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 68)
    print("  SUMMARY")
    print("=" * 68)
    print(f"  Tables analyzed      : {len(ALL_TABLES)}")
    print(f"  Missing indexes found: {len(all_missing)}")
    print(f"  Indexes applied      : {sum(1 for a in applied if a['status'] == 'created')}")
    print("=" * 68)


if __name__ == "__main__":
    run()
