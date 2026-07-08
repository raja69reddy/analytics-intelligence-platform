"""
SmartAlertDetector — multi-signal alert detection using IsolationForest,
statistical thresholds, and rolling averages.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)

# Lazy OpenAI import — only used if OPENAI_API_KEY is set
_openai_available = bool(os.environ.get("OPENAI_API_KEY"))


def _load_db() -> "function":
    import sys
    from pathlib import Path
    ROOT = Path(__file__).resolve().parent.parent.parent
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from utils.db import query_df
    return query_df


# ── Alert dataclass (inline fallback — alert_models must be importable) ───────

def _make_alert(alert_type, severity, title, message, recommended_action,
                metric_value=None, threshold_value=None):
    from ai.smart_alerts.alert_models import Alert, Severity
    sev = Severity(severity.upper()) if isinstance(severity, str) else severity
    return Alert(
        alert_type=alert_type,
        severity=sev,
        title=title,
        message=message,
        recommended_action=recommended_action,
        metric_value=metric_value,
        threshold_value=threshold_value,
    )


class SmartAlertDetector:
    """
    Multi-signal smart alert detector.

    Combines IsolationForest anomaly detection with statistical thresholds
    and rolling-average trend analysis to produce actionable alerts.
    """

    def __init__(
        self,
        contamination: float = 0.05,
        traffic_drop_pct: float = 0.20,
        conversion_drop_pct: float = 0.15,
        bounce_spike_pct: float = 0.10,
        engagement_drop_pct: float = 0.15,
        random_state: int = 42,
    ) -> None:
        self.contamination       = contamination
        self.traffic_drop_pct    = traffic_drop_pct
        self.conversion_drop_pct = conversion_drop_pct
        self.bounce_spike_pct    = bounce_spike_pct
        self.engagement_drop_pct = engagement_drop_pct
        self.random_state        = random_state

    # ── Traffic anomalies (IsolationForest) ───────────────────────────────────

    def detect_traffic_anomalies(self, df: pd.DataFrame) -> list:
        """
        Use IsolationForest to flag statistically abnormal days in the
        daily traffic dataframe (expects columns: total_sessions, bounce_rate_pct,
        avg_session_duration).
        """
        alerts = []
        required = {"total_sessions", "bounce_rate_pct", "avg_session_duration"}
        missing = required - set(df.columns)
        if missing or len(df) < 5:
            logger.debug("detect_traffic_anomalies: insufficient data (%d rows)", len(df))
            return alerts

        features = df[list(required)].fillna(0).values
        iso = IsolationForest(
            contamination=self.contamination,
            random_state=self.random_state,
            n_estimators=100,
        )
        preds = iso.fit_predict(features)
        scores = -iso.decision_function(features)

        anomaly_idx = np.where(preds == -1)[0]
        if len(anomaly_idx) == 0:
            return alerts

        for i in anomaly_idx:
            row    = df.iloc[i]
            score  = float(scores[i])
            sev    = "CRITICAL" if score > 0.15 else "WARNING"
            date   = str(row.get("session_date", "unknown"))[:10]
            sess   = int(row.get("total_sessions", 0))
            alerts.append(_make_alert(
                alert_type="TRAFFIC_ANOMALY",
                severity=sev,
                title=f"Traffic anomaly detected on {date}",
                message=(
                    f"IsolationForest detected abnormal traffic on {date}: "
                    f"{sess:,} sessions (anomaly score {score:.3f})."
                ),
                recommended_action=(
                    "Review server logs and marketing campaigns for "
                    "the flagged date. Check for deployment events or outages."
                ),
                metric_value=sess,
                threshold_value=round(score, 4),
            ))

        logger.info("detect_traffic_anomalies: %d anomalies found", len(alerts))
        return alerts

    # ── Conversion drops (statistical threshold) ──────────────────────────────

    def detect_conversion_drops(self, df: pd.DataFrame) -> list:
        """
        Alert if CVR dropped >conversion_drop_pct% vs the 7-day rolling average.
        Expects columns: session_date, sessions, goal_completions.
        """
        alerts = []
        if "sessions" not in df.columns or len(df) < 8:
            return alerts

        df = df.copy().sort_values("session_date")
        df["cvr"] = df.get("goal_completions", 0) / df["sessions"].replace(0, np.nan)
        df["cvr_7d_avg"] = df["cvr"].rolling(7, min_periods=3).mean()

        last = df.iloc[-1]
        cvr_today = float(last["cvr"] or 0)
        cvr_avg   = float(last["cvr_7d_avg"] or 0)
        if cvr_avg > 0:
            drop = (cvr_avg - cvr_today) / cvr_avg
            if drop > self.conversion_drop_pct:
                sev = "CRITICAL" if drop > 0.30 else "WARNING"
                alerts.append(_make_alert(
                    alert_type="CONVERSION_DROP",
                    severity=sev,
                    title="Conversion rate dropped significantly",
                    message=(
                        f"CVR dropped {drop*100:.1f}% vs 7-day average "
                        f"({cvr_today*100:.4f}% vs avg {cvr_avg*100:.4f}%)."
                    ),
                    recommended_action=(
                        "Check checkout flow, payment gateway health, "
                        "and active promotional campaigns."
                    ),
                    metric_value=round(cvr_today * 100, 4),
                    threshold_value=round(cvr_avg * 100, 4),
                ))

        return alerts

    # ── Bounce spikes (rolling average) ──────────────────────────────────────

    def detect_bounce_spikes(self, df: pd.DataFrame) -> list:
        """
        Alert if bounce rate increased >bounce_spike_pct% relative to rolling avg.
        Expects columns: session_date, bounce_rate_pct (or sessions + bounce counts).
        """
        alerts = []
        if "bounce_rate_pct" not in df.columns or len(df) < 5:
            return alerts

        df = df.copy().sort_values("session_date")
        df["br_7d_avg"] = df["bounce_rate_pct"].rolling(7, min_periods=3).mean()

        last    = df.iloc[-1]
        br_now  = float(last["bounce_rate_pct"] or 0)
        br_avg  = float(last["br_7d_avg"] or 0)
        if br_avg > 0:
            spike = (br_now - br_avg) / br_avg
            if spike > self.bounce_spike_pct:
                sev = "CRITICAL" if spike > 0.25 else "WARNING"
                alerts.append(_make_alert(
                    alert_type="BOUNCE_SPIKE",
                    severity=sev,
                    title="Bounce rate spike detected",
                    message=(
                        f"Bounce rate {br_now:.1f}% is {spike*100:.1f}% above "
                        f"7-day average of {br_avg:.1f}%."
                    ),
                    recommended_action=(
                        "Review recent landing page changes, ad targeting quality, "
                        "and page load times."
                    ),
                    metric_value=round(br_now, 2),
                    threshold_value=round(br_avg, 2),
                ))

        return alerts

    # ── Engagement drops (trend analysis) ────────────────────────────────────

    def detect_engagement_drops(self, df: pd.DataFrame) -> list:
        """
        Alert if avg session duration shows a declining trend vs 7-day avg.
        Expects columns: session_date, avg_session_duration.
        """
        alerts = []
        col = "avg_session_duration"
        if col not in df.columns or len(df) < 5:
            return alerts

        df = df.copy().sort_values("session_date")
        df["dur_7d_avg"] = df[col].rolling(7, min_periods=3).mean()

        last     = df.iloc[-1]
        dur_now  = float(last[col] or 0)
        dur_avg  = float(last["dur_7d_avg"] or 0)
        if dur_avg > 0:
            drop = (dur_avg - dur_now) / dur_avg
            if drop > self.engagement_drop_pct:
                sev = "CRITICAL" if drop > 0.30 else "WARNING"
                alerts.append(_make_alert(
                    alert_type="ENGAGEMENT_DROP",
                    severity=sev,
                    title="Session engagement dropping",
                    message=(
                        f"Avg session duration {dur_now:.0f}s is {drop*100:.1f}% below "
                        f"7-day average of {dur_avg:.0f}s."
                    ),
                    recommended_action=(
                        "Review content quality, page load speeds, and "
                        "recent changes to the user interface."
                    ),
                    metric_value=round(dur_now, 1),
                    threshold_value=round(dur_avg, 1),
                ))

        return alerts

    # ── AI message generation ─────────────────────────────────────────────────

    def generate_alert_message(self, alert_type: str, data: dict) -> str:
        """
        Generate a human-readable alert message using OpenAI (if available)
        or fall back to a template-based message.
        """
        if _openai_available:
            try:
                from openai import OpenAI
                client = OpenAI()
                prompt = (
                    f"You are a web analytics expert. Write a concise, actionable alert "
                    f"message (2-3 sentences) for the following alert:\n"
                    f"Type: {alert_type}\nData: {data}\n"
                    f"Focus on what the business impact is and what to check first."
                )
                resp = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=150,
                    temperature=0.4,
                )
                return resp.choices[0].message.content.strip()
            except Exception as exc:
                logger.warning("OpenAI alert generation failed: %s", exc)

        # Fallback template
        templates = {
            "TRAFFIC_ANOMALY":   "Traffic anomaly detected. Review server logs and campaigns for the affected date.",
            "CONVERSION_DROP":   "Conversion rate has dropped significantly. Check checkout flow and payment gateway.",
            "BOUNCE_SPIKE":      "Bounce rate spike detected. Review landing pages and ad targeting.",
            "ENGAGEMENT_DROP":   "Session engagement has declined. Review content quality and page performance.",
        }
        return templates.get(alert_type, f"Alert detected: {alert_type}. Please investigate.")

    # ── Run all detectors ─────────────────────────────────────────────────────

    def run_all(self, df: pd.DataFrame) -> list:
        """Run all detectors and return a combined list of Alert objects."""
        all_alerts = []
        all_alerts.extend(self.detect_traffic_anomalies(df))
        all_alerts.extend(self.detect_conversion_drops(df))
        all_alerts.extend(self.detect_bounce_spikes(df))
        all_alerts.extend(self.detect_engagement_drops(df))
        logger.info("SmartAlertDetector.run_all: %d alerts generated", len(all_alerts))
        return all_alerts
