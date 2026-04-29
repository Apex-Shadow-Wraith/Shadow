"""Cerberus settings schema.

Includes `creator_auth_token` (SecretStr) needed by the creator-override
system. Absence is allowed at Settings construction — the override system
fails loud only when `verify_hardware_auth` is actually invoked without
a token configured. This preserves startup for deployments where no
creator override is needed.

Also includes the absorbed Sentinel security surface's settings under
the nested ``security`` field (Phase A merge). Cerberus itself still
reads its own config via the legacy dict bridge; this typed schema is
forward-compat scaffolding so the eventual typed-settings migration
has a target shape already in place.
"""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, SecretStr


class CerberusSecuritySettings(BaseModel):
    """Settings for Cerberus's absorbed security surface (post-Phase-A).

    Reached via ``config.cerberus.security.*`` and bridged at runtime
    through ``config.get("security", {})`` inside Cerberus.__init__.

    The baseline path defaults to ``data/sentinel_baseline.json`` —
    preserved verbatim from pre-merge Sentinel so existing baseline
    data is not lost on first boot. The "sentinel" filename is a
    historical provenance marker, not a scope indicator.
    """

    model_config = ConfigDict(extra="allow")

    baseline_file: str = "data/sentinel_baseline.json"
    quarantine_dir: str = "data/research/quarantine"


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

    security: CerberusSecuritySettings = Field(
        default_factory=CerberusSecuritySettings
    )
