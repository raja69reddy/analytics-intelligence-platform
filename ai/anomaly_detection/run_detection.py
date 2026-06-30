"""End-to-end anomaly detection pipeline — loads model, runs detection, saves results."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import pandas as pd

# Allow running as a script from any working directory
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ai.anomaly_detection.detector import AnomalyDetector
from ai.anomaly_detection.train import load_model
from ai.anomaly_detection.utils import load_traffic_data

logger = logging.getLogger(__name__)

_OUTPUT_PATH = Path(__file__).resolve().parents[2] / "data" / "processed" / "anomalies.csv"


def run_detection() -> pd.DataFrame:
    """Load model + data, detect anomalies, print summary, save CSV.

    Returns:
        DataFrame of detected anomaly rows (empty if none found).
    """
    # Load model
    try:
        model = load_model()
        logger.info("Loaded pre-trained model.")
    except FileNotFoundError:
        logger.warning("No saved model found — training a new one on the fly.")
        from ai.anomaly_detection.train import train_traffic_model, save_model
        model = train_traffic_model()
        save_model(model)

    # Load latest traffic data
    df = load_traffic_data()
    if df.empty:
        print("No traffic data available. Exiting.")
        return pd.DataFrame()

    # Run detection
    detector = AnomalyDetector()
    detector._traffic_model = model
    annotated = detector.detect_traffic_anomalies(df)
    anomalies = annotated[annotated["is_anomaly"]].copy()

    # Print summary
    summary = detector.get_anomaly_summary(df)
    _print_summary(summary, annotated)

    # Save results
    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    annotated.to_csv(_OUTPUT_PATH, index=False)
    print(f"\nResults saved to: {_OUTPUT_PATH}")
    print(f"  Total rows    : {len(annotated):,}")
    print(f"  Anomalies     : {len(anomalies):,}")

    return anomalies


def _print_summary(summary, annotated: pd.DataFrame) -> None:
    print("\n=== Anomaly Detection Results ===")
    print(f"  Total anomalies : {summary.total_anomalies}")
    print(f"  High severity   : {summary.severity_counts.get('high', 0)}")
    print(f"  Medium severity : {summary.severity_counts.get('medium', 0)}")
    print(f"  Low severity    : {summary.severity_counts.get('low', 0)}")

    if summary.anomaly_dates:
        print("\n  Anomaly dates:")
        for d in summary.anomaly_dates[:10]:
            row = annotated[annotated["session_date"].astype(str) == d]
            sev = row["severity"].values[0] if len(row) else "unknown"
            badge = {"high": "[HIGH]", "medium": "[MED] ", "low": "[LOW] "}.get(sev, "[???] ")
            print(f"    {badge} {d}")
        if len(summary.anomaly_dates) > 10:
            print(f"    ... and {len(summary.anomaly_dates) - 10} more")

    print("\n  Recommended actions:")
    for action in summary.recommended_actions:
        print(f"    * {action}")
    print("=" * 34)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run_detection()
