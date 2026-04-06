"""
Tests for Wraith Proactive Intelligence System
================================================
Covers TemporalTracker, NeglectDetector, proactive suggestions,
and tool integration through Wraith.execute().
"""

import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from modules.wraith.wraith import NeglectDetector, TemporalTracker, Wraith


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tracker(tmp_path: Path) -> TemporalTracker:
    """Fresh TemporalTracker with an in-memory-like temp DB."""
    t = TemporalTracker(tmp_path / "temporal.db")
    t.initialize()
    return t


@pytest.fixture
def detector() -> NeglectDetector:
    return NeglectDetector()


@pytest.fixture
def wraith(tmp_path: Path) -> Wraith:
    config = {
        "reminder_file": str(tmp_path / "reminders.json"),
        "temporal_db": str(tmp_path / "temporal.db"),
    }
    return Wraith(config)


@pytest.fixture
async def online_wraith(wraith: Wraith) -> Wraith:
    await wraith.initialize()
    return wraith


# ---------------------------------------------------------------------------
# TemporalTracker tests
# ---------------------------------------------------------------------------

class TestTemporalTracker:
    """Tests for temporal event recording and pattern detection."""

    def test_record_event(self, tracker: TemporalTracker) -> None:
        """Record an event and verify it's stored in DB."""
        result = tracker.record_event("weather_check")
        assert result["event_type"] == "weather_check"
        assert "timestamp" in result
        assert result["day_of_week"] == datetime.now().weekday()
        assert result["hour_of_day"] == datetime.now().hour

        # Verify it's actually in the DB
        row = tracker._conn.execute(
            "SELECT * FROM wraith_temporal_events WHERE event_type = ?",
            ("weather_check",),
        ).fetchone()
        assert row is not None
        assert row["event_type"] == "weather_check"

    def test_record_event_with_metadata(self, tracker: TemporalTracker) -> None:
        """Record with metadata dict, verify JSON stored correctly."""
        meta = {"source": "user", "query": "forecast"}
        result = tracker.record_event("weather_check", metadata=meta)
        assert result["metadata"] == meta

        row = tracker._conn.execute(
            "SELECT metadata FROM wraith_temporal_events WHERE event_type = ?",
            ("weather_check",),
        ).fetchone()
        import json
        assert json.loads(row["metadata"]) == meta

    def test_detect_daily_pattern(self, tracker: TemporalTracker) -> None:
        """Record same event at similar times on 4 different days -> daily pattern."""
        now = datetime.now()
        for day_offset in range(4):
            ts = now - timedelta(days=day_offset)
            tracker._conn.execute(
                "INSERT INTO wraith_temporal_events "
                "(event_type, timestamp, metadata, day_of_week, hour_of_day) "
                "VALUES (?, ?, NULL, ?, ?)",
                ("morning_briefing", ts.isoformat(), ts.weekday(), now.hour),
            )
        tracker._conn.commit()

        patterns = tracker.detect_patterns(min_occurrences=3)
        daily = [p for p in patterns if p["pattern"] == "daily_time"]
        assert len(daily) >= 1
        assert daily[0]["event_type"] == "morning_briefing"
        assert daily[0]["occurrences"] >= 3

    def test_detect_weekly_pattern(self, tracker: TemporalTracker) -> None:
        """Record same event on same weekday 3 times -> weekly pattern."""
        now = datetime.now()
        target_dow = 1  # Tuesday
        for week_offset in range(3):
            ts = now - timedelta(weeks=week_offset)
            tracker._conn.execute(
                "INSERT INTO wraith_temporal_events "
                "(event_type, timestamp, metadata, day_of_week, hour_of_day) "
                "VALUES (?, ?, NULL, ?, ?)",
                ("lmn_estimates", ts.isoformat(), target_dow, 9),
            )
        tracker._conn.commit()

        patterns = tracker.detect_patterns(min_occurrences=3, time_window_days=21)
        weekly = [p for p in patterns if p["pattern"] == "weekly"]
        assert len(weekly) >= 1
        assert weekly[0]["event_type"] == "lmn_estimates"
        assert weekly[0]["typical_time"] == "Tuesday"

    def test_no_pattern_insufficient_data(self, tracker: TemporalTracker) -> None:
        """Only 2 occurrences -> no pattern detected."""
        now = datetime.now()
        for i in range(2):
            ts = now - timedelta(days=i)
            tracker._conn.execute(
                "INSERT INTO wraith_temporal_events "
                "(event_type, timestamp, metadata, day_of_week, hour_of_day) "
                "VALUES (?, ?, NULL, ?, ?)",
                ("rare_event", ts.isoformat(), ts.weekday(), 10),
            )
        tracker._conn.commit()

        patterns = tracker.detect_patterns(min_occurrences=3)
        relevant = [p for p in patterns if p["event_type"] == "rare_event"]
        assert len(relevant) == 0

    def test_pattern_confidence_scales(self, tracker: TemporalTracker) -> None:
        """More occurrences -> higher confidence."""
        now = datetime.now()
        # 3 occurrences
        for i in range(3):
            ts = now - timedelta(days=i)
            tracker._conn.execute(
                "INSERT INTO wraith_temporal_events "
                "(event_type, timestamp, metadata, day_of_week, hour_of_day) "
                "VALUES (?, ?, NULL, ?, ?)",
                ("low_freq", ts.isoformat(), ts.weekday(), 8),
            )
        # 6 occurrences of another event
        for i in range(6):
            ts = now - timedelta(days=i)
            tracker._conn.execute(
                "INSERT INTO wraith_temporal_events "
                "(event_type, timestamp, metadata, day_of_week, hour_of_day) "
                "VALUES (?, ?, NULL, ?, ?)",
                ("high_freq", ts.isoformat(), ts.weekday(), 8),
            )
        tracker._conn.commit()

        patterns = tracker.detect_patterns(min_occurrences=3)
        low = [p for p in patterns if p["event_type"] == "low_freq" and p["pattern"] == "daily_time"]
        high = [p for p in patterns if p["event_type"] == "high_freq" and p["pattern"] == "daily_time"]
        assert len(low) >= 1
        assert len(high) >= 1
        assert high[0]["confidence"] > low[0]["confidence"]

    def test_time_window_respected(self, tracker: TemporalTracker) -> None:
        """Events outside the time window are excluded from detection."""
        now = datetime.now()
        # 4 events, but all 30 days ago (outside 14-day default window)
        for i in range(4):
            ts = now - timedelta(days=30 + i)
            tracker._conn.execute(
                "INSERT INTO wraith_temporal_events "
                "(event_type, timestamp, metadata, day_of_week, hour_of_day) "
                "VALUES (?, ?, NULL, ?, ?)",
                ("old_event", ts.isoformat(), ts.weekday(), 10),
            )
        tracker._conn.commit()

        patterns = tracker.detect_patterns(min_occurrences=3, time_window_days=14)
        relevant = [p for p in patterns if p["event_type"] == "old_event"]
        assert len(relevant) == 0


# ---------------------------------------------------------------------------
# NeglectDetector tests
# ---------------------------------------------------------------------------

class _MockTaskTracker:
    """Minimal mock matching TaskTracker.list_tasks() interface."""

    def __init__(self, tasks: list[dict]) -> None:
        self._tasks = tasks

    def list_tasks(self, status_filter: str | None = None) -> list[dict]:
        if status_filter:
            return [t for t in self._tasks if t.get("status") == status_filter]
        return self._tasks


class TestNeglectDetector:
    """Tests for neglect detection across tasks and decision queue items."""

    def test_no_neglect_fresh_items(self, detector: NeglectDetector) -> None:
        """All items created within 24h -> empty list."""
        tracker = _MockTaskTracker([
            {"description": "Fresh task", "status": "queued", "created_at": time.time() - 3600},
        ])
        queue = [
            {"description": "Fresh decision", "status": "pending",
             "timestamp": datetime.now().isoformat()},
        ]
        items = detector.check_neglected_items(task_tracker=tracker, decision_queue=queue)
        assert items == []

    def test_neglect_24h_severity1(self, detector: NeglectDetector) -> None:
        """Task queued 30h ago -> severity 1."""
        tracker = _MockTaskTracker([
            {"description": "Stale task", "status": "queued",
             "created_at": time.time() - (30 * 3600)},
        ])
        items = detector.check_neglected_items(task_tracker=tracker)
        assert len(items) == 1
        assert items[0]["severity"] == 1
        assert items[0]["item_type"] == "task"
        assert items[0]["age_hours"] >= 29  # allow small timing variance

    def test_neglect_72h_severity2(self, detector: NeglectDetector) -> None:
        """Task queued 80h ago -> severity 2."""
        tracker = _MockTaskTracker([
            {"description": "Old task", "status": "queued",
             "created_at": time.time() - (80 * 3600)},
        ])
        items = detector.check_neglected_items(task_tracker=tracker)
        assert len(items) == 1
        assert items[0]["severity"] == 2

    def test_neglect_7d_severity3(self, detector: NeglectDetector) -> None:
        """Decision queue item 8 days old -> severity 3."""
        old_ts = (datetime.now() - timedelta(days=8)).isoformat()
        queue = [
            {"description": "Ancient decision", "status": "pending", "timestamp": old_ts},
        ]
        items = detector.check_neglected_items(decision_queue=queue)
        assert len(items) == 1
        assert items[0]["severity"] == 3
        assert items[0]["item_type"] == "decision"

    def test_neglect_completed_tasks_excluded(self, detector: NeglectDetector) -> None:
        """Completed tasks are never flagged as neglected."""
        tracker = _MockTaskTracker([
            {"description": "Done task", "status": "completed",
             "created_at": time.time() - (200 * 3600)},
            {"description": "Failed task", "status": "failed",
             "created_at": time.time() - (200 * 3600)},
        ])
        items = detector.check_neglected_items(task_tracker=tracker)
        assert items == []

    def test_neglect_report_formatted(self, detector: NeglectDetector) -> None:
        """format_neglect_report produces readable string."""
        items = [
            {"item_type": "task", "description": "Fix bug", "age_hours": 50.0, "severity": 1},
            {"item_type": "decision", "description": "Approve deploy", "age_hours": 200.0, "severity": 3},
        ]
        report = detector.format_neglect_report(items)
        assert "2 items" in report
        assert "Fix bug" in report
        assert "Approve deploy" in report
        assert "High" in report
        assert "Low" in report

    def test_neglect_report_empty(self, detector: NeglectDetector) -> None:
        """Empty list -> no neglected items message."""
        report = detector.format_neglect_report([])
        assert "No neglected items" in report


# ---------------------------------------------------------------------------
# Proactive suggestions tests
# ---------------------------------------------------------------------------

class TestProactiveSuggestions:
    """Tests for the proactive suggestions engine."""

    @pytest.mark.asyncio
    async def test_suggestions_from_patterns(self, online_wraith: Wraith) -> None:
        """Set up a daily pattern matching current time -> suggestion generated."""
        now = datetime.now()
        tracker = online_wraith._temporal_tracker
        # Insert 4 events at the current hour on different days
        for day_offset in range(4):
            ts = now - timedelta(days=day_offset)
            tracker._conn.execute(
                "INSERT INTO wraith_temporal_events "
                "(event_type, timestamp, metadata, day_of_week, hour_of_day) "
                "VALUES (?, ?, NULL, ?, ?)",
                ("weather_check", ts.isoformat(), ts.weekday(), now.hour),
            )
        tracker._conn.commit()
        # Invalidate cache
        tracker._pattern_cache = None

        result = await online_wraith.execute("proactive_suggestions", {})
        assert result.success
        suggestions = result.content["suggestions"]
        pattern_suggestions = [s for s in suggestions if s["source"] == "pattern"]
        assert len(pattern_suggestions) >= 1
        assert "weather_check" in pattern_suggestions[0]["suggestion"]

    @pytest.mark.asyncio
    async def test_suggestions_from_neglect(self, online_wraith: Wraith) -> None:
        """Add an old neglected task -> suggestion to address it."""
        tracker = _MockTaskTracker([
            {"description": "Update docs", "status": "queued",
             "created_at": time.time() - (100 * 3600)},
        ])
        result = await online_wraith.execute(
            "proactive_suggestions", {"task_tracker": tracker}
        )
        assert result.success
        suggestions = result.content["suggestions"]
        neglect_suggestions = [s for s in suggestions if s["source"] == "neglect"]
        assert len(neglect_suggestions) >= 1
        assert "Update docs" in neglect_suggestions[0]["suggestion"]

    @pytest.mark.asyncio
    async def test_suggestions_max_three(self, online_wraith: Wraith) -> None:
        """Many possible suggestions -> capped at 3."""
        # Create 5 neglected tasks
        tasks = [
            {"description": f"Task {i}", "status": "queued",
             "created_at": time.time() - ((30 + i * 10) * 3600)}
            for i in range(5)
        ]
        tracker = _MockTaskTracker(tasks)
        result = await online_wraith.execute(
            "proactive_suggestions", {"task_tracker": tracker}
        )
        assert result.success
        assert result.content["count"] <= 3

    @pytest.mark.asyncio
    async def test_suggestions_sorted_by_confidence(self, online_wraith: Wraith) -> None:
        """Higher confidence suggestions come first."""
        # Mix of severities -> different confidence scores
        tasks = [
            {"description": "Low sev", "status": "queued",
             "created_at": time.time() - (30 * 3600)},  # severity 1 -> conf 0.33
            {"description": "High sev", "status": "queued",
             "created_at": time.time() - (200 * 3600)},  # severity 3 -> conf 1.0
        ]
        tracker = _MockTaskTracker(tasks)
        result = await online_wraith.execute(
            "proactive_suggestions", {"task_tracker": tracker}
        )
        assert result.success
        suggestions = result.content["suggestions"]
        if len(suggestions) >= 2:
            assert suggestions[0]["confidence"] >= suggestions[1]["confidence"]

    @pytest.mark.asyncio
    async def test_no_suggestions_when_nothing_detected(self, online_wraith: Wraith) -> None:
        """Clean state -> empty list."""
        result = await online_wraith.execute("proactive_suggestions", {})
        assert result.success
        assert result.content["count"] == 0
        assert result.content["suggestions"] == []


# ---------------------------------------------------------------------------
# Tool integration tests
# ---------------------------------------------------------------------------

class TestToolIntegration:
    """Tests for new tools executing through Wraith.execute()."""

    @pytest.mark.asyncio
    async def test_temporal_record_tool(self, online_wraith: Wraith) -> None:
        """Execute temporal_record through Wraith.execute()."""
        result = await online_wraith.execute(
            "temporal_record", {"event_type": "email_check", "metadata": {"count": 5}}
        )
        assert result.success
        assert result.content["event_type"] == "email_check"
        assert result.content["metadata"] == {"count": 5}
        assert result.tool_name == "temporal_record"
        assert result.module == "wraith"

    @pytest.mark.asyncio
    async def test_temporal_record_empty_type_fails(self, online_wraith: Wraith) -> None:
        """Empty event_type should fail."""
        result = await online_wraith.execute("temporal_record", {"event_type": ""})
        assert not result.success
        assert "event_type" in result.error

    @pytest.mark.asyncio
    async def test_temporal_patterns_tool(self, online_wraith: Wraith) -> None:
        """Execute temporal_patterns through Wraith.execute()."""
        result = await online_wraith.execute("temporal_patterns", {})
        assert result.success
        assert "patterns" in result.content
        assert "count" in result.content
        assert result.tool_name == "temporal_patterns"

    @pytest.mark.asyncio
    async def test_neglect_check_tool(self, online_wraith: Wraith) -> None:
        """Execute neglect_check through Wraith.execute()."""
        result = await online_wraith.execute("neglect_check", {})
        assert result.success
        assert "neglected_items" in result.content
        assert "report" in result.content
        assert result.tool_name == "neglect_check"

    @pytest.mark.asyncio
    async def test_get_tools_includes_new_tools(self, wraith: Wraith) -> None:
        """get_tools() returns 12 tools (8 original + 4 new)."""
        tools = wraith.get_tools()
        assert len(tools) == 12
        names = {t["name"] for t in tools}
        assert "temporal_record" in names
        assert "temporal_patterns" in names
        assert "neglect_check" in names
        assert "proactive_suggestions" in names
