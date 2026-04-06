"""Tests for Harbinger evening summary assembly pipeline."""

import time

import pytest
from unittest.mock import MagicMock

from modules.harbinger.harbinger import Harbinger
from modules.base import ToolResult


@pytest.fixture
def harbinger(tmp_path):
    """Create a Harbinger instance with tmp_path for queue persistence."""
    queue_file = tmp_path / "harbinger_queue.json"
    return Harbinger(config={"queue_file": str(queue_file)})


@pytest.fixture
def mock_task_tracker():
    """Mock TaskTracker with completed, queued, and running tasks."""
    m = MagicMock()
    today = time.strftime("%Y-%m-%d")

    def list_tasks(status_filter=None):
        tasks = {
            "completed": [
                {
                    "id": "t1",
                    "description": "Mow Johnson property",
                    "status": "completed",
                    "completed_at": f"{today}T14:30:00",
                    "priority": 2,
                },
                {
                    "id": "t2",
                    "description": "Order spring mulch",
                    "status": "completed",
                    "completed_at": f"{today}T16:00:00",
                    "priority": 3,
                },
                {
                    "id": "t3",
                    "description": "Yesterday's task",
                    "status": "completed",
                    "completed_at": "2026-04-04T09:00:00",
                    "priority": 3,
                },
            ],
            "queued": [
                {
                    "id": "t4",
                    "description": "Schedule crew for Friday",
                    "status": "queued",
                    "priority": 2,
                },
                {
                    "id": "t5",
                    "description": "Review equipment maintenance",
                    "status": "queued",
                    "priority": 4,
                },
            ],
            "running": [
                {
                    "id": "t6",
                    "description": "Downloading supplier catalog",
                    "status": "running",
                    "priority": 3,
                },
            ],
        }
        return tasks.get(status_filter, [])

    m.list_tasks.side_effect = list_tasks
    return m


@pytest.fixture
def mock_void():
    """Mock Void module with _system_health()."""
    m = MagicMock()
    m._system_health.return_value = ToolResult(
        success=True,
        content={
            "cpu_percent": 18.3,
            "ram_percent": 42.1,
            "disk_percent": 51.0,
        },
        tool_name="system_health",
        module="void",
    )
    return m


@pytest.fixture
def mock_reaper():
    """Mock Reaper module with get_briefing_data()."""
    m = MagicMock()
    m.get_briefing_data.return_value = {
        "generated_at": "2026-04-05T17:00:00",
        "research": [
            {"content": "Spring aeration best practices", "source": "web"},
            {"content": "New mulch pricing from supplier", "source": "web"},
        ],
        "reddit": [],
    }
    return m


@pytest.fixture
def all_modules(mock_task_tracker, mock_void, mock_reaper):
    """Dict of all mocked modules for evening summary."""
    return {
        "task_tracker": mock_task_tracker,
        "void": mock_void,
        "reaper": mock_reaper,
    }


class TestEveningSummaryStructure:
    """Test that evening summary has the correct structure."""

    def test_evening_summary_structure(self, harbinger, all_modules):
        """Verify all 5 sections present with correct names."""
        summary = harbinger.assemble_evening_summary(all_modules)

        assert summary["type"] == "evening_summary"
        assert "compiled_at" in summary
        assert "date" in summary
        assert summary["section_count"] == 5
        assert len(summary["sections"]) == 5

        titles = [s["title"] for s in summary["sections"]]
        assert "Completed Today" in titles
        assert "Pending Items" in titles
        assert "Tomorrow Preview" in titles
        assert "Shadow Activity" in titles
        assert "Overnight Plan" in titles

    def test_sections_have_required_fields(self, harbinger, all_modules):
        """Every section has title, content, priority, and source."""
        summary = harbinger.assemble_evening_summary(all_modules)

        for section in summary["sections"]:
            assert "title" in section
            assert "content" in section
            assert "priority" in section
            assert "source" in section

    def test_priority_sorting(self, harbinger, all_modules):
        """Sections are sorted by priority (1 first)."""
        summary = harbinger.assemble_evening_summary(all_modules)

        priorities = [s["priority"] for s in summary["sections"]]
        assert priorities == sorted(priorities)


class TestEveningSummaryNoModules:
    """Test graceful degradation when no modules available."""

    def test_evening_summary_no_modules(self, harbinger):
        """Graceful degradation when no modules available."""
        summary = harbinger.assemble_evening_summary({})

        assert summary["type"] == "evening_summary"
        assert summary["section_count"] == 5

        # All module-dependent sections should degrade gracefully
        for section in summary["sections"]:
            assert section["content"] is not None
            # Should not have crashed — content is either "Module not available"
            # or a valid dict/string
            assert isinstance(section["content"], (str, dict))

    def test_overnight_plan_always_present(self, harbinger):
        """Overnight plan section is always present even with no modules."""
        summary = harbinger.assemble_evening_summary({})

        overnight = next(s for s in summary["sections"] if s["title"] == "Overnight Plan")
        assert "Phase 1" in overnight["content"]
        assert overnight["source"] == "harbinger"


class TestCompletedTasksInSummary:
    """Test that completed tasks appear correctly."""

    def test_completed_tasks_in_summary(self, harbinger, all_modules):
        """Mock task tracker with completed tasks, verify they appear."""
        summary = harbinger.assemble_evening_summary(all_modules)

        completed_section = next(
            s for s in summary["sections"] if s["title"] == "Completed Today"
        )
        content = completed_section["content"]
        assert content["count"] == 2  # Only today's tasks, not yesterday's
        assert len(content["tasks"]) == 2

    def test_completed_excludes_other_days(self, harbinger, mock_task_tracker):
        """Only today's completed tasks are included."""
        summary = harbinger.assemble_evening_summary({"task_tracker": mock_task_tracker})

        completed_section = next(
            s for s in summary["sections"] if s["title"] == "Completed Today"
        )
        descriptions = [t["description"] for t in completed_section["content"]["tasks"]]
        assert "Yesterday's task" not in descriptions
        assert "Mow Johnson property" in descriptions

    def test_no_task_tracker_shows_unavailable(self, harbinger):
        """Without task_tracker, completed section degrades gracefully."""
        summary = harbinger.assemble_evening_summary({})

        completed_section = next(
            s for s in summary["sections"] if s["title"] == "Completed Today"
        )
        assert completed_section["content"] == "Module not available"
        assert completed_section["source"] is None


class TestPendingItemsIncludeDecisionQueue:
    """Test that pending items include both tasks and decision queue."""

    def test_pending_items_include_decision_queue(self, harbinger, mock_task_tracker):
        """Add items to decision queue, verify they appear in pending section."""
        # Add decision queue items
        harbinger._queue = [
            {
                "id": "1",
                "description": "Approve new equipment purchase",
                "importance": 4,
                "status": "pending",
            },
            {
                "id": "2",
                "description": "Review crew schedule change",
                "importance": 3,
                "status": "pending",
            },
        ]

        summary = harbinger.assemble_evening_summary({"task_tracker": mock_task_tracker})

        pending_section = next(
            s for s in summary["sections"] if s["title"] == "Pending Items"
        )
        content = pending_section["content"]
        assert content["decision_queue_count"] == 2
        assert content["task_count"] == 3  # 2 queued + 1 running

    def test_pending_with_no_tasks_but_decisions(self, harbinger):
        """Decision queue items show up even without task tracker."""
        harbinger._queue = [
            {
                "id": "1",
                "description": "Approve something",
                "importance": 3,
                "status": "pending",
            },
        ]

        summary = harbinger.assemble_evening_summary({})

        pending_section = next(
            s for s in summary["sections"] if s["title"] == "Pending Items"
        )
        assert pending_section["content"]["decision_queue_count"] == 1
        assert pending_section["priority"] == 1  # High priority when items pending

    def test_pending_resolved_decisions_excluded(self, harbinger):
        """Resolved decisions don't count in pending."""
        harbinger._queue = [
            {"id": "1", "description": "Done", "importance": 3, "status": "resolved"},
        ]

        summary = harbinger.assemble_evening_summary({})

        pending_section = next(
            s for s in summary["sections"] if s["title"] == "Pending Items"
        )
        # No pending tasks or decisions — should show empty
        assert pending_section["content"] == "Module not available"


class TestTomorrowPreview:
    """Test tomorrow preview section."""

    def test_tomorrow_shows_queued_count(self, harbinger, mock_task_tracker):
        """Tomorrow preview shows count of queued tasks."""
        summary = harbinger.assemble_evening_summary({"task_tracker": mock_task_tracker})

        tomorrow = next(
            s for s in summary["sections"] if s["title"] == "Tomorrow Preview"
        )
        assert tomorrow["content"]["queued_count"] == 2

    def test_tomorrow_shows_high_priority(self, harbinger, mock_task_tracker):
        """Tomorrow preview highlights high-priority items (priority <= 3)."""
        summary = harbinger.assemble_evening_summary({"task_tracker": mock_task_tracker})

        tomorrow = next(
            s for s in summary["sections"] if s["title"] == "Tomorrow Preview"
        )
        # t4 has priority 2 (high), t5 has priority 4 (not high)
        assert tomorrow["content"]["high_priority_count"] == 1
        assert tomorrow["content"]["high_priority_tasks"][0]["description"] == "Schedule crew for Friday"


class TestShadowActivity:
    """Test shadow activity section."""

    def test_shadow_activity_with_modules(self, harbinger, mock_void, mock_reaper):
        """Shadow activity includes health and research data."""
        modules = {"void": mock_void, "reaper": mock_reaper}
        summary = harbinger.assemble_evening_summary(modules)

        activity = next(
            s for s in summary["sections"] if s["title"] == "Shadow Activity"
        )
        content = activity["content"]
        assert "system_health" in content
        assert content["system_health"]["cpu_percent"] == 18.3
        assert content["research_completed"] == 2

    def test_shadow_activity_no_modules(self, harbinger):
        """Shadow activity degrades when no modules available."""
        summary = harbinger.assemble_evening_summary({})

        activity = next(
            s for s in summary["sections"] if s["title"] == "Shadow Activity"
        )
        assert activity["content"] == "Module not available"


class TestFormatEveningSummary:
    """Test format_evening_summary() output."""

    def test_produces_readable_string(self, harbinger, all_modules):
        """Format produces a non-empty readable string."""
        summary = harbinger.assemble_evening_summary(all_modules)
        text = harbinger.format_evening_summary(summary)

        assert isinstance(text, str)
        assert len(text) > 100
        assert "SHADOW EVENING SUMMARY" in text
        assert "END SUMMARY" in text

    def test_contains_all_section_titles(self, harbinger, all_modules):
        """Formatted text includes all section titles."""
        summary = harbinger.assemble_evening_summary(all_modules)
        text = harbinger.format_evening_summary(summary)

        for section in summary["sections"]:
            assert section["title"] in text

    def test_empty_summary_format(self, harbinger):
        """Formatting with no modules still works."""
        summary = harbinger.assemble_evening_summary({})
        text = harbinger.format_evening_summary(summary)

        assert "SHADOW EVENING SUMMARY" in text
        assert "5 sections" in text


class TestBriefingCompileEvening:
    """Test that briefing_compile tool works with evening + modules."""

    @pytest.mark.asyncio
    async def test_evening_compile_with_modules(self, harbinger, all_modules):
        """briefing_compile with evening type and modules uses assemble_evening_summary."""
        await harbinger.initialize()
        result = await harbinger.execute("briefing_compile", {
            "briefing_type": "evening",
            "modules": all_modules,
        })

        assert result.success is True
        assert result.content["type"] == "evening"
        assert len(result.content["sections"]) == 5

        names = [s["name"] for s in result.content["sections"]]
        assert "completed_today" in names
        assert "overnight_plan" in names

    @pytest.mark.asyncio
    async def test_evening_compile_without_modules_uses_template(self, harbinger):
        """briefing_compile without modules falls back to template behavior."""
        await harbinger.initialize()
        result = await harbinger.execute("briefing_compile", {
            "briefing_type": "evening",
        })

        assert result.success is True
        assert result.content["type"] == "evening"
        assert len(result.content["sections"]) == 5
        # Template mode — sections have "No data available." default
        for section in result.content["sections"]:
            assert "name" in section


class TestModuleExceptionHandling:
    """Test that module exceptions don't crash the evening summary."""

    def test_broken_task_tracker(self, harbinger):
        """If task tracker raises, sections still work."""
        broken = MagicMock()
        broken.list_tasks.side_effect = RuntimeError("DB locked")

        summary = harbinger.assemble_evening_summary({"task_tracker": broken})

        assert summary["section_count"] == 5
        completed = next(s for s in summary["sections"] if s["title"] == "Completed Today")
        assert "Error" in str(completed["content"])

    def test_broken_void(self, harbinger):
        """If Void raises, shadow activity still works."""
        broken_void = MagicMock()
        broken_void._system_health.side_effect = RuntimeError("psutil error")

        summary = harbinger.assemble_evening_summary({"void": broken_void})

        activity = next(s for s in summary["sections"] if s["title"] == "Shadow Activity")
        # Should have error info but not crash
        assert "system_health_error" in activity["content"]


class TestApexStatsInEvening:
    """Test Apex escalation stats in evening summary."""

    def test_apex_stats_in_evening(self, harbinger):
        """Mock apex module — escalation stats appear in Shadow Activity section."""
        mock_apex = MagicMock()
        mock_apex._escalation_stats.return_value = ToolResult(
            success=True,
            content={
                "total_escalations": 7,
                "total_cost_usd": 0.25,
                "by_type": {"question": 4, "research": 3},
            },
            tool_name="escalation_stats", module="apex",
        )

        summary = harbinger.assemble_evening_summary({"apex": mock_apex})
        activity = next(s for s in summary["sections"] if s["title"] == "Shadow Activity")

        assert "escalation_stats" in activity["content"]
        assert activity["content"]["escalation_stats"]["total_escalations"] == 7
        assert activity["content"]["escalation_stats"]["total_cost"] == 0.25

    def test_apex_exception_in_evening(self, harbinger):
        """Apex exception doesn't crash evening summary."""
        mock_apex = MagicMock()
        mock_apex._escalation_stats.side_effect = RuntimeError("API down")

        summary = harbinger.assemble_evening_summary({"apex": mock_apex})
        activity = next(s for s in summary["sections"] if s["title"] == "Shadow Activity")

        assert "escalation_error" in activity["content"]


class TestProactiveSuggestionsInEvening:
    """Test Wraith proactive suggestions in evening summary."""

    def test_proactive_suggestions_in_evening(self, harbinger):
        """Mock wraith with suggestions — appear in evening summary."""
        mock_wraith = MagicMock()
        mock_wraith._proactive_suggestions.return_value = ToolResult(
            success=True,
            content={
                "suggestions": [
                    {"suggestion": "Review weekly invoices", "confidence": 0.8, "source": "pattern"},
                    {"suggestion": "Check supplier prices", "confidence": 0.6, "source": "neglect"},
                ],
                "count": 2,
                "checked_at": "2026-04-05T18:00:00",
            },
            tool_name="proactive_suggestions", module="wraith",
        )

        summary = harbinger.assemble_evening_summary({"wraith": mock_wraith})
        activity = next(s for s in summary["sections"] if s["title"] == "Shadow Activity")

        assert "proactive_suggestions" in activity["content"]
        assert len(activity["content"]["proactive_suggestions"]) == 2

    def test_wraith_exception_in_evening(self, harbinger):
        """Wraith exception doesn't crash evening summary."""
        mock_wraith = MagicMock()
        mock_wraith._proactive_suggestions.side_effect = RuntimeError("Wraith error")

        summary = harbinger.assemble_evening_summary({"wraith": mock_wraith})
        activity = next(s for s in summary["sections"] if s["title"] == "Shadow Activity")

        assert "proactive_error" in activity["content"]

    def test_empty_suggestions_not_included(self, harbinger):
        """Empty suggestions list is not added to activity."""
        mock_wraith = MagicMock()
        mock_wraith._proactive_suggestions.return_value = ToolResult(
            success=True,
            content={"suggestions": [], "count": 0, "checked_at": "2026-04-05T18:00:00"},
            tool_name="proactive_suggestions", module="wraith",
        )

        summary = harbinger.assemble_evening_summary({"wraith": mock_wraith})
        activity = next(s for s in summary["sections"] if s["title"] == "Shadow Activity")

        # Empty suggestions should not be in activity content
        assert "proactive_suggestions" not in activity.get("content", {})
