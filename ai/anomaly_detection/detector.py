"""AnomalyDetector — IsolationForest-based anomaly detection for traffic data."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from ai.anomaly_detection.utils import prepare_features, score_anomaly

logger = logging.getLogger(__name__)


@dataclass
class AnomalyResult:
    total_anomalies: int
    anomaly_dates: list[str]
    severity_counts: dict[str, int]
    anomalies_df: pd.DataFrame
    recommended_actions: list[str] = field(default_factory=list)


class AnomalyDetector:
    """Detect anomalies in web analytics metrics using IsolationForest."""

    def __init__(self, contamination: float = 0.05, random_state: int = 42) -> None:
        self.contamination = contamination
        self.random_state = random_state
        self._traffic_model: IsolationForest | None = None
        self._conversion_model: IsolationForest | None = None
        self._bounce_model: IsolationForest | None = None

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _fit_model(self) -> IsolationForest:
        return IsolationForest(
            contamination=self.contamination,
            random_state=self.random_state,
            n_estimators=100,
        )

    def _run_detection(
        self,
        df: pd.DataFrame,
        feature_cols: list[str],
        date_col: str = "session_date",
        model: IsolationForest | None = None,
    ) -> pd.DataFrame:
        """Fit (or reuse) a model and annotate df with anomaly labels."""
        if df.empty or not all(c in df.columns for c in feature_cols):
            return df.assign(is_anomaly=False, anomaly_score=0.0, severity="none")

        X = df[feature_cols].fillna(0).values
        if model is None:
            model = self._fit_model()
            model.fit(X)

        raw_scores = model.decision_function(X)
        predictions = model.predict(X)          # -1 = anomaly, 1 = normal

        result = df.copy()
        result["is_anomaly"] = predictions == -1
        result["anomaly_score"] = -raw_scores   # higher → more anomalous
        result["severity"] = result["anomaly_score"].apply(score_anomaly)
        return result

    # ── Public detection methods ──────────────────────────────────────────────

    def detect_traffic_anomalies(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect anomalies in traffic metrics (sessions, pageviews, bounce rate)."""
        features = prepare_features(df, metric_type="traffic")
        result = self._run_detection(df, features, model=self._traffic_model)
        if self._traffic_model is None:
            # Cache trained model so callers can reuse it
            model = self._fit_model()
            if not df.empty and all(c in df.columns for c in features):
                model.fit(df[features].fillna(0).values)
            self._traffic_model = model
        return result

    def detect_conversion_anomalies(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect anomalies in conversion rate metrics."""
        features = prepare_features(df, metric_type="conversion")
        result = self._run_detection(df, features, model=self._conversion_model)
        if self._conversion_model is None:
            model = self._fit_model()
            if not df.empty and all(c in df.columns for c in features):
                model.fit(df[features].fillna(0).values)
            self._conversion_model = model
        return result

    def detect_bounce_rate_anomalies(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect anomalies in bounce-rate data."""
        features = prepare_features(df, metric_type="bounce")
        result = self._run_detection(df, features, model=self._bounce_model)
        if self._bounce_model is None:
            model = self._fit_model()
            if not df.empty and all(c in df.columns for c in features):
                model.fit(df[features].fillna(0).values)
            self._bounce_model = model
        return result

    # ── Summary ───────────────────────────────────────────────────────────────

    def get_anomaly_summary(self, df: pd.DataFrame) -> AnomalyResult:
        """Run all detectors and return a consolidated AnomalyResult.

        Columns required in df: session_date plus any traffic/conversion/bounce cols.
        """
        annotated = self.detect_traffic_anomalies(df)
        anomalies = annotated[annotated["is_anomaly"]]

        date_col = "session_date" if "session_date" in annotated.columns else annotated.index.name
        if date_col and date_col in annotated.columns:
            anomaly_dates = (
                anomalies[date_col].astype(str).tolist()
                if not anomalies.empty else []
            )
        else:
            anomaly_dates = []

        severity_counts: dict[str, int] = {"low": 0, "medium": 0, "high": 0}
        if not anomalies.empty and "severity" in anomalies.columns:
            for sev, cnt in anomalies["severity"].value_counts().items():
                if sev in severity_counts:
                    severity_counts[sev] = int(cnt)

        actions = _build_recommended_actions(severity_counts, len(anomaly_dates))

        return AnomalyResult(
            total_anomalies=len(anomalies),
            anomaly_dates=anomaly_dates,
            severity_counts=severity_counts,
            anomalies_df=anomalies,
            recommended_actions=actions,
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_recommended_actions(severity_counts: dict[str, int], total: int) -> list[str]:
    actions: list[str] = []
    if total == 0:
        actions.append("No anomalies detected — traffic looks healthy.")
        return actions
    if severity_counts.get("high", 0) > 0:
        actions.append("Investigate high-severity anomaly dates immediately — possible bot traffic or outage.")
    if severity_counts.get("medium", 0) > 0:
        actions.append("Review medium-severity dates for campaign spikes or tracking issues.")
    if severity_counts.get("low", 0) > 0:
        actions.append("Monitor low-severity anomalies over the next 7 days.")
    actions.append("Cross-reference anomaly dates with marketing calendar and deployment logs.")
    return actions
