"""
AlertRule class and pre-defined rules for the smart alerts system.
Each rule encapsulates a name, condition function, severity, and message template.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class AlertRule:
    """A single alerting rule with a callable condition."""

    name: str
    condition: Callable[[], dict]
    severity: str  # "critical" | "warning" | "info"
    description: str
    recommended_action: str = ""

    def evaluate(self) -> dict:
        """Run the condition and return a standardised result dict."""
        try:
            result = self.condition()
            result.setdefault("rule", self.name)
            result.setdefault("severity", self.severity)
            result.setdefault("recommended_action", self.recommended_action)
            return result
        except Exception as exc:
            logger.error(f"AlertRule '{self.name}' evaluation error: {exc}")
            return {
                "rule": self.name,
                "status": "error",
                "message": str(exc),
                "severity": self.severity,
            }


# ── Rule definitions ──────────────────────────────────────────────────────────


def _get_rules() -> list[AlertRule]:
    """Lazy import avoids circular deps; called only when rules are evaluated."""
    from utils.alerts import (
        check_traffic_drop,
        check_bounce_spike,
        check_conversion_drop,
        check_anomaly_detected,
        check_data_staleness,
        check_page_speed_degradation,
    )

    TRAFFIC_DROP_RULE = AlertRule(
        name="TRAFFIC_DROP",
        condition=check_traffic_drop,
        severity="critical",
        description="Sessions dropped more than 20% day-over-day",
        recommended_action="Check server health, tracking code, and recent deploys.",
    )

    BOUNCE_SPIKE_RULE = AlertRule(
        name="BOUNCE_SPIKE",
        condition=check_bounce_spike,
        severity="warning",
        description="Bounce rate increased more than 10% relative to prior day",
        recommended_action="Review landing page changes and traffic quality.",
    )

    CONVERSION_DROP_RULE = AlertRule(
        name="CONVERSION_DROP",
        condition=check_conversion_drop,
        severity="critical",
        description="CVR dropped more than 15% vs 7-day average",
        recommended_action="Check checkout flow, payment gateway, and offers.",
    )

    ANOMALY_DETECTED_RULE = AlertRule(
        name="ANOMALY_DETECTED",
        condition=check_anomaly_detected,
        severity="warning",
        description="AI anomaly detector found traffic anomalies",
        recommended_action="Review anomaly dates in the Traffic dashboard.",
    )

    DATA_STALE_RULE = AlertRule(
        name="DATA_STALE",
        condition=check_data_staleness,
        severity="warning",
        description="Data has not been refreshed in more than 24 hours",
        recommended_action="Run ingestion/run_all.py --mode full to refresh data.",
    )

    PAGE_SPEED_RULE = AlertRule(
        name="PAGE_SPEED_DEGRADATION",
        condition=check_page_speed_degradation,
        severity="warning",
        description="Average page load time exceeds 2000ms threshold",
        recommended_action="Review slow pages in SEO dashboard and optimise assets.",
    )

    return [
        TRAFFIC_DROP_RULE,
        BOUNCE_SPIKE_RULE,
        CONVERSION_DROP_RULE,
        ANOMALY_DETECTED_RULE,
        DATA_STALE_RULE,
        PAGE_SPEED_RULE,
    ]


def evaluate_all_rules() -> list[dict]:
    """
    Evaluate every AlertRule and return a list of violation dicts
    (i.e. results where status == 'alert').
    """
    rules = _get_rules()
    violations = []
    for rule in rules:
        result = rule.evaluate()
        if result.get("status") == "alert":
            violations.append(result)
            logger.warning(f"Rule '{rule.name}' violated: {result.get('message', '')}")
    return violations


def get_all_rule_results() -> list[dict]:
    """Evaluate every rule and return ALL results (including ok/error)."""
    return [rule.evaluate() for rule in _get_rules()]
