"""Conversion rate forecasting using Facebook Prophet."""
import logging
import pickle
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
MODELS_DIR  = ROOT / "ai" / "models"
OUTPUTS_DIR = ROOT / "data" / "processed"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH   = MODELS_DIR / "conversion_forecast_model.pkl"
FORECAST_CSV = OUTPUTS_DIR / "conversion_forecast.csv"

logger = logging.getLogger(__name__)


class ConversionForecaster:
    """Trains a Prophet model on daily CVR and forecasts future conversion rate."""

    def __init__(self):
        self._model = None

    def load_conversion_data(self) -> pd.DataFrame:
        """Load daily CVR (0-100 scale) from DB."""
        from utils.db import query_df
        df = query_df("""
            SELECT
                session_date AS ds,
                ROUND(SUM(conversions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 4) AS y
            FROM raw_ga4_sessions
            GROUP BY session_date
            ORDER BY session_date
        """)
        df["ds"] = pd.to_datetime(df["ds"])
        df["y"]  = df["y"].astype(float).fillna(0.0)
        logger.info(f"Loaded {len(df)} days of CVR data")
        return df

    def train_model(self, df: pd.DataFrame | None = None):
        """Train Prophet model on daily CVR."""
        from prophet import Prophet

        if df is None:
            df = self.load_conversion_data()

        # Keep only ds + y, drop nulls
        prophet_df = df[["ds", "y"]].dropna().sort_values("ds").reset_index(drop=True)

        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            seasonality_mode="additive",
            interval_width=0.80,
        )
        model.fit(prophet_df)
        self._model = model
        logger.info("ConversionForecaster model trained")
        return model

    def forecast(self, days: int = 30) -> pd.DataFrame:
        """Generate `days`-day CVR forecast."""
        if self._model is None:
            self.train_model()

        future = self._model.make_future_dataframe(periods=days)
        forecast_df = self._model.predict(future)

        # Clip CVR to valid range (0-100)
        forecast_df["yhat"]       = forecast_df["yhat"].clip(lower=0, upper=100)
        forecast_df["yhat_lower"] = forecast_df["yhat_lower"].clip(lower=0, upper=100)
        forecast_df["yhat_upper"] = forecast_df["yhat_upper"].clip(lower=0, upper=100)
        return forecast_df

    def get_forecast_summary(self, forecast_df: pd.DataFrame | None = None, days: int = 30) -> dict:
        """Return high/low/avg CVR for the forecast period."""
        if forecast_df is None:
            forecast_df = self.forecast(days=days)

        # Take only future rows (beyond history)
        from utils.db import query_df
        max_hist = query_df("SELECT MAX(session_date) AS mx FROM raw_ga4_sessions")["mx"].iloc[0]
        future_mask = forecast_df["ds"] > pd.Timestamp(max_hist)
        fc = forecast_df[future_mask]

        return {
            "avg_cvr_pct":  round(float(fc["yhat"].mean()), 4),
            "high_cvr_pct": round(float(fc["yhat"].max()), 4),
            "low_cvr_pct":  round(float(fc["yhat"].min()), 4),
            "forecast_days": int(future_mask.sum()),
        }

    def save_forecast(self, forecast_df: pd.DataFrame | None = None) -> Path:
        """Save forecast CSV and trained model pickle."""
        if forecast_df is None:
            forecast_df = self.forecast()

        cols = ["ds", "yhat", "yhat_lower", "yhat_upper"]
        out = forecast_df[cols].copy()
        out["ds"] = out["ds"].dt.strftime("%Y-%m-%d")
        out.to_csv(FORECAST_CSV, index=False)
        logger.info(f"CVR forecast saved to {FORECAST_CSV}")

        with open(MODEL_PATH, "wb") as f:
            pickle.dump(self._model, f)
        logger.info(f"CVR model saved to {MODEL_PATH}")
        return FORECAST_CSV


def load_model() -> "ConversionForecaster":
    """Load a saved ConversionForecaster from disk."""
    forecaster = ConversionForecaster()
    with open(MODEL_PATH, "rb") as f:
        forecaster._model = pickle.load(f)
    return forecaster
