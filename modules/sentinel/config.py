"""Sentinel settings schema."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SentinelSettings(BaseModel):
    model_config = ConfigDict(extra="allow")
