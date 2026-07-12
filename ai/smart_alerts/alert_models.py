"""
Data models for the Smart Alerts system.
Alert and AlertSummary are plain dataclasses — no DB dependency.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    OK = "OK"


@dataclass
class Alert:
    """
    A single smart alert raised by the SmartAlertDetector.

    Fields
    ------
    alert_id         : Auto-generated UUID for this alert instance.
    alert_type       : Machine-readable type (TRAFFIC_ANOMALY, BOUNCE_SPIKE, etc.).
    severity         : CRITICAL | WARNING | OK.
    title            : Short human-readable title (one sentence).
    message          : Detailed explanation of what was detected.
    recommended_action : What the analyst should do next.
    metric_value     : The observed metric value that triggered the alert.
    threshold_value  : The baseline / threshold the metric was compared against.
    detected_at      : Timestamp when the alert was generated.
    """

    alert_type: str
    severity: Severity
    title: str
    message: str
    recommended_action: str
    metric_value: Optional[float] = None
    threshold_value: Optional[float] = None
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    detected_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "recommended_action": self.recommended_action,
            "metric_value": self.metric_value,
            "threshold_value": self.threshold_value,
            "detected_at": self.detected_at.isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"Alert(type={self.alert_type!r}, severity={self.severity.value}, "
            f"title={self.title!r})"
        )


@dataclass
class AlertSummary:
    """
    Aggregated summary of all alerts from a single detector run.

    Fields
    ------
    total_alerts  : Total number of alerts raised.
    critical_count: Number of CRITICAL severity alerts.
    warning_count : Number of WARNING severity alerts.
    ok_count      : Number of OK (no-issue) signals.
    alerts        : The full list of Alert objects.
    generated_at  : Timestamp of this summary.
    """

    total_alerts: int
    critical_count: int
    warning_count: int
    ok_count: int
    alerts: list[Alert] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def from_alerts(cls, alerts: list[Alert]) -> "AlertSummary":
        critical = sum(1 for a in alerts if a.severity == Severity.CRITICAL)
        warning = sum(1 for a in alerts if a.severity == Severity.WARNING)
        ok = sum(1 for a in alerts if a.severity == Severity.OK)
        return cls(
            total_alerts=len(alerts),
            critical_count=critical,
            warning_count=warning,
            ok_count=ok,
            alerts=alerts,
        )

    @property
    def all_clear(self) -> bool:
        return self.critical_count == 0 and self.warning_count == 0

    def to_dict(self) -> dict:
        return {
            "total_alerts": self.total_alerts,
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "ok_count": self.ok_count,
            "all_clear": self.all_clear,
            "generated_at": self.generated_at.isoformat(),
            "alerts": [a.to_dict() for a in self.alerts],
        }

    def __repr__(self) -> str:
        return (
            f"AlertSummary(total={self.total_alerts}, "
            f"critical={self.critical_count}, warning={self.warning_count})"
        )
