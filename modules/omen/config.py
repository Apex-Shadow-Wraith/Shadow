"""Omen settings schema."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class OmenSettings(BaseModel):
    model_config = ConfigDict(extra="allow")

    code_model: str = "gemma4:26b"
    ollama_base_url: str = "http://localhost:11434"
    project_root: str = "."
