"""Traffic forecasting using Facebook Prophet."""
import logging
import pickle
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
MODELS_DIR  = ROOT / "ai" / "models"
OUTPUTS_DIR = ROOT / "data" / "processed"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH    = MODELS_DIR / "traffic_forecast_model.pkl"
FORECAST_CSV  = OUTPUTS_DIR / "traffic_forecast.csv"

logger = logging.getLogger(__name__)


class TrafficForecaster:
    """Trains a Prophet model on daily sessions and forecasts future traffic."""

    def __init__(self):
        self._model = None

    def load_historical_data(self) -> pd.DataFrame:
        """Load daily total sessions from DB."""
        from utils.db import query_df
        df = query_df("""
            SELECT session_date AS ds, SUM(sessions) AS y
            FROM raw_ga4_sessions
            GROUP BY session_date
            ORDER BY session_date
        """)
        df["ds"] = pd.to_datetime(df["ds"])
        df["y"]  = df["y"].astype(float)
        logger.info(f"Loaded {len(df)} days of traffic data")
        return df

    def prepare_prophet_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure correct Prophet format: ds (datetime) and y (float)."""
        out = df[["ds", "y"]].copy()
        out["ds"] = pd.to_datetime(out["ds"])
        out = out.dropna().sort_values("ds").reset_index(drop=True)
        return out

    def train_model(self, df: pd.DataFrame | None = None):
        """Train Prophet model with yearly + weekly seasonality."""
        from prophet import Prophet

        if df is None:
            df = self.load_historical_data()
        prophet_df = self.prepare_prophet_data(df)

        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            seasonality_mode="additive",
            interval_width=0.80,
        )
        model.fit(prophet_df)
        self._model = model
        logger.info("TrafficForecaster model trained")
        return model

    def forecast(self, days: int = 30) -> pd.DataFrame:
        """Generate `days`-day forecast. Trains model if not already trained."""
        if self._model is None:
            self.train_model()

        future = self._model.make_future_dataframe(periods=days)
        forecast_df = self._model.predict(future)
        # Clip negative predictions to 0
        forecast_df["yhat"]       = forecast_df["yhat"].clip(lower=0)
        forecast_df["yhat_lower"] = forecast_df["yhat_lower"].clip(lower=0)
        forecast_df["yhat_upper"] = forecast_df["yhat_upper"].clip(lower=0)
        return forecast_df

    def plot_forecast(self, forecast_df: pd.DataFrame):
        """Return a Plotly figure with actual + forecast + confidence intervals."""
        import plotly.graph_objects as go

        # Historical actuals
        hist = self.load_historical_data()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=hist["ds"], y=hist["y"],
            mode="lines", name="Actual Sessions",
            line=dict(color="#1f77b4"),
        ))

        future_mask = forecast_df["ds"] > hist["ds"].max()
        fc_future   = forecast_df[future_mask]

        fig.add_trace(go.Scatter(
            x=forecast_df["ds"], y=forecast_df["yhat"],
            mode="lines", name="Forecast",
            line=dict(color="#ff7f0e", dash="dash"),
        ))
        fig.add_trace(go.Scatter(
            x=pd.concat([fc_future["ds"], fc_future["ds"].iloc[::-1]]),
            y=pd.concat([fc_future["yhat_upper"], fc_future["yhat_lower"].iloc[::-1]]),
            fill="toself",
            fillcolor="rgba(255,127,14,0.15)",
            line=dict(color="rgba(255,255,255,0)"),
            name="80% Confidence",
        ))
        fig.update_layout(
            title="Traffic Forecast — Next 30 Days",
            xaxis_title="Date",
            yaxis_title="Sessions",
            height=450,
            hovermode="x unified",
        )
        return fig

    def save_forecast(self, forecast_df: pd.DataFrame) -> Path:
        """Save forecast CSV and trained model pickle."""
        cols = ["ds", "yhat", "yhat_lower", "yhat_upper"]
        out = forecast_df[cols].copy()
        out["ds"] = out["ds"].dt.strftime("%Y-%m-%d")
        out.to_csv(FORECAST_CSV, index=False)
        logger.info(f"Forecast saved to {FORECAST_CSV}")

        with open(MODEL_PATH, "wb") as f:
            pickle.dump(self._model, f)
        logger.info(f"Model saved to {MODEL_PATH}")
        return FORECAST_CSV


def load_model() -> "TrafficForecaster":
    """Load a saved TrafficForecaster from disk."""
    forecaster = TrafficForecaster()
    with open(MODEL_PATH, "rb") as f:
        forecaster._model = pickle.load(f)
    return forecaster
