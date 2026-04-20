"""Apex settings schema.

Commit 1: mirror the YAML `modules.apex.*` block. Commit 2 extends this
with SecretStr fields for API keys and a model_validator that fails loud
when `dry_run=False` and no API keys are configured.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ApexSettings(BaseModel):
    """Non-secret Apex settings loaded from config.yaml."""

    model_config = ConfigDict(extra="allow")

    dry_run: bool = False
    escalation_db: str = "data/apex_escalation.db"
    log_file: str = "data/apex_log.json"
    claude_model: str = "claude-sonnet-4-20250514"
    openai_model: str = "gpt-4o"
    max_response_tokens: int = 2048
