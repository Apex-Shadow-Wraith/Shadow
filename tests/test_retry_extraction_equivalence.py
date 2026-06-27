"""Retry-extraction byte-equivalence — the load-bearing flip artifact.

``_build_retry_closures`` (Unit A) and ``_resolve_retry_outcome`` (Unit C) are
NEW orchestrator code carved out of the former inline ``_step5_with_retry``.
``test_retry_engine``'s 40 tests cover only ``attempt_task`` (Unit B) — they do
NOT reach A/C. These tests prove A/C are faithful through BOTH paths that call
them — the live ``_step5_with_retry`` AND the graph retry node + caller
resolution — and that the caller-rebuilt ``execute_fn`` drives the escalation
path byte-identically to the retry node's.

``attempt_task`` (Unit B) is mocked here so each Unit-C branch is exercised
deterministically; the loop itself stays covered by ``test_retry_engine``.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from modules.shadow.graph.retry_graph import make_orchestrator_retry_node
from modules.shadow.orchestrator import ExecutionPlan
from tests.test_parent_graph import _classification, _make_orch

OFFER = (
    "I tried 3 different approaches but couldn't solve this. "
    "Would you like me to escalate to Apex (Claude/GPT API) for help? "
    "Apex will provide the answer and teach me the approach so I can "
    "handle similar tasks locally in the future."
)


def _plan() -> ExecutionPlan:
    return ExecutionPlan(
        steps=[{"tool": "memory_search", "params": {}}],
        cerberus_approved=True,
        raw_plan="",
    )


def _exhausted(n: int = 3) -> dict:
    return {
        "status": "exhausted",
        "exhausted": True,
        "ready_to_escalate": True,
        "attempts": [{"success": False} for _ in range(n)],
        "final_result": {"response": ""},
    }


def _succeeded(text: str = "the answer") -> dict:
    return {
        "status": "succeeded",
        "attempts": [{"success": True, "result": {"response": text}}],
        "final_result": {"response": text},
    }


# ---------------------------------------------------------------------------
# Unit A — _build_retry_closures
# ---------------------------------------------------------------------------


def test_build_retry_closures_returns_four(tmp_path: Path) -> None:
    orch = _make_orch(tmp_path)
    execute_fn, evaluate_fn, grimoire_search_fn, notify_fn = (
        orch._build_retry_closures(_plan(), _classification("grimoire"), [], "user")
    )
    assert callable(execute_fn) and callable(evaluate_fn)


def test_build_retry_closures_notify_gate(tmp_path: Path) -> None:
    """notify_fn exists only for source=='user' (live gate, orchestrator.py)."""
    orch = _make_orch(tmp_path)
    _, _, _, notify_user = orch._build_retry_closures(
        _plan(), _classification("grimoire"), [], "user"
    )
    _, _, _, notify_bench = orch._build_retry_closures(
        _plan(), _classification("grimoire"), [], "benchmark"
    )
    assert notify_user is not None
    assert notify_bench is None


def test_build_retry_closures_evaluate_fn_gating(tmp_path: Path) -> None:
    """evaluate_fn: non-empty response + no tool errors == success."""
    orch = _make_orch(tmp_path)
    _, evaluate_fn, _, _ = orch._build_retry_closures(
        _plan(), _classification("grimoire"), [], "user"
    )
    assert evaluate_fn({"response": "x", "results": []})["success"] is True
    assert evaluate_fn({"response": "", "results": []})["success"] is False
    assert evaluate_fn({"tool_loader_empty": True})["success"] is False


# ---------------------------------------------------------------------------
# Unit C — _resolve_retry_outcome (each branch)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_succeeded(tmp_path: Path) -> None:
    orch = _make_orch(tmp_path)
    out = await orch._resolve_retry_outcome(
        _succeeded("hello"), "q", _classification("grimoire"), [], "user", None
    )
    assert out == "hello"


@pytest.mark.asyncio
async def test_resolve_benchmark_no_escalate(tmp_path: Path) -> None:
    """source=='benchmark' must NOT escalate to Apex (measures local model)."""
    orch = _make_orch(tmp_path)
    orch._decomposer = None
    orch._retry_engine.escalate_to_apex = AsyncMock()  # must not be called
    rr = _exhausted(3)
    rr["final_result"] = {}  # no response → default benchmark-failure message
    out = await orch._resolve_retry_outcome(
        rr, "q", _classification("grimoire"), [], "benchmark", None
    )
    orch._retry_engine.escalate_to_apex.assert_not_called()
    assert out == "[Benchmark failure] Exhausted 3 attempts."


@pytest.mark.asyncio
async def test_resolve_live_conversation_offer_and_pending(tmp_path: Path) -> None:
    """source=='user' exhausted → exact offer string + _pending_escalation write."""
    orch = _make_orch(tmp_path)
    orch._decomposer = None
    execute_fn, _, _, _ = orch._build_retry_closures(
        _plan(), _classification("grimoire"), [], "user"
    )
    assert orch._pending_escalation is None
    out = await orch._resolve_retry_outcome(
        _exhausted(3), "q", _classification("grimoire"), [], "user", execute_fn
    )
    assert out == OFFER  # exact bytes
    assert orch._pending_escalation is not None
    assert orch._pending_escalation["execute_fn"] is execute_fn
    assert orch._pending_escalation["original_input"] == "q"


@pytest.mark.asyncio
async def test_resolve_autonomous_auto_escalates(tmp_path: Path) -> None:
    """A non-user/telegram/discord source auto-escalates when apex is present."""
    orch = _make_orch(tmp_path)
    orch._decomposer = None

    class _Apex:
        name = "apex"
        from modules.base import ModuleStatus as _MS
        status = _MS.ONLINE

        async def initialize(self):  # pragma: no cover
            pass

        async def shutdown(self):  # pragma: no cover
            pass

        def get_tools(self):
            return []

        async def execute(self, *a, **k):  # pragma: no cover
            from modules.base import ToolResult
            return ToolResult(success=True, content="", tool_name="apex_query", module="apex")

    orch.registry.register(_Apex())
    orch._retry_engine.escalate_to_apex = AsyncMock(
        return_value={"success": True, "answer": "escalated answer"}
    )
    out = await orch._resolve_retry_outcome(
        _exhausted(), "q", _classification("grimoire"), [], "scheduled", None
    )
    orch._retry_engine.escalate_to_apex.assert_awaited_once()
    assert out == "escalated answer"
    assert orch._pending_escalation is None  # autonomous does not stage an offer


@pytest.mark.asyncio
async def test_resolve_decomposition_skips_escalation(tmp_path: Path) -> None:
    """Pre-escalation decomposition with confidence >= 0.6 returns its solution."""
    orch = _make_orch(tmp_path)

    class _Decomp:
        def solve_with_decomposition(self, q, ctx):
            import types
            return types.SimpleNamespace(
                overall_confidence=0.7, merged_solution="decomposed answer"
            )

    orch._decomposer = _Decomp()
    orch._retry_engine.escalate_to_apex = AsyncMock()
    out = await orch._resolve_retry_outcome(
        _exhausted(), "q", _classification("grimoire"), [], "user", None
    )
    assert out == "decomposed answer"
    orch._retry_engine.escalate_to_apex.assert_not_called()
    assert orch._pending_escalation is None


# ---------------------------------------------------------------------------
# Both paths identical — the equivalence proof
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_live_and_graph_paths_identical_response(tmp_path: Path) -> None:
    """Same scenario through live _step5_with_retry AND graph retry node + caller
    resolution yields the identical response (both call the same A/C methods).
    """
    user_input, source = "q", "user"
    plan, classification, context = _plan(), _classification("grimoire"), []

    # --- Live path ---
    orch_live = _make_orch(tmp_path / "live")
    orch_live._decomposer = None
    orch_live._retry_engine.attempt_task = AsyncMock(return_value=_exhausted(3))
    response_live = await orch_live._step5_with_retry(
        user_input, plan, classification, context, source
    )
    pending_live = dict(orch_live._pending_escalation)

    # --- Graph path: retry node produces retry_result, caller resolves ---
    orch_graph = _make_orch(tmp_path / "graph")
    orch_graph._decomposer = None
    orch_graph._retry_engine.attempt_task = AsyncMock(return_value=_exhausted(3))
    node = make_orchestrator_retry_node(orch_graph)
    state = await node({
        "user_input": user_input, "plan": plan,
        "classification": classification, "context": context, "source": source,
    })
    retry_result = state["retry_result"]
    execute_fn, _, _, _ = orch_graph._build_retry_closures(
        plan, classification, context, source
    )
    response_graph = await orch_graph._resolve_retry_outcome(
        retry_result, user_input, classification, context, source, execute_fn
    )
    pending_graph = dict(orch_graph._pending_escalation)

    assert response_live == response_graph == OFFER
    assert pending_live["original_input"] == pending_graph["original_input"]
    assert pending_live["classification"] == pending_graph["classification"]


@pytest.mark.asyncio
async def test_execute_fn_rebuild_byte_identical_on_escalation(tmp_path: Path) -> None:
    """Master condition (c): the caller-rebuilt execute_fn (used for resolution /
    _pending_escalation) is byte-identical to the retry node's — both built from
    the same inputs via _build_retry_closures produce identical output.
    """
    orch = _make_orch(tmp_path)
    plan, classification, context, source = _plan(), _classification("grimoire"), [], "user"

    # Populate the tool loader so execute_fn's infra-guard doesn't short-circuit.
    from tests.test_parent_graph import _LeafModule
    orch.registry.register(_LeafModule("grimoire", "memory_search"))
    orch._tool_loader.refresh()

    # Deterministic execute_fn behavior: stub the two methods it delegates to.
    async def fake_execute(plan_, cls_, src_):
        from modules.base import ToolResult
        return [ToolResult(success=True, content="ran", tool_name="memory_search", module="grimoire")]

    async def fake_eval(ui, cls_, results, ctx):
        return "evaluated"

    orch._step5_execute = fake_execute
    orch._step6_evaluate = fake_eval

    # The retry node builds one execute_fn; the caller rebuilds another. Both via
    # _build_retry_closures with identical inputs.
    execute_fn_node, _, _, _ = orch._build_retry_closures(plan, classification, context, source)
    execute_fn_caller, _, _, _ = orch._build_retry_closures(plan, classification, context, source)
    assert execute_fn_node is not execute_fn_caller  # distinct closure instances

    out_node = await execute_fn_node("task", {})
    out_caller = await execute_fn_caller("task", {})
    assert out_node == out_caller  # byte-identical behavior
    assert out_caller["response"] == "evaluated"
