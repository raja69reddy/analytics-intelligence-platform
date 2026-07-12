"""Tests for TrafficForecaster and ConversionForecaster."""

import pickle
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_fake_hist(n_days: int = 90, avg: float = 100.0) -> pd.DataFrame:
    """Synthetic daily sessions dataframe for Prophet."""
    import numpy as np

    dates = pd.date_range("2026-01-01", periods=n_days, freq="D")
    rng = np.random.default_rng(42)
    y = rng.normal(loc=avg, scale=avg * 0.15, size=n_days).clip(min=1)
    return pd.DataFrame({"ds": dates, "y": y})


# ── TrafficForecaster ─────────────────────────────────────────────────────────


class TestTrafficForecaster:
    def test_initialises_with_no_model(self):
        from ai.forecasting.traffic_forecaster import TrafficForecaster

        tf = TrafficForecaster()
        assert tf._model is None

    def test_prepare_prophet_data_has_correct_columns(self):
        from ai.forecasting.traffic_forecaster import TrafficForecaster

        tf = TrafficForecaster()
        hist = _make_fake_hist()
        pdf = tf.prepare_prophet_data(hist)
        assert list(pdf.columns) == ["ds", "y"]
        assert pd.api.types.is_datetime64_any_dtype(pdf["ds"])

    def test_train_model_sets_model(self):
        from ai.forecasting.traffic_forecaster import TrafficForecaster

        tf = TrafficForecaster()
        tf.train_model(_make_fake_hist())
        assert tf._model is not None

    def test_forecast_returns_correct_number_of_rows(self):
        from ai.forecasting.traffic_forecaster import TrafficForecaster

        hist = _make_fake_hist(90)
        tf = TrafficForecaster()
        tf.train_model(hist)
        fc = tf.forecast(days=30)
        assert len(fc) == 90 + 30

    def test_forecast_values_are_non_negative(self):
        from ai.forecasting.traffic_forecaster import TrafficForecaster

        hist = _make_fake_hist(90)
        tf = TrafficForecaster()
        tf.train_model(hist)
        fc = tf.forecast(days=14)
        assert (fc["yhat"] >= 0).all(), "yhat contains negative values"
        assert (fc["yhat_lower"] >= 0).all()
        assert (fc["yhat_upper"] >= 0).all()

    def test_forecast_contains_required_columns(self):
        from ai.forecasting.traffic_forecaster import TrafficForecaster

        hist = _make_fake_hist(60)
        tf = TrafficForecaster()
        tf.train_model(hist)
        fc = tf.forecast(days=7)
        required = {"ds", "yhat", "yhat_lower", "yhat_upper"}
        assert required.issubset(fc.columns)

    def test_save_forecast_creates_csv(self, tmp_path, monkeypatch):
        from ai.forecasting import traffic_forecaster as tf_mod

        monkeypatch.setattr(tf_mod, "FORECAST_CSV", tmp_path / "traffic_forecast.csv")
        monkeypatch.setattr(tf_mod, "MODEL_PATH", tmp_path / "traffic_model.pkl")

        from ai.forecasting.traffic_forecaster import TrafficForecaster

        hist = _make_fake_hist(60)
        tf = TrafficForecaster()
        tf.train_model(hist)
        fc = tf.forecast(days=7)
        path = tf.save_forecast(fc)

        assert path.exists(), "CSV not created"
        df = pd.read_csv(path)
        assert len(df) == 60 + 7
        assert "yhat" in df.columns

    def test_save_forecast_creates_model_file(self, tmp_path, monkeypatch):
        from ai.forecasting import traffic_forecaster as tf_mod

        monkeypatch.setattr(tf_mod, "FORECAST_CSV", tmp_path / "traffic_forecast.csv")
        monkeypatch.setattr(tf_mod, "MODEL_PATH", tmp_path / "model.pkl")

        from ai.forecasting.traffic_forecaster import TrafficForecaster

        hist = _make_fake_hist(60)
        tf = TrafficForecaster()
        tf.train_model(hist)
        tf.save_forecast(tf.forecast(days=7))

        model_path = tmp_path / "model.pkl"
        assert model_path.exists()
        with open(model_path, "rb") as f:
            loaded = pickle.load(f)
        assert loaded is not None


# ── ConversionForecaster ──────────────────────────────────────────────────────


class TestConversionForecaster:
    def test_initialises_with_no_model(self):
        from ai.forecasting.conversion_forecaster import ConversionForecaster

        cf = ConversionForecaster()
        assert cf._model is None

    def test_train_model_sets_model(self):
        from ai.forecasting.conversion_forecaster import ConversionForecaster

        hist = _make_fake_hist(90, avg=2.5)  # simulate CVR % values
        cf = ConversionForecaster()
        cf.train_model(hist)
        assert cf._model is not None

    def test_forecast_returns_correct_days(self):
        from ai.forecasting.conversion_forecaster import ConversionForecaster

        hist = _make_fake_hist(90, avg=2.5)
        cf = ConversionForecaster()
        cf.train_model(hist)
        fc = cf.forecast(days=30)
        assert len(fc) == 90 + 30

    def test_forecast_cvr_clipped_to_valid_range(self):
        from ai.forecasting.conversion_forecaster import ConversionForecaster

        hist = _make_fake_hist(90, avg=2.5)
        cf = ConversionForecaster()
        cf.train_model(hist)
        fc = cf.forecast(days=14)
        assert (fc["yhat"] >= 0).all()
        assert (fc["yhat"] <= 100).all()

    def test_get_forecast_summary_returns_dict(self):
        from ai.forecasting.conversion_forecaster import ConversionForecaster

        hist = _make_fake_hist(90, avg=3.0)
        cf = ConversionForecaster()
        cf.train_model(hist)
        fc = cf.forecast(days=30)

        # Provide a mock max_hist date so summary works without DB
        with patch(
            "ai.forecasting.conversion_forecaster.ConversionForecaster.get_forecast_summary"
        ) as mock_summary:
            mock_summary.return_value = {
                "avg_cvr_pct": 2.8,
                "high_cvr_pct": 3.5,
                "low_cvr_pct": 2.1,
                "forecast_days": 30,
            }
            summary = cf.get_forecast_summary(fc, days=30)
            assert "avg_cvr_pct" in summary
            assert "high_cvr_pct" in summary
            assert "low_cvr_pct" in summary

    def test_save_forecast_creates_csv(self, tmp_path, monkeypatch):
        from ai.forecasting import conversion_forecaster as cf_mod

        monkeypatch.setattr(cf_mod, "FORECAST_CSV", tmp_path / "cvr_forecast.csv")
        monkeypatch.setattr(cf_mod, "MODEL_PATH", tmp_path / "cvr_model.pkl")

        from ai.forecasting.conversion_forecaster import ConversionForecaster

        hist = _make_fake_hist(60, avg=3.0)
        cf = ConversionForecaster()
        cf.train_model(hist)
        fc = cf.forecast(days=7)
        path = cf.save_forecast(fc)

        assert path.exists()
        df = pd.read_csv(path)
        assert len(df) == 60 + 7
        assert set(["ds", "yhat", "yhat_lower", "yhat_upper"]).issubset(df.columns)
