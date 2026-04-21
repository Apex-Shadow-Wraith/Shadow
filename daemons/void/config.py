"""Typed settings for the Void daemon."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class VoidThresholds(BaseModel):
    """Warning/critical thresholds (percent) for the three core resources."""

    model_config = ConfigDict(extra="forbid")

    cpu_warning: float = 80.0
    cpu_critical: float = 95.0
    ram_warning: float = 85.0
    ram_critical: float = 95.0
    disk_warning: float = 90.0
    disk_critical: float = 95.0


class VoidDaemonSettings(BaseModel):
    """All tunable settings for the Void daemon."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    poll_interval_seconds: int = Field(default=60, ge=5, le=3600)
    db_path: Path = Path("data/void_metrics.db")
    latest_snapshot_path: Path = Path("data/void_latest.json")
    retention_days: int = Field(default=30, ge=1)
    thresholds: VoidThresholds = Field(default_factory=VoidThresholds)
