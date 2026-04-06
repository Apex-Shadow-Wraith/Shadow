"""
Tests for Harbinger new tools — preemptive_approval_scan, briefing_deliver, personalization
============================================================================================
"""

import pytest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from modules.base import ToolResult
from modules.harbinger.harbinger import Harbinger


@pytest.fixture
def harbinger(tmp_path: Path) -> Harbinger:
    """Create a Harbinger instance with temp paths."""
    config = {
        "queue_file": str(tmp_path / "queue.json"),
        "personalization_db": str(tmp_path / "personalization.db"),
    }
    return Harbinger(config)


@pytest.fixture
async def online_harbinger(harbinger: Harbinger) -> Harbinger:
    """Create and initialize a Harbinger instance."""
    await harbinger.initialize()
    return harbinger


# =============================================================================
# Preemptive Approval Scan
# =============================================================================


class TestPreemptiveApprovalScan:
    @pytest.mark.asyncio
    async def test_preemptive_scan_no_items(self, online_harbinger: Harbinger):
        """No pending items returns empty list with message."""
        result = online_harbinger._preemptive_approval_scan({})
        assert result.success is True
        assert result.content["items"] == []
        assert "No upcoming actions" in result.content["message"]

    @pytest.mark.asyncio
    async def test_preemptive_scan_finds_pending_decisions(self, online_harbinger: Harbinger):
        """Pending decision queue items appear in the scan."""
        online_harbinger._decision_queue_add({
            "description": "Approve backup schedule change",
            "context": "New schedule proposed by Void",
            "recommendation": "Accept new schedule",
            "importance": 3,
            "source_module": "void",
        })
        result = online_harbinger._preemptive_approval_scan({})
        assert result.success is True
        assert len(result.content["items"]) == 1
        item = result.content["items"][0]
        assert item["description"] == "Approve backup schedule change"
        assert item["source"] == "decision_queue (void)"
        assert item["risk_level"] == "medium"

    @pytest.mark.asyncio
    async def test_preemptive_scan_sorted_by_risk(self, online_harbinger: Harbinger):
        """Multiple items are sorted high -> medium -> low."""
        online_harbinger._decision_queue_add({
            "description": "Low importance item",
            "context": "", "recommendation": "",
            "importance": 1, "source_module": "test",
        })
        online_harbinger._decision_queue_add({
            "description": "High importance item",
            "context": "", "recommendation": "",
            "importance": 5, "source_module": "test",
        })
        online_harbinger._decision_queue_add({
            "description": "Medium importance item",
            "context": "", "recommendation": "",
            "importance": 3, "source_module": "test",
        })
        result = online_harbinger._preemptive_approval_scan({})
        assert result.success is True
        items = result.content["items"]
        assert len(items) == 3
        assert items[0]["risk_level"] == "high"
        assert items[1]["risk_level"] == "medium"
        assert items[2]["risk_level"] == "low"

    @pytest.mark.asyncio
    async def test_preemptive_scan_no_modules(self, online_harbinger: Harbinger):
        """Without modules dict, still scans decision queue."""
        online_harbinger._decision_queue_add({
            "description": "Test item",
            "context": "", "recommendation": "",
            "importance": 4, "source_module": "test",
        })
        result = online_harbinger._preemptive_approval_scan({})
        assert result.success is True
        assert len(result.content["items"]) == 1

    @pytest.mark.asyncio
    async def test_preemptive_scan_tool_execution(self, online_harbinger: Harbinger):
        """Execute through harbinger.execute()."""
        result = await online_harbinger.execute("preemptive_approval_scan", {})
        assert result.success is True
        assert "items" in result.content


# =============================================================================
# Briefing Deliver
# =============================================================================


class TestBriefingDeliver:
    def _sample_briefing(self) -> dict[str, Any]:
        """Return a minimal briefing dict."""
        return {
            "type": "morning_briefing",
            "date": "Sunday, April 05, 2026",
            "compiled_at": "2026-04-05T08:00:00",
            "section_count": 1,
            "sections": [
                {
                    "title": "Test Section",
                    "priority": 2,
                    "source": "test",
                    "content": "All clear.",
                },
            ],
        }

    @pytest.mark.asyncio
    async def test_deliver_telegram_success(self, online_harbinger: Harbinger):
        """Successful Telegram delivery."""
        online_harbinger._telegram = MagicMock()
        online_harbinger._telegram.is_configured.return_value = True
        online_harbinger._telegram.send_message.return_value = True

        result = online_harbinger._briefing_deliver({
            "briefing": self._sample_briefing(),
            "channel": "telegram",
        })
        assert result.success is True
        assert result.content["channel_used"] == "telegram"
        assert result.content["fallback_used"] is False
        assert result.content["delivered"] is True

    @pytest.mark.asyncio
    async def test_deliver_telegram_fallback(self, online_harbinger: Harbinger):
        """Telegram fails, falls back to console."""
        online_harbinger._telegram = MagicMock()
        online_harbinger._telegram.is_configured.return_value = True
        online_harbinger._telegram.send_message.return_value = False

        result = online_harbinger._briefing_deliver({
            "briefing": self._sample_briefing(),
            "channel": "telegram",
        })
        assert result.success is True
        assert result.content["channel_used"] == "console"
        assert result.content["fallback_used"] is True

    @pytest.mark.asyncio
    async def test_deliver_console(self, online_harbinger: Harbinger):
        """Direct console delivery."""
        result = online_harbinger._briefing_deliver({
            "briefing": self._sample_briefing(),
            "channel": "console",
        })
        assert result.success is True
        assert result.content["channel_used"] == "console"
        assert result.content["fallback_used"] is False

    @pytest.mark.asyncio
    async def test_deliver_no_telegram(self, online_harbinger: Harbinger):
        """Telegram not configured, falls back to console."""
        online_harbinger._telegram = MagicMock()
        online_harbinger._telegram.is_configured.return_value = False

        result = online_harbinger._briefing_deliver({
            "briefing": self._sample_briefing(),
            "channel": "telegram",
        })
        assert result.success is True
        assert result.content["channel_used"] == "console"
        assert result.content["fallback_used"] is True

    @pytest.mark.asyncio
    async def test_deliver_tool_execution(self, online_harbinger: Harbinger):
        """Execute through harbinger.execute()."""
        result = await online_harbinger.execute("briefing_deliver", {
            "briefing": self._sample_briefing(),
            "channel": "console",
        })
        assert result.success is True
        assert result.content["delivered"] is True


# =============================================================================
# Personalization
# =============================================================================


class TestPersonalization:
    @pytest.mark.asyncio
    async def test_personalization_record(self, online_harbinger: Harbinger):
        """Record an engagement interaction."""
        result = online_harbinger._personalization_update({
            "section_name": "safety_status",
            "action": "engaged",
        })
        assert result.success is True
        assert result.content["section_name"] == "safety_status"
        assert result.content["action"] == "engaged"

    @pytest.mark.asyncio
    async def test_personalization_weights_computed(self, online_harbinger: Harbinger):
        """Multiple interactions produce correct scores."""
        for _ in range(3):
            online_harbinger._personalization_update({
                "section_name": "weather",
                "action": "engaged",
            })
        online_harbinger._personalization_update({
            "section_name": "weather",
            "action": "skipped",
        })

        weights = online_harbinger.get_personalization_weights()
        assert "weather" in weights
        assert weights["weather"]["total_interactions"] == 4
        assert weights["weather"]["score"] == 0.75

    @pytest.mark.asyncio
    async def test_personalization_high_engagement(self, online_harbinger: Harbinger):
        """Section with >80% engagement is flagged for promotion."""
        for _ in range(9):
            online_harbinger._personalization_update({
                "section_name": "tasks",
                "action": "engaged",
            })
        online_harbinger._personalization_update({
            "section_name": "tasks",
            "action": "skipped",
        })

        weights = online_harbinger.get_personalization_weights()
        assert weights["tasks"]["trend"] == "promote"
        assert weights["tasks"]["score"] == 0.9

    @pytest.mark.asyncio
    async def test_personalization_low_engagement(self, online_harbinger: Harbinger):
        """Section with <20% engagement is flagged for demotion."""
        online_harbinger._personalization_update({
            "section_name": "research",
            "action": "engaged",
        })
        for _ in range(9):
            online_harbinger._personalization_update({
                "section_name": "research",
                "action": "skipped",
            })

        weights = online_harbinger.get_personalization_weights()
        assert weights["research"]["trend"] == "demote"
        assert weights["research"]["score"] == 0.1

    @pytest.mark.asyncio
    async def test_personalization_empty_data(self, online_harbinger: Harbinger):
        """No data returns empty weights."""
        weights = online_harbinger.get_personalization_weights()
        assert weights == {}

    @pytest.mark.asyncio
    async def test_personalization_tool_execution(self, online_harbinger: Harbinger):
        """Execute personalization_update through harbinger.execute()."""
        result = await online_harbinger.execute("personalization_update", {
            "section_name": "alerts",
            "action": "expanded",
        })
        assert result.success is True
        assert result.content["action"] == "expanded"

        # Also test personalization_weights via execute
        result2 = await online_harbinger.execute("personalization_weights", {})
        assert result2.success is True
        assert "alerts" in result2.content
