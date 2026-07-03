"""Predictive Analytics dashboard page."""
import os
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from utils.db import query_df

st.set_page_config(page_title="Predictive Analytics", page_icon="🔮", layout="wide")
st.title("🔮 Predictive Analytics")
st.caption("Facebook Prophet models trained on historical traffic and CVR data.")

# ── DB guard ──────────────────────────────────────────────────────────────────
try:
    query_df("SELECT 1 AS ok")
except Exception as exc:
    st.error(f"Database connection failed: {exc}")
    st.stop()

# ── Forecast period selector ──────────────────────────────────────────────────
forecast_days = st.selectbox(
    "Forecast period",
    options=[7, 14, 30, 60],
    index=2,
    format_func=lambda d: f"{d} days",
    key="forecast_days_select",
)

st.divider()

# ── KPI cards ─────────────────────────────────────────────────────────────────
st.subheader("Forecast KPIs")


@st.cache_data(ttl=600)
def _load_kpi_forecasts(days: int):
    from ai.forecasting.traffic_forecaster import TrafficForecaster
    from ai.forecasting.conversion_forecaster import ConversionForecaster

    tf = TrafficForecaster()
    hist_df = tf.load_historical_data()
    tf.train_model(hist_df)
    fc_t = tf.forecast(days=days)
    hist_end = hist_df["ds"].max()
    future_t = fc_t[fc_t["ds"] > hist_end]
    predicted_sessions_total = int(future_t["yhat"].clip(lower=0).sum())

    # Next traffic peak (day with highest predicted sessions)
    if not future_t.empty:
        peak_row = future_t.loc[future_t["yhat"].idxmax()]
        days_to_peak = int((peak_row["ds"] - hist_end).days)
    else:
        days_to_peak = 0

    cf = ConversionForecaster()
    hist_cvr = cf.load_conversion_data()
    cf.train_model(hist_cvr)
    fc_c = cf.forecast(days=days)
    summary = cf.get_forecast_summary(fc_c, days=days)

    # Confidence score: 80% interval — narrower = higher confidence
    if not future_t.empty:
        avg_upper = future_t["yhat_upper"].mean()
        avg_lower = future_t["yhat_lower"].mean()
        avg_pred  = future_t["yhat"].clip(lower=1).mean()
        interval_pct = (avg_upper - avg_lower) / avg_pred * 100
        confidence = max(0, min(100, round(100 - interval_pct / 2, 0)))
    else:
        confidence = 50

    return predicted_sessions_total, summary["avg_cvr_pct"], confidence, days_to_peak


with st.spinner("Loading forecast KPIs..."):
    try:
        _pred_sessions, _pred_cvr, _confidence, _peak_days = _load_kpi_forecasts(forecast_days)
        k1, k2, k3, k4 = st.columns(4)
        k1.metric(f"Predicted Sessions (Next {forecast_days}d)", f"{_pred_sessions:,}")
        k2.metric(f"Predicted Avg CVR (Next {forecast_days}d)", f"{_pred_cvr:.4f}%")
        k3.metric("Forecast Confidence Score", f"{int(_confidence)} / 100")
        k4.metric("Days Until Next Traffic Peak", f"{_peak_days} days")
    except Exception as exc:
        st.error(f"Could not load KPIs: {exc}")

st.divider()


# ── Traffic forecast ──────────────────────────────────────────────────────────
st.subheader("Traffic Forecast")


@st.cache_data(ttl=600)
def _load_traffic_forecast(days: int):
    from ai.forecasting.traffic_forecaster import TrafficForecaster
    tf = TrafficForecaster()
    hist_df = tf.load_historical_data()
    tf.train_model(hist_df)
    fc = tf.forecast(days=days)
    return hist_df, fc


with st.spinner("Generating traffic forecast..."):
    try:
        _hist_df, _traffic_fc = _load_traffic_forecast(forecast_days)

        fig_traffic = go.Figure()

        # Actuals
        fig_traffic.add_trace(go.Scatter(
            x=_hist_df["ds"], y=_hist_df["y"],
            mode="lines", name="Actual Sessions",
            line=dict(color="#1f77b4", width=2),
        ))

        # Split into fitted (historical) + future
        _hist_end = _hist_df["ds"].max()
        _fc_hist  = _traffic_fc[_traffic_fc["ds"] <= _hist_end]
        _fc_fut   = _traffic_fc[_traffic_fc["ds"] > _hist_end]

        fig_traffic.add_trace(go.Scatter(
            x=_fc_fut["ds"], y=_fc_fut["yhat"],
            mode="lines", name="Forecast",
            line=dict(color="#ff7f0e", width=2, dash="dash"),
        ))

        # Confidence band
        fig_traffic.add_trace(go.Scatter(
            x=pd.concat([_fc_fut["ds"], _fc_fut["ds"].iloc[::-1]]),
            y=pd.concat([_fc_fut["yhat_upper"], _fc_fut["yhat_lower"].iloc[::-1]]),
            fill="toself",
            fillcolor="rgba(255,127,14,0.15)",
            line=dict(color="rgba(0,0,0,0)"),
            name="80% Confidence Interval",
        ))

        fig_traffic.update_layout(
            xaxis_title="Date", yaxis_title="Sessions",
            height=420, hovermode="x unified",
            legend=dict(orientation="h", y=-0.15),
        )
        st.plotly_chart(fig_traffic, use_container_width=True)

    except Exception as exc:
        st.error(f"Traffic forecast error: {exc}")

st.divider()

# ── CVR forecast ──────────────────────────────────────────────────────────────
st.subheader("Conversion Rate Forecast")


@st.cache_data(ttl=600)
def _load_cvr_forecast(days: int):
    from ai.forecasting.conversion_forecaster import ConversionForecaster
    cf = ConversionForecaster()
    hist_df = cf.load_conversion_data()
    cf.train_model(hist_df)
    fc = cf.forecast(days=days)
    summary = cf.get_forecast_summary(fc, days=days)
    return hist_df, fc, summary


with st.spinner("Generating CVR forecast..."):
    try:
        _cvr_hist, _cvr_fc, _cvr_summary = _load_cvr_forecast(forecast_days)

        fig_cvr = go.Figure()

        fig_cvr.add_trace(go.Scatter(
            x=_cvr_hist["ds"], y=_cvr_hist["y"],
            mode="lines", name="Actual CVR %",
            line=dict(color="#2ca02c", width=2),
        ))

        _cvr_hist_end = _cvr_hist["ds"].max()
        _cvr_fut = _cvr_fc[_cvr_fc["ds"] > _cvr_hist_end]

        fig_cvr.add_trace(go.Scatter(
            x=_cvr_fut["ds"], y=_cvr_fut["yhat"],
            mode="lines", name="CVR Forecast",
            line=dict(color="#d62728", width=2, dash="dash"),
        ))

        fig_cvr.add_trace(go.Scatter(
            x=pd.concat([_cvr_fut["ds"], _cvr_fut["ds"].iloc[::-1]]),
            y=pd.concat([_cvr_fut["yhat_upper"], _cvr_fut["yhat_lower"].iloc[::-1]]),
            fill="toself",
            fillcolor="rgba(214,39,40,0.10)",
            line=dict(color="rgba(0,0,0,0)"),
            name="80% Confidence Interval",
        ))

        fig_cvr.update_layout(
            xaxis_title="Date", yaxis_title="CVR (%)",
            height=380, hovermode="x unified",
            legend=dict(orientation="h", y=-0.15),
        )
        st.plotly_chart(fig_cvr, use_container_width=True)

    except Exception as exc:
        st.error(f"CVR forecast error: {exc}")

st.divider()

# ── Forecast vs actual comparison table ───────────────────────────────────────
st.subheader("Forecast vs Actual — Last 14 Days")

try:
    # Join historical actuals with in-sample predictions
    _actual = _hist_df.rename(columns={"ds": "date", "y": "actual_sessions"}).tail(14)
    _fitted = _traffic_fc[_traffic_fc["ds"] <= _hist_end].rename(
        columns={"ds": "date", "yhat": "predicted_sessions",
                 "yhat_lower": "lower", "yhat_upper": "upper"}
    ).tail(14)
    _compare = _actual.merge(_fitted[["date", "predicted_sessions", "lower", "upper"]], on="date", how="inner")
    _compare["error"] = (_compare["actual_sessions"] - _compare["predicted_sessions"]).round(1)
    _compare["error_pct"] = (
        (_compare["actual_sessions"] - _compare["predicted_sessions"])
        / _compare["actual_sessions"].replace(0, float("nan")) * 100
    ).round(2)
    _compare["date"] = _compare["date"].dt.strftime("%Y-%m-%d")
    for col in ["actual_sessions", "predicted_sessions", "lower", "upper"]:
        _compare[col] = _compare[col].round(0).astype(int)

    st.dataframe(_compare, use_container_width=True, hide_index=True)
except Exception as exc:
    st.info(f"Could not build comparison table: {exc}")

st.divider()

# ── Regenerate button ─────────────────────────────────────────────────────────
if st.button("Regenerate Forecast", type="primary"):
    _load_traffic_forecast.clear()
    _load_cvr_forecast.clear()
    st.success("Cache cleared — forecasts will retrain on next load.")
    st.rerun()
