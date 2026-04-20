"""Harbinger settings schema.

Commit 1: empty stub (no YAML section exists today). Commit 4 adds
SecretStr fields for Telegram/Discord bot tokens.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class HarbingerSettings(BaseModel):
    model_config = ConfigDict(extra="allow")
