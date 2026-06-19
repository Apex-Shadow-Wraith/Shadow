"""Phase B / Track B — Step 3 retry node + conditional self-edge tests.

Covers the retry delegating node at :mod:`modules.shadow.graph.retry_graph`,
which translates the orchestrator's 12-attempt retry loop into **one** node with
a conditional **self-edge**. The load-bearing invariants, in order of importance:

1. **Self-edge loops then exits (rotation is data).** Drive an engine that fails
   N times then succeeds — assert the node was re-entered exactly N+1 times via
   the self-edge and exited on ``"succeeded"``. The loop *count* comes from the
   engine's verdicts, not from a fixed topology of unrolled retry nodes.
2. **Exhaustion path.** Always-fail → the engine's ``should_escalate`` flips the
   verdict to ``"exhausted"`` at ``max_attempts`` and the self-edge routes to
   ``END``. No infinite loop: the edge respects the engine's give-up.
3. **Delegation parity canary.** The node routes strategy selection *through*
   ``RetryEngine.get_strategy_for_attempt`` once per attempt — proving rotation
   is delegated, not reimplemented in the node. Same posture as the other nodes'
   ``_call_count`` canaries.
4. **Checkpoint round-trip.** An attempt's ``ToolResult`` survives
   ``AsyncSqliteSaver`` via ``shadow_serde``, mirroring the dispatch sub-graph
   test.

Span parity is the inverse of the other nodes: the live per-attempt path *emits*
the ``retry_attempt`` span (``retry_engine.py:358``), so the node must preserve
it — asserted by source inspection.
"""

from __future__ import annotations

import inspect

import pytest
from langgraph.graph import END, START

from modules.base import ToolResult
from modules.shadow.graph import (
    build_retry_subgraph,
    compile_retry_subgraph,
    make_retry_node,
    open_async_sqlite_saver,
)
from modules.shadow.graph.retry_graph import _route
from modules.shadow.retry_engine import RetryEngine, RetrySession


# ---------------------------------------------------------------------------
# Helpers — caller closures matching the live execute_fn / evaluate_fn shape
# ---------------------------------------------------------------------------


def _make_evaluate_fn():
    """Evaluate gate matching the live orchestrator closure: non-empty response
    + no tool errors == success (``orchestrator.py:4637-4668``, simplified)."""

    def evaluate_fn(result: dict) -> dict:
        if result.get("response"):
            return {"success": True, "confidence": 0.7, "reason": "ok"}
        return {"success": False, "confidence": 0.0, "reason": "Empty response"}

    return evaluate_fn


def _make_execute_fn(succeed_on_attempt: int | None):
    """Build an async execute_fn that returns an empty (failing) response until
    ``succeed_on_attempt``, then a non-empty (passing) one.

    ``succeed_on_attempt=None`` never succeeds → drives the exhaustion path.
    The counter also records how many real attempts the engine drove, distinct
    from node re-entries (they should match 1:1 across the self-edge).
    """
    calls = {"n": 0}

    async def execute_fn(task: str, strategy_context: dict) -> dict:
        calls["n"] += 1
        if succeed_on_attempt is not None and calls["n"] >= succeed_on_attempt:
            return {"response": f"solved on attempt {calls['n']}", "results": []}
        return {"response": "", "results": []}

    return execute_fn, calls


def _initial_state() -> dict:
    return {
        "task": "do the thing",
        "module": "omen",
        "context": {"task_type": "code_generation", "tools": ["code_generate"]},
    }


# ---------------------------------------------------------------------------
# 1. Self-edge loops then exits — the rotation-as-data assertion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_self_edge_loops_n_times_then_exits_on_success() -> None:
    """Fail 2× then succeed → node re-entered exactly 3× via the self-edge.

    This is the load-bearing proof: the loop count (3) is produced by the
    engine's verdicts ("retry", "retry", "succeeded"), not by a fixed chain of
    retry nodes. Three distinct strategies are used — the rotation the engine
    owns advanced on every re-entry.
    """
    engine = RetryEngine()
    execute_fn, calls = _make_execute_fn(succeed_on_attempt=3)
    graph = compile_retry_subgraph(engine, execute_fn, _make_evaluate_fn())

    out = await graph.ainvoke(_initial_state())

    # The self-edge fired twice and exited on the third visit.
    assert len(out["attempts"]) == 3, out["attempts"]
    assert calls["n"] == 3, "one execute per node visit — re-entry == attempt"
    assert out["verdict"] == "succeeded"
    assert out["status"] == "succeeded"

    # Last attempt succeeded; the prior two failed and rotated strategies.
    assert out["attempts"][-1].success is True
    assert [a.success for a in out["attempts"]] == [False, False, True]
    strategies = [a.strategy for a in out["attempts"]]
    assert len(set(strategies)) == 3, f"rotation must not repeat: {strategies}"

    # Every attempt accumulated a ToolResult under the append reducer.
    assert len(out["tool_results"]) == 3
    assert out["tool_results"][-1].success is True


def test_route_predicate_is_a_thin_read_of_the_verdict() -> None:
    """``_route`` reads the engine-decided verdict verbatim — the edge owns
    nothing but the loop-or-exit branch."""
    assert _route({"verdict": "retry"}) == "retry"
    assert _route({"verdict": "succeeded"}) == "succeeded"
    assert _route({"verdict": "exhausted"}) == "exhausted"
    # Defensive default: a missing verdict exits rather than spins forever.
    assert _route({}) == "exhausted"


def test_self_edge_is_one_node_not_an_unrolled_chain() -> None:
    """Topology proof: a single ``retry_attempt`` node whose ``"retry"`` branch
    loops back onto itself; ``"succeeded"`` / ``"exhausted"`` reach ``END``.

    Rotation lives in the engine, not in N unrolled retry-k nodes.
    """
    engine = RetryEngine()
    execute_fn, _ = _make_execute_fn(succeed_on_attempt=1)
    builder = build_retry_subgraph(engine, execute_fn, _make_evaluate_fn())

    # Exactly one retry node (besides START/END internals).
    assert "retry_attempt" in builder.nodes

    ends = builder.branches["retry_attempt"]["_route"].ends
    assert ends == {
        "retry": "retry_attempt",  # the self-edge
        "succeeded": END,
        "exhausted": END,
    }

    compiled = compile_retry_subgraph(engine, execute_fn, _make_evaluate_fn())
    edges = [(e.source, e.target) for e in compiled.get_graph().edges]
    # The self-edge is present in the compiled topology.
    assert ("retry_attempt", "retry_attempt") in edges


# ---------------------------------------------------------------------------
# 2. Exhaustion path — the engine's give-up is respected, no infinite loop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exhaustion_exits_at_max_attempts_no_infinite_loop() -> None:
    """Always-fail → the engine's ``should_escalate`` flips the verdict to
    ``"exhausted"`` at ``max_attempts`` (12) and the self-edge routes to END.

    The whole point of keeping rotation as data: the edge respects the engine's
    give-up. If the node owned the give-up decision instead, this would spin.
    """
    engine = RetryEngine()
    execute_fn, calls = _make_execute_fn(succeed_on_attempt=None)
    # Generous recursion limit so a *correct* exit (12) is not masked by the
    # LangGraph guard — proving termination comes from the verdict, not the cap.
    graph = compile_retry_subgraph(engine, execute_fn, _make_evaluate_fn())

    out = await graph.ainvoke(_initial_state(), {"recursion_limit": 100})

    assert len(out["attempts"]) == 12, "engine max_attempts is the exit point"
    assert calls["n"] == 12
    assert out["verdict"] == "exhausted"
    assert out["status"] == "exhausted"
    assert all(a.success is False for a in out["attempts"])
    # The engine itself agrees this session is escalation-ready (give-up owned
    # by the engine, read by the edge): 12 attempts hit max_attempts.
    assert engine.should_escalate(
        RetrySession(attempts=out["attempts"])
    ) is True


@pytest.mark.asyncio
async def test_exhaustion_via_hardware_impossibility_short_circuits() -> None:
    """A hardware-impossibility error makes ``should_escalate`` return True
    early — the self-edge exits before exhausting all 12 strategies.

    Proves the give-up verdict tracks the engine's impossibility detection
    (``retry_engine.py:_is_impossibility``), not a hardcoded attempt count in
    the node.
    """
    engine = RetryEngine()
    eval_fn = _make_evaluate_fn()

    async def execute_fn(task: str, strategy_context: dict) -> dict:
        # Empty response → evaluate_fn fails it; the reason carries the
        # impossibility marker that should_escalate scans attempt.error for.
        return {"response": "", "results": [], "error": "CUDA out of memory"}

    def evaluate_fn(result: dict) -> dict:
        if result.get("response"):
            return {"success": True, "confidence": 0.7, "reason": "ok"}
        return {"success": False, "confidence": 0.0, "reason": "CUDA out of memory"}

    graph = compile_retry_subgraph(engine, execute_fn, evaluate_fn)
    out = await graph.ainvoke(_initial_state(), {"recursion_limit": 100})

    assert out["verdict"] == "exhausted"
    # Exited on the FIRST attempt — impossibility, not the 12-attempt cap.
    assert len(out["attempts"]) == 1, out["attempts"]


# ---------------------------------------------------------------------------
# 3. Delegation parity canary — rotation routes through the engine
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rotation_delegates_to_engine_get_strategy_for_attempt(
    monkeypatch,
) -> None:
    """The node calls ``RetryEngine.get_strategy_for_attempt`` once per attempt.

    The rotation-delegation analog of the other nodes' ``_call_count`` canaries:
    if a refactor reimplemented the strategy table inside the node, this counter
    would not advance and the rotation would drift from the 40-test engine
    contract.
    """
    engine = RetryEngine()
    real = engine.get_strategy_for_attempt
    seen: list[int] = []

    def spy(attempt_number, previous_attempts):
        seen.append(attempt_number)
        return real(attempt_number, previous_attempts)

    monkeypatch.setattr(engine, "get_strategy_for_attempt", spy)

    execute_fn, calls = _make_execute_fn(succeed_on_attempt=4)
    graph = compile_retry_subgraph(engine, execute_fn, _make_evaluate_fn())
    out = await graph.ainvoke(_initial_state())

    assert len(out["attempts"]) == 4
    # One delegated rotation call per attempt, numbered 1..4 in order.
    assert seen == [1, 2, 3, 4], seen
    assert calls["n"] == 4


def test_retry_node_factory_returns_a_callable() -> None:
    """``make_retry_node`` mirrors the other node factories — closes over the
    live engine + caller closures and returns a bare async node callable."""
    engine = RetryEngine()
    execute_fn, _ = _make_execute_fn(succeed_on_attempt=1)
    node = make_retry_node(engine, execute_fn, _make_evaluate_fn())
    assert callable(node)


# ---------------------------------------------------------------------------
# 4. Checkpoint round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_attempt_toolresult_round_trips_through_checkpoint(
    tmp_path,
) -> None:
    """An attempt's ``ToolResult`` survives ``AsyncSqliteSaver`` losslessly.

    Mirrors the dispatch sub-graph checkpoint test: Step 1's serde wiring carries
    the ``ToolResult`` through the checkpoint with full dataclass identity. The
    ``Attempt`` carriers in state ride the permissive JsonPlus fallback; the
    assertion here is on the ``ToolResult`` the allowlist guarantees.
    """
    engine = RetryEngine()
    execute_fn, _ = _make_execute_fn(succeed_on_attempt=1)
    db = tmp_path / "retry-checkpoint.sqlite"
    config = {"configurable": {"thread_id": "retry-cp"}}

    async with open_async_sqlite_saver(str(db)) as saver:
        graph = compile_retry_subgraph(
            engine, execute_fn, _make_evaluate_fn(), checkpointer=saver
        )
        out = await graph.ainvoke(_initial_state(), config=config)
        live_tr = out["tool_results"][-1]
        assert isinstance(live_tr, ToolResult)

    async with open_async_sqlite_saver(str(db)) as saver2:
        graph2 = compile_retry_subgraph(
            engine, execute_fn, _make_evaluate_fn(), checkpointer=saver2
        )
        snapshot = await graph2.aget_state(config)

    assert snapshot is not None
    persisted = snapshot.values["tool_results"][-1]
    assert isinstance(persisted, ToolResult), type(persisted)
    assert persisted == live_tr


# ---------------------------------------------------------------------------
# Span parity — the inverse of the other nodes
# ---------------------------------------------------------------------------


def test_retry_node_preserves_the_retry_attempt_span() -> None:
    """Unlike every other span-silent Track B node, the retry node *emits* the
    ``retry_attempt`` span — because the live per-attempt path emits it
    (``retry_engine.py:358-364``) and updates its metadata
    (``retry_engine.py:425-432``). Span parity preserves; it does not strip.
    """
    from modules.shadow.graph import retry_graph as retry_graph_module

    src = inspect.getsource(retry_graph_module)
    assert 'observed_span(' in src
    assert '"retry_attempt"' in src
    assert "retry_span.update(metadata=" in src
