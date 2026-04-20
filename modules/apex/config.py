"""Apex settings schema.

Fields are read by `shadow.config` from (in precedence order) OS env →
`.env` → `config/config.local.yaml` → `config/config.yaml` → defaults.

Secrets use `SecretStr` so they redact in logs and `model_dump_json`.
Flat `.env` names like `ANTHROPIC_API_KEY` map here via `validation_alias`
— the existing `.env` file format keeps working unchanged.

Fail-loud policy: if `dry_run=False` and BOTH API keys are missing, the
singleton fails at startup with a clear remediation message. Dry-run
must be EXPLICIT — never inferred from missing keys.
"""

from __future__ import annotations

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    model_validator,
)


class ApexSettings(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    dry_run: bool = False
    escalation_db: str = "data/apex_escalation.db"
    log_file: str = "data/apex_log.json"
    claude_model: str = "claude-sonnet-4-20250514"
    openai_model: str = "gpt-4o"
    max_response_tokens: int = 2048
    max_turns: int = 10
    training_data_dir: str = "training_data/apex_sessions"

    anthropic_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "anthropic_api_key",
            "ANTHROPIC_API_KEY",
            "APEX__ANTHROPIC_API_KEY",
        ),
    )
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "openai_api_key",
            "OPENAI_API_KEY",
            "APEX__OPENAI_API_KEY",
        ),
    )

    @model_validator(mode="after")
    def _require_key_unless_dry_run(self) -> "ApexSettings":
        if (
            not self.dry_run
            and self.anthropic_api_key is None
            and self.openai_api_key is None
        ):
            raise ValueError(
                "Apex requires an API key when dry_run=False. "
                "Set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env, "
                "or enable apex.dry_run: true in config.yaml."
            )
        return self
