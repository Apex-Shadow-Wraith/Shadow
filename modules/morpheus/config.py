"""Morpheus settings schema."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class MorpheusSettings(BaseModel):
    model_config = ConfigDict(extra="allow")

    # Dormancy flag. When False, main.py does NOT instantiate Morpheus
    # and the router's is_routable() check skips it in every routing
    # surface. Default False because Morpheus is dormant until its
    # creative-discovery pipeline is validated against the benchmark
    # (see CLAUDE.md, Phase A).
    enabled: bool = False
