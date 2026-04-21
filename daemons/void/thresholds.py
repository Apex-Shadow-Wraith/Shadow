"""Threshold evaluation for the Void daemon.

Extracted verbatim from modules/void/void.py's _health_check logic.
Returns a structured verdict; the monitor loop maps the severity level
to a journald log call.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from daemons.void.config import VoidThresholds


def evaluate(snapshot: dict[str, Any], thresholds: VoidThresholds) -> dict[str, Any]:
    """Compare CPU / RAM / disk percentages against warning/critical thresholds.

    Returns a dict:
        {
            "status": "healthy" | "warning" | "critical",
            "alerts": [ {metric, value, threshold, severity}, ... ],
            "current": {cpu_percent, ram_percent, disk_percent},
            "thresholds": <thresholds as dict>,
            "timestamp": <iso8601>,
        }
    """
    checks = [
        (
            "cpu",
            snapshot["cpu_percent"],
            thresholds.cpu_warning,
            thresholds.cpu_critical,
        ),
        (
            "ram",
            snapshot["ram_percent"],
            thresholds.ram_warning,
            thresholds.ram_critical,
        ),
        (
            "disk",
            snapshot["disk_percent"],
            thresholds.disk_warning,
            thresholds.disk_critical,
        ),
    ]

    alerts: list[dict[str, Any]] = []
    for metric, value, warning, critical in checks:
        if value >= critical:
            alerts.append(
                {"metric": metric, "value": value, "threshold": critical, "severity": "critical"}
            )
        elif value >= warning:
            alerts.append(
                {"metric": metric, "value": value, "threshold": warning, "severity": "warning"}
            )

    if any(a["severity"] == "critical" for a in alerts):
        status = "critical"
    elif alerts:
        status = "warning"
    else:
        status = "healthy"

    return {
        "status": status,
        "alerts": alerts,
        "current": {
            "cpu_percent": snapshot["cpu_percent"],
            "ram_percent": snapshot["ram_percent"],
            "disk_percent": snapshot["disk_percent"],
        },
        "thresholds": thresholds.model_dump(),
        "timestamp": datetime.now().isoformat(),
    }
