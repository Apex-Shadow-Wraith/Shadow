"""
Tests for Tool Chain Workflow Storage
"""

import time
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from modules.shadow.workflow_store import WorkflowStore, StoredWorkflow, WorkflowStep


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def tmp_db(tmp_path):
    """Return a temp DB path."""
    return str(tmp_path / "test_workflows.db")


@pytest.fixture
def mock_grimoire():
    """Return a mocked Grimoire instance."""
    g = MagicMock()
    g.remember.return_value = "mem-123"
    g.recall.return_value = []
    return g


@pytest.fixture
def store(tmp_db):
    """WorkflowStore with no Grimoire (SQLite-only mode)."""
    s = WorkflowStore(grimoire=None, db_path=tmp_db)
    yield s
    s.close()


@pytest.fixture
def store_with_grimoire(tmp_db, mock_grimoire):
    """WorkflowStore with mocked Grimoire."""
    s = WorkflowStore(grimoire=mock_grimoire, db_path=tmp_db)
    yield s
    s.close()


def _sample_steps():
    """Return sample workflow steps as dicts."""
    return [
        {
            "step_number": 1,
            "tool": "reaper",
            "action": "web_search",
            "input_source": "user",
            "output_format": "json",
            "transform": "",
        },
        {
            "step_number": 2,
            "tool": "cipher",
            "action": "summarize_data",
            "input_source": "step_1",
            "output_format": "text",
            "transform": "extract_key_points",
        },
    ]


# =============================================================================
# store_workflow tests
# =============================================================================

class TestStoreWorkflow:
    """Tests for store_workflow method."""

    def test_creates_valid_workflow_in_sqlite(self, store):
        """store_workflow creates a valid StoredWorkflow in SQLite."""
        wf_id = store.store_workflow(
            task_type="research",
            description="Search and summarize",
            steps=_sample_steps(),
        )
        assert wf_id is not None

        # Verify it's retrievable
        row = store.conn.execute(
            "SELECT * FROM workflows WHERE workflow_id = ?", (wf_id,)
        ).fetchone()
        assert row is not None
        assert row["task_type"] == "research"
        assert row["success_count"] == 1

    def test_stores_in_grimoire(self, store_with_grimoire, mock_grimoire):
        """store_workflow also stores in Grimoire for semantic search."""
        store_with_grimoire.store_workflow(
            task_type="research",
            description="Search and summarize",
            steps=_sample_steps(),
        )
        mock_grimoire.remember.assert_called_once()
        call_kwargs = mock_grimoire.remember.call_args
        assert "workflow" in call_kwargs.kwargs.get("category", call_kwargs[1].get("category", ""))

    def test_deduplicates_same_tool_sequence(self, store):
        """store_workflow deduplicates workflows with same tool sequence."""
        wf_id1 = store.store_workflow(
            task_type="research",
            description="First search",
            steps=_sample_steps(),
        )
        wf_id2 = store.store_workflow(
            task_type="research",
            description="Second search",
            steps=_sample_steps(),
        )
        # Should return same ID (dedup)
        assert wf_id1 == wf_id2

        # success_count should be 2 (initial 1 + 1 update)
        row = store.conn.execute(
            "SELECT success_count FROM workflows WHERE workflow_id = ?", (wf_id1,)
        ).fetchone()
        assert row["success_count"] == 2

    def test_different_tools_not_deduped(self, store):
        """Workflows with different tool sequences are not deduped."""
        wf_id1 = store.store_workflow(
            task_type="research",
            description="Search",
            steps=[{"tool": "reaper", "action": "search"}],
        )
        wf_id2 = store.store_workflow(
            task_type="code",
            description="Lint code",
            steps=[{"tool": "omen", "action": "lint"}],
        )
        assert wf_id1 != wf_id2

    def test_stores_domain_tags(self, store):
        """store_workflow stores domain tags correctly."""
        wf_id = store.store_workflow(
            task_type="research",
            description="Web research",
            steps=_sample_steps(),
            domain_tags=["landscaping", "pricing"],
        )
        row = store.conn.execute(
            "SELECT domain_tags FROM workflows WHERE workflow_id = ?", (wf_id,)
        ).fetchone()
        import json
        tags = json.loads(row["domain_tags"])
        assert "landscaping" in tags
        assert "pricing" in tags

    def test_single_step_workflow_valid(self, store):
        """Workflow with a single step is valid."""
        wf_id = store.store_workflow(
            task_type="quick",
            description="Single tool",
            steps=[{"tool": "cipher", "action": "calculate"}],
        )
        assert wf_id is not None


# =============================================================================
# find_workflow tests
# =============================================================================

class TestFindWorkflow:
    """Tests for find_workflow method."""

    def test_returns_matching_workflows(self, store):
        """find_workflow returns matching workflows via SQLite fallback."""
        store.store_workflow(
            task_type="research",
            description="Search web for competitor pricing",
            steps=_sample_steps(),
        )
        results = store.find_workflow("competitor pricing")
        assert len(results) >= 1
        assert results[0].task_type == "research"

    def test_ranks_by_success_count(self, store):
        """find_workflow ranks by relevance * success_count."""
        wf1 = store.store_workflow(
            task_type="research",
            description="Search web data analysis",
            steps=[{"tool": "reaper", "action": "search"}],
        )
        wf2 = store.store_workflow(
            task_type="research",
            description="Search web data processing",
            steps=[{"tool": "cipher", "action": "process"}],
        )
        # Boost wf2's success count
        for _ in range(5):
            store.record_usage(wf2, success=True)

        results = store.find_workflow("search web data")
        assert len(results) >= 2
        # Higher success_count should rank first
        assert results[0].workflow_id == wf2

    def test_filters_by_task_type(self, store):
        """find_workflow filters by task_type."""
        store.store_workflow(
            task_type="research",
            description="Web search task",
            steps=[{"tool": "reaper", "action": "search"}],
        )
        store.store_workflow(
            task_type="code",
            description="Code search lint",
            steps=[{"tool": "omen", "action": "lint"}],
        )
        results = store.find_workflow("search", task_type="code")
        assert all(r.task_type == "code" for r in results)

    def test_filters_by_required_tools(self, store):
        """find_workflow filters by required_tools."""
        store.store_workflow(
            task_type="research",
            description="Search summarize analyze",
            steps=_sample_steps(),  # reaper + cipher
        )
        store.store_workflow(
            task_type="research",
            description="Search summarize only",
            steps=[{"tool": "reaper", "action": "search"}],
        )
        results = store.find_workflow(
            "search summarize", required_tools=["cipher"]
        )
        assert all("cipher" in r.tools_required for r in results)

    def test_find_with_grimoire(self, store_with_grimoire, mock_grimoire):
        """find_workflow uses Grimoire semantic search when available."""
        # Store a workflow first
        wf_id = store_with_grimoire.store_workflow(
            task_type="research",
            description="Search and summarize",
            steps=_sample_steps(),
        )
        # Mock Grimoire to return this workflow
        mock_grimoire.recall.return_value = [
            {"metadata": {"workflow_id": wf_id}, "content": "test"}
        ]
        results = store_with_grimoire.find_workflow("find stuff online")
        mock_grimoire.recall.assert_called()
        assert len(results) >= 1

    def test_empty_store_returns_empty(self, store):
        """Empty store: find_workflow returns empty list."""
        results = store.find_workflow("anything")
        assert results == []


# =============================================================================
# adapt_workflow tests
# =============================================================================

class TestAdaptWorkflow:
    """Tests for adapt_workflow method."""

    def test_preserves_tool_sequence(self, store):
        """adapt_workflow preserves the tool sequence."""
        wf_id = store.store_workflow(
            task_type="research",
            description="Search and summarize",
            steps=_sample_steps(),
        )
        wf = store.get_popular_workflows(1)[0]
        adapted = store.adapt_workflow(wf, "find landscaping trends")
        assert len(adapted) == 2
        assert adapted[0]["tool"] == "reaper"
        assert adapted[1]["tool"] == "cipher"

    def test_returns_adapted_steps_as_dicts(self, store):
        """adapt_workflow returns steps as list of dicts."""
        wf_id = store.store_workflow(
            task_type="research",
            description="Search and summarize",
            steps=_sample_steps(),
        )
        wf = store.get_popular_workflows(1)[0]
        adapted = store.adapt_workflow(wf, "new task")
        assert isinstance(adapted, list)
        assert all(isinstance(s, dict) for s in adapted)
        assert "adapted for: new task" in adapted[0]["action"]


# =============================================================================
# record_usage tests
# =============================================================================

class TestRecordUsage:
    """Tests for record_usage method."""

    def test_increments_success_count(self, store):
        """record_usage increments success_count on success."""
        wf_id = store.store_workflow(
            task_type="research",
            description="Test workflow",
            steps=_sample_steps(),
        )
        store.record_usage(wf_id, success=True)
        row = store.conn.execute(
            "SELECT success_count FROM workflows WHERE workflow_id = ?", (wf_id,)
        ).fetchone()
        assert row["success_count"] == 2  # 1 initial + 1

    def test_updates_average_duration(self, store):
        """record_usage updates average_duration."""
        wf_id = store.store_workflow(
            task_type="research",
            description="Test workflow",
            steps=_sample_steps(),
            duration=10.0,
        )
        store.record_usage(wf_id, success=True, duration=20.0)
        row = store.conn.execute(
            "SELECT average_duration FROM workflows WHERE workflow_id = ?", (wf_id,)
        ).fetchone()
        # (10*1 + 20) / 2 = 15
        assert abs(row["average_duration"] - 15.0) < 0.01

    def test_failure_doesnt_decrement(self, store):
        """record_usage: failure doesn't decrement success_count."""
        wf_id = store.store_workflow(
            task_type="research",
            description="Test workflow",
            steps=_sample_steps(),
        )
        store.record_usage(wf_id, success=False)
        row = store.conn.execute(
            "SELECT success_count FROM workflows WHERE workflow_id = ?", (wf_id,)
        ).fetchone()
        assert row["success_count"] == 1  # unchanged

    def test_nonexistent_workflow_returns_false(self, store):
        """record_usage returns False for nonexistent workflow."""
        result = store.record_usage("nonexistent-id", success=True)
        assert result is False


# =============================================================================
# get_popular_workflows tests
# =============================================================================

class TestGetPopularWorkflows:
    """Tests for get_popular_workflows method."""

    def test_returns_most_used(self, store):
        """get_popular_workflows returns workflows ordered by success_count."""
        store.store_workflow(
            task_type="a", description="low use",
            steps=[{"tool": "t1", "action": "a"}],
        )
        wf2 = store.store_workflow(
            task_type="b", description="high use",
            steps=[{"tool": "t2", "action": "b"}],
        )
        for _ in range(5):
            store.record_usage(wf2, success=True)

        popular = store.get_popular_workflows(limit=2)
        assert len(popular) == 2
        assert popular[0].workflow_id == wf2

    def test_empty_store_returns_empty(self, store):
        """Empty store: get_popular_workflows returns empty list."""
        assert store.get_popular_workflows() == []


# =============================================================================
# get_workflow_stats tests
# =============================================================================

class TestGetWorkflowStats:
    """Tests for get_workflow_stats method."""

    def test_returns_accurate_counts(self, store):
        """get_workflow_stats returns accurate aggregate stats."""
        store.store_workflow(
            task_type="research", description="wf1",
            steps=_sample_steps(),
        )
        store.store_workflow(
            task_type="code", description="wf2",
            steps=[{"tool": "omen", "action": "lint"}],
        )
        stats = store.get_workflow_stats()
        assert stats["total_workflows"] == 2
        assert stats["total_usages"] == 2  # each starts at 1
        assert "reaper" in stats["most_used_tools"] or "omen" in stats["most_used_tools"]
        assert stats["avg_steps_per_workflow"] > 0

    def test_empty_store_stats(self, store):
        """Empty store: stats returns valid zeroes."""
        stats = store.get_workflow_stats()
        assert stats["total_workflows"] == 0
        assert stats["total_usages"] == 0
        assert stats["most_used_tools"] == []


# =============================================================================
# cleanup_unused tests
# =============================================================================

class TestCleanupUnused:
    """Tests for cleanup_unused method."""

    def test_flags_old_workflows(self, store):
        """cleanup_unused flags workflows not used in N days."""
        wf_id = store.store_workflow(
            task_type="old", description="ancient workflow",
            steps=[{"tool": "t1", "action": "a"}],
        )
        # Backdate last_used to 100 days ago
        old_time = time.time() - (100 * 86400)
        store.conn.execute(
            "UPDATE workflows SET last_used = ? WHERE workflow_id = ?",
            (old_time, wf_id),
        )
        store.conn.commit()

        count = store.cleanup_unused(days=90)
        assert count == 1

        row = store.conn.execute(
            "SELECT flagged_unused FROM workflows WHERE workflow_id = ?", (wf_id,)
        ).fetchone()
        assert row["flagged_unused"] == 1

    def test_doesnt_delete_anything(self, store):
        """cleanup_unused flags but never deletes."""
        wf_id = store.store_workflow(
            task_type="old", description="old workflow",
            steps=[{"tool": "t1", "action": "a"}],
        )
        old_time = time.time() - (200 * 86400)
        store.conn.execute(
            "UPDATE workflows SET last_used = ? WHERE workflow_id = ?",
            (old_time, wf_id),
        )
        store.conn.commit()

        store.cleanup_unused(days=90)

        # Workflow still exists
        row = store.conn.execute(
            "SELECT * FROM workflows WHERE workflow_id = ?", (wf_id,)
        ).fetchone()
        assert row is not None

    def test_recent_workflows_not_flagged(self, store):
        """cleanup_unused doesn't flag recently used workflows."""
        store.store_workflow(
            task_type="new", description="fresh workflow",
            steps=[{"tool": "t1", "action": "a"}],
        )
        count = store.cleanup_unused(days=90)
        assert count == 0


# =============================================================================
# Edge cases
# =============================================================================

class TestEdgeCases:
    """Edge cases and resilience tests."""

    def test_sqlite_db_created_on_init(self, tmp_db):
        """SQLite DB is created on init."""
        s = WorkflowStore(db_path=tmp_db)
        assert Path(tmp_db).exists()
        s.close()

    def test_graceful_without_grimoire(self, store):
        """All operations work when Grimoire is unavailable (SQLite-only)."""
        wf_id = store.store_workflow(
            task_type="test", description="no grimoire test",
            steps=_sample_steps(),
        )
        assert wf_id is not None

        results = store.find_workflow("no grimoire test")
        assert len(results) >= 1

        assert store.record_usage(wf_id, success=True)
        assert len(store.get_popular_workflows()) >= 1
        assert store.get_workflow_stats()["total_workflows"] >= 1
