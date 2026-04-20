"""Cerberus settings schema.

Commit 1: non-secret fields only. Commit 3 adds `creator_auth_token`
(SecretStr) and replaces the hand-rolled .env parsing in
`creator_override.py`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CerberusSettings(BaseModel):
    model_config = ConfigDict(extra="allow")

    limits_file: str = "config/cerberus_limits.yaml"
    log_all_checks: bool = True
    use_llm_judgment: bool = False
