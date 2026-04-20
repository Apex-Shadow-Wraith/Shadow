"""Cerberus settings schema.

Includes `creator_auth_token` (SecretStr) needed by the creator-override
system. Absence is allowed at Settings construction — the override system
fails loud only when `verify_hardware_auth` is actually invoked without
a token configured. This preserves startup for deployments where no
creator override is needed.
"""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, SecretStr


class CerberusSettings(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    limits_file: str = "config/cerberus_limits.yaml"
    log_all_checks: bool = True
    use_llm_judgment: bool = False

    creator_auth_token: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "creator_auth_token",
            "CREATOR_AUTH_TOKEN",
            "CERBERUS__CREATOR_AUTH_TOKEN",
        ),
    )
