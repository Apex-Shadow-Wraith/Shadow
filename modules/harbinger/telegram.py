"""
Telegram Delivery — Harbinger's primary notification channel
=============================================================
Sends notifications via the Telegram Bot API. Falls back gracefully
if not configured or if delivery fails.

Phase 2: Real delivery. Phase 1 was log-only.
"""

import logging
from typing import Any

import requests

logger = logging.getLogger("shadow.harbinger.telegram")


class TelegramDelivery:
    """Delivers notifications via the Telegram Bot API.

    Args:
        bot_token: Telegram bot token from BotFather.
        chat_id: Target chat/user ID for messages.
    """

    SEVERITY_PREFIXES = {
        1: "\u2139\ufe0f SILENT",
        2: "\ud83d\udce9 QUIET",
        3: "\ud83d\udd14 AUDIBLE",
        4: "\ud83d\udea8 URGENT",
    }

    def __init__(self, bot_token: str, chat_id: str) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id

    def is_configured(self) -> bool:
        """Return True if bot_token and chat_id are non-empty strings."""
        return bool(
            isinstance(self._bot_token, str) and self._bot_token.strip()
            and isinstance(self._chat_id, str) and self._chat_id.strip()
        )

    def send_message(self, text: str, severity: int = 1) -> bool:
        """Send a plain text message via Telegram Bot API.

        Args:
            text: Message body.
            severity: Notification severity (1-4), used for logging only.

        Returns:
            True on success, False on failure. Never raises.
        """
        if not self.is_configured():
            logger.warning("Telegram not configured — cannot send message.")
            return False

        url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "HTML",
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    logger.info("Telegram message sent (severity=%d).", severity)
                    return True
                logger.warning(
                    "Telegram API returned ok=false: %s",
                    data.get("description", "unknown error"),
                )
                return False
            logger.warning(
                "Telegram API HTTP %d: %s",
                response.status_code,
                response.text[:200],
            )
            return False
        except requests.exceptions.Timeout:
            logger.warning("Telegram send timed out (10s).")
            return False
        except requests.exceptions.RequestException as e:
            logger.warning("Telegram send failed: %s", e)
            return False
        except Exception as e:
            logger.error("Unexpected error sending Telegram message: %s", e)
            return False

    def send_alert(self, message: str, severity: int, category: str) -> bool:
        """Format and send a structured alert via Telegram.

        Prepends severity prefix and category to the message.

        Args:
            message: Alert body.
            severity: Notification severity (1-4).
            category: Alert category (e.g. 'security', 'system').

        Returns:
            True on success, False on failure.
        """
        prefix = self.SEVERITY_PREFIXES.get(severity, f"[LEVEL {severity}]")
        formatted = f"<b>{prefix} [{category.upper()}]</b>\n{message}"
        return self.send_message(formatted, severity=severity)
