"""Tests for pipeline_monitor, alerts, and run_all dry-run."""
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent


# ── run_all.py --dry-run ─────────────────────────────────────────────────────

class TestRunAllDryRun:
    def test_dry_run_exits_zero(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "ingestion" / "run_all.py"), "--mode", "full", "--dry-run"],
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0, f"dry-run failed: {result.stderr}"

    def test_dry_run_output_contains_ok(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "ingestion" / "run_all.py"), "--mode", "full", "--dry-run"],
            capture_output=True, text=True, timeout=60,
        )
        assert "OK" in result.stdout or "ok" in result.stdout.lower()

    def test_pipeline_flag_ga4_only(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "ingestion" / "run_all.py"),
             "--mode", "full", "--pipeline", "ga4", "--dry-run"],
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0
        assert "ga4" in result.stdout.lower()

    def test_pipeline_flag_scraper_only(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "ingestion" / "run_all.py"),
             "--mode", "full", "--pipeline", "scraper", "--dry-run"],
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0

    def test_dry_run_saves_log_file(self):
        log_dir = ROOT / "data" / "processed" / "pipeline_logs"
        before_files = set(log_dir.glob("run_*.log")) if log_dir.exists() else set()
        subprocess.run(
            [sys.executable, str(ROOT / "ingestion" / "run_all.py"), "--mode", "full", "--dry-run"],
            capture_output=True, text=True, timeout=60,
        )
        after_files = set(log_dir.glob("run_*.log"))
        assert len(after_files) > len(before_files), "No new log file created"


# ── pipeline_monitor ──────────────────────────────────────────────────────────

class TestPipelineMonitor:
    def test_log_pipeline_run_returns_dict(self, tmp_path, monkeypatch):
        import utils.pipeline_monitor as pm
        monkeypatch.setattr(pm, "_HISTORY_FILE", tmp_path / "history.json")
        record = pm.log_pipeline_run("ga4", 1000, 2.5, "success")
        assert record["name"] == "ga4"
        assert record["rows"] == 1000
        assert record["status"] == "success"
        assert "timestamp" in record

    def test_get_pipeline_history_returns_list(self, tmp_path, monkeypatch):
        import utils.pipeline_monitor as pm
        monkeypatch.setattr(pm, "_HISTORY_FILE", tmp_path / "history.json")
        pm.log_pipeline_run("ga4", 1000, 2.5, "success")
        pm.log_pipeline_run("server_logs", 5000, 4.1, "success")
        history = pm.get_pipeline_history(limit=10)
        assert isinstance(history, list)
        assert len(history) == 2

    def test_get_pipeline_history_newest_first(self, tmp_path, monkeypatch):
        import utils.pipeline_monitor as pm
        monkeypatch.setattr(pm, "_HISTORY_FILE", tmp_path / "history.json")
        pm.log_pipeline_run("ga4", 100, 1.0, "success")
        pm.log_pipeline_run("scraper", 50, 0.5, "success")
        history = pm.get_pipeline_history()
        assert history[0]["name"] == "scraper"

    def test_get_pipeline_history_respects_limit(self, tmp_path, monkeypatch):
        import utils.pipeline_monitor as pm
        monkeypatch.setattr(pm, "_HISTORY_FILE", tmp_path / "history.json")
        for i in range(15):
            pm.log_pipeline_run("ga4", i * 100, 1.0, "success")
        history = pm.get_pipeline_history(limit=5)
        assert len(history) == 5

    def test_get_pipeline_stats_calculates_correctly(self, tmp_path, monkeypatch):
        import utils.pipeline_monitor as pm
        monkeypatch.setattr(pm, "_HISTORY_FILE", tmp_path / "history.json")
        pm.log_pipeline_run("ga4", 1000, 2.0, "success")
        pm.log_pipeline_run("ga4", 0, 0.5, "error: test")
        stats = pm.get_pipeline_stats()
        assert "ga4" in stats
        assert stats["ga4"]["total_runs"] == 2
        assert stats["ga4"]["success_rate_pct"] == 50.0
        assert stats["ga4"]["avg_duration_s"] == 1.25

    def test_alert_on_failure_writes_log(self, tmp_path, monkeypatch):
        import utils.pipeline_monitor as pm
        log_path = tmp_path / "alerts.log"
        monkeypatch.setattr(pm, "LOG_DIR", tmp_path)
        pm.alert_on_failure("clickstream", "CSV missing")
        alert_log = tmp_path / "alerts.log"
        assert alert_log.exists()
        content = alert_log.read_text()
        assert "clickstream" in content
        assert "CSV missing" in content

    def test_save_run_report_creates_json(self, tmp_path, monkeypatch):
        import utils.pipeline_monitor as pm
        monkeypatch.setattr(pm, "REPORTS_DIR", tmp_path)
        report = {"pipelines": ["ga4", "scraper"], "total_rows": 1050}
        path = pm.save_run_report(report)
        assert path.exists()
        loaded = json.loads(path.read_text())
        assert loaded["total_rows"] == 1050


# ── alerts.py ─────────────────────────────────────────────────────────────────

class TestAlerts:
    def test_check_traffic_anomalies_returns_dict(self):
        from utils.alerts import check_traffic_anomalies
        result = check_traffic_anomalies()
        assert isinstance(result, dict)
        assert "status" in result
        assert result["status"] in ("ok", "alert", "error")

    def test_check_conversion_drop_returns_dict(self):
        from utils.alerts import check_conversion_drop
        result = check_conversion_drop()
        assert isinstance(result, dict)
        assert result["status"] in ("ok", "alert", "error")

    def test_check_data_freshness_returns_dict(self):
        from utils.alerts import check_data_freshness
        result = check_data_freshness()
        assert isinstance(result, dict)
        assert result["status"] in ("ok", "alert", "error")

    def test_check_error_rate_returns_dict(self):
        from utils.alerts import check_error_rate
        result = check_error_rate()
        assert isinstance(result, dict)
        assert result["status"] in ("ok", "alert", "error")

    def test_run_all_checks_returns_results(self):
        from utils.alerts import run_all_checks
        results = run_all_checks()
        assert len(results) >= 4, f"Expected at least 4 checks, got {len(results)}"
        check_names = {r["check"] for r in results}
        assert "traffic_drop" in check_names or "traffic_anomalies" in check_names
        assert "conversion_drop" in check_names
        assert "data_staleness" in check_names or "data_freshness" in check_names
        assert "error_rate" in check_names

    def test_send_alert_writes_to_log(self, tmp_path, monkeypatch):
        import utils.alerts as al
        log_path = tmp_path / "alerts.log"
        monkeypatch.setattr(al, "ALERT_LOG", log_path)
        al.send_alert("Test critical alert", severity="critical")
        content = log_path.read_text()
        assert "Test critical alert" in content
        assert "CRITICAL" in content

    def test_send_alert_warning_severity(self, tmp_path, monkeypatch):
        import utils.alerts as al
        log_path = tmp_path / "alerts.log"
        monkeypatch.setattr(al, "ALERT_LOG", log_path)
        al.send_alert("Test warning", severity="warning")
        content = log_path.read_text()
        assert "WARNING" in content
