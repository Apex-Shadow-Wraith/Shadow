"""Reaper settings schema.

Lives separately from `modules/reaper/config.py` (which holds standing
research topics, subreddits, keywords — data that isn't environment
configuration). Commit 5 adds SecretStr fields for Brave and Reddit
API credentials.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ReaperSettings(BaseModel):
    model_config = ConfigDict(extra="allow")

    search_backends: list[str] = Field(default_factory=lambda: ["duckduckgo", "brave", "bing"])
    search_backend: str = "ddg"
    max_results_per_query: int = 5
    stealth_mode: bool = True
    searxng_enabled: bool = False
