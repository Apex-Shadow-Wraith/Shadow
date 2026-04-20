"""Observability (Langfuse) settings schema.

Langfuse is opt-in — absent keys silently disable tracing (no warning,
no error). The host field defaults to Langfuse Cloud but can be pointed
at a self-hosted instance via config.yaml or the LANGFUSE_HOST env var.
"""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, SecretStr


class ObservabilitySettings(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    langfuse_host: str = Field(
        default="https://cloud.langfuse.com",
        validation_alias=AliasChoices(
            "langfuse_host",
            "LANGFUSE_HOST",
            "OBSERVABILITY__LANGFUSE_HOST",
        ),
    )
    langfuse_public_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "langfuse_public_key",
            "LANGFUSE_PUBLIC_KEY",
            "OBSERVABILITY__LANGFUSE_PUBLIC_KEY",
        ),
    )
    langfuse_secret_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "langfuse_secret_key",
            "LANGFUSE_SECRET_KEY",
            "OBSERVABILITY__LANGFUSE_SECRET_KEY",
        ),
    )
