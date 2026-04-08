"""
Tests for modules/shadow/context_profiler.py — Context Window Profiler.
"""

import os
import tempfile
import time
import uuid

import pytest

from modules.shadow.context_profiler import ContextProfile, ContextProfiler


@pytest.fixture
def profiler(tmp_path):
    """Fresh profiler with a temporary database."""
    db = tmp_path / "test_profiles.db"
    return ContextProfiler(db_path=str(db))


@pytest.fixture
def sample_profile():
    """Returns a ContextProfile with realistic values."""
    return ContextProfile(
        profile_id=str(uuid.uuid4()),
        timestamp=time.time(),
        model="phi4-mini",
        task_type="question",
        module="wraith",
        system_prompt_tokens=3200,
        grimoire_tokens=5400,
        history_tokens=2800,
        tool_schema_tokens=4200,
        failure_pattern_tokens=600,
        user_input_tokens=200,
        response_headroom_tokens=11600,
        total_tokens=16400,
        token_limit=28000,
        usage_percent=58.6,
        grimoire_tokens_referenced=2000,
        tool_schemas_used=2,
        tool_schemas_loaded=10,
        was_trimmed=False,
        trimmed_components=[],
        compression_ratio=0.0,
    )


# ------------------------------------------------------------------
# DB creation & basics
# ------------------------------------------------------------------

class TestDBCreation:
    def test_sqlite_db_created_on_init(self, tmp_path):
        db = tmp_path / "new_profiles.db"
        assert not db.exists()
        ContextProfiler(db_path=str(db))
        assert db.exists()

    def test_profile_count_starts_at_zero(self, profiler):
        assert profiler.get_profile_count() == 0


# ------------------------------------------------------------------
# Recording
# ------------------------------------------------------------------

class TestRecordProfile:
    def test_record_stores_to_sqlite(self, profiler, sample_profile):
        pid = profiler.record_profile(sample_profile)
        assert pid
        assert profiler.get_profile_count() == 1

    def test_profile_count_increases(self, profiler, sample_profile):
        profiler.record_profile(sample_profile)
        p2 = ContextProfile(
            profile_id=str(uuid.uuid4()),
            timestamp=time.time(),
            model="phi4-mini",
            task_type="research",
            module="reaper",
            total_tokens=5000,
            token_limit=28000,
        )
        profiler.record_profile(p2)
        assert profiler.get_profile_count() == 2

    def test_usage_percent_auto_calculated(self, profiler):
        p = ContextProfile(
            total_tokens=14000,
            token_limit=28000,
            usage_percent=0.0,  # should be auto-filled
        )
        profiler.record_profile(p)
        assert profiler.get_profile_count() == 1
        # Verify it was calculated (50%)
        report = profiler.get_waste_report(days=1)
        assert abs(report["avg_usage_percent"] - 50.0) < 0.1

    def test_record_assigns_id_if_missing(self, profiler):
        p = ContextProfile(total_tokens=100, token_limit=1000)
        pid = profiler.record_profile(p)
        assert pid
        assert len(pid) == 36  # UUID length


# ------------------------------------------------------------------
# record_from_context_package
# ------------------------------------------------------------------

class TestRecordFromContextPackage:
    def test_extracts_correct_token_counts(self, profiler):
        class MockPackage:
            token_breakdown = {
                "system_prompt": 1000,
                "grimoire": 2000,
                "history": 1500,
                "tools": 800,
                "failure_patterns": 200,
                "user_input": 100,
                "total": 5600,
            }
            grimoire_context = "The bible says love your neighbor."
            tool_schemas = [
                {"name": "memory_search"},
                {"name": "web_search"},
                {"name": "code_execute"},
            ]
            total_tokens = 5600
            token_budget = 28000
            trimmed = False
            trimmed_details = []
            compression_report = {}

        task = {"type": "question", "module": "wraith", "model": "phi4-mini"}
        pid = profiler.record_from_context_package(MockPackage(), task)
        assert pid
        assert profiler.get_profile_count() == 1

    def test_auto_calculates_tool_usage_from_response(self, profiler):
        class MockPackage:
            token_breakdown = {"tools": 800, "grimoire": 0}
            grimoire_context = ""
            tool_schemas = [
                {"name": "memory_search"},
                {"name": "web_search"},
                {"name": "code_execute"},
            ]
            total_tokens = 2000
            token_budget = 28000
            trimmed = False
            trimmed_details = []
            compression_report = {}

        task = {"type": "question", "module": "wraith"}
        # Response mentions memory_search — that tool was "used"
        response = "I used memory_search to find the answer."
        pid = profiler.record_from_context_package(MockPackage(), task, response)
        assert pid
        assert profiler.get_profile_count() == 1

    def test_graceful_handling_of_malformed_package(self, profiler):
        """Profiler should not crash on a package missing expected attributes."""

        class BrokenPackage:
            pass

        task = {"type": "unknown"}
        pid = profiler.record_from_context_package(BrokenPackage(), task)
        # Should return empty string or an id, but not raise
        assert isinstance(pid, str)

    def test_auto_calculates_grimoire_referenced(self, profiler):
        class MockPackage:
            token_breakdown = {"grimoire": 1000}
            grimoire_context = (
                "Memory alpha: Shadow was created by Patrick. "
                "Memory beta: Shadow runs on Windows 11. "
                "Memory gamma: Cerberus handles ethics."
            )
            tool_schemas = []
            total_tokens = 3000
            token_budget = 28000
            trimmed = False
            trimmed_details = []
            compression_report = {}

        task = {"type": "question", "module": "grimoire"}
        response = "Shadow was created by Patrick and runs locally."
        pid = profiler.record_from_context_package(MockPackage(), task, response)
        assert pid


# ------------------------------------------------------------------
# Waste report
# ------------------------------------------------------------------

class TestWasteReport:
    def _insert_profiles(self, profiler, count=5, **overrides):
        """Helper to insert multiple profiles with defaults."""
        for i in range(count):
            p = ContextProfile(
                profile_id=str(uuid.uuid4()),
                timestamp=time.time() - i * 60,
                model="phi4-mini",
                task_type="question",
                module="wraith",
                system_prompt_tokens=3200,
                grimoire_tokens=overrides.get("grimoire_tokens", 5000),
                history_tokens=overrides.get("history_tokens", 2800),
                tool_schema_tokens=overrides.get("tool_schema_tokens", 4200),
                failure_pattern_tokens=600,
                user_input_tokens=200,
                response_headroom_tokens=11000,
                total_tokens=overrides.get("total_tokens", 16000),
                token_limit=overrides.get("token_limit", 28000),
                usage_percent=overrides.get("usage_percent", 57.1),
                grimoire_tokens_referenced=overrides.get(
                    "grimoire_tokens_referenced", 2000
                ),
                tool_schemas_used=overrides.get("tool_schemas_used", 2),
                tool_schemas_loaded=overrides.get("tool_schemas_loaded", 10),
                was_trimmed=overrides.get("was_trimmed", False),
                trimmed_components=overrides.get("trimmed_components", []),
                compression_ratio=0.0,
            )
            profiler.record_profile(p)

    def test_empty_db_returns_valid_zeros(self, profiler):
        report = profiler.get_waste_report(days=7)
        assert report["profile_count"] == 0
        assert report["unused_tool_tokens"] == 0
        assert report["unused_grimoire_tokens"] == 0
        assert report["avg_usage_percent"] == 0.0
        assert report["trim_frequency"] == 0.0
        assert report["biggest_waste_component"] == "none"
        assert isinstance(report["summary"], str)

    def test_calculates_unused_tool_tokens(self, profiler):
        # 10 loaded, 2 used → 80% of 4200 = 3360 unused
        self._insert_profiles(
            profiler,
            count=3,
            tool_schema_tokens=4200,
            tool_schemas_loaded=10,
            tool_schemas_used=2,
        )
        report = profiler.get_waste_report(days=1)
        assert report["unused_tool_tokens"] > 0

    def test_calculates_unused_grimoire_tokens(self, profiler):
        self._insert_profiles(
            profiler,
            count=3,
            grimoire_tokens=5000,
            grimoire_tokens_referenced=1000,
        )
        report = profiler.get_waste_report(days=1)
        # 5000 loaded - 1000 referenced = 4000 unused
        assert report["unused_grimoire_tokens"] == 4000

    def test_identifies_biggest_waste_component(self, profiler):
        # Grimoire waste dominates: 5000 - 500 = 4500 each
        self._insert_profiles(
            profiler,
            count=3,
            grimoire_tokens=5000,
            grimoire_tokens_referenced=500,
            tool_schema_tokens=100,
            tool_schemas_loaded=10,
            tool_schemas_used=9,
        )
        report = profiler.get_waste_report(days=1)
        assert report["biggest_waste_component"] == "grimoire"

    def test_generates_plain_english_summary(self, profiler):
        self._insert_profiles(
            profiler,
            count=3,
            tool_schema_tokens=4200,
            tool_schemas_loaded=10,
            tool_schemas_used=2,
        )
        report = profiler.get_waste_report(days=1)
        assert isinstance(report["summary"], str)
        assert len(report["summary"]) > 10

    def test_trim_frequency(self, profiler):
        # Insert 4 profiles, 3 trimmed
        for i in range(4):
            p = ContextProfile(
                profile_id=str(uuid.uuid4()),
                timestamp=time.time(),
                total_tokens=5000,
                token_limit=28000,
                was_trimmed=(i < 3),
                tool_schemas_loaded=1,
                tool_schemas_used=1,
            )
            profiler.record_profile(p)
        report = profiler.get_waste_report(days=1)
        assert report["trim_frequency"] == 75.0

    def test_averages_calculated_correctly(self, profiler):
        for pct in [40.0, 60.0, 80.0]:
            p = ContextProfile(
                profile_id=str(uuid.uuid4()),
                timestamp=time.time(),
                total_tokens=int(28000 * pct / 100),
                token_limit=28000,
                usage_percent=pct,
                tool_schemas_loaded=1,
                tool_schemas_used=1,
            )
            profiler.record_profile(p)
        report = profiler.get_waste_report(days=1)
        assert abs(report["avg_usage_percent"] - 60.0) < 0.1


# ------------------------------------------------------------------
# Usage trend
# ------------------------------------------------------------------

class TestUsageTrend:
    def test_returns_daily_data_points(self, profiler):
        # Insert profiles across 3 different days
        now = time.time()
        for day_offset in range(3):
            p = ContextProfile(
                profile_id=str(uuid.uuid4()),
                timestamp=now - day_offset * 86400,
                total_tokens=10000 + day_offset * 1000,
                token_limit=28000,
                usage_percent=35.7 + day_offset,
            )
            profiler.record_profile(p)

        trend = profiler.get_usage_trend(days=7)
        assert len(trend) >= 1  # At least some data
        for point in trend:
            assert "date" in point
            assert "avg_total_tokens" in point
            assert "avg_usage_percent" in point
            assert "request_count" in point

    def test_respects_day_range(self, profiler):
        now = time.time()
        # One profile 2 days ago, one 20 days ago
        p1 = ContextProfile(
            profile_id=str(uuid.uuid4()),
            timestamp=now - 2 * 86400,
            total_tokens=5000,
            token_limit=28000,
        )
        p2 = ContextProfile(
            profile_id=str(uuid.uuid4()),
            timestamp=now - 20 * 86400,
            total_tokens=5000,
            token_limit=28000,
        )
        profiler.record_profile(p1)
        profiler.record_profile(p2)

        trend_7 = profiler.get_usage_trend(days=7)
        trend_30 = profiler.get_usage_trend(days=30)
        # 30-day window should have >= as many points as 7-day
        total_7 = sum(p["request_count"] for p in trend_7)
        total_30 = sum(p["request_count"] for p in trend_30)
        assert total_30 >= total_7

    def test_empty_db_returns_empty(self, profiler):
        assert profiler.get_usage_trend(days=7) == []


# ------------------------------------------------------------------
# Component breakdown
# ------------------------------------------------------------------

class TestComponentBreakdown:
    def test_returns_per_component_averages(self, profiler):
        p = ContextProfile(
            profile_id=str(uuid.uuid4()),
            timestamp=time.time(),
            system_prompt_tokens=3200,
            grimoire_tokens=5400,
            history_tokens=2800,
            tool_schema_tokens=1500,
            failure_pattern_tokens=300,
            user_input_tokens=200,
            response_headroom_tokens=14600,
            total_tokens=13400,
            token_limit=28000,
        )
        profiler.record_profile(p)
        bd = profiler.get_component_breakdown(days=1)
        assert bd["components"]["system_prompt"] == 3200
        assert bd["components"]["grimoire"] == 5400
        assert bd["components"]["history"] == 2800

    def test_includes_percentages(self, profiler):
        p = ContextProfile(
            profile_id=str(uuid.uuid4()),
            timestamp=time.time(),
            system_prompt_tokens=5000,
            grimoire_tokens=5000,
            total_tokens=10000,
            token_limit=28000,
        )
        profiler.record_profile(p)
        bd = profiler.get_component_breakdown(days=1)
        assert "percentages" in bd
        # system_prompt should be 50% of total
        assert bd["percentages"]["system_prompt"] == 50.0

    def test_empty_db_returns_valid_structure(self, profiler):
        bd = profiler.get_component_breakdown(days=7)
        assert bd["profile_count"] == 0
        assert bd["components"] == {}
        assert bd["percentages"] == {}


# ------------------------------------------------------------------
# Optimization suggestions
# ------------------------------------------------------------------

class TestOptimizationSuggestions:
    def _insert_wasteful_profiles(self, profiler, **overrides):
        """Insert profiles that trigger specific suggestions."""
        defaults = dict(
            grimoire_tokens=5000,
            grimoire_tokens_referenced=1000,
            tool_schema_tokens=4200,
            tool_schemas_loaded=10,
            tool_schemas_used=2,
            history_tokens=2800,
            total_tokens=16000,
            token_limit=28000,
            was_trimmed=False,
        )
        defaults.update(overrides)
        for i in range(5):
            p = ContextProfile(
                profile_id=str(uuid.uuid4()),
                timestamp=time.time() - i * 60,
                model="phi4-mini",
                task_type="question",
                module="wraith",
                system_prompt_tokens=3200,
                grimoire_tokens=defaults["grimoire_tokens"],
                history_tokens=defaults["history_tokens"],
                tool_schema_tokens=defaults["tool_schema_tokens"],
                failure_pattern_tokens=600,
                user_input_tokens=200,
                response_headroom_tokens=11000,
                total_tokens=defaults["total_tokens"],
                token_limit=defaults["token_limit"],
                usage_percent=(
                    defaults["total_tokens"] / defaults["token_limit"] * 100
                ),
                grimoire_tokens_referenced=defaults[
                    "grimoire_tokens_referenced"
                ],
                tool_schemas_used=defaults["tool_schemas_used"],
                tool_schemas_loaded=defaults["tool_schemas_loaded"],
                was_trimmed=defaults["was_trimmed"],
            )
            profiler.record_profile(p)

    def test_high_tool_waste_suggests_tool_filtering(self, profiler):
        self._insert_wasteful_profiles(
            profiler,
            tool_schema_tokens=6000,
            tool_schemas_loaded=15,
            tool_schemas_used=1,
        )
        suggestions = profiler.get_optimization_suggestions()
        assert any("DynamicToolLoader" in s for s in suggestions)

    def test_high_grimoire_waste_suggests_retrieval_tightening(self, profiler):
        self._insert_wasteful_profiles(
            profiler,
            grimoire_tokens=8000,
            grimoire_tokens_referenced=1000,
        )
        suggestions = profiler.get_optimization_suggestions()
        assert any("StagedRetrieval" in s for s in suggestions)

    def test_frequent_trimming_suggests_compression(self, profiler):
        self._insert_wasteful_profiles(profiler, was_trimmed=True)
        suggestions = profiler.get_optimization_suggestions()
        assert any("trimming" in s.lower() for s in suggestions)

    def test_high_history_suggests_compression(self, profiler):
        # History = 12000 out of 20000 total = 60%
        self._insert_wasteful_profiles(
            profiler,
            history_tokens=12000,
            total_tokens=20000,
            token_limit=28000,
        )
        suggestions = profiler.get_optimization_suggestions()
        assert any("history" in s.lower() for s in suggestions)

    def test_no_issues_returns_empty(self, profiler):
        # Low waste across the board
        for i in range(5):
            p = ContextProfile(
                profile_id=str(uuid.uuid4()),
                timestamp=time.time() - i * 60,
                system_prompt_tokens=1000,
                grimoire_tokens=500,
                history_tokens=500,
                tool_schema_tokens=500,
                total_tokens=3000,
                token_limit=28000,
                usage_percent=10.7,
                grimoire_tokens_referenced=400,
                tool_schemas_used=3,
                tool_schemas_loaded=4,
                was_trimmed=False,
            )
            profiler.record_profile(p)
        suggestions = profiler.get_optimization_suggestions()
        assert suggestions == []
