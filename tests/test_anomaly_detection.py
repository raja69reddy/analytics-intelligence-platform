"""Tests for ai/anomaly_detection — detector, utils, and model persistence."""
import os
import pickle
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import IsolationForest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai.anomaly_detection.detector import AnomalyDetector
from ai.anomaly_detection.utils import prepare_features, score_anomaly
from ai.anomaly_detection.train import (
    load_model,
    save_model,
    train_traffic_model,
    _generate_synthetic_traffic,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def traffic_df():
    """Minimal traffic DataFrame matching the feature schema."""
    rng = np.random.default_rng(0)
    n = 60
    return pd.DataFrame({
        "session_date":         pd.date_range("2025-01-01", periods=n, freq="D"),
        "total_sessions":       rng.integers(500, 2000, n).astype(float),
        "total_pageviews":      rng.integers(1500, 6000, n).astype(float),
        "avg_bounce_rate":      rng.uniform(25, 70, n),
        "avg_session_duration": rng.uniform(60, 400, n),
        "sessions_7day_avg":    rng.uniform(500, 2000, n),
    })


@pytest.fixture()
def trained_detector(traffic_df):
    detector = AnomalyDetector()
    detector.detect_traffic_anomalies(traffic_df)
    return detector


# ── AnomalyDetector initialisation ───────────────────────────────────────────

class TestAnomalyDetectorInit:
    def test_default_contamination(self):
        d = AnomalyDetector()
        assert d.contamination == 0.05

    def test_custom_contamination(self):
        d = AnomalyDetector(contamination=0.10)
        assert d.contamination == 0.10

    def test_default_random_state(self):
        d = AnomalyDetector()
        assert d.random_state == 42

    def test_models_none_before_detection(self):
        d = AnomalyDetector()
        assert d._traffic_model is None
        assert d._conversion_model is None
        assert d._bounce_model is None


# ── detect_traffic_anomalies ─────────────────────────────────────────────────

class TestDetectTrafficAnomalies:
    def test_returns_dataframe(self, traffic_df):
        d = AnomalyDetector()
        result = d.detect_traffic_anomalies(traffic_df)
        assert isinstance(result, pd.DataFrame)

    def test_adds_is_anomaly_column(self, traffic_df):
        d = AnomalyDetector()
        result = d.detect_traffic_anomalies(traffic_df)
        assert "is_anomaly" in result.columns

    def test_adds_anomaly_score_column(self, traffic_df):
        d = AnomalyDetector()
        result = d.detect_traffic_anomalies(traffic_df)
        assert "anomaly_score" in result.columns

    def test_adds_severity_column(self, traffic_df):
        d = AnomalyDetector()
        result = d.detect_traffic_anomalies(traffic_df)
        assert "severity" in result.columns

    def test_is_anomaly_is_boolean(self, traffic_df):
        d = AnomalyDetector()
        result = d.detect_traffic_anomalies(traffic_df)
        assert result["is_anomaly"].dtype == bool

    def test_severity_values_valid(self, traffic_df):
        d = AnomalyDetector()
        result = d.detect_traffic_anomalies(traffic_df)
        valid = {"low", "medium", "high"}
        assert set(result["severity"].unique()).issubset(valid)

    def test_row_count_preserved(self, traffic_df):
        d = AnomalyDetector()
        result = d.detect_traffic_anomalies(traffic_df)
        assert len(result) == len(traffic_df)

    def test_empty_dataframe_returns_empty(self):
        d = AnomalyDetector()
        empty = pd.DataFrame(columns=["session_date", "total_sessions", "total_pageviews",
                                      "avg_bounce_rate", "avg_session_duration"])
        result = d.detect_traffic_anomalies(empty)
        assert result.empty or not result["is_anomaly"].any()

    def test_anomaly_count_within_contamination_range(self, traffic_df):
        d = AnomalyDetector(contamination=0.05)
        result = d.detect_traffic_anomalies(traffic_df)
        anomaly_rate = result["is_anomaly"].mean()
        # Allow a small tolerance around the contamination rate
        assert 0.0 <= anomaly_rate <= 0.15


# ── score_anomaly ─────────────────────────────────────────────────────────────

class TestScoreAnomaly:
    def test_high_score_returns_high(self):
        assert score_anomaly(0.20) == "high"

    def test_medium_score_returns_medium(self):
        assert score_anomaly(0.10) == "medium"

    def test_low_score_returns_low(self):
        assert score_anomaly(0.01) == "low"

    def test_boundary_high(self):
        assert score_anomaly(0.15) == "high"

    def test_boundary_medium(self):
        assert score_anomaly(0.05) == "medium"

    def test_negative_score_returns_low(self):
        assert score_anomaly(-0.5) == "low"

    def test_zero_returns_low(self):
        assert score_anomaly(0.0) == "low"

    def test_returns_string(self):
        assert isinstance(score_anomaly(0.1), str)


# ── Model save / load ────────────────────────────────────────────────────────

class TestModelPersistence:
    def test_save_creates_file(self, traffic_df):
        from ai.anomaly_detection.train import train_traffic_model, save_model
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test_model.pkl"
            model = train_traffic_model()
            saved_path = save_model(model, path)
            assert saved_path.exists()

    def test_load_returns_isolation_forest(self, traffic_df):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test_model.pkl"
            model = train_traffic_model()
            save_model(model, path)
            loaded = load_model(path)
            assert isinstance(loaded, IsolationForest)

    def test_loaded_model_predicts(self, traffic_df):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test_model.pkl"
            # Train directly on the fixture so feature counts match
            features = prepare_features(traffic_df, "traffic")
            X = traffic_df[features].fillna(0).values
            model = IsolationForest(contamination=0.05, random_state=42)
            model.fit(X)
            save_model(model, path)
            loaded = load_model(path)
            preds = loaded.predict(X)
            assert set(preds).issubset({-1, 1})

    def test_load_missing_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_model("/nonexistent/path/model.pkl")


# ── get_anomaly_summary ────────────────────────────────────────────────────────

class TestGetAnomalySummary:
    def test_returns_anomaly_result(self, traffic_df):
        from ai.anomaly_detection.detector import AnomalyResult
        d = AnomalyDetector()
        summary = d.get_anomaly_summary(traffic_df)
        assert isinstance(summary, AnomalyResult)

    def test_total_anomalies_non_negative(self, traffic_df):
        d = AnomalyDetector()
        summary = d.get_anomaly_summary(traffic_df)
        assert summary.total_anomalies >= 0

    def test_severity_counts_keys(self, traffic_df):
        d = AnomalyDetector()
        summary = d.get_anomaly_summary(traffic_df)
        assert set(summary.severity_counts.keys()) == {"low", "medium", "high"}

    def test_recommended_actions_is_list(self, traffic_df):
        d = AnomalyDetector()
        summary = d.get_anomaly_summary(traffic_df)
        assert isinstance(summary.recommended_actions, list)
