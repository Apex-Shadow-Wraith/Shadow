"""
Tests for Wraith — Shadow's Fast Brain & Daily Workhorse
=========================================================
Covers lifecycle, reminder CRUD, dismiss escalation, classification,
proactive checks, and persistence.
"""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

from modules.base import ModuleStatus, ToolResult
from modules.wraith.wraith import Wraith


@pytest.fixture
def wraith(tmp_path: Path) -> Wraith:
    """Create a Wraith instance with a temp reminder file."""
    config = {"reminder_file": str(tmp_path / "reminders.json")}
    return Wraith(config)


@pytest.fixture
async def online_wraith(wraith: Wraith) -> Wraith:
    """Create and initialize a Wraith instance."""
    await wraith.initialize()
    return wraith


# --- Lifecycle tests ---

class TestWraithLifecycle:
    @pytest.mark.asyncio
    async def test_initialize_sets_online(self, wraith: Wraith):
        assert wraith.status == ModuleStatus.OFFLINE
        await wraith.initialize()
        assert wraith.status == ModuleStatus.ONLINE

    @pytest.mark.asyncio
    async def test_shutdown_sets_offline(self, wraith: Wraith):
        await wraith.initialize()
        await wraith.shutdown()
        assert wraith.status == ModuleStatus.OFFLINE

    @pytest.mark.asyncio
    async def test_shutdown_persists_reminders(self, wraith: Wraith):
        await wraith.initialize()
        await wraith.execute("reminder_create", {"content": "Test", "importance": 3})
        await wraith.shutdown()
        assert wraith._reminder_file.exists()

    def test_get_tools_returns_all_tools(self, wraith: Wraith):
        tools = wraith.get_tools()
        assert isinstance(tools, list)
        assert len(tools) == 7
        tool_names = [t["name"] for t in tools]
        assert "quick_answer" in tool_names
        assert "reminder_create" in tool_names
        assert "reminder_list" in tool_names
        assert "reminder_dismiss" in tool_names
        assert "reminder_kill" in tool_names
        assert "classify_task" in tool_names
        assert "proactive_check" in tool_names

    def test_all_tools_have_required_fields(self, wraith: Wraith):
        for tool in wraith.get_tools():
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert "permission_level" in tool

    def test_module_info(self, wraith: Wraith):
        info = wraith.info
        assert info["name"] == "wraith"
        assert info["status"] == "offline"


# --- Quick answer tests ---

class TestQuickAnswer:
    @pytest.mark.asyncio
    async def test_with_context(self, online_wraith: Wraith):
        result = await online_wraith.execute(
            "quick_answer", {"query": "What time?", "context": "It is 3 PM."}
        )
        assert result.success is True
        assert result.content["answer"] == "It is 3 PM."

    @pytest.mark.asyncio
    async def test_without_context(self, online_wraith: Wraith):
        result = await online_wraith.execute("quick_answer", {"query": "Hello?"})
        assert result.success is True
        assert "No context" in result.content["answer"]

    @pytest.mark.asyncio
    async def test_empty_query_fails(self, online_wraith: Wraith):
        result = await online_wraith.execute("quick_answer", {"query": ""})
        assert result.success is False
        assert "No query" in result.error


# --- Reminder create tests ---

class TestReminderCreate:
    @pytest.mark.asyncio
    async def test_create_basic(self, online_wraith: Wraith):
        result = await online_wraith.execute(
            "reminder_create", {"content": "Buy mulch", "importance": 4}
        )
        assert result.success is True
        assert result.content["content"] == "Buy mulch"
        assert result.content["importance"] == 4
        assert result.content["killed"] is False

    @pytest.mark.asyncio
    async def test_default_importance(self, online_wraith: Wraith):
        result = await online_wraith.execute(
            "reminder_create", {"content": "Something"}
        )
        assert result.success is True
        assert result.content["importance"] == 3

    @pytest.mark.asyncio
    async def test_empty_content_fails(self, online_wraith: Wraith):
        result = await online_wraith.execute("reminder_create", {"content": ""})
        assert result.success is False

    @pytest.mark.asyncio
    async def test_invalid_importance_fails(self, online_wraith: Wraith):
        result = await online_wraith.execute(
            "reminder_create", {"content": "Test", "importance": 6}
        )
        assert result.success is False
        assert "1 and 5" in result.error

    @pytest.mark.asyncio
    async def test_importance_zero_fails(self, online_wraith: Wraith):
        result = await online_wraith.execute(
            "reminder_create", {"content": "Test", "importance": 0}
        )
        assert result.success is False

    @pytest.mark.asyncio
    async def test_sequential_ids(self, online_wraith: Wraith):
        r1 = await online_wraith.execute("reminder_create", {"content": "First"})
        r2 = await online_wraith.execute("reminder_create", {"content": "Second"})
        assert int(r1.content["id"]) < int(r2.content["id"])


# --- Reminder list tests ---

class TestReminderList:
    @pytest.mark.asyncio
    async def test_empty_list(self, online_wraith: Wraith):
        result = await online_wraith.execute("reminder_list", {})
        assert result.success is True
        assert result.content["total"] == 0

    @pytest.mark.asyncio
    async def test_sorted_by_importance(self, online_wraith: Wraith):
        await online_wraith.execute("reminder_create", {"content": "Low", "importance": 1})
        await online_wraith.execute("reminder_create", {"content": "High", "importance": 5})
        await online_wraith.execute("reminder_create", {"content": "Mid", "importance": 3})

        result = await online_wraith.execute("reminder_list", {})
        reminders = result.content["reminders"]
        assert reminders[0]["importance"] == 5
        assert reminders[1]["importance"] == 3
        assert reminders[2]["importance"] == 1

    @pytest.mark.asyncio
    async def test_excludes_killed(self, online_wraith: Wraith):
        r = await online_wraith.execute("reminder_create", {"content": "Kill me"})
        await online_wraith.execute("reminder_kill", {"reminder_id": r.content["id"]})

        result = await online_wraith.execute("reminder_list", {})
        assert result.content["active"] == 0
        assert result.content["killed"] == 1

    @pytest.mark.asyncio
    async def test_include_killed(self, online_wraith: Wraith):
        r = await online_wraith.execute("reminder_create", {"content": "Kill me"})
        await online_wraith.execute("reminder_kill", {"reminder_id": r.content["id"]})

        result = await online_wraith.execute("reminder_list", {"include_killed": True})
        assert result.content["total"] == 1


# --- Reminder dismiss tests ---

class TestReminderDismiss:
    @pytest.mark.asyncio
    async def test_first_dismiss_1_day(self, online_wraith: Wraith):
        r = await online_wraith.execute("reminder_create", {"content": "Dismiss me"})
        result = await online_wraith.execute(
            "reminder_dismiss", {"reminder_id": r.content["id"]}
        )
        assert result.success is True
        assert result.content["dismiss_count"] == 1
        assert result.content["resurface_days"] == 1

    @pytest.mark.asyncio
    async def test_second_dismiss_3_days(self, online_wraith: Wraith):
        r = await online_wraith.execute("reminder_create", {"content": "Dismiss me"})
        rid = r.content["id"]
        await online_wraith.execute("reminder_dismiss", {"reminder_id": rid})
        result = await online_wraith.execute("reminder_dismiss", {"reminder_id": rid})
        assert result.content["dismiss_count"] == 2
        assert result.content["resurface_days"] == 3

    @pytest.mark.asyncio
    async def test_third_dismiss_7_days(self, online_wraith: Wraith):
        r = await online_wraith.execute("reminder_create", {"content": "Dismiss me"})
        rid = r.content["id"]
        for _ in range(2):
            await online_wraith.execute("reminder_dismiss", {"reminder_id": rid})
        result = await online_wraith.execute("reminder_dismiss", {"reminder_id": rid})
        assert result.content["dismiss_count"] == 3
        assert result.content["resurface_days"] == 7

    @pytest.mark.asyncio
    async def test_fourth_dismiss_weekly(self, online_wraith: Wraith):
        r = await online_wraith.execute("reminder_create", {"content": "Dismiss me"})
        rid = r.content["id"]
        for _ in range(3):
            await online_wraith.execute("reminder_dismiss", {"reminder_id": rid})
        result = await online_wraith.execute("reminder_dismiss", {"reminder_id": rid})
        assert result.content["dismiss_count"] == 4
        assert result.content["resurface_days"] == 7

    @pytest.mark.asyncio
    async def test_dismiss_nonexistent_fails(self, online_wraith: Wraith):
        result = await online_wraith.execute("reminder_dismiss", {"reminder_id": "999"})
        assert result.success is False
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_dismiss_killed_fails(self, online_wraith: Wraith):
        r = await online_wraith.execute("reminder_create", {"content": "Kill me"})
        rid = r.content["id"]
        await online_wraith.execute("reminder_kill", {"reminder_id": rid})
        result = await online_wraith.execute("reminder_dismiss", {"reminder_id": rid})
        assert result.success is False
        assert "killed" in result.error

    @pytest.mark.asyncio
    async def test_dismiss_missing_id_fails(self, online_wraith: Wraith):
        result = await online_wraith.execute("reminder_dismiss", {})
        assert result.success is False


# --- Reminder kill tests ---

class TestReminderKill:
    @pytest.mark.asyncio
    async def test_kill_reminder(self, online_wraith: Wraith):
        r = await online_wraith.execute("reminder_create", {"content": "Kill me"})
        result = await online_wraith.execute(
            "reminder_kill", {"reminder_id": r.content["id"]}
        )
        assert result.success is True
        assert result.content["status"] == "killed"

    @pytest.mark.asyncio
    async def test_kill_nonexistent_fails(self, online_wraith: Wraith):
        result = await online_wraith.execute("reminder_kill", {"reminder_id": "999"})
        assert result.success is False

    @pytest.mark.asyncio
    async def test_kill_missing_id_fails(self, online_wraith: Wraith):
        result = await online_wraith.execute("reminder_kill", {})
        assert result.success is False


# --- Classify task tests ---

class TestClassifyTask:
    @pytest.mark.asyncio
    async def test_memory_classification(self, online_wraith: Wraith):
        result = await online_wraith.execute(
            "classify_task", {"input_text": "remember that I like pizza"}
        )
        assert result.success is True
        assert result.content["module"] == "grimoire"
        assert result.content["task_type"] == "memory"

    @pytest.mark.asyncio
    async def test_research_classification(self, online_wraith: Wraith):
        result = await online_wraith.execute(
            "classify_task", {"input_text": "search for RTX 5090 prices"}
        )
        assert result.success is True
        assert result.content["module"] == "reaper"

    @pytest.mark.asyncio
    async def test_math_classification(self, online_wraith: Wraith):
        result = await online_wraith.execute(
            "classify_task", {"input_text": "calculate 15% of 250"}
        )
        assert result.success is True
        assert result.content["module"] == "cipher"

    @pytest.mark.asyncio
    async def test_code_classification(self, online_wraith: Wraith):
        result = await online_wraith.execute(
            "classify_task", {"input_text": "write code for a Python web scraper"}
        )
        assert result.success is True
        assert result.content["module"] == "omen"

    @pytest.mark.asyncio
    async def test_default_classification(self, online_wraith: Wraith):
        result = await online_wraith.execute(
            "classify_task", {"input_text": "how are you doing today"}
        )
        assert result.success is True
        assert result.content["module"] == "wraith"

    @pytest.mark.asyncio
    async def test_empty_input_fails(self, online_wraith: Wraith):
        result = await online_wraith.execute("classify_task", {"input_text": ""})
        assert result.success is False


# --- Proactive check tests ---

class TestProactiveCheck:
    @pytest.mark.asyncio
    async def test_no_due_reminders(self, online_wraith: Wraith):
        result = await online_wraith.execute("proactive_check", {})
        assert result.success is True
        assert result.content["count"] == 0

    @pytest.mark.asyncio
    async def test_due_reminder_surfaces(self, online_wraith: Wraith):
        # Create a reminder — its next_surface is now, so it should be due
        await online_wraith.execute(
            "reminder_create", {"content": "Due now", "importance": 5}
        )
        result = await online_wraith.execute("proactive_check", {})
        assert result.content["count"] == 1
        assert result.content["suggestions"][0]["content"] == "Due now"

    @pytest.mark.asyncio
    async def test_dismissed_not_due_yet(self, online_wraith: Wraith):
        r = await online_wraith.execute(
            "reminder_create", {"content": "Not yet", "importance": 3}
        )
        await online_wraith.execute("reminder_dismiss", {"reminder_id": r.content["id"]})
        result = await online_wraith.execute("proactive_check", {})
        # After dismiss, next_surface is tomorrow — not due now
        assert result.content["count"] == 0


# --- Persistence tests ---

class TestPersistence:
    @pytest.mark.asyncio
    async def test_reminders_persist_across_instances(self, tmp_path: Path):
        config = {"reminder_file": str(tmp_path / "reminders.json")}

        # First instance: create a reminder
        w1 = Wraith(config)
        await w1.initialize()
        await w1.execute("reminder_create", {"content": "Persist me", "importance": 5})
        await w1.shutdown()

        # Second instance: should load the reminder
        w2 = Wraith(config)
        await w2.initialize()
        result = await w2.execute("reminder_list", {})
        assert result.content["total"] == 1
        assert result.content["reminders"][0]["content"] == "Persist me"
        await w2.shutdown()

    @pytest.mark.asyncio
    async def test_corrupted_file_starts_fresh(self, tmp_path: Path):
        reminder_file = tmp_path / "reminders.json"
        reminder_file.write_text("not valid json!!!")

        config = {"reminder_file": str(reminder_file)}
        w = Wraith(config)
        await w.initialize()
        result = await w.execute("reminder_list", {})
        assert result.content["total"] == 0
        await w.shutdown()


# --- Unknown tool test ---

class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_fails(self, online_wraith: Wraith):
        result = await online_wraith.execute("nonexistent_tool", {})
        assert result.success is False
        assert "Unknown tool" in result.error


# --- Execution time tracking ---

class TestExecutionTracking:
    @pytest.mark.asyncio
    async def test_execution_time_recorded(self, online_wraith: Wraith):
        result = await online_wraith.execute("reminder_list", {})
        assert result.execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_success_rate_tracked(self, online_wraith: Wraith):
        await online_wraith.execute("reminder_list", {})
        await online_wraith.execute("reminder_create", {"content": ""})  # Will fail
        assert online_wraith.success_rate == pytest.approx(0.5)
