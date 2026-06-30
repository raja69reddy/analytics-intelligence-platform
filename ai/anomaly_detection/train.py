"""Training pipeline for the traffic anomaly detection model."""
from __future__ import annotations

import logging
import os
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split

from ai.anomaly_detection.utils import load_traffic_data, prepare_features

logger = logging.getLogger(__name__)

_MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
_DEFAULT_MODEL_PATH = _MODELS_DIR / "traffic_anomaly_model.pkl"


# ── Synthetic fallback ────────────────────────────────────────────────────────

def _generate_synthetic_traffic(n_days: int = 365) -> pd.DataFrame:
    """Generate synthetic daily traffic data for training when DB is unavailable."""
    rng = np.random.default_rng(42)
    dates = pd.date_range(end=pd.Timestamp.today(), periods=n_days, freq="D")
    sessions = rng.integers(800, 2000, n_days).astype(float)
    # Inject a handful of anomalies
    anomaly_idx = rng.choice(n_days, size=int(n_days * 0.05), replace=False)
    sessions[anomaly_idx] *= rng.uniform(3.0, 6.0, size=len(anomaly_idx))

    return pd.DataFrame({
        "session_date":          dates,
        "total_sessions":        sessions,
        "total_pageviews":       sessions * rng.uniform(2.5, 4.0, n_days),
        "avg_bounce_rate":       rng.uniform(30, 65, n_days),
        "avg_session_duration":  rng.uniform(90, 300, n_days),
        "sessions_7day_avg":     pd.Series(sessions).rolling(7, min_periods=1).mean().values,
    })


# ── Public API ────────────────────────────────────────────────────────────────

def train_traffic_model(
    contamination: float = 0.05,
    random_state: int = 42,
) -> IsolationForest:
    """Train an IsolationForest on daily traffic data.

    Attempts to load real data from the database; falls back to synthetic
    data if the DB is unreachable.

    Returns:
        A fitted IsolationForest instance.
    """
    df = load_traffic_data()
    if df.empty:
        logger.info("No DB data available — using synthetic traffic data for training.")
        df = _generate_synthetic_traffic()

    features = prepare_features(df, metric_type="traffic")
    if not features:
        raise ValueError("No usable feature columns found in the training DataFrame.")

    X = df[features].fillna(0).values
    logger.info("Training IsolationForest on %d rows × %d features.", *X.shape)

    model = IsolationForest(
        n_estimators=100,
        contamination=contamination,
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(X)
    logger.info("Training complete. Estimators: %d", model.n_estimators)
    return model


def save_model(model: IsolationForest, path: str | Path = _DEFAULT_MODEL_PATH) -> Path:
    """Serialize model to disk with pickle.

    Args:
        model: Fitted IsolationForest.
        path:  Destination file path (default: ai/models/traffic_anomaly_model.pkl).

    Returns:
        The resolved Path where the model was saved.
    """
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        pickle.dump(model, f)
    logger.info("Model saved to %s", dest)
    return dest


def load_model(path: str | Path = _DEFAULT_MODEL_PATH) -> IsolationForest:
    """Load a pickled IsolationForest from disk.

    Args:
        path: Path to the .pkl file.

    Returns:
        The deserialized IsolationForest model.

    Raises:
        FileNotFoundError: If no model file exists at path.
    """
    dest = Path(path)
    if not dest.exists():
        raise FileNotFoundError(f"No model found at {dest}. Run train_traffic_model() first.")
    with open(dest, "rb") as f:
        model = pickle.load(f)
    logger.info("Model loaded from %s", dest)
    return model


def evaluate_model(model: IsolationForest, df: pd.DataFrame) -> None:
    """Print a brief performance summary for the given model and DataFrame.

    Uses the model's own contamination rate to derive a pseudo-ground-truth
    label (bottom-contamination% of scores = anomaly) so we can compute
    precision/recall without hand-labelled data.
    """
    features = prepare_features(df, metric_type="traffic")
    if not features:
        print("No feature columns available for evaluation.")
        return

    X = df[features].fillna(0).values
    scores = model.decision_function(X)
    preds  = model.predict(X)           # -1 anomaly, 1 normal

    threshold = np.percentile(scores, model.contamination * 100)
    pseudo_labels = (scores < threshold).astype(int)   # 1 = anomaly
    pred_labels   = (preds == -1).astype(int)

    anomaly_count = int((preds == -1).sum())
    normal_count  = int((preds == 1).sum())

    print("\n-- Model Evaluation Summary ---------------------------------")
    print(f"  Rows evaluated   : {len(X):,}")
    print(f"  Anomalies found  : {anomaly_count:,} ({anomaly_count / len(X) * 100:.1f}%)")
    print(f"  Normal rows      : {normal_count:,}")
    print(f"  Contamination    : {model.contamination:.0%}")
    print(f"  Score range      : [{scores.min():.4f}, {scores.max():.4f}]")
    print("-------------------------------------------------------------\n")


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print("Training traffic anomaly detection model…")
    model = train_traffic_model()
    dest  = save_model(model)
    print(f"Model saved to: {dest}")

    df = load_traffic_data()
    if df.empty:
        from ai.anomaly_detection.train import _generate_synthetic_traffic
        df = _generate_synthetic_traffic()

    evaluate_model(model, df)
    print("Training complete.")
