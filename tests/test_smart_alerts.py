"""Tests for ai/smart_alerts/ — SmartAlertDetector, alert models, and DB save."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.smart_alerts.alert_models import Alert, AlertSummary, Severity  # noqa: E402
from ai.smart_alerts.detector import SmartAlertDetector  # noqa: E402

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_traffic_df(n: int = 30, spike_idx: int | None = None) -> pd.DataFrame:
    """Create synthetic daily traffic data."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2026-01-01", periods=n, freq="D")
    sessions = rng.integers(400, 600, size=n).astype(float)
    bounce = rng.uniform(40, 60, size=n)
    duration = rng.uniform(120, 240, size=n)

    if spike_idx is not None:
        sessions[spike_idx] = 50  # major traffic drop
        bounce[spike_idx] = 95  # extreme bounce

    return pd.DataFrame(
        {
            "session_date": dates,
            "total_sessions": sessions,
            "bounce_rate_pct": bounce,
            "avg_session_duration": duration,
        }
    )


def _make_conversion_df(n: int = 30, drop: bool = False) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    dates = pd.date_range("2026-01-01", periods=n, freq="D")
    sessions = rng.integers(400, 600, size=n).astype(float)
    conv = rng.integers(5, 15, size=n).astype(float)
    if drop:
        conv[-1] = 0  # CVR goes to zero on last day
    return pd.DataFrame(
        {"session_date": dates, "sessions": sessions, "goal_completions": conv}
    )


# ── Test 1: SmartAlertDetector initializes with defaults ─────────────────────


def test_smart_alert_detector_initializes():
    d = SmartAlertDetector()
    assert d.contamination == 0.05
    assert d.traffic_drop_pct == 0.20
    assert d.conversion_drop_pct == 0.15
    assert d.bounce_spike_pct == 0.10
    assert d.engagement_drop_pct == 0.15


def test_smart_alert_detector_custom_params():
    d = SmartAlertDetector(contamination=0.10, traffic_drop_pct=0.30)
    assert d.contamination == 0.10
    assert d.traffic_drop_pct == 0.30


# ── Test 2: detect_traffic_anomalies returns Alert objects ───────────────────


def test_detect_traffic_anomalies_returns_alert_objects():
    df = _make_traffic_df(n=40, spike_idx=15)
    d = SmartAlertDetector(contamination=0.10)
    alerts = d.detect_traffic_anomalies(df)
    assert isinstance(alerts, list)
    if alerts:
        for a in alerts:
            assert isinstance(a, Alert)


def test_detect_traffic_anomalies_empty_df_returns_no_alerts():
    d = SmartAlertDetector()
    df = pd.DataFrame()
    assert d.detect_traffic_anomalies(df) == []


def test_detect_traffic_anomalies_too_few_rows_returns_no_alerts():
    d = SmartAlertDetector()
    df = _make_traffic_df(n=3)
    assert d.detect_traffic_anomalies(df) == []


# ── Test 3: Alert severity is always a valid Severity value ──────────────────


def test_alert_severity_values_are_valid():
    df = _make_traffic_df(n=40, spike_idx=15)
    d = SmartAlertDetector(contamination=0.10)
    all_alerts = d.run_all(df)
    for a in all_alerts:
        assert a.severity in (Severity.CRITICAL, Severity.WARNING, Severity.OK)


def test_alert_to_dict_has_required_keys():
    a = Alert(
        alert_type="TEST",
        severity=Severity.WARNING,
        title="Test alert",
        message="Something happened.",
        recommended_action="Investigate.",
        metric_value=42.0,
        threshold_value=100.0,
    )
    d = a.to_dict()
    required = {
        "alert_id",
        "alert_type",
        "severity",
        "title",
        "message",
        "recommended_action",
        "metric_value",
        "threshold_value",
        "detected_at",
    }
    assert required <= set(d.keys())
    assert d["severity"] == "WARNING"
    assert d["metric_value"] == 42.0


# ── Test 4: Alerts can be saved to and deleted from PostgreSQL ────────────────


def test_alerts_save_and_delete_from_postgres():
    from utils.db import get_engine
    from sqlalchemy import text

    engine = get_engine()
    tag = "pytest_smart_alerts_test"
    with engine.begin() as conn:
        conn.execute(
            text("""
            INSERT INTO alerts (alert_type, severity, message, recommended_action)
            VALUES (:at, :sev, :msg, :rec)
        """),
            {"at": tag, "sev": "warning", "msg": "Test message", "rec": "No action"},
        )

    with engine.connect() as conn:
        df = pd.read_sql(
            text("SELECT id FROM alerts WHERE alert_type = :at"),
            conn,
            params={"at": tag},
        )
    assert len(df) >= 1

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM alerts WHERE alert_type = :at"), {"at": tag})


# ── Test 5: run_alerts.py pipeline completes without errors ──────────────────


def test_run_alerts_pipeline_completes(monkeypatch):
    df_traffic = _make_traffic_df(n=30)
    df_conv = _make_conversion_df(n=30)

    # Patch DB loaders so no real DB is needed for this test
    monkeypatch.setattr(
        "ai.smart_alerts.run_alerts._load_traffic_df", lambda: df_traffic
    )
    monkeypatch.setattr(
        "ai.smart_alerts.run_alerts._load_conversions_df", lambda: df_conv
    )
    monkeypatch.setattr(
        "ai.smart_alerts.run_alerts._save_alerts_to_db", lambda alerts: len(alerts)
    )

    from ai.smart_alerts.run_alerts import run_pipeline
    from ai.smart_alerts.alert_models import AlertSummary

    summary = run_pipeline(save_to_db=True, verbose=False)

    assert isinstance(summary, AlertSummary)
    assert summary.total_alerts >= 0


# ── Test 6: AlertSummary.from_alerts aggregates correctly ────────────────────


def test_alert_summary_from_alerts():
    alerts = [
        Alert("T1", Severity.CRITICAL, "t1", "m1", "r1"),
        Alert("T2", Severity.WARNING, "t2", "m2", "r2"),
        Alert("T3", Severity.WARNING, "t3", "m3", "r3"),
        Alert("T4", Severity.OK, "t4", "m4", "r4"),
    ]
    s = AlertSummary.from_alerts(alerts)
    assert s.total_alerts == 4
    assert s.critical_count == 1
    assert s.warning_count == 2
    assert s.ok_count == 1
    assert not s.all_clear


def test_alert_summary_all_clear():
    s = AlertSummary.from_alerts([])
    assert s.all_clear
    assert s.total_alerts == 0


# ── Test 7: generate_alert_message returns a string ──────────────────────────


def test_generate_alert_message_returns_string(monkeypatch):
    # Ensure OpenAI is not called (set key to empty)
    monkeypatch.setenv("OPENAI_API_KEY", "")
    # Re-import to re-evaluate the module-level check
    import ai.smart_alerts.detector as det

    monkeypatch.setattr(det, "_openai_available", False)

    d = SmartAlertDetector()
    msg = d.generate_alert_message("TRAFFIC_ANOMALY", {"sessions": 100})
    assert isinstance(msg, str)
    assert len(msg) > 0


# ── Test 8: bounce spike detection triggers on synthetic data ─────────────────


def test_detect_bounce_spikes_triggers():
    rng = np.random.default_rng(1)
    n = 20
    dates = pd.date_range("2026-01-01", periods=n)
    br = rng.uniform(40, 50, size=n)
    br[-1] = 90.0  # spike on last day

    df = pd.DataFrame(
        {
            "session_date": dates,
            "bounce_rate_pct": br,
        }
    )
    d = SmartAlertDetector(bounce_spike_pct=0.05)
    alerts = d.detect_bounce_spikes(df)
    assert len(alerts) >= 1
    assert alerts[0].alert_type == "BOUNCE_SPIKE"
