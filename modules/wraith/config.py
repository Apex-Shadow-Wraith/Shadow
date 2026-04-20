"""Wraith settings schema."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class WraithSettings(BaseModel):
    model_config = ConfigDict(extra="allow")

    timezone: str = "America/Chicago"
