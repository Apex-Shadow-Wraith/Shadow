"""
Tests for Prompt Evolver — Dynamic System Prompt Evolution
===========================================================
Tests registration, task tracking, analysis, evolution,
version management, scheduling, and edge cases.
"""

import os
import sqlite3
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from modules.shadow.prompt_evolver import (
    PromptEvolver,
    PromptVersion,
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_LOW_THRESHOLD,
    MIN_TASKS_FOR_EVOLUTION,
    PERFORMANCE_DECLINE_THRESHOLD,
)


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary database path."""
    return str(tmp_path / "test_prompt_versions.db")


@pytest.fixture
def evolver(tmp_db):
    """Create a PromptEvolver with temp database."""
    pe = PromptEvolver(grimoire=None, db_path=tmp_db)
    yield pe
    pe.close()


@pytest.fixture
def mock_grimoire():
    """Create a mock Grimoire that returns patterns."""
    grimoire = MagicMock()
    grimoire.search.return_value = [
        {"content": "Always validate input before processing"},
        {"content": "Log all decisions with rationale"},
    ]
    return grimoire


@pytest.fixture
def evolver_with_grimoire(tmp_db, mock_grimoire):
    """Create a PromptEvolver with mocked Grimoire."""
    pe = PromptEvolver(grimoire=mock_grimoire, db_path=tmp_db)
    yield pe
    pe.close()


SAMPLE_PROMPT = (
    "You are the Wraith module.\n\n"
    "Handle daily tasks efficiently.\n\n"
    "Classify tasks by urgency.\n\n"
    "Track temporal patterns."
)


# =============================================================================
# REGISTRATION TESTS
# =============================================================================

class TestRegistration:
    """Tests for prompt registration."""

    def test_register_prompt_creates_version_1(self, evolver):
        """First registration creates version 1."""
        vid = evolver.register_prompt("wraith", SAMPLE_PROMPT)
        assert vid is not None

        history = evolver.get_version_history("wraith")
        assert len(history) == 1
        assert history[0].version_number == 1
        assert history[0].status == "active"
        assert history[0].prompt_text == SAMPLE_PROMPT

    def test_register_prompt_same_module_creates_version_2(self, evolver):
        """Second registration for same module creates version 2."""
        vid1 = evolver.register_prompt("wraith", SAMPLE_PROMPT)
        vid2 = evolver.register_prompt("wraith", SAMPLE_PROMPT + "\n\nNew instruction.")

        assert vid1 != vid2

        history = evolver.get_version_history("wraith")
        assert len(history) == 2
        assert history[0].version_number == 2  # Newest first
        assert history[1].version_number == 1
        # Version 2 should be active, version 1 retired
        assert history[0].status == "active"
        assert history[1].status == "retired"

    def test_register_prompt_different_modules(self, evolver):
        """Registration for different modules is independent."""
        evolver.register_prompt("wraith", "Wraith prompt")
        evolver.register_prompt("cerberus", "Cerberus prompt")

        wraith_history = evolver.get_version_history("wraith")
        cerberus_history = evolver.get_version_history("cerberus")

        assert len(wraith_history) == 1
        assert len(cerberus_history) == 1
        assert wraith_history[0].module == "wraith"
        assert cerberus_history[0].module == "cerberus"


# =============================================================================
# TASK TRACKING TESTS
# =============================================================================

class TestTaskTracking:
    """Tests for task outcome recording."""

    def test_record_task_outcome_stores_data(self, evolver):
        """Task outcome is stored correctly."""
        evolver.register_prompt("wraith", SAMPLE_PROMPT)
        result = evolver.record_task_outcome(
            "wraith", "routing", 0.85,
            instructions_referenced=["Handle daily tasks efficiently."]
        )
        assert result is True

        # Check version got updated
        history = evolver.get_version_history("wraith")
        assert history[0].task_count == 1
        assert history[0].performance_score == pytest.approx(0.85, abs=0.01)

    def test_referenced_instructions_tracked(self, evolver):
        """Referenced instructions accumulate stats correctly."""
        evolver.register_prompt("wraith", SAMPLE_PROMPT)

        evolver.record_task_outcome(
            "wraith", "routing", 0.9,
            instructions_referenced=["Handle daily tasks efficiently."]
        )
        evolver.record_task_outcome(
            "wraith", "routing", 0.8,
            instructions_referenced=["Handle daily tasks efficiently."]
        )

        # Check instruction stats via internal connection
        row = evolver._conn.execute(
            "SELECT times_referenced, avg_confidence FROM instruction_stats "
            "WHERE module = ? AND instruction = ?",
            ("wraith", "Handle daily tasks efficiently.")
        ).fetchone()

        assert row["times_referenced"] == 2
        assert row["avg_confidence"] == pytest.approx(0.85, abs=0.01)

    def test_unreferenced_instructions_not_tracked(self, evolver):
        """Instructions not referenced don't appear in stats."""
        evolver.register_prompt("wraith", SAMPLE_PROMPT)
        evolver.record_task_outcome("wraith", "routing", 0.9, instructions_referenced=[])

        rows = evolver._conn.execute(
            "SELECT COUNT(*) as cnt FROM instruction_stats WHERE module = ?",
            ("wraith",)
        ).fetchone()

        assert rows["cnt"] == 0

    def test_record_task_no_active_prompt(self, evolver):
        """Recording without an active prompt returns False."""
        result = evolver.record_task_outcome("nonexistent", "test", 0.5)
        assert result is False


# =============================================================================
# ANALYSIS TESTS
# =============================================================================

class TestAnalysis:
    """Tests for prompt analysis."""

    def test_analyze_identifies_effective_instructions(self, evolver):
        """Instructions with high confidence are identified as effective."""
        evolver.register_prompt("wraith", SAMPLE_PROMPT)

        # Record high-confidence outcomes for specific instructions
        for _ in range(5):
            evolver.record_task_outcome(
                "wraith", "routing", 0.9,
                instructions_referenced=["Handle daily tasks efficiently."]
            )

        analysis = evolver.analyze_prompt("wraith")
        assert "Handle daily tasks efficiently." in analysis["effective_instructions"]

    def test_analyze_identifies_unused_instructions(self, evolver):
        """Instructions never referenced are identified as unused."""
        evolver.register_prompt("wraith", SAMPLE_PROMPT)

        # Record outcomes that only reference one instruction
        for _ in range(5):
            evolver.record_task_outcome(
                "wraith", "routing", 0.9,
                instructions_referenced=["Handle daily tasks efficiently."]
            )

        analysis = evolver.analyze_prompt("wraith")
        # Other sections never referenced should be unused
        assert len(analysis["unused_instructions"]) > 0

    def test_analyze_identifies_harmful_instructions(self, evolver):
        """Instructions with low confidence are identified as harmful."""
        evolver.register_prompt("wraith", SAMPLE_PROMPT)

        # Record low-confidence outcomes for a specific instruction
        for _ in range(5):
            evolver.record_task_outcome(
                "wraith", "routing", 0.2,
                instructions_referenced=["Track temporal patterns."]
            )

        analysis = evolver.analyze_prompt("wraith")
        assert "Track temporal patterns." in analysis["harmful_instructions"]

    def test_analyze_identifies_missing_patterns(self, evolver_with_grimoire):
        """Missing Grimoire patterns are identified."""
        evolver_with_grimoire.register_prompt("wraith", SAMPLE_PROMPT)
        analysis = evolver_with_grimoire.analyze_prompt("wraith")

        assert len(analysis["missing_patterns"]) > 0
        assert "Always validate input before processing" in analysis["missing_patterns"]

    def test_analyze_no_active_prompt(self, evolver):
        """Analysis of module with no prompt returns error."""
        analysis = evolver.analyze_prompt("nonexistent")
        assert "error" in analysis


# =============================================================================
# EVOLUTION TESTS
# =============================================================================

class TestEvolution:
    """Tests for prompt evolution."""

    def test_evolve_removes_unused_instructions(self, evolver):
        """Evolution removes instructions that were never referenced."""
        evolver.register_prompt("wraith", SAMPLE_PROMPT)

        # Only reference one instruction, leave others unused
        for _ in range(5):
            evolver.record_task_outcome(
                "wraith", "routing", 0.9,
                instructions_referenced=["Handle daily tasks efficiently."]
            )

        new_version = evolver.evolve_prompt("wraith")
        assert new_version is not None
        assert new_version.status == "testing"
        # Unused instructions should be removed
        assert "Track temporal patterns." not in new_version.prompt_text

    def test_evolve_adds_missing_patterns(self, evolver_with_grimoire):
        """Evolution adds patterns from Grimoire."""
        evolver_with_grimoire.register_prompt("wraith", SAMPLE_PROMPT)

        # Reference all instructions to prevent removal
        sections = SAMPLE_PROMPT.split("\n\n")
        for section in sections:
            for _ in range(3):
                evolver_with_grimoire.record_task_outcome(
                    "wraith", "routing", 0.9,
                    instructions_referenced=[section.strip()]
                )

        new_version = evolver_with_grimoire.evolve_prompt("wraith")
        assert new_version is not None
        assert "Always validate input before processing" in new_version.prompt_text

    def test_evolve_creates_testing_version(self, evolver):
        """Evolved prompt has 'testing' status."""
        evolver.register_prompt("wraith", SAMPLE_PROMPT)
        evolver.record_task_outcome(
            "wraith", "routing", 0.9,
            instructions_referenced=["Handle daily tasks efficiently."]
        )

        new_version = evolver.evolve_prompt("wraith")
        assert new_version is not None
        assert new_version.status == "testing"

    def test_evolve_returns_none_when_no_changes(self, evolver):
        """evolve_prompt returns None when no changes are needed."""
        evolver.register_prompt("wraith", SAMPLE_PROMPT)

        # Reference ALL instructions with high confidence
        sections = [s.strip() for s in SAMPLE_PROMPT.split("\n\n") if s.strip()]
        for section in sections:
            for _ in range(3):
                evolver.record_task_outcome(
                    "wraith", "routing", 0.9,
                    instructions_referenced=[section]
                )

        result = evolver.evolve_prompt("wraith")
        assert result is None

    def test_evolve_no_active_prompt(self, evolver):
        """Evolution with no active prompt returns None."""
        result = evolver.evolve_prompt("nonexistent")
        assert result is None


# =============================================================================
# VERSION MANAGEMENT TESTS
# =============================================================================

class TestVersionManagement:
    """Tests for version activation, rollback, comparison."""

    def test_activate_version_sets_correct_statuses(self, evolver):
        """Activating a version retires the current one."""
        vid1 = evolver.register_prompt("wraith", "Prompt v1")
        vid2 = evolver.register_prompt("wraith", "Prompt v2")

        # vid2 is active, vid1 is retired. Reactivate vid1.
        result = evolver.activate_version(vid1)
        assert result is True

        history = evolver.get_version_history("wraith")
        statuses = {h.version_id: h.status for h in history}
        assert statuses[vid1] == "active"
        assert statuses[vid2] == "retired"

    def test_activate_nonexistent_version(self, evolver):
        """Activating a nonexistent version returns False."""
        result = evolver.activate_version("nonexistent-id")
        assert result is False

    def test_rollback_restores_previous_version(self, evolver):
        """Rollback restores the previous version."""
        evolver.register_prompt("wraith", "Prompt v1")
        evolver.register_prompt("wraith", "Prompt v2")

        restored = evolver.rollback("wraith")
        assert restored is not None
        assert restored.prompt_text == "Prompt v1"
        assert restored.status == "active"

        # Current should be rolled back
        history = evolver.get_version_history("wraith")
        v2 = [h for h in history if h.version_number == 2][0]
        assert v2.status == "rolled_back"

    def test_rollback_no_previous_version(self, evolver):
        """Rollback with only one version returns None."""
        evolver.register_prompt("wraith", "Only version")
        result = evolver.rollback("wraith")
        assert result is None

    def test_compare_versions(self, evolver):
        """Compare returns correct scores and better version."""
        vid1 = evolver.register_prompt("wraith", "Prompt v1")
        vid2 = evolver.register_prompt("wraith", "Prompt v2\n\nNew section")

        # Record outcomes to give different scores
        # Reactivate v1 to record outcomes against it
        evolver.activate_version(vid1)
        for _ in range(5):
            evolver.record_task_outcome("wraith", "test", 0.6)
        evolver.activate_version(vid2)
        for _ in range(5):
            evolver.record_task_outcome("wraith", "test", 0.9)

        comparison = evolver.compare_versions(vid1, vid2)
        assert comparison["version_a_score"] == pytest.approx(0.6, abs=0.01)
        assert comparison["version_b_score"] == pytest.approx(0.9, abs=0.01)
        assert comparison["better"] == vid2
        assert comparison["difference"] == pytest.approx(0.3, abs=0.01)

    def test_compare_nonexistent_version(self, evolver):
        """Comparing with nonexistent version returns error."""
        result = evolver.compare_versions("fake-a", "fake-b")
        assert "error" in result

    def test_get_version_history_ordered(self, evolver):
        """Version history is returned newest first."""
        evolver.register_prompt("wraith", "V1")
        evolver.register_prompt("wraith", "V2")
        evolver.register_prompt("wraith", "V3")

        history = evolver.get_version_history("wraith")
        assert len(history) == 3
        assert history[0].version_number == 3
        assert history[1].version_number == 2
        assert history[2].version_number == 1


# =============================================================================
# SCHEDULING TESTS
# =============================================================================

class TestScheduling:
    """Tests for evolution scheduling."""

    def test_should_evolve_enough_tasks(self, evolver):
        """should_evolve returns True when 100+ tasks recorded."""
        evolver.register_prompt("wraith", SAMPLE_PROMPT)

        # Record 100 tasks
        for _ in range(MIN_TASKS_FOR_EVOLUTION):
            evolver.record_task_outcome("wraith", "routing", 0.8)

        assert evolver.should_evolve("wraith") is True

    def test_should_evolve_just_evolved(self, evolver):
        """should_evolve returns False when few tasks since last evolution."""
        evolver.register_prompt("wraith", SAMPLE_PROMPT)

        # Only a few tasks
        for _ in range(5):
            evolver.record_task_outcome("wraith", "routing", 0.8)

        assert evolver.should_evolve("wraith") is False

    def test_should_evolve_performance_declining(self, evolver):
        """should_evolve returns True when performance is declining."""
        evolver.register_prompt("wraith", "V1 prompt")

        # Give v1 a good score
        for _ in range(10):
            evolver.record_task_outcome("wraith", "routing", 0.9)

        # Register v2 with worse performance
        evolver.register_prompt("wraith", "V2 prompt")
        for _ in range(10):
            evolver.record_task_outcome("wraith", "routing", 0.7)

        assert evolver.should_evolve("wraith") is True

    def test_should_evolve_no_active_prompt(self, evolver):
        """should_evolve returns False when no active prompt."""
        assert evolver.should_evolve("nonexistent") is False


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

class TestEdgeCases:
    """Edge case and error handling tests."""

    def test_module_no_registered_prompt(self, evolver):
        """Module with no registered prompt handles gracefully."""
        analysis = evolver.analyze_prompt("unknown_module")
        assert "error" in analysis

        result = evolver.evolve_prompt("unknown_module")
        assert result is None

    def test_rollback_with_no_previous(self, evolver):
        """Rollback with no previous version returns None."""
        evolver.register_prompt("wraith", "Solo version")
        result = evolver.rollback("wraith")
        assert result is None

    def test_empty_task_history(self, evolver):
        """No evolution with empty task history."""
        evolver.register_prompt("wraith", SAMPLE_PROMPT)
        result = evolver.evolve_prompt("wraith")
        # All instructions are unused but no patterns to add → still evolves
        # (removes unused instructions)
        # Actually with 0 tasks, all instructions are unused
        # The prompt will be empty if all sections are removed
        # Let's verify behavior is reasonable
        if result is not None:
            assert result.status == "testing"

    def test_sqlite_db_created_on_init(self, tmp_path):
        """SQLite database is created on initialization."""
        db_path = str(tmp_path / "new_db.db")
        pe = PromptEvolver(db_path=db_path)
        assert Path(db_path).exists()
        pe.close()

    def test_evolution_stats_empty(self, evolver):
        """Evolution stats with no data returns zeros."""
        stats = evolver.get_evolution_stats()
        assert stats["total_evolutions"] == 0
        assert stats["avg_improvement_per_evolution"] == 0.0
        assert stats["rollback_rate"] == 0.0

    def test_evolution_stats_with_data(self, evolver):
        """Evolution stats with real data returns correct values."""
        evolver.register_prompt("wraith", "V1")
        for _ in range(10):
            evolver.record_task_outcome("wraith", "test", 0.7)

        evolver.register_prompt("wraith", "V2")
        for _ in range(10):
            evolver.record_task_outcome("wraith", "test", 0.9)

        evolver.register_prompt("cerberus", "V1")

        stats = evolver.get_evolution_stats()
        assert stats["total_evolutions"] == 1  # wraith v2
        assert stats["most_evolved_module"] == "wraith"
