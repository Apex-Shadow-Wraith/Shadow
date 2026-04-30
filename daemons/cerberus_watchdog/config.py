"""Typed settings for the Cerberus Watchdog daemon."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class CerberusWatchdogSettings(BaseModel):
    """Tunable settings for the Cerberus Watchdog daemon.

    Defaults match the original watchdog_cerberus.py constants so the
    promotion is behaviour-preserving.
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    # How often to read the heartbeat file.
    check_interval_seconds: int = Field(default=10, ge=1, le=300)
    # Heartbeat is considered stale beyond this age (seconds).
    max_heartbeat_age_seconds: int = Field(default=30, ge=5, le=600)
    # Number of consecutive stale reads before emergency response fires.
    consecutive_failures_to_emergency: int = Field(default=2, ge=1, le=10)
    # After emergency, sleep this long before resuming polling.
    cooldown_seconds: int = Field(default=60, ge=10, le=3600)

    heartbeat_path: Path = Path("data/cerberus_heartbeat.json")
    env_path: Path = Path(".env")
