"""
Tests for Harbinger — Shadow's Communications Director
========================================================
Covers decision queue, notification severity, nighttime rules,
briefing compilation, report generation, channel fallback, persistence.
"""

import json
import pytest
from datetime import time as dtime
from pathlib import Path
from typing import Any

from modules.base import ModuleStatus, ToolResult
from modules.harbinger.harbinger import Harbinger


@pytest.fixture
def harbinger(tmp_path: Path) -> Harbinger:
    """Create a Harbinger instance with a temp queue file."""
    config = {"queue_file": str(tmp_path / "queue.json")}
    return Harbinger(config)


@pytest.fixture
async def online_harbinger(harbinger: Harbinger) -> Harbinger:
    """Create and initialize a Harbinger instance."""
    await harbinger.initialize()
    return harbinger


# --- Lifecycle tests ---

class TestHarbingerLifecycle:
    @pytest.mark.asyncio
    async def test_initialize_sets_online(self, harbinger: Harbinger):
        await harbinger.initialize()
        assert harbinger.status == ModuleStatus.ONLINE

    @pytest.mark.asyncio
    async def test_shutdown_sets_offline(self, harbinger: Harbinger):
        await harbinger.initialize()
        await harbinger.shutdown()
        assert harbinger.status == ModuleStatus.OFFLINE

    def test_get_tools_returns_all(self, harbinger: Harbinger):
        tools = harbinger.get_tools()
        assert len(tools) == 8
        names = [t["name"] for t in tools]
        assert "briefing_compile" in names
        assert "decision_queue_add" in names
        assert "notification_send" in names

    def test_all_tools_have_required_fields(self, harbinger: Harbinger):
        for tool in harbinger.get_tools():
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert "permission_level" in tool


# --- Decision queue tests ---

class TestDecisionQueue:
    @pytest.mark.asyncio
    async def test_add_item(self, online_harbinger: Harbinger):
        result = await online_harbinger.execute("decision_queue_add", {
            "description": "Approve hardware purchase",
            "context": "RTX 5090 restocked at MSRP",
            "recommendation": "Buy now",
            "importance": 4,
            "source_module": "reaper",
        })
        assert result.success is True
        assert result.content["description"] == "Approve hardware purchase"
        assert result.content["status"] == "pending"

    @pytest.mark.asyncio
    async def test_add_empty_description_fails(self, online_harbinger: Harbinger):
        result = await online_harbinger.execute("decision_queue_add", {
            "description": "", "importance": 3,
        })
        assert result.success is False

    @pytest.mark.asyncio
    async def test_add_invalid_importance_fails(self, online_harbinger: Harbinger):
        result = await online_harbinger.execute("decision_queue_add", {
            "description": "Test", "importance": 6,
        })
        assert result.success is False

    @pytest.mark.asyncio
    async def test_read_pending(self, online_harbinger: Harbinger):
        await online_harbinger.execute("decision_queue_add", {
            "description": "Item 1", "importance": 2,
        })
        await online_harbinger.execute("decision_queue_add", {
            "description": "Item 2", "importance": 5,
        })
        result = await online_harbinger.execute("decision_queue_read", {})
        assert result.success is True
        assert result.content["pending_count"] == 2
        # Sorted by importance descending
        assert result.content["items"][0]["importance"] == 5

    @pytest.mark.asyncio
    async def test_resolve_item(self, online_harbinger: Harbinger):
        r = await online_harbinger.execute("decision_queue_add", {
            "description": "Buy GPU?", "importance": 4,
        })
        result = await online_harbinger.execute("decision_queue_resolve", {
            "decision_id": r.content["id"],
            "resolution": "Approved. Buy at MSRP.",
        })
        assert result.success is True
        assert result.content["status"] == "resolved"

    @pytest.mark.asyncio
    async def test_resolve_missing_id_fails(self, online_harbinger: Harbinger):
        result = await online_harbinger.execute("decision_queue_resolve", {
            "decision_id": "", "resolution": "test",
        })
        assert result.success is False

    @pytest.mark.asyncio
    async def test_resolve_missing_resolution_fails(self, online_harbinger: Harbinger):
        r = await online_harbinger.execute("decision_queue_add", {
            "description": "Test", "importance": 3,
        })
        result = await online_harbinger.execute("decision_queue_resolve", {
            "decision_id": r.content["id"], "resolution": "",
        })
        assert result.success is False

    @pytest.mark.asyncio
    async def test_resolve_nonexistent_fails(self, online_harbinger: Harbinger):
        result = await online_harbinger.execute("decision_queue_resolve", {
            "decision_id": "999", "resolution": "test",
        })
        assert result.success is False

    @pytest.mark.asyncio
    async def test_resolved_excluded_from_pending(self, online_harbinger: Harbinger):
        r = await online_harbinger.execute("decision_queue_add", {
            "description": "Test", "importance": 3,
        })
        await online_harbinger.execute("decision_queue_resolve", {
            "decision_id": r.content["id"], "resolution": "Done",
        })
        result = await online_harbinger.execute("decision_queue_read", {})
        assert result.content["pending_count"] == 0


# --- Notification tests ---

class TestNotifications:
    @pytest.mark.asyncio
    async def test_send_notification(self, online_harbinger: Harbinger):
        result = await online_harbinger.execute("notification_send", {
            "message": "Test alert",
            "severity": 2,
            "category": "system",
        })
        assert result.success is True
        assert result.content["severity"] == 2

    @pytest.mark.asyncio
    async def test_empty_message_fails(self, online_harbinger: Harbinger):
        result = await online_harbinger.execute("notification_send", {
            "message": "", "severity": 1,
        })
        assert result.success is False

    @pytest.mark.asyncio
    async def test_invalid_severity_fails(self, online_harbinger: Harbinger):
        result = await online_harbinger.execute("notification_send", {
            "message": "Test", "severity": 5,
        })
        assert result.success is False

    @pytest.mark.asyncio
    async def test_severity_assignment_urgent(self, online_harbinger: Harbinger):
        result = await online_harbinger.execute("notification_severity_assign", {
            "event": "Security breach detected on port 22",
            "category": "security",
        })
        assert result.success is True
        assert result.content["severity"] == 4

    @pytest.mark.asyncio
    async def test_severity_assignment_audible(self, online_harbinger: Harbinger):
        result = await online_harbinger.execute("notification_severity_assign", {
            "event": "Backup failed at 3 AM",
            "category": "system",
        })
        assert result.content["severity"] == 3

    @pytest.mark.asyncio
    async def test_severity_assignment_quiet(self, online_harbinger: Harbinger):
        result = await online_harbinger.execute("notification_severity_assign", {
            "event": "Software update available for Ollama",
        })
        assert result.content["severity"] == 2

    @pytest.mark.asyncio
    async def test_severity_assignment_silent(self, online_harbinger: Harbinger):
        result = await online_harbinger.execute("notification_severity_assign", {
            "event": "Research run completed normally",
        })
        assert result.content["severity"] == 1

    @pytest.mark.asyncio
    async def test_severity_empty_event_fails(self, online_harbinger: Harbinger):
        result = await online_harbinger.execute("notification_severity_assign", {
            "event": "",
        })
        assert result.success is False


# --- Nighttime rules ---

class TestNighttimeRules:
    def test_sleep_time_detection_night(self, harbinger: Harbinger):
        assert harbinger._is_sleep_time(dtime(23, 0)) is True

    def test_sleep_time_detection_early_morning(self, harbinger: Harbinger):
        assert harbinger._is_sleep_time(dtime(3, 0)) is True

    def test_awake_time_detection(self, harbinger: Harbinger):
        assert harbinger._is_sleep_time(dtime(12, 0)) is False

    def test_boundary_start(self, harbinger: Harbinger):
        assert harbinger._is_sleep_time(dtime(22, 0)) is True

    def test_boundary_end(self, harbinger: Harbinger):
        assert harbinger._is_sleep_time(dtime(6, 0)) is False


# --- Briefing tests ---

class TestBriefing:
    @pytest.mark.asyncio
    async def test_morning_briefing_structure(self, online_harbinger: Harbinger):
        result = await online_harbinger.execute("briefing_compile", {
            "briefing_type": "morning",
        })
        assert result.success is True
        assert result.content["type"] == "morning"
        assert len(result.content["sections"]) == 10

    @pytest.mark.asyncio
    async def test_evening_briefing_structure(self, online_harbinger: Harbinger):
        result = await online_harbinger.execute("briefing_compile", {
            "briefing_type": "evening",
        })
        assert result.success is True
        assert result.content["type"] == "evening"
        assert len(result.content["sections"]) == 5

    @pytest.mark.asyncio
    async def test_invalid_briefing_type_fails(self, online_harbinger: Harbinger):
        result = await online_harbinger.execute("briefing_compile", {
            "briefing_type": "midnight",
        })
        assert result.success is False

    @pytest.mark.asyncio
    async def test_morning_includes_decision_queue(self, online_harbinger: Harbinger):
        await online_harbinger.execute("decision_queue_add", {
            "description": "Pending decision", "importance": 5,
        })
        result = await online_harbinger.execute("briefing_compile", {
            "briefing_type": "morning",
        })
        queue_section = next(
            s for s in result.content["sections"] if s["name"] == "decision_queue"
        )
        assert isinstance(queue_section["content"], dict)
        assert queue_section["content"]["count"] == 1


# --- Report compilation ---

class TestReportCompile:
    @pytest.mark.asyncio
    async def test_compile_report(self, online_harbinger: Harbinger):
        result = await online_harbinger.execute("report_compile", {
            "title": "Weekly Review",
            "sections": [
                {"heading": "Summary", "content": "Good week."},
                {"heading": "Metrics", "content": "All green."},
            ],
        })
        assert result.success is True
        assert result.content["title"] == "Weekly Review"
        assert len(result.content["sections"]) == 2


# --- Channel fallback ---

class TestChannelFallback:
    @pytest.mark.asyncio
    async def test_telegram_falls_back_to_signal(self, online_harbinger: Harbinger):
        result = await online_harbinger.execute("channel_fallback", {
            "failed_channel": "telegram",
        })
        assert result.content["next_channel"] == "signal"

    @pytest.mark.asyncio
    async def test_email_falls_back_to_queue(self, online_harbinger: Harbinger):
        result = await online_harbinger.execute("channel_fallback", {
            "failed_channel": "email",
        })
        assert result.content["next_channel"] == "decision_queue"

    @pytest.mark.asyncio
    async def test_last_resort_is_queue(self, online_harbinger: Harbinger):
        result = await online_harbinger.execute("channel_fallback", {
            "failed_channel": "decision_queue",
        })
        assert result.content["next_channel"] == "decision_queue"

    @pytest.mark.asyncio
    async def test_unknown_channel_starts_at_telegram(self, online_harbinger: Harbinger):
        result = await online_harbinger.execute("channel_fallback", {
            "failed_channel": "pigeon",
        })
        assert result.content["next_channel"] == "telegram"


# --- Persistence ---

class TestHarbingerPersistence:
    @pytest.mark.asyncio
    async def test_queue_persists(self, tmp_path: Path):
        config = {"queue_file": str(tmp_path / "queue.json")}

        h1 = Harbinger(config)
        await h1.initialize()
        await h1.execute("decision_queue_add", {
            "description": "Persist me", "importance": 4,
        })
        await h1.shutdown()

        h2 = Harbinger(config)
        await h2.initialize()
        result = await h2.execute("decision_queue_read", {})
        assert result.content["pending_count"] == 1
        await h2.shutdown()


# --- Unknown tool ---

class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_fails(self, online_harbinger: Harbinger):
        result = await online_harbinger.execute("nonexistent", {})
        assert result.success is False
        assert "Unknown tool" in result.error
