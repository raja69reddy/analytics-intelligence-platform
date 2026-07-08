"""
System health check for the Analytics Intelligence Platform.
Checks PostgreSQL, tables, views, AI models, and report artifacts.
Prints a color-coded report and returns an overall score.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass
class HealthItem:
    name: str
    passed: bool
    detail: str = ""

    def __repr__(self) -> str:
        status = "[ OK ]" if self.passed else "[FAIL]"
        tail   = f" -- {self.detail}" if self.detail else ""
        return f"  {status} {self.name}{tail}"


# ── Individual checks ─────────────────────────────────────────────────────────

def _check_postgres() -> HealthItem:
    try:
        from utils.db import query_df
        df = query_df("SELECT version() AS v")
        return HealthItem("PostgreSQL connection", True, str(df["v"].iloc[0])[:60])
    except Exception as exc:
        return HealthItem("PostgreSQL connection", False, str(exc)[:80])


def _check_tables() -> list[HealthItem]:
    tables = [
        "raw_ga4_sessions",
        "raw_server_logs",
        "raw_clickstream_events",
        "raw_scrape_pages",
        "dim_dates",
        "alerts",
    ]
    items = []
    try:
        from utils.db import query_df
        for tbl in tables:
            try:
                df = query_df(f"SELECT COUNT(*) AS n FROM {tbl}")
                n  = int(df["n"].iloc[0])
                items.append(HealthItem(f"Table: {tbl}", True, f"{n:,} rows"))
            except Exception as exc:
                items.append(HealthItem(f"Table: {tbl}", False, str(exc)[:60]))
    except Exception as exc:
        items.append(HealthItem("Tables (DB unavailable)", False, str(exc)[:60]))
    return items


def _check_views() -> list[HealthItem]:
    views = [
        "vw_daily_traffic",
        "vw_channel_performance",
        "vw_top_pages",
        "vw_conversions",
        "vw_device_breakdown",
        "vw_seo",
    ]
    items = []
    try:
        from utils.db import query_df
        for vw in views:
            try:
                df = query_df(f"SELECT * FROM {vw} LIMIT 1")
                items.append(HealthItem(f"View: {vw}", True, f"{len(df.columns)} columns"))
            except Exception as exc:
                items.append(HealthItem(f"View: {vw}", False, str(exc)[:60]))
    except Exception as exc:
        items.append(HealthItem("Views (DB unavailable)", False, str(exc)[:60]))
    return items


def _check_ai_models() -> list[HealthItem]:
    model_dir = ROOT / "ai" / "models"
    models = [
        "traffic_anomaly_model.pkl",
        "traffic_forecast_model.pkl",
        "conversion_forecast_model.pkl",
    ]
    items = []
    for m in models:
        path = model_dir / m
        if path.exists():
            size_kb = path.stat().st_size // 1024
            items.append(HealthItem(f"Model: {m}", True, f"{size_kb} KB"))
        else:
            items.append(HealthItem(f"Model: {m}", False, "file not found"))
    return items


def _check_smart_alerts() -> HealthItem:
    try:
        from ai.smart_alerts.detector import SmartAlertDetector
        from ai.smart_alerts.alert_models import Alert, AlertSummary, Severity
        d = SmartAlertDetector()
        return HealthItem("Smart Alerts module", True, "SmartAlertDetector importable")
    except Exception as exc:
        return HealthItem("Smart Alerts module", False, str(exc)[:60])


def _check_report_artifacts() -> list[HealthItem]:
    artifacts = {
        "Weekly digest dir":  ROOT / "data" / "processed" / "digests",
        "Alerts dir":         ROOT / "data" / "processed" / "alerts",
        "Explore notebook":   ROOT / "analysis" / "explore.ipynb",
        "DATA_DICTIONARY.md": ROOT / "data" / "DATA_DICTIONARY.md",
    }
    items = []
    for name, path in artifacts.items():
        exists = path.exists()
        detail = "exists" if exists else "missing"
        items.append(HealthItem(name, exists, detail))
    return items


def _check_dashboard_pages() -> list[HealthItem]:
    pages_dir = ROOT / "dashboard" / "pages"
    expected  = [
        "1_traffic.py", "2_behavior.py", "3_conversions.py",
        "4_seo.py", "5_nlq.py", "6_reports.py", "7_pipeline.py", "8_forecasting.py",
    ]
    items = []
    for pg in expected:
        path = pages_dir / pg
        exists = path.exists()
        items.append(HealthItem(f"Dashboard: {pg}", exists, "exists" if exists else "missing"))
    return items


# ── Main run ──────────────────────────────────────────────────────────────────

def run_health_check() -> dict:
    """Run all health checks. Returns dict with items, score, and generated_at."""
    sections: dict[str, list[HealthItem]] = {
        "PostgreSQL":       [_check_postgres()],
        "Tables":           _check_tables(),
        "Views":            _check_views(),
        "AI Models":        _check_ai_models(),
        "Smart Alerts":     [_check_smart_alerts()],
        "Report Artifacts": _check_report_artifacts(),
        "Dashboard Pages":  _check_dashboard_pages(),
    }

    all_items = [item for grp in sections.values() for item in grp]
    total     = len(all_items)
    passed    = sum(1 for i in all_items if i.passed)
    score     = round(passed / total * 100) if total > 0 else 0

    return {
        "sections":     sections,
        "all_items":    all_items,
        "total":        total,
        "passed":       passed,
        "failed":       total - passed,
        "score":        score,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def print_report(result: dict) -> None:
    sep = "=" * 58
    print(f"\n{sep}")
    print("  ANALYTICS INTELLIGENCE PLATFORM -- HEALTH CHECK")
    print(sep)
    print(f"  Generated: {result['generated_at']}")
    print(sep)

    for section_name, items in result["sections"].items():
        print(f"\n  [{section_name}]")
        for item in items:
            print(repr(item))

    score = result["score"]
    print(f"\n{sep}")
    print(f"  OVERALL SCORE: {result['passed']}/{result['total']} checks passed  ({score}/100)")
    if score == 100:
        print("  STATUS: ALL SYSTEMS HEALTHY")
    elif score >= 80:
        print("  STATUS: HEALTHY (minor issues)")
    elif score >= 60:
        print("  STATUS: DEGRADED (attention needed)")
    else:
        print("  STATUS: UNHEALTHY (immediate action required)")
    print(sep)


if __name__ == "__main__":
    result = run_health_check()
    print_report(result)
    sys.exit(0 if result["failed"] == 0 else 1)
