"""Harbinger settings schema.

Telegram / Discord credentials are SecretStr so they redact in logs and
JSON dumps. Absence is allowed — delivery is best-effort and gracefully
degrades when a token is missing (the `TelegramDelivery.is_configured()`
check handles empty values).
"""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, SecretStr


class HarbingerSettings(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    queue_file: str = "data/harbinger_queue.json"
    personalization_db: str = "data/harbinger_personalization.db"
    sleep_start_hour: int = 22
    sleep_end_hour: int = 6

    telegram_bot_token: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "telegram_bot_token",
            "TELEGRAM_BOT_TOKEN",
            "HARBINGER__TELEGRAM_BOT_TOKEN",
        ),
    )
    telegram_chat_id: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "telegram_chat_id",
            "TELEGRAM_CHAT_ID",
            "HARBINGER__TELEGRAM_CHAT_ID",
        ),
    )
    discord_bot_token: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "discord_bot_token",
            "DISCORD_BOT_TOKEN",
            "HARBINGER__DISCORD_BOT_TOKEN",
        ),
    )
