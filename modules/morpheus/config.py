"""Morpheus settings schema."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class MorpheusSettings(BaseModel):
    model_config = ConfigDict(extra="allow")
