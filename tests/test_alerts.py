"""Unit tests for utils/alerts.py, utils/alert_rules.py, and utils/weekly_digest.py."""

from datetime import datetime
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_sessions_df(**overrides):
    """Minimal DataFrame that mimics two days of raw_ga4_sessions aggregates."""
    base = {
        "session_date": [datetime(2025, 1, 1), datetime(2025, 1, 2)],
        "sessions": [100, 80],
        "new_users": [60, 50],
        "bounce": [False, True],
        "session_duration_s": [120, 90],
        "conversions": [5, 3],
        "revenue": [500.0, 300.0],
        "channel_grouping": ["Organic", "Direct"],
        "device_category": ["desktop", "mobile"],
        "landing_page": ["/", "/blog/"],
        "pageviews": [3, 2],
        "ingested_at": [datetime(2025, 1, 2, 10, 0), datetime(2025, 1, 2, 10, 0)],
    }
    base.update(overrides)
    return pd.DataFrame(base)


# ── 1. check_traffic_drop returns correct dict format ─────────────────────────


def test_traffic_drop_format(monkeypatch, tmp_path):
    monkeypatch.setattr("utils.alerts.ALERT_LOG", tmp_path / "alerts.log")

    df_drop = pd.DataFrame(
        {
            "dod_pct": [-25.0],
            "y_sessions": [75],
            "d2_sessions": [100],
        }
    )

    with patch("utils.alerts._qdf", return_value=df_drop):
        from utils.alerts import check_traffic_drop

        result = check_traffic_drop()

    assert result["status"] == "alert"
    assert result["severity"] == "critical"
    assert result["check"] == "traffic_drop"
    assert "message" in result
    assert "recommended_action" in result
    assert result["pct_change"] == pytest.approx(-25.0)


# ── 2. check_bounce_spike detects a spike ─────────────────────────────────────


def test_bounce_spike_detection(monkeypatch, tmp_path):
    monkeypatch.setattr("utils.alerts.ALERT_LOG", tmp_path / "alerts.log")

    # 15% relative rise in bounce rate > 10% threshold
    df_bounce = pd.DataFrame(
        {
            "y_br": [60.0],
            "d2_br": [52.0],
            "rel_change_pct": [15.4],
        }
    )

    with patch("utils.alerts._qdf", return_value=df_bounce):
        from utils.alerts import check_bounce_spike

        result = check_bounce_spike()

    assert result["status"] == "alert"
    assert result["severity"] == "warning"
    assert result["check"] == "bounce_spike"
    assert result["pct_change"] > 10


# ── 3. evaluate_all_rules returns only violations ─────────────────────────────


def test_evaluate_all_rules_returns_violations(monkeypatch, tmp_path):
    monkeypatch.setattr("utils.alerts.ALERT_LOG", tmp_path / "alerts.log")

    ok_result = {"status": "ok", "check": "traffic_drop"}
    alert_result = {
        "status": "alert",
        "severity": "warning",
        "message": "Test alert",
        "check": "bounce_spike",
        "recommended_action": "Check it.",
    }

    with patch("utils.alert_rules._get_rules") as mock_rules:
        rule_ok = MagicMock()
        rule_ok.evaluate.return_value = ok_result
        rule_alert = MagicMock()
        rule_alert.evaluate.return_value = alert_result
        mock_rules.return_value = [rule_ok, rule_alert]

        from utils.alert_rules import evaluate_all_rules

        violations = evaluate_all_rules()

    assert len(violations) == 1
    assert violations[0]["status"] == "alert"
    assert violations[0]["check"] == "bounce_spike"


# ── 4. alerts table INSERT works via SQLAlchemy ────────────────────────────────


def test_alerts_save_to_postgres():
    """Verify the alerts table accepts inserts and we can query them back."""
    from utils.db import query_df, get_engine
    from sqlalchemy import text

    engine = get_engine()
    test_msg = f"pytest_test_alert_{datetime.now().isoformat()}"

    with engine.begin() as conn:
        conn.execute(
            text("""
            INSERT INTO alerts (alert_type, severity, message, recommended_action)
            VALUES (:at, :sev, :msg, :rec)
        """),
            {
                "at": "PYTEST",
                "sev": "info",
                "msg": test_msg,
                "rec": "No action needed.",
            },
        )

    df = query_df(
        "SELECT message FROM alerts WHERE alert_type='PYTEST' ORDER BY created_at DESC LIMIT 1"
    )
    assert not df.empty, "Expected at least one PYTEST alert in database"
    assert df["message"].iloc[0] == test_msg

    # cleanup
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM alerts WHERE alert_type='PYTEST'"))


# ── 5. weekly_digest.py generates a markdown file ─────────────────────────────


def test_weekly_digest_generates_file(monkeypatch, tmp_path):
    monkeypatch.setattr("utils.weekly_digest.DIGESTS", tmp_path)

    empty_df = pd.DataFrame()

    def _fake_qdf(sql):
        if "SUM(sessions)" in sql and "bounce" in sql and "avg_s" not in sql:
            return pd.DataFrame(
                {
                    "total_sessions": [100],
                    "new_users": [60],
                    "bounce_rate_pct": [40.0],
                    "avg_duration_s": [130.0],
                }
            )
        return empty_df

    with patch("utils.weekly_digest._qdf", side_effect=_fake_qdf):
        from utils.weekly_digest import generate_weekly_digest

        path = generate_weekly_digest(reference_date=datetime(2025, 3, 15))

    assert path.exists(), f"Digest file not found at {path}"
    content = path.read_text(encoding="utf-8")
    assert "Weekly Analytics Digest" in content
    assert "2025-03-" in content


# ── 6. generate_alert_summary returns correct summary structure ───────────────


def test_generate_alert_summary_structure(monkeypatch, tmp_path):
    monkeypatch.setattr("utils.alerts.ALERT_LOG", tmp_path / "alerts.log")

    mock_results = [
        {"status": "ok", "check": "traffic_drop"},
        {
            "status": "alert",
            "check": "bounce_spike",
            "severity": "warning",
            "message": "bounce up",
        },
        {
            "status": "alert",
            "check": "data_staleness",
            "severity": "critical",
            "message": "stale",
        },
    ]

    with patch("utils.alerts.run_all_checks", return_value=mock_results):
        from utils.alerts import generate_alert_summary

        s = generate_alert_summary()

    assert s["total_checks"] == 3
    assert s["active_alerts"] == 2
    assert s["critical_count"] == 1
    assert s["warning_count"] == 1
    assert s["all_clear"] is False
    assert "timestamp" in s


# ── 7. AlertRule.evaluate sets default fields ─────────────────────────────────


def test_alert_rule_evaluate_defaults():
    from utils.alert_rules import AlertRule

    def my_condition():
        return {"status": "alert", "message": "test msg"}

    rule = AlertRule(
        name="TEST_RULE",
        condition=my_condition,
        severity="warning",
        description="test",
        recommended_action="fix it",
    )
    result = rule.evaluate()
    assert result["rule"] == "TEST_RULE"
    assert result["severity"] == "warning"
    assert result["recommended_action"] == "fix it"
    assert result["message"] == "test msg"
