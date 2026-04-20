"""Cipher settings schema. Cipher is stateless; no configuration today."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CipherSettings(BaseModel):
    model_config = ConfigDict(extra="allow")
