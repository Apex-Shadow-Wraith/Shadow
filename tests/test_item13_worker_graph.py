"""Item 13 — async worker routes deferred tasks through the parent graph.

Before the flip the async worker called ``module.execute`` directly, bypassing
the Cerberus plan-gate. After the flip it delegates to
``Orchestrator.run_deferred_through_graph``, so a deferred task traverses the
dormancy gate and the plan-gate: a Cerberus-DENIED plan reaches the terminal
``blocked`` node and **never executes a module**, and ``cerberus_approved`` is
computed by the real ``_step4_plan`` inside the plan node (never hardcoded).

This is the adversarial gate the cutover dispatch requires: the gate must BITE
through the worker path, structurally and behaviourally.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from modules.shadow.async_tasks import AsyncTaskQueue
from modules.shadow.task_queue import PriorityTaskQueue
from modules.shadow.task_tracker import TaskTracker
# Reuse the parent-graph canary modules + helpers (deny-Cerberus stub, leaf
# "did I run" canary, lightweight orchestrator, pinned classifier).
from tests.test_parent_graph import (
    _DenyCerberus,
    _LeafModule,
    _make_orch,
    _pin_classification,
)


@pytest.mark.asyncio
async def test_run_deferred_through_graph_denied_reaches_blocked(tmp_path: Path) -> None:
    """Structural+behavioural: a denied deferred task reaches ``blocked``.

    ``cerberus_approved`` is computed by the real ``_step4_plan`` (driven to DENY
    by the stub). The blocked terminal is reached, the leaf module's ``execute``
    never fires, and the returned state carries the denial envelope.
    """
    orch = _make_orch(tmp_path)
    _pin_classification(orch, "grimoire")
    orch.registry.register(_DenyCerberus())
    leaf = _LeafModule("grimoire", "memory_search")
    orch.registry.register(leaf)
    orch._tool_loader.refresh()

    state = await orch.run_deferred_through_graph(
        "search the memory for cats", source="autonomous"
    )

    assert leaf.executed is False, "a denied deferred task must never reach a module"
    assert any(
        getattr(tr, "error", None) == "Plan was denied by Cerberus"
        and getattr(tr, "tool_name", None) == "plan"
        for tr in state.get("tool_results", [])
    ), state.get("tool_results")
    # No retry leg ran (short-circuited at the plan-gate).
    assert state.get("retry_result") is None

    await orch.shutdown()


@pytest.mark.asyncio
async def test_worker_routes_denied_task_to_blocked(tmp_path: Path) -> None:
    """The DENIED deferred task reaches ``blocked`` *through the worker loop*.

    Submit a task, run the worker, and assert: the leaf never executed and the
    recorded result names the Cerberus denial. ``cerberus_approved`` is plan-
    computed (the stub drives ``_step4_plan`` to DENY) — never hardcoded.
    """
    orch = _make_orch(tmp_path)
    _pin_classification(orch, "grimoire")
    orch.registry.register(_DenyCerberus())
    leaf = _LeafModule("grimoire", "memory_search")
    orch.registry.register(leaf)
    orch._tool_loader.refresh()

    queue = PriorityTaskQueue(persist_path=tmp_path / "queue.json")
    queue.initialize()
    tracker = TaskTracker(db_path=tmp_path / "tasks.db")
    tracker.initialize()
    aq = AsyncTaskQueue(queue, tracker, orch.registry, orchestrator=orch)

    task_id = aq.submit_task(
        module_name="grimoire",
        tool_name="memory_search",
        params={"query": "cats"},
        description="search the memory for cats",
    )
    await aq.start()
    try:
        for _ in range(100):  # up to ~10s
            if aq.get_status(task_id) in ("completed", "failed"):
                break
            await asyncio.sleep(0.1)
    finally:
        await aq.stop()

    assert leaf.executed is False, "denied deferred task must not reach a module via the worker"
    result = aq.get_result(task_id)
    assert result is not None, "worker recorded no result"
    assert result.get("success") is False
    assert result.get("error") == "Plan was denied by Cerberus"
    assert result.get("tool_name") == "plan"

    tracker.close()
    await orch.shutdown()


@pytest.mark.asyncio
async def test_worker_approved_task_runs_through_graph(tmp_path: Path) -> None:
    """An APPROVED deferred task reaches the module via the graph retry leg.

    No Cerberus registered → plan approved → retry leg runs → the leaf executes.
    Proves the reroute is not a blanket denial: the gate bites only on denial.
    """
    orch = _make_orch(tmp_path)
    _pin_classification(orch, "grimoire")

    async def fake_eval(user_input, classification, results, context):
        return "evaluated ok"

    orch._step6_evaluate = fake_eval  # avoid Ollama in evaluation (covered elsewhere)
    leaf = _LeafModule("grimoire", "memory_search")
    orch.registry.register(leaf)  # no cerberus → approved
    orch._tool_loader.refresh()

    state = await orch.run_deferred_through_graph(
        "search the memory for cats", source="autonomous"
    )

    assert leaf.executed is True, "an approved deferred task must reach the module"
    assert state.get("status") == "succeeded"
    assert (state.get("retry_result") or {}).get("final_result", {}).get(
        "response"
    ) == "evaluated ok"

    await orch.shutdown()
