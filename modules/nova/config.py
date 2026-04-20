"""Nova settings schema."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class NovaSettings(BaseModel):
    model_config = ConfigDict(extra="allow")

    ollama_base_url: str = "http://localhost:11434"
    content_model: str = "gemma4:26b"
