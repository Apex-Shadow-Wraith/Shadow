"""Reaper settings schema.

Lives separately from `modules/reaper/config.py` (which holds standing
research topics, subreddits, keywords — data that isn't environment
configuration). This file defines the Pydantic settings schema consumed
by `shadow.config` for Reaper's runtime knobs and API credentials.
"""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, SecretStr


class ReaperSettings(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    search_backends: list[str] = Field(
        default_factory=lambda: ["duckduckgo", "brave", "bing"]
    )
    search_backend: str = "ddg"
    max_results_per_query: int = 5
    stealth_mode: bool = True
    searxng_enabled: bool = False

    brave_search_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "brave_search_api_key",
            "BRAVE_SEARCH_API_KEY",
            "REAPER__BRAVE_SEARCH_API_KEY",
        ),
    )
    reddit_client_id: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "reddit_client_id",
            "REDDIT_CLIENT_ID",
            "REAPER__REDDIT_CLIENT_ID",
        ),
    )
    reddit_client_secret: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "reddit_client_secret",
            "REDDIT_CLIENT_SECRET",
            "REAPER__REDDIT_CLIENT_SECRET",
        ),
    )
    # User agent is NOT a secret — it's a public identifier sent in HTTP headers.
    reddit_user_agent: str = Field(
        default="Shadow/1.0",
        validation_alias=AliasChoices(
            "reddit_user_agent",
            "REDDIT_USER_AGENT",
            "REAPER__REDDIT_USER_AGENT",
        ),
    )
