"""Phase B / Track B — Step 3 retry node tests (whole-loop delegation rebuild).

Covers the retry delegating node at :mod:`modules.shadow.graph.retry_graph`,
rebuilt to delegate the **whole** 12-attempt loop to live code via a single
:meth:`RetryEngine.attempt_task` call (``START → retry → END``, no self-edge).
This supersedes the prior self-edge node, which reimplemented the loop from
lower-level primitives and silently dropped five behaviors that live *inside*
``attempt_task``.

Load-bearing invariants, in order of importance:

1. **Whole-loop delegation runs through ``attempt_task``.** A multi-attempt
   scenario drives the engine's real loop: ``attempt_task`` is called exactly
   once per node visit and the returned session carries every attempt — proving
   the node uses the live driver, not a reimplemented one.
2. **The 5 previously-dropped behaviors survive** — the two that matter most:
   - **Deterministic-failure early-exit** (``retry_engine.py:476-489``): a
     deterministic failure escalates at attempt 1 instead of looping to
     exhaustion. This is the exact divergence the old self-edge node had.
   - **``_record_session`` fires** (``retry_engine.py:444`` etc.): the engine
     records the session on exit; the old node never did.
   Plus forwarding of the ``grimoire_search_fn`` preflight and the ``notify_fn``
   progress callback (behaviors 3 and 4).
3. **Delegation parity canary** — ``attempt_task`` is reached exactly once,
   same posture as the other nodes' ``_call_count`` canaries.
4. **Span preserved through delegation** — the live ``retry_attempt`` span fires
   from *inside* ``attempt_task``; the node layer adds no second span.
5. **Checkpoint round-trip** — an attempt's ``ToolResult`` survives
   ``AsyncSqliteSaver`` via ``shadow_serde``.
"""

from __future__ import annotations

import inspect
from contextlib import contextmanager

import pytest
from langgraph.graph import END, START

from modules.base import ToolResult
from modules.shadow.graph import (
    build_retry_subgraph,
    compile_retry_subgraph,
    make_retry_node,
    open_async_sqlite_saver,
)
from modules.shadow.retry_engine import RetryEngine


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
    The counter records how many real attempts the engine drove inside its own
    loop — distinct from node visits (there is exactly one node visit total).
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
# 1. Whole-loop delegation runs through attempt_task
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_whole_loop_delegates_through_attempt_task() -> None:
    """Fail 2× then succeed → the engine's real loop runs three attempts inside a
    single ``attempt_task`` call driven by one node visit.

    This is the load-bearing proof of the rebuild: the node hands the *whole*
    loop to live code. The attempt count (3) is produced by the engine's own
    ``for`` loop, surfaced verbatim on ``retry_result``; the rotation advanced on
    every internal attempt (three distinct strategies).
    """
    engine = RetryEngine()
    execute_fn, calls = _make_execute_fn(succeed_on_attempt=3)
    graph = compile_retry_subgraph(engine, execute_fn, _make_evaluate_fn())

    out = await graph.ainvoke(_initial_state())

    # The engine drove three real attempts inside its own loop.
    assert calls["n"] == 3
    assert out["status"] == "succeeded"
    assert out["retry_result"]["status"] == "succeeded"
    assert len(out["retry_result"]["attempts"]) == 3
    assert out["retry_result"]["attempts"][-1]["success"] is True
    assert [a["success"] for a in out["retry_result"]["attempts"]] == [
        False, False, True,
    ]

    # Rotation (engine-owned, untouched by the node) advanced each attempt.
    strategies = [a["strategy"] for a in out["retry_result"]["attempts"]]
    assert len(set(strategies)) == 3, f"rotation must not repeat: {strategies}"

    # One ToolResult per real attempt, accumulated under the append reducer.
    assert len(out["tool_results"]) == 3
    assert out["tool_results"][-1].success is True


@pytest.mark.asyncio
async def test_exhaustion_runs_full_engine_loop() -> None:
    """Always-fail → the engine runs all 12 attempts inside ``attempt_task`` and
    returns an exhausted session. Termination comes from the engine's own
    ``max_attempts``, not any graph topology (there is no self-edge to cap)."""
    engine = RetryEngine()
    execute_fn, calls = _make_execute_fn(succeed_on_attempt=None)
    graph = compile_retry_subgraph(engine, execute_fn, _make_evaluate_fn())

    out = await graph.ainvoke(_initial_state())

    assert calls["n"] == 12, "engine max_attempts is the exit point"
    assert out["status"] == "exhausted"
    assert out["retry_result"]["exhausted"] is True
    assert out["retry_result"]["ready_to_escalate"] is True
    assert len(out["retry_result"]["attempts"]) == 12
    assert all(a["success"] is False for a in out["retry_result"]["attempts"])
    assert len(out["tool_results"]) == 12


def test_topology_is_one_node_no_self_edge() -> None:
    """Topology proof: a single ``retry`` node on ``START → retry → END`` with no
    self-edge. The 12-attempt loop is data owned by the engine, not unrolled or
    self-looped graph topology."""
    engine = RetryEngine()
    execute_fn, _ = _make_execute_fn(succeed_on_attempt=1)
    builder = build_retry_subgraph(engine, execute_fn, _make_evaluate_fn())

    assert "retry" in builder.nodes
    # No conditional branches at all — the old self-edge is gone.
    assert builder.branches == {}

    compiled = compile_retry_subgraph(engine, execute_fn, _make_evaluate_fn())
    edges = [(e.source, e.target) for e in compiled.get_graph().edges]
    # No node loops back onto itself.
    assert ("retry", "retry") not in edges


# ---------------------------------------------------------------------------
# 2. The 5 previously-dropped behaviors now survive the cutover
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deterministic_failure_escalates_early_not_to_exhaustion() -> None:
    """A deterministic failure escalates at attempt 1 — it does NOT loop to
    exhaustion. This is the behavior the superseded self-edge node dropped: it
    reclassified the failure as ``"retry"`` and spun to 12 attempts.

    The whole-loop delegation runs ``attempt_task``'s deterministic-failure
    early-exit (``retry_engine.py:476-489``) untouched.
    """
    engine = RetryEngine()

    async def execute_fn(task: str, strategy_context: dict) -> dict:
        # Empty response → evaluate_fn fails it with a deterministic marker
        # ("validation error") that classify_failure pins as DETERMINISTIC.
        return {"response": "", "results": []}

    def evaluate_fn(result: dict) -> dict:
        if result.get("response"):
            return {"success": True, "confidence": 0.7, "reason": "ok"}
        return {
            "success": False,
            "confidence": 0.0,
            "reason": "schema validation error: field is required",
        }

    graph = compile_retry_subgraph(engine, execute_fn, evaluate_fn)
    out = await graph.ainvoke(_initial_state())

    # Exited on the FIRST attempt — escalated, not looped to exhaustion.
    assert len(out["retry_result"]["attempts"]) == 1, out["retry_result"]["attempts"]
    assert out["status"] == "deterministic_failure"
    assert out["retry_result"]["deterministic_failure"] is True
    assert out["retry_result"]["ready_to_escalate"] is True


@pytest.mark.asyncio
async def test_record_session_fires_through_delegation() -> None:
    """``attempt_task`` records the session in ``RetryEngine._session_history`` on
    exit (``retry_engine.py:444`` / ``:521``). The superseded node never recorded
    a session — breaking the retry session trail. Whole-call delegation restores
    it."""
    engine = RetryEngine()
    assert engine._session_history == []

    execute_fn, _ = _make_execute_fn(succeed_on_attempt=2)
    graph = compile_retry_subgraph(engine, execute_fn, _make_evaluate_fn())
    await graph.ainvoke(_initial_state())

    assert len(engine._session_history) == 1, "session must be recorded on exit"
    assert engine._session_history[-1]["status"] == "succeeded"


@pytest.mark.asyncio
async def test_grimoire_preflight_and_notify_are_forwarded() -> None:
    """The node forwards ``grimoire_search_fn`` (preflight lesson-loading,
    ``retry_engine.py:329-350``) and ``notify_fn`` (progress notifications,
    ``:502-503``) — behaviors 3 and 4 the self-edge node had no parameters for.

    Drive an exhaustion run: the preflight fires once before the loop and the
    progress callback fires at attempts 4 / 8 / 12.
    """
    engine = RetryEngine()
    preflight_queries: list[str] = []
    notifications: list[str] = []

    def grimoire_search_fn(query: str) -> list[dict]:
        preflight_queries.append(query)
        return [{"content": "prior lesson: check inputs first"}]

    async def notify_fn(msg: str) -> None:
        notifications.append(msg)

    execute_fn, _ = _make_execute_fn(succeed_on_attempt=None)
    graph = compile_retry_subgraph(
        engine,
        execute_fn,
        _make_evaluate_fn(),
        grimoire_search_fn=grimoire_search_fn,
        notify_fn=notify_fn,
    )
    await graph.ainvoke(_initial_state())

    # Preflight ran once before the loop, querying for failure patterns.
    assert len(preflight_queries) == 1
    assert "failure_pattern" in preflight_queries[0]
    # Progress notifications fired at 4 / 8 / 12.
    assert len(notifications) == 3


# ---------------------------------------------------------------------------
# 3. Delegation parity canary — exactly one attempt_task call per node visit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_node_calls_attempt_task_exactly_once(monkeypatch) -> None:
    """The node delegates the whole loop with ONE ``attempt_task`` call per visit.

    The whole-loop analog of the other nodes' ``_call_count`` canaries: if a
    refactor reverted to driving the loop from lower-level primitives, this
    counter would not read 1 (it would be 0, with N primitive calls instead).
    """
    engine = RetryEngine()
    real = engine.attempt_task
    calls = {"n": 0}

    async def spy(*args, **kwargs):
        calls["n"] += 1
        return await real(*args, **kwargs)

    monkeypatch.setattr(engine, "attempt_task", spy)

    execute_fn, _ = _make_execute_fn(succeed_on_attempt=4)
    graph = compile_retry_subgraph(engine, execute_fn, _make_evaluate_fn())
    out = await graph.ainvoke(_initial_state())

    assert calls["n"] == 1, "one whole-loop delegation per node visit"
    assert len(out["retry_result"]["attempts"]) == 4


def test_retry_node_factory_returns_a_callable() -> None:
    """``make_retry_node`` mirrors the other node factories — closes over the live
    engine + caller closures and returns a bare async node callable."""
    engine = RetryEngine()
    execute_fn, _ = _make_execute_fn(succeed_on_attempt=1)
    node = make_retry_node(engine, execute_fn, _make_evaluate_fn())
    assert callable(node)


# ---------------------------------------------------------------------------
# 4. Span preserved through delegation; node adds no second span
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_attempt_span_fires_through_delegation(monkeypatch) -> None:
    """The live ``retry_attempt`` span fires from *inside* the delegated
    ``attempt_task`` call (``retry_engine.py:358``), once per real attempt —
    whole-call delegation preserves it automatically."""
    spans: list[str] = []

    @contextmanager
    def span_spy(name, **metadata):
        spans.append(name)
        yield None

    monkeypatch.setattr("modules.shadow.retry_engine.observed_span", span_spy)

    engine = RetryEngine()
    execute_fn, _ = _make_execute_fn(succeed_on_attempt=3)
    graph = compile_retry_subgraph(engine, execute_fn, _make_evaluate_fn())
    await graph.ainvoke(_initial_state())

    # One retry_attempt span per real attempt, emitted by the delegated engine.
    assert spans.count("retry_attempt") == 3


def test_node_layer_is_span_silent() -> None:
    """The node layer opens no span of its own — re-emitting ``retry_attempt``
    here would double the span the engine already emits. Source inspection: no
    ``observed_span`` call in the node module."""
    from modules.shadow.graph import retry_graph as retry_graph_module

    src = inspect.getsource(retry_graph_module)
    assert "observed_span(" not in src


# ---------------------------------------------------------------------------
# 5. Checkpoint round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_attempt_toolresult_round_trips_through_checkpoint(
    tmp_path,
) -> None:
    """An attempt's ``ToolResult`` survives ``AsyncSqliteSaver`` losslessly.

    Mirrors the dispatch sub-graph checkpoint test: Step 1's serde wiring carries
    the ``ToolResult`` through the checkpoint with full dataclass identity.
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
