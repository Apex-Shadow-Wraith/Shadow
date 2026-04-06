"""Tests for Harbinger morning briefing assembly pipeline."""

import pytest
from unittest.mock import MagicMock, PropertyMock

from modules.harbinger.harbinger import Harbinger
from modules.base import ToolResult


@pytest.fixture
def harbinger(tmp_path):
    """Create a Harbinger instance with tmp_path for queue persistence."""
    queue_file = tmp_path / "harbinger_queue.json"
    h = Harbinger(config={"queue_file": str(queue_file)})
    return h


@pytest.fixture
def mock_grimoire():
    """Mock Grimoire module with stats()."""
    m = MagicMock()
    m.stats.return_value = {
        "active_memories": 33,
        "inactive_memories": 2,
        "total_stored": 35,
        "vector_count": 33,
        "by_category": {"fact": 20, "preference": 10, "correction": 5},
        "by_source": {"user": 15, "system": 20},
    }
    return m


@pytest.fixture
def mock_cerberus():
    """Mock Cerberus module with stats property."""
    m = MagicMock()
    type(m).stats = PropertyMock(return_value={
        "checks": 142,
        "denials": 3,
        "false_positives": 1,
        "denial_rate": 0.021,
        "audit_entries": 142,
        "config_hash": "abc123",
    })
    return m


@pytest.fixture
def mock_wraith():
    """Mock Wraith module with _proactive_check()."""
    m = MagicMock()
    m._proactive_check.return_value = ToolResult(
        success=True,
        content={
            "suggestions": [
                {"description": "Call supplier about mulch delivery", "importance": 4},
                {"description": "Review weekly invoice batch", "importance": 3},
            ],
            "count": 2,
            "checked_at": "2026-04-05T06:00:00",
        },
        tool_name="proactive_check",
        module="wraith",
    )
    return m


@pytest.fixture
def mock_void():
    """Mock Void module with _system_health()."""
    m = MagicMock()
    m._system_health.return_value = ToolResult(
        success=True,
        content={
            "cpu_percent": 12.5,
            "ram_total_gb": 32.0,
            "ram_used_gb": 8.2,
            "ram_percent": 25.6,
            "disk_total_gb": 1000.0,
            "disk_used_gb": 450.0,
            "disk_percent": 45.0,
            "alerts": [],
            "timestamp": "2026-04-05T06:00:00",
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
        "generated_at": "2026-04-05T05:30:00",
        "research": [
            {"content": "New Python 3.14 feature: template strings", "source": "web"},
        ],
        "reddit": [
            {"content": "r/landscaping post about spring aeration timing", "source": "reddit"},
        ],
        "youtube": [],
    }
    return m


@pytest.fixture
def all_modules(mock_grimoire, mock_cerberus, mock_wraith, mock_void, mock_reaper):
    """Dict of all mocked modules."""
    return {
        "grimoire": mock_grimoire,
        "cerberus": mock_cerberus,
        "wraith": mock_wraith,
        "void": mock_void,
        "reaper": mock_reaper,
    }


class TestAssembleMorningBriefing:
    """Tests for assemble_morning_briefing()."""

    def test_all_modules_available(self, harbinger, all_modules):
        """Briefing assembles correctly with all modules present."""
        briefing = harbinger.assemble_morning_briefing(all_modules)

        assert briefing["type"] == "morning_briefing"
        assert "compiled_at" in briefing
        assert "date" in briefing
        assert briefing["section_count"] == 6
        assert len(briefing["sections"]) == 6

    def test_sections_have_required_fields(self, harbinger, all_modules):
        """Every section has title, content, and priority."""
        briefing = harbinger.assemble_morning_briefing(all_modules)

        for section in briefing["sections"]:
            assert "title" in section
            assert "content" in section
            assert "priority" in section
            assert section["priority"] in (1, 2, 3)

    def test_priority_sorting(self, harbinger, all_modules):
        """Sections are sorted by priority (1 first)."""
        briefing = harbinger.assemble_morning_briefing(all_modules)

        priorities = [s["priority"] for s in briefing["sections"]]
        assert priorities == sorted(priorities)

    def test_some_modules_missing(self, harbinger, mock_grimoire, mock_cerberus):
        """Briefing degrades gracefully when some modules are absent."""
        partial = {"grimoire": mock_grimoire, "cerberus": mock_cerberus}
        briefing = harbinger.assemble_morning_briefing(partial)

        assert briefing["section_count"] == 6
        sources = {s.get("source") for s in briefing["sections"]}
        assert "grimoire" in sources
        assert "cerberus" in sources
        # Missing modules should have None source
        unavailable = [s for s in briefing["sections"] if s["source"] is None]
        assert len(unavailable) == 3  # wraith, void, reaper missing

    def test_no_modules(self, harbinger):
        """Briefing with empty modules dict still returns valid structure."""
        briefing = harbinger.assemble_morning_briefing({})

        assert briefing["type"] == "morning_briefing"
        assert briefing["section_count"] == 6
        for section in briefing["sections"]:
            assert section["content"] == "Module not available" or section["source"] == "harbinger"

    def test_grimoire_data_in_briefing(self, harbinger, all_modules):
        """Grimoire memory stats appear in briefing."""
        briefing = harbinger.assemble_morning_briefing(all_modules)

        memory_section = next(s for s in briefing["sections"] if s["source"] == "grimoire")
        assert memory_section["title"] == "Memory Status"
        assert memory_section["content"]["active_memories"] == 33
        assert memory_section["content"]["total_stored"] == 35

    def test_cerberus_data_in_briefing(self, harbinger, all_modules):
        """Cerberus safety stats appear in briefing."""
        briefing = harbinger.assemble_morning_briefing(all_modules)

        safety_section = next(s for s in briefing["sections"] if s["source"] == "cerberus")
        assert safety_section["title"] == "Safety Status"
        assert safety_section["content"]["checks"] == 142
        assert safety_section["content"]["denials"] == 3

    def test_wraith_reminders_in_briefing(self, harbinger, all_modules):
        """Due reminders from Wraith appear in briefing."""
        briefing = harbinger.assemble_morning_briefing(all_modules)

        reminder_section = next(s for s in briefing["sections"] if s["source"] == "wraith")
        assert reminder_section["title"] == "Reminders & Tasks"
        assert reminder_section["content"]["count"] == 2
        assert len(reminder_section["content"]["due_items"]) == 2

    def test_decision_queue_in_briefing(self, harbinger):
        """Pending decision queue items appear in briefing."""
        # Add items to the queue directly
        harbinger._queue = [
            {
                "id": "1",
                "description": "Approve mulch order from Home Depot",
                "context": "Spring inventory",
                "recommendation": "Approve — price is good",
                "importance": 4,
                "timestamp": "2026-04-04T10:00:00",
                "source_module": "wraith",
                "status": "pending",
                "resolution": None,
                "resolved_at": None,
            },
            {
                "id": "2",
                "description": "Review Sentinel alert",
                "context": "Network scan",
                "recommendation": "Investigate",
                "importance": 3,
                "timestamp": "2026-04-04T12:00:00",
                "source_module": "sentinel",
                "status": "pending",
                "resolution": None,
                "resolved_at": None,
            },
        ]

        briefing = harbinger.assemble_morning_briefing({})
        queue_section = next(s for s in briefing["sections"] if s["source"] == "harbinger")
        assert queue_section["title"] == "Decision Queue"
        assert queue_section["content"]["pending_count"] == 2
        # Should be sorted by importance descending
        items = queue_section["content"]["items"]
        assert items[0]["importance"] >= items[1]["importance"]

    def test_decision_queue_with_pending_gets_priority_1(self, harbinger):
        """Decision queue section gets priority 1 when items are pending."""
        harbinger._queue = [
            {
                "id": "1",
                "description": "Test decision",
                "importance": 3,
                "status": "pending",
            }
        ]
        briefing = harbinger.assemble_morning_briefing({})
        queue_section = next(s for s in briefing["sections"] if s["source"] == "harbinger")
        assert queue_section["priority"] == 1

    def test_module_exception_handled_gracefully(self, harbinger):
        """If a module raises an exception, briefing still works."""
        broken_grimoire = MagicMock()
        broken_grimoire.stats.side_effect = RuntimeError("DB connection lost")

        briefing = harbinger.assemble_morning_briefing({"grimoire": broken_grimoire})

        assert briefing["section_count"] == 6
        error_section = next(s for s in briefing["sections"] if s["title"] == "Memory Status")
        assert "Error" in str(error_section["content"])

    def test_void_system_health_in_briefing(self, harbinger, all_modules):
        """Void system health data appears in briefing."""
        briefing = harbinger.assemble_morning_briefing(all_modules)

        health_section = next(s for s in briefing["sections"] if s["source"] == "void")
        assert health_section["title"] == "System Health"
        assert health_section["content"]["cpu_percent"] == 12.5
        assert health_section["content"]["ram_percent"] == 25.6

    def test_reaper_research_in_briefing(self, harbinger, all_modules):
        """Reaper research data appears in briefing."""
        briefing = harbinger.assemble_morning_briefing(all_modules)

        research_section = next(s for s in briefing["sections"] if s["source"] == "reaper")
        assert research_section["title"] == "Research Intel"
        assert len(research_section["content"]["research"]) == 1
        assert len(research_section["content"]["reddit"]) == 1


class TestFormatBriefingText:
    """Tests for format_briefing_text()."""

    def test_produces_readable_string(self, harbinger, all_modules):
        """Format produces a non-empty readable string."""
        briefing = harbinger.assemble_morning_briefing(all_modules)
        text = harbinger.format_briefing_text(briefing)

        assert isinstance(text, str)
        assert len(text) > 100
        assert "SHADOW MORNING BRIEFING" in text
        assert "END BRIEFING" in text

    def test_contains_all_section_titles(self, harbinger, all_modules):
        """Formatted text includes all section titles."""
        briefing = harbinger.assemble_morning_briefing(all_modules)
        text = harbinger.format_briefing_text(briefing)

        for section in briefing["sections"]:
            assert section["title"] in text

    def test_priority_labels_present(self, harbinger, all_modules):
        """Formatted text shows priority labels."""
        briefing = harbinger.assemble_morning_briefing(all_modules)
        text = harbinger.format_briefing_text(briefing)

        assert "[HIGH]" in text or "[MEDIUM]" in text or "[LOW]" in text

    def test_numbered_sections(self, harbinger, all_modules):
        """Sections are numbered in the output."""
        briefing = harbinger.assemble_morning_briefing(all_modules)
        text = harbinger.format_briefing_text(briefing)

        assert "--- 1." in text
        assert "--- 2." in text

    def test_empty_briefing_format(self, harbinger):
        """Formatting an empty briefing still works."""
        briefing = harbinger.assemble_morning_briefing({})
        text = harbinger.format_briefing_text(briefing)

        assert "SHADOW MORNING BRIEFING" in text
        assert "[Not available]" in text

    def test_section_count_in_footer(self, harbinger, all_modules):
        """Footer shows correct section count."""
        briefing = harbinger.assemble_morning_briefing(all_modules)
        text = harbinger.format_briefing_text(briefing)

        assert "6 sections" in text

    def test_date_in_header(self, harbinger, all_modules):
        """Formatted text includes the date."""
        briefing = harbinger.assemble_morning_briefing(all_modules)
        text = harbinger.format_briefing_text(briefing)

        assert "Date:" in text
        assert "2026" in text  # Current year
