"""
Tests for Harbinger Telegram Delivery
=======================================
Covers TelegramDelivery class, Harbinger integration with Telegram,
nighttime importance gating, and fallback on delivery failure.

All tests mock the network — no real Telegram API calls.
"""

import pytest
from datetime import datetime, time as dtime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from modules.harbinger.harbinger import Harbinger
from modules.harbinger.telegram import TelegramDelivery


# === TelegramDelivery unit tests ===


class TestTelegramDeliveryConfig:
    def test_is_configured_with_valid_credentials(self):
        td = TelegramDelivery("123:ABC", "456")
        assert td.is_configured() is True

    def test_not_configured_empty_token(self):
        td = TelegramDelivery("", "456")
        assert td.is_configured() is False

    def test_not_configured_empty_chat_id(self):
        td = TelegramDelivery("123:ABC", "")
        assert td.is_configured() is False

    def test_not_configured_whitespace_only(self):
        td = TelegramDelivery("  ", " ")
        assert td.is_configured() is False

    def test_not_configured_none_values(self):
        td = TelegramDelivery(None, None)  # type: ignore[arg-type]
        assert td.is_configured() is False

    def test_not_configured_non_string(self):
        td = TelegramDelivery(123, 456)  # type: ignore[arg-type]
        assert td.is_configured() is False


class TestTelegramSendMessage:
    @patch("modules.harbinger.telegram.requests.post")
    def test_send_message_success(self, mock_post: MagicMock):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"ok": True, "result": {"message_id": 1}},
        )
        td = TelegramDelivery("123:ABC", "456")
        assert td.send_message("Hello", severity=2) is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["json"]["chat_id"] == "456"
        assert call_kwargs[1]["json"]["text"] == "Hello"
        assert call_kwargs[1]["json"]["parse_mode"] == "HTML"
        assert call_kwargs[1]["timeout"] == 10

    @patch("modules.harbinger.telegram.requests.post")
    def test_send_message_api_returns_not_ok(self, mock_post: MagicMock):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"ok": False, "description": "Bad Request"},
        )
        td = TelegramDelivery("123:ABC", "456")
        assert td.send_message("Hello") is False

    @patch("modules.harbinger.telegram.requests.post")
    def test_send_message_http_error(self, mock_post: MagicMock):
        mock_post.return_value = MagicMock(
            status_code=500,
            text="Internal Server Error",
        )
        td = TelegramDelivery("123:ABC", "456")
        assert td.send_message("Hello") is False

    @patch("modules.harbinger.telegram.requests.post")
    def test_send_message_timeout(self, mock_post: MagicMock):
        import requests
        mock_post.side_effect = requests.exceptions.Timeout("timed out")
        td = TelegramDelivery("123:ABC", "456")
        assert td.send_message("Hello") is False

    @patch("modules.harbinger.telegram.requests.post")
    def test_send_message_connection_error(self, mock_post: MagicMock):
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("refused")
        td = TelegramDelivery("123:ABC", "456")
        assert td.send_message("Hello") is False

    def test_send_message_not_configured(self):
        td = TelegramDelivery("", "")
        assert td.send_message("Hello") is False


class TestTelegramSendAlert:
    @patch("modules.harbinger.telegram.requests.post")
    def test_send_alert_formats_correctly(self, mock_post: MagicMock):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"ok": True, "result": {"message_id": 1}},
        )
        td = TelegramDelivery("123:ABC", "456")
        result = td.send_alert("Disk full", severity=4, category="system")
        assert result is True
        sent_text = mock_post.call_args[1]["json"]["text"]
        assert "URGENT" in sent_text
        assert "SYSTEM" in sent_text
        assert "Disk full" in sent_text

    @patch("modules.harbinger.telegram.requests.post")
    def test_send_alert_severity_2(self, mock_post: MagicMock):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"ok": True, "result": {"message_id": 1}},
        )
        td = TelegramDelivery("123:ABC", "456")
        td.send_alert("Update ready", severity=2, category="updates")
        sent_text = mock_post.call_args[1]["json"]["text"]
        assert "QUIET" in sent_text
        assert "UPDATES" in sent_text


# === Harbinger integration tests ===


@pytest.fixture
def harbinger_with_telegram(tmp_path: Path) -> Harbinger:
    """Create Harbinger with mock Telegram credentials."""
    config = {
        "queue_file": str(tmp_path / "queue.json"),
        "telegram_bot_token": "test-token-123",
        "telegram_chat_id": "test-chat-456",
    }
    return Harbinger(config)


@pytest.fixture
def harbinger_no_telegram(tmp_path: Path) -> Harbinger:
    """Create Harbinger without Telegram credentials."""
    config = {
        "queue_file": str(tmp_path / "queue.json"),
        "telegram_bot_token": "",
        "telegram_chat_id": "",
    }
    return Harbinger(config)


class TestHarbingerTelegramIntegration:
    def test_telegram_configured_from_config(self, harbinger_with_telegram: Harbinger):
        assert harbinger_with_telegram._telegram is not None
        assert harbinger_with_telegram._telegram.is_configured() is True

    def test_telegram_not_configured_when_empty(self, harbinger_no_telegram: Harbinger):
        assert harbinger_no_telegram._telegram.is_configured() is False

    @pytest.mark.asyncio
    @patch("modules.harbinger.harbinger.datetime")
    @patch("modules.harbinger.telegram.requests.post")
    async def test_notification_sends_via_telegram(
        self, mock_post: MagicMock, mock_dt: MagicMock,
        harbinger_with_telegram: Harbinger,
    ):
        mock_dt.now.return_value.time.return_value = dtime(12, 0)
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"ok": True, "result": {"message_id": 1}},
        )
        mock_dt.now.return_value.isoformat.return_value = "2026-04-05T12:00:00"
        await harbinger_with_telegram.initialize()
        result = await harbinger_with_telegram.execute("notification_send", {
            "message": "Test alert",
            "severity": 2,
            "category": "system",
        })
        assert result.success is True
        assert result.content["channel"] == "telegram"
        assert result.content["telegram_sent"] is True
        mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_notification_logs_only_without_telegram(
        self, harbinger_no_telegram: Harbinger,
    ):
        await harbinger_no_telegram.initialize()
        result = await harbinger_no_telegram.execute("notification_send", {
            "message": "Test alert",
            "severity": 2,
            "category": "system",
        })
        assert result.success is True
        assert result.content["channel"] == "log"
        assert result.content["telegram_sent"] is False

    @pytest.mark.asyncio
    async def test_severity_1_skips_telegram(
        self, harbinger_with_telegram: Harbinger,
    ):
        """Severity 1 (Silent) should not attempt Telegram delivery."""
        await harbinger_with_telegram.initialize()
        with patch("modules.harbinger.telegram.requests.post") as mock_post:
            result = await harbinger_with_telegram.execute("notification_send", {
                "message": "Silent notification",
                "severity": 1,
                "category": "system",
            })
            assert result.success is True
            assert result.content["channel"] == "log"
            mock_post.assert_not_called()

    @pytest.mark.asyncio
    @patch("modules.harbinger.harbinger.datetime")
    @patch("modules.harbinger.telegram.requests.post")
    async def test_telegram_failure_queues_decision(
        self, mock_post: MagicMock, mock_dt: MagicMock,
        harbinger_with_telegram: Harbinger,
    ):
        """When Telegram delivery fails, a decision queue item is created."""
        mock_dt.now.return_value.time.return_value = dtime(12, 0)
        mock_dt.now.return_value.isoformat.return_value = "2026-04-05T12:00:00"
        mock_post.return_value = MagicMock(
            status_code=500,
            text="Server Error",
        )
        await harbinger_with_telegram.initialize()
        result = await harbinger_with_telegram.execute("notification_send", {
            "message": "Important alert",
            "severity": 3,
            "category": "security",
        })
        assert result.success is True
        assert result.content["telegram_sent"] is False

        # Check decision queue has fallback entry
        queue_result = await harbinger_with_telegram.execute("decision_queue_read", {})
        assert queue_result.content["pending_count"] >= 1
        descriptions = [i["description"] for i in queue_result.content["items"]]
        assert any("delivery failed" in d for d in descriptions)

    @pytest.mark.asyncio
    async def test_notification_includes_importance(
        self, harbinger_no_telegram: Harbinger,
    ):
        await harbinger_no_telegram.initialize()
        result = await harbinger_no_telegram.execute("notification_send", {
            "message": "Test",
            "severity": 2,
            "category": "system",
            "importance": 4,
        })
        assert result.success is True
        assert result.content["importance"] == 4

    @pytest.mark.asyncio
    async def test_importance_defaults_to_3(
        self, harbinger_no_telegram: Harbinger,
    ):
        await harbinger_no_telegram.initialize()
        result = await harbinger_no_telegram.execute("notification_send", {
            "message": "Test",
            "severity": 2,
            "category": "system",
        })
        assert result.content["importance"] == 3


class TestNighttimeImportanceGating:
    """Test that severity-3 notifications during sleep hours
    are only delivered if importance >= 5."""

    @pytest.mark.asyncio
    @patch("modules.harbinger.harbinger.datetime")
    async def test_severity3_held_during_sleep_low_importance(
        self, mock_dt: MagicMock, harbinger_no_telegram: Harbinger,
    ):
        """Severity 3, importance < 5, during sleep: held."""
        mock_dt.now.return_value.time.return_value = dtime(23, 30)
        mock_dt.now.return_value.isoformat.return_value = "2026-04-05T23:30:00"
        await harbinger_no_telegram.initialize()
        result = await harbinger_no_telegram.execute("notification_send", {
            "message": "Backup warning",
            "severity": 3,
            "category": "system",
            "importance": 3,
        })
        assert result.success is True
        assert result.content["delivered"] is False
        assert result.content["held_for_morning"] is True

    @pytest.mark.asyncio
    @patch("modules.harbinger.harbinger.datetime")
    async def test_severity3_delivered_during_sleep_high_importance(
        self, mock_dt: MagicMock, harbinger_no_telegram: Harbinger,
    ):
        """Severity 3, importance = 5, during sleep: delivered."""
        mock_dt.now.return_value.time.return_value = dtime(23, 30)
        mock_dt.now.return_value.isoformat.return_value = "2026-04-05T23:30:00"
        await harbinger_no_telegram.initialize()
        result = await harbinger_no_telegram.execute("notification_send", {
            "message": "Critical backup warning",
            "severity": 3,
            "category": "system",
            "importance": 5,
        })
        assert result.success is True
        assert result.content["delivered"] is True

    @pytest.mark.asyncio
    @patch("modules.harbinger.harbinger.datetime")
    async def test_severity4_always_delivered_during_sleep(
        self, mock_dt: MagicMock, harbinger_no_telegram: Harbinger,
    ):
        """Severity 4 always delivered, regardless of sleep hours."""
        mock_dt.now.return_value.time.return_value = dtime(2, 0)
        mock_dt.now.return_value.isoformat.return_value = "2026-04-06T02:00:00"
        await harbinger_no_telegram.initialize()
        result = await harbinger_no_telegram.execute("notification_send", {
            "message": "Security breach",
            "severity": 4,
            "category": "security",
            "importance": 1,
        })
        assert result.success is True
        assert result.content["delivered"] is True

    @pytest.mark.asyncio
    @patch("modules.harbinger.harbinger.datetime")
    async def test_severity12_held_during_sleep(
        self, mock_dt: MagicMock, harbinger_no_telegram: Harbinger,
    ):
        """Severity 1-2 always held during sleep regardless of importance."""
        mock_dt.now.return_value.time.return_value = dtime(1, 0)
        mock_dt.now.return_value.isoformat.return_value = "2026-04-06T01:00:00"
        await harbinger_no_telegram.initialize()
        result = await harbinger_no_telegram.execute("notification_send", {
            "message": "Low priority",
            "severity": 2,
            "category": "system",
            "importance": 5,
        })
        assert result.success is True
        assert result.content["delivered"] is False
