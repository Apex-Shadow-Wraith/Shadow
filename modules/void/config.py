"""Void settings schema."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class VoidSettings(BaseModel):
    model_config = ConfigDict(extra="allow")
