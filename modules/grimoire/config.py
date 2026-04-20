"""Grimoire settings schema."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class GrimoireSettings(BaseModel):
    model_config = ConfigDict(extra="allow")

    db_path: str = "data/memory/shadow_memory.db"
    vector_path: str = "data/vectors"
    collection_name: str = "shadow_memories"
    max_search_results: int = 5
    auto_link: bool = True
