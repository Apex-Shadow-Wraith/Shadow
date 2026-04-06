"""
Tests for Morpheus — Creative Discovery Pipeline (Phase 1)
============================================================
Experiment tracking, evaluation tiers, state transitions, queue, reports.
"""

import pytest
from pathlib import Path
from typing import Any

from modules.base import ModuleStatus, ToolResult
from modules.morpheus.morpheus import Morpheus


@pytest.fixture
def morpheus(tmp_path: Path) -> Morpheus:
    config = {"db_path": str(tmp_path / "morpheus_experiments.db")}
    return Morpheus(config)


@pytest.fixture
async def online_morpheus(morpheus: Morpheus) -> Morpheus:
    await morpheus.initialize()
    return morpheus


async def _propose(m: Morpheus, **overrides) -> ToolResult:
    """Helper to propose an experiment with defaults."""
    params = {
        "title": "Test experiment",
        "hypothesis": "This will work",
        "category": "exploration",
        "priority": 3,
    }
    params.update(overrides)
    return await m.execute("experiment_propose", params)


async def _full_lifecycle(m: Morpheus, **propose_overrides) -> str:
    """Helper: propose -> start -> complete. Returns experiment_id."""
    r = await _propose(m, **propose_overrides)
    eid = r.content["experiment_id"]
    await m.execute("experiment_start", {"experiment_id": eid})
    await m.execute("experiment_complete", {
        "experiment_id": eid,
        "result_data": {"output": "test result"},
    })
    return eid


# --- Lifecycle ---

class TestLifecycle:
    @pytest.mark.asyncio
    async def test_initialize(self, morpheus: Morpheus):
        await morpheus.initialize()
        assert morpheus.status == ModuleStatus.ONLINE

    @pytest.mark.asyncio
    async def test_shutdown(self, morpheus: Morpheus):
        await morpheus.initialize()
        await morpheus.shutdown()
        assert morpheus.status == ModuleStatus.OFFLINE

    def test_get_tools(self, morpheus: Morpheus):
        tools = morpheus.get_tools()
        assert len(tools) == 7
        names = {t["name"] for t in tools}
        assert names == {
            "experiment_propose", "experiment_start", "experiment_complete",
            "experiment_evaluate", "experiment_list", "experiment_queue",
            "morpheus_report",
        }
        # All autonomous
        for t in tools:
            assert t["permission_level"] == "autonomous"

    @pytest.mark.asyncio
    async def test_unknown_tool(self, online_morpheus: Morpheus):
        r = await online_morpheus.execute("nonexistent", {})
        assert r.success is False
        assert "Unknown tool" in r.error


# --- Propose ---

class TestExperimentPropose:
    @pytest.mark.asyncio
    async def test_propose_basic(self, online_morpheus: Morpheus):
        r = await _propose(online_morpheus, title="New algo", category="optimization")
        assert r.success is True
        exp = r.content
        assert exp["title"] == "New algo"
        assert exp["category"] == "optimization"
        assert exp["status"] == "proposed"
        assert exp["priority"] == 3
        assert exp["experiment_id"]  # UUID generated
        assert exp["proposed_at"]
        assert exp["evaluation_score"] is None
        assert exp["evaluation_tier"] is None

    @pytest.mark.asyncio
    async def test_propose_with_input_data(self, online_morpheus: Morpheus):
        r = await _propose(online_morpheus, input_data={"model": "phi4", "temp": 0.7})
        assert r.success is True
        assert r.content["input_data"] == {"model": "phi4", "temp": 0.7}

    @pytest.mark.asyncio
    async def test_propose_with_priority(self, online_morpheus: Morpheus):
        r = await _propose(online_morpheus, priority=1)
        assert r.content["priority"] == 1

    @pytest.mark.asyncio
    async def test_propose_missing_title(self, online_morpheus: Morpheus):
        r = await _propose(online_morpheus, title="")
        assert r.success is False
        assert "Title" in r.error

    @pytest.mark.asyncio
    async def test_propose_missing_hypothesis(self, online_morpheus: Morpheus):
        r = await _propose(online_morpheus, hypothesis="")
        assert r.success is False
        assert "Hypothesis" in r.error

    @pytest.mark.asyncio
    async def test_propose_invalid_category(self, online_morpheus: Morpheus):
        r = await _propose(online_morpheus, category="magic")
        assert r.success is False
        assert "Category" in r.error

    @pytest.mark.asyncio
    async def test_propose_invalid_priority(self, online_morpheus: Morpheus):
        r = await _propose(online_morpheus, priority=0)
        assert r.success is False
        assert "Priority" in r.error

    @pytest.mark.asyncio
    async def test_propose_priority_too_high(self, online_morpheus: Morpheus):
        r = await _propose(online_morpheus, priority=6)
        assert r.success is False

    @pytest.mark.asyncio
    async def test_propose_parent_experiment(self, online_morpheus: Morpheus):
        parent = await _propose(online_morpheus, title="Parent")
        parent_id = parent.content["experiment_id"]
        child = await _propose(
            online_morpheus, title="Follow-up",
            parent_experiment_id=parent_id,
        )
        assert child.success is True
        assert child.content["parent_experiment_id"] == parent_id

    @pytest.mark.asyncio
    async def test_propose_invalid_parent(self, online_morpheus: Morpheus):
        r = await _propose(online_morpheus, parent_experiment_id="nonexistent-uuid")
        assert r.success is False
        assert "not found" in r.error


# --- Start ---

class TestExperimentStart:
    @pytest.mark.asyncio
    async def test_start(self, online_morpheus: Morpheus):
        r = await _propose(online_morpheus)
        eid = r.content["experiment_id"]
        start = await online_morpheus.execute("experiment_start", {"experiment_id": eid})
        assert start.success is True
        assert start.content["status"] == "running"
        assert start.content["started_at"] is not None

    @pytest.mark.asyncio
    async def test_start_missing_id(self, online_morpheus: Morpheus):
        r = await online_morpheus.execute("experiment_start", {})
        assert r.success is False

    @pytest.mark.asyncio
    async def test_start_nonexistent(self, online_morpheus: Morpheus):
        r = await online_morpheus.execute("experiment_start", {"experiment_id": "bad-uuid"})
        assert r.success is False
        assert "not found" in r.error

    @pytest.mark.asyncio
    async def test_cannot_start_completed(self, online_morpheus: Morpheus):
        """Cannot start an experiment that's already completed."""
        eid = await _full_lifecycle(online_morpheus)
        r = await online_morpheus.execute("experiment_start", {"experiment_id": eid})
        assert r.success is False
        assert "Cannot start" in r.error

    @pytest.mark.asyncio
    async def test_cannot_start_running(self, online_morpheus: Morpheus):
        """Cannot start an experiment that's already running."""
        r = await _propose(online_morpheus)
        eid = r.content["experiment_id"]
        await online_morpheus.execute("experiment_start", {"experiment_id": eid})
        r2 = await online_morpheus.execute("experiment_start", {"experiment_id": eid})
        assert r2.success is False
        assert "Cannot start" in r2.error

    @pytest.mark.asyncio
    async def test_cannot_start_rejected(self, online_morpheus: Morpheus):
        """Cannot start a rejected experiment."""
        # Reject by transitioning through the invalid path check
        r = await _propose(online_morpheus)
        eid = r.content["experiment_id"]
        # Manually reject via DB for this test
        online_morpheus._conn.execute(
            "UPDATE morpheus_experiments SET status='rejected' WHERE experiment_id=?",
            (eid,),
        )
        online_morpheus._conn.commit()
        r2 = await online_morpheus.execute("experiment_start", {"experiment_id": eid})
        assert r2.success is False


# --- Complete ---

class TestExperimentComplete:
    @pytest.mark.asyncio
    async def test_complete(self, online_morpheus: Morpheus):
        r = await _propose(online_morpheus)
        eid = r.content["experiment_id"]
        await online_morpheus.execute("experiment_start", {"experiment_id": eid})
        complete = await online_morpheus.execute("experiment_complete", {
            "experiment_id": eid,
            "result_data": {"accuracy": 0.95, "notes": "Great results"},
        })
        assert complete.success is True
        assert complete.content["status"] == "completed"
        assert complete.content["completed_at"] is not None
        assert complete.content["result_data"]["accuracy"] == 0.95

    @pytest.mark.asyncio
    async def test_complete_as_failed(self, online_morpheus: Morpheus):
        r = await _propose(online_morpheus)
        eid = r.content["experiment_id"]
        await online_morpheus.execute("experiment_start", {"experiment_id": eid})
        complete = await online_morpheus.execute("experiment_complete", {
            "experiment_id": eid,
            "result_data": {"error": "OOM"},
            "failed": True,
        })
        assert complete.success is True
        assert complete.content["status"] == "failed"

    @pytest.mark.asyncio
    async def test_cannot_complete_proposed(self, online_morpheus: Morpheus):
        """Cannot complete an experiment that hasn't started."""
        r = await _propose(online_morpheus)
        eid = r.content["experiment_id"]
        complete = await online_morpheus.execute("experiment_complete", {
            "experiment_id": eid,
            "result_data": {"output": "test"},
        })
        assert complete.success is False
        assert "Cannot complete" in complete.error

    @pytest.mark.asyncio
    async def test_complete_missing_result_data(self, online_morpheus: Morpheus):
        r = await _propose(online_morpheus)
        eid = r.content["experiment_id"]
        await online_morpheus.execute("experiment_start", {"experiment_id": eid})
        complete = await online_morpheus.execute("experiment_complete", {
            "experiment_id": eid,
        })
        assert complete.success is False
        assert "result_data" in complete.error


# --- Evaluate ---

class TestExperimentEvaluate:
    @pytest.mark.asyncio
    async def test_evaluate_tier1(self, online_morpheus: Morpheus):
        eid = await _full_lifecycle(online_morpheus)
        r = await online_morpheus.execute("experiment_evaluate", {
            "experiment_id": eid, "score": 0.95, "tier": 1,
            "notes": "Breakthrough approach",
        })
        assert r.success is True
        assert r.content["evaluation_score"] == 0.95
        assert r.content["evaluation_tier"] == 1
        assert r.content["evaluation_notes"] == "Breakthrough approach"

    @pytest.mark.asyncio
    async def test_evaluate_all_tiers(self, online_morpheus: Morpheus):
        for tier in (1, 2, 3, 4):
            eid = await _full_lifecycle(online_morpheus, title=f"Tier {tier} test")
            r = await online_morpheus.execute("experiment_evaluate", {
                "experiment_id": eid, "score": 0.5, "tier": tier,
            })
            assert r.success is True
            assert r.content["evaluation_tier"] == tier

    @pytest.mark.asyncio
    async def test_evaluate_invalid_score(self, online_morpheus: Morpheus):
        eid = await _full_lifecycle(online_morpheus)
        r = await online_morpheus.execute("experiment_evaluate", {
            "experiment_id": eid, "score": 1.5, "tier": 1,
        })
        assert r.success is False
        assert "score" in r.error

    @pytest.mark.asyncio
    async def test_evaluate_negative_score(self, online_morpheus: Morpheus):
        eid = await _full_lifecycle(online_morpheus)
        r = await online_morpheus.execute("experiment_evaluate", {
            "experiment_id": eid, "score": -0.1, "tier": 1,
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_evaluate_invalid_tier(self, online_morpheus: Morpheus):
        eid = await _full_lifecycle(online_morpheus)
        r = await online_morpheus.execute("experiment_evaluate", {
            "experiment_id": eid, "score": 0.5, "tier": 5,
        })
        assert r.success is False
        assert "tier" in r.error

    @pytest.mark.asyncio
    async def test_evaluate_missing_score(self, online_morpheus: Morpheus):
        eid = await _full_lifecycle(online_morpheus)
        r = await online_morpheus.execute("experiment_evaluate", {
            "experiment_id": eid, "tier": 1,
        })
        assert r.success is False
        assert "score" in r.error

    @pytest.mark.asyncio
    async def test_cannot_evaluate_proposed(self, online_morpheus: Morpheus):
        """Can only evaluate completed experiments."""
        r = await _propose(online_morpheus)
        eid = r.content["experiment_id"]
        ev = await online_morpheus.execute("experiment_evaluate", {
            "experiment_id": eid, "score": 0.5, "tier": 2,
        })
        assert ev.success is False
        assert "Cannot evaluate" in ev.error

    @pytest.mark.asyncio
    async def test_cannot_evaluate_running(self, online_morpheus: Morpheus):
        r = await _propose(online_morpheus)
        eid = r.content["experiment_id"]
        await online_morpheus.execute("experiment_start", {"experiment_id": eid})
        ev = await online_morpheus.execute("experiment_evaluate", {
            "experiment_id": eid, "score": 0.5, "tier": 2,
        })
        assert ev.success is False
        assert "Cannot evaluate" in ev.error

    @pytest.mark.asyncio
    async def test_evaluate_nonexistent(self, online_morpheus: Morpheus):
        r = await online_morpheus.execute("experiment_evaluate", {
            "experiment_id": "bad-uuid", "score": 0.5, "tier": 1,
        })
        assert r.success is False


# --- List ---

class TestExperimentList:
    @pytest.mark.asyncio
    async def test_list_empty(self, online_morpheus: Morpheus):
        r = await online_morpheus.execute("experiment_list", {})
        assert r.success is True
        assert r.content["total"] == 0
        assert r.content["experiments"] == []

    @pytest.mark.asyncio
    async def test_list_all(self, online_morpheus: Morpheus):
        await _propose(online_morpheus, title="A")
        await _propose(online_morpheus, title="B")
        r = await online_morpheus.execute("experiment_list", {})
        assert r.content["total"] == 2

    @pytest.mark.asyncio
    async def test_list_filter_status(self, online_morpheus: Morpheus):
        p = await _propose(online_morpheus, title="Running one")
        eid = p.content["experiment_id"]
        await online_morpheus.execute("experiment_start", {"experiment_id": eid})
        await _propose(online_morpheus, title="Proposed one")

        r = await online_morpheus.execute("experiment_list", {"status": "running"})
        assert r.content["total"] == 1
        assert r.content["experiments"][0]["title"] == "Running one"

    @pytest.mark.asyncio
    async def test_list_filter_category(self, online_morpheus: Morpheus):
        await _propose(online_morpheus, category="optimization")
        await _propose(online_morpheus, category="exploration")
        r = await online_morpheus.execute("experiment_list", {"category": "optimization"})
        assert r.content["total"] == 1

    @pytest.mark.asyncio
    async def test_list_invalid_status(self, online_morpheus: Morpheus):
        r = await online_morpheus.execute("experiment_list", {"status": "bogus"})
        assert r.success is False

    @pytest.mark.asyncio
    async def test_list_invalid_category(self, online_morpheus: Morpheus):
        r = await online_morpheus.execute("experiment_list", {"category": "bogus"})
        assert r.success is False

    @pytest.mark.asyncio
    async def test_list_sorted_by_priority(self, online_morpheus: Morpheus):
        await _propose(online_morpheus, title="Low priority", priority=5)
        await _propose(online_morpheus, title="High priority", priority=1)
        await _propose(online_morpheus, title="Mid priority", priority=3)
        r = await online_morpheus.execute("experiment_list", {})
        titles = [e["title"] for e in r.content["experiments"]]
        assert titles[0] == "High priority"
        assert titles[-1] == "Low priority"


# --- Queue ---

class TestExperimentQueue:
    @pytest.mark.asyncio
    async def test_queue_empty(self, online_morpheus: Morpheus):
        r = await online_morpheus.execute("experiment_queue", {})
        assert r.success is True
        assert r.content["queue_size"] == 0

    @pytest.mark.asyncio
    async def test_queue_respects_max(self, tmp_path: Path):
        m = Morpheus({"db_path": str(tmp_path / "test.db"), "max_queue": 2})
        await m.initialize()
        for i in range(5):
            await _propose(m, title=f"Exp {i}")
        r = await m.execute("experiment_queue", {})
        assert r.content["queue_size"] == 2
        assert r.content["total_proposed"] == 5

    @pytest.mark.asyncio
    async def test_queue_sorted_by_priority(self, online_morpheus: Morpheus):
        await _propose(online_morpheus, title="P5", priority=5)
        await _propose(online_morpheus, title="P1", priority=1)
        await _propose(online_morpheus, title="P3", priority=3)
        r = await online_morpheus.execute("experiment_queue", {})
        titles = [e["title"] for e in r.content["queue"]]
        assert titles[0] == "P1"

    @pytest.mark.asyncio
    async def test_queue_excludes_non_proposed(self, online_morpheus: Morpheus):
        p = await _propose(online_morpheus, title="Started")
        eid = p.content["experiment_id"]
        await online_morpheus.execute("experiment_start", {"experiment_id": eid})
        await _propose(online_morpheus, title="Still proposed")
        r = await online_morpheus.execute("experiment_queue", {})
        assert r.content["queue_size"] == 1
        assert r.content["queue"][0]["title"] == "Still proposed"

    @pytest.mark.asyncio
    async def test_queue_custom_max(self, online_morpheus: Morpheus):
        for i in range(10):
            await _propose(online_morpheus, title=f"Exp {i}")
        r = await online_morpheus.execute("experiment_queue", {"max_items": 3})
        assert r.content["queue_size"] == 3


# --- Report ---

class TestMorpheusReport:
    @pytest.mark.asyncio
    async def test_report_empty(self, online_morpheus: Morpheus):
        r = await online_morpheus.execute("morpheus_report", {})
        assert r.success is True
        assert r.content["highlight_count"] == 0
        assert r.content["failed_count"] == 0
        assert r.content["total_experiments"] == 0

    @pytest.mark.asyncio
    async def test_report_highlights(self, online_morpheus: Morpheus):
        # Create a tier 1 and tier 2 experiment
        for tier, title in [(1, "Breakthrough"), (2, "Useful find")]:
            eid = await _full_lifecycle(online_morpheus, title=title)
            await online_morpheus.execute("experiment_evaluate", {
                "experiment_id": eid, "score": 0.9, "tier": tier,
            })
        # Create a tier 4 (should not appear in highlights)
        eid3 = await _full_lifecycle(online_morpheus, title="Noise")
        await online_morpheus.execute("experiment_evaluate", {
            "experiment_id": eid3, "score": 0.1, "tier": 4,
        })

        r = await online_morpheus.execute("morpheus_report", {})
        assert r.content["highlight_count"] == 2
        highlight_titles = {h["title"] for h in r.content["highlights"]}
        assert "Breakthrough" in highlight_titles
        assert "Useful find" in highlight_titles
        assert "Noise" not in highlight_titles

    @pytest.mark.asyncio
    async def test_report_failed(self, online_morpheus: Morpheus):
        p = await _propose(online_morpheus, title="Doomed")
        eid = p.content["experiment_id"]
        await online_morpheus.execute("experiment_start", {"experiment_id": eid})
        await online_morpheus.execute("experiment_complete", {
            "experiment_id": eid,
            "result_data": {"error": "crashed"},
            "failed": True,
        })
        r = await online_morpheus.execute("morpheus_report", {})
        assert r.content["failed_count"] == 1
        assert r.content["failed"][0]["title"] == "Doomed"

    @pytest.mark.asyncio
    async def test_report_queue_status(self, online_morpheus: Morpheus):
        await _propose(online_morpheus, title="Pending 1")
        await _propose(online_morpheus, title="Pending 2")
        p = await _propose(online_morpheus, title="Running")
        eid = p.content["experiment_id"]
        await online_morpheus.execute("experiment_start", {"experiment_id": eid})

        r = await online_morpheus.execute("morpheus_report", {})
        assert r.content["queue_size"] == 2
        assert r.content["running_count"] == 1
        assert r.content["total_experiments"] == 3


# --- Full lifecycle ---

class TestFullLifecycle:
    @pytest.mark.asyncio
    async def test_propose_start_complete_evaluate(self, online_morpheus: Morpheus):
        """Full experiment lifecycle: propose -> start -> complete -> evaluate."""
        # Propose
        r1 = await _propose(online_morpheus, title="Full lifecycle test",
                            hypothesis="We can track experiments end-to-end",
                            category="validation")
        assert r1.success is True
        eid = r1.content["experiment_id"]
        assert r1.content["status"] == "proposed"

        # Start
        r2 = await online_morpheus.execute("experiment_start", {"experiment_id": eid})
        assert r2.success is True
        assert r2.content["status"] == "running"

        # Complete
        r3 = await online_morpheus.execute("experiment_complete", {
            "experiment_id": eid,
            "result_data": {"accuracy": 0.99, "latency_ms": 42},
        })
        assert r3.success is True
        assert r3.content["status"] == "completed"
        assert r3.content["result_data"]["accuracy"] == 0.99

        # Evaluate
        r4 = await online_morpheus.execute("experiment_evaluate", {
            "experiment_id": eid, "score": 0.95, "tier": 1,
            "notes": "Excellent tracking system",
        })
        assert r4.success is True
        assert r4.content["evaluation_tier"] == 1
        assert r4.content["evaluation_score"] == 0.95

    @pytest.mark.asyncio
    async def test_parent_child_chain(self, online_morpheus: Morpheus):
        """Parent experiment spawns follow-up child."""
        parent = await _propose(online_morpheus, title="Initial study")
        parent_id = parent.content["experiment_id"]

        child = await _propose(online_morpheus, title="Follow-up",
                               parent_experiment_id=parent_id)
        assert child.success is True
        assert child.content["parent_experiment_id"] == parent_id

        # Verify listing shows both
        r = await online_morpheus.execute("experiment_list", {})
        assert r.content["total"] == 2


# --- Persistence ---

class TestPersistence:
    @pytest.mark.asyncio
    async def test_db_persists(self, tmp_path: Path):
        db_path = str(tmp_path / "persist_test.db")

        m1 = Morpheus({"db_path": db_path})
        await m1.initialize()
        await _propose(m1, title="Persist me")
        await m1.shutdown()

        m2 = Morpheus({"db_path": db_path})
        await m2.initialize()
        r = await m2.execute("experiment_list", {})
        assert r.content["total"] == 1
        assert r.content["experiments"][0]["title"] == "Persist me"
        await m2.shutdown()

    @pytest.mark.asyncio
    async def test_db_persists_full_state(self, tmp_path: Path):
        """Verify all fields survive shutdown/restart."""
        db_path = str(tmp_path / "state_test.db")

        m1 = Morpheus({"db_path": db_path})
        await m1.initialize()
        eid = await _full_lifecycle(m1, title="State test", category="comparison")
        await m1.execute("experiment_evaluate", {
            "experiment_id": eid, "score": 0.8, "tier": 2, "notes": "Good",
        })
        await m1.shutdown()

        m2 = Morpheus({"db_path": db_path})
        await m2.initialize()
        r = await m2.execute("experiment_list", {})
        exp = r.content["experiments"][0]
        assert exp["title"] == "State test"
        assert exp["category"] == "comparison"
        assert exp["status"] == "completed"
        assert exp["evaluation_score"] == 0.8
        assert exp["evaluation_tier"] == 2
        assert exp["evaluation_notes"] == "Good"
        assert exp["result_data"] == {"output": "test result"}
        await m2.shutdown()
