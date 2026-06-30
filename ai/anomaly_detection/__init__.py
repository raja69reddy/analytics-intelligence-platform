"""
Anomaly Detection module for the Analytics Intelligence Platform.

Uses scikit-learn's IsolationForest to automatically identify unusual
patterns in web traffic, conversion rates, and bounce-rate data.

Public API
----------
AnomalyDetector
    Core class — call detect_traffic_anomalies(df) to get annotated results
    with is_anomaly, anomaly_score, and severity columns.

run_detection
    End-to-end pipeline: loads the saved model, fetches the latest traffic
    data from PostgreSQL, runs detection, and saves results to
    data/processed/anomalies.csv.
"""

from ai.anomaly_detection.detector import AnomalyDetector
from ai.anomaly_detection.run_detection import run_detection

__all__ = ["AnomalyDetector", "run_detection"]
