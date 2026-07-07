"""Phase B / Track B — Router delegating node tests.

Covers the single delegating node at :mod:`modules.shadow.graph.router_node`.
The router lands as a *node*, not a sub-graph (the route decision writes
``classification`` / ``last_route`` directly onto ``ShadowState`` with no
internal fan-out to wrap), so most of these call the node coroutine directly.
Two tests build a real-checkpointer parent graph to prove the load-bearing
``last_route`` bridge.

Invariants pinned here:

- Delegation preserves the route decision byte-for-byte — fast-path omen route,
  the Session-47 informational-guard override, the LLM router tier, and the
  keyword fallback tier all reach state through ``_step2_classify``, never a
  reimplementation.
- Return shape — the node writes ``{"classification": ..., "last_route": ...}``
  onto ``ShadowState`` (both the request-scoped classification and the
  checkpointed route).
- **The ``last_route`` bridge (the silent-failure seam).** Cross-invocation
  route memory must flow through the checkpointed ``state["last_route"]``, not a
  leftover instance attribute. The bridge test resumes a *fresh* orchestrator
  from the same checkpoint DB + ``thread_id`` and asserts the contextual
  re-route ("do that" → previous module at confidence 0.90) still fires. The
  negative control proves that without a checkpointed route the contextual
  branch does NOT fire — so the bridge test is exercising the bridge, not a
  coincidental keyword match.
- Span parity — the node adds no ``observed_span``; the live route path has
  none inside the classifier.

The two fast-path inputs used below were verified against the live classifier:
``"write a python function to sort a list"`` → omen/creation/0.85;
``"do that"`` with a hydrated ``_last_route`` → omen/creation/0.90;
``"do that"`` with no route → ``None`` (falls through to the LLM tier);
``"explain this function"`` → omen/analysis/0.85 (Session-47 override).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from langgraph.graph import END, START, StateGraph

from modules.shadow.graph import (
    ShadowState,
    make_router_node,
    open_async_sqlite_saver,
)
from modules.shadow.orchestrator import (
    BrainType,
    Orchestrator,
    TaskClassification,
    TaskType,
)
from tests.test_orchestrator import TEST_CONFIG


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_orch(tmp_path: Path, tag: str = "state") -> Orchestrator:
    """Construct a lightweight Orchestrator (no registry / Ollama boot).

    Mirrors the direct ``Orchestrator(config)`` construction the fallback-
    classifier unit tests use — cheap, no module registration. The state file
    is rerouted into ``tmp_path`` so nothing touches real state.
    """
    cfg = dict(TEST_CONFIG)
    cfg["system"] = {"state_file": str(tmp_path / f"{tag}.json")}
    return Orchestrator(cfg)


def _build_router_graph(orchestrator: Orchestrator, checkpointer=None):
    """Compile a ``START → router → END`` parent graph over ``ShadowState``."""
    builder: StateGraph = StateGraph(ShadowState)
    builder.add_node("router", make_router_node(orchestrator))
    builder.add_edge(START, "router")
    builder.add_edge("router", END)
    if checkpointer is None:
        return builder.compile()
    return builder.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# Delegation + return shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_router_node_fast_path_writes_classification_and_last_route(
    tmp_path: Path,
) -> None:
    """A fast-path input round-trips an omen classification through the node.

    The node writes both ``classification`` (request-scoped) and ``last_route``
    (checkpointed). No LLM is touched — the fast-path stem matcher resolves the
    route. Proves the node delegates to ``_step2_classify`` (which calls
    ``_fast_path_classify``) rather than reimplementing routing.
    """
    orch = _make_orch(tmp_path)
    node = make_router_node(orch)

    out = await node({"user_input": "write a python function to sort a list"})

    cls = out["classification"]
    assert isinstance(cls, TaskClassification)
    assert cls.target_module == "omen"
    assert cls.task_type == TaskType.CREATION
    assert cls.confidence == pytest.approx(0.85)
    # last_route mirrors the classification so the checkpoint carries it.
    assert out["last_route"] is cls


@pytest.mark.asyncio
async def test_router_node_preserves_session_47_override(tmp_path: Path) -> None:
    """The Session-47 informational-guard override survives delegation.

    "explain this function" hits an informational prefix ("explain") that would
    otherwise read as a knowledge question, but the override at
    ``orchestrator.py:2736-2741`` flips it to an Omen ANALYSIS route because
    analysis intent + a code-context token are present. The node must not
    reimplement classification, so this can only pass if it delegates to
    ``_fast_path_classify``.
    """
    orch = _make_orch(tmp_path)
    node = make_router_node(orch)

    out = await node({"user_input": "explain this function"})

    cls = out["classification"]
    assert cls.target_module == "omen"
    assert cls.task_type == TaskType.ANALYSIS
    assert cls.confidence == pytest.approx(0.85)


@pytest.mark.asyncio
async def test_router_node_delegates_to_llm_router_tier(tmp_path: Path) -> None:
    """When the fast path declines, the node reaches the LLM router tier.

    Force ``_fast_path_classify`` to return ``None`` (so the fast path
    declines) and stub ``_ollama_chat`` to return a router JSON verdict. The
    node must surface the LLM-tier classification at ``confidence=0.70`` —
    proving the node delegates through the whole ``_step2_classify`` tier
    ladder, not just the fast path.
    """
    orch = _make_orch(tmp_path)
    orch._fast_path_classify = lambda _u, _lr=None: None  # type: ignore[method-assign]
    orch._ollama_chat = lambda **_kw: (  # type: ignore[method-assign]
        '{"task_type": "research", "complexity": "moderate", '
        '"target_module": "reaper", "brain": "fast_brain", '
        '"safety_flag": false, "priority": 1}'
    )
    node = make_router_node(orch)

    out = await node({"user_input": "what is the latest on RTX 5090 restocks"})

    cls = out["classification"]
    assert cls.target_module == "reaper"
    assert cls.task_type == TaskType.RESEARCH
    assert cls.confidence == pytest.approx(0.70)


@pytest.mark.asyncio
async def test_router_node_delegates_to_keyword_fallback_tier(
    tmp_path: Path,
) -> None:
    """When the LLM router errors, the node reaches the keyword fallback tier.

    Force the fast path to decline and ``_ollama_chat`` to raise. The node must
    surface the keyword-fallback classification at ``confidence=0.50`` — here
    the generic input has no fallback keyword, so it defaults to ``direct``.
    """
    orch = _make_orch(tmp_path)
    orch._fast_path_classify = lambda _u, _lr=None: None  # type: ignore[method-assign]

    def _raise(**_kw):
        raise RuntimeError("router LLM unavailable")

    orch._ollama_chat = _raise  # type: ignore[method-assign]
    node = make_router_node(orch)

    out = await node({"user_input": "mauve sklorptang frobnicate"})

    cls = out["classification"]
    assert cls.target_module == "direct"
    assert cls.task_type == TaskType.CONVERSATION
    assert cls.confidence == pytest.approx(0.50)


# ---------------------------------------------------------------------------
# The last_route bridge (load-bearing) — cross-invocation memory
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_last_route_bridges_across_invocations_via_checkpoint(
    tmp_path: Path,
) -> None:
    """Route memory survives across invocations THROUGH the checkpoint.

    The acceptance proof for the single highest-risk seam in the router
    migration. Invocation 1 routes "write a python function …" to omen and the
    checkpoint persists ``last_route``. Invocation 2 resumes on the **same
    thread_id with a FRESH orchestrator** (``_last_route is None``) and sends a
    contextual reference ("do that"); the node must hydrate ``_last_route`` from
    the checkpointed ``state["last_route"]`` so the contextual re-route fires
    and lands back on omen at confidence 0.90.

    The fresh second orchestrator is what makes this a bridge test and not an
    instance-state test: the only place "omen" can come from on invocation 2 is
    the checkpoint.
    """
    db = tmp_path / "router-xinvoke.sqlite"
    config = {"configurable": {"thread_id": "conv-1"}}

    # --- Invocation 1: fresh orch, establishes the route ---
    orch1 = _make_orch(tmp_path, tag="orch1")
    async with open_async_sqlite_saver(str(db)) as saver1:
        graph1 = _build_router_graph(orch1, checkpointer=saver1)
        out1 = await graph1.ainvoke(
            {"user_input": "write a python function to sort a list"},
            config=config,
        )
    assert out1["classification"].target_module == "omen"
    assert out1["last_route"].target_module == "omen"

    # --- Invocation 2: FRESH orch (no instance memory), same thread_id ---
    orch2 = _make_orch(tmp_path, tag="orch2")
    assert orch2._last_route is None, "fresh orchestrator must start with no route"

    async with open_async_sqlite_saver(str(db)) as saver2:
        graph2 = _build_router_graph(orch2, checkpointer=saver2)
        out2 = await graph2.ainvoke({"user_input": "do that"}, config=config)

    cls2 = out2["classification"]
    assert cls2.target_module == "omen", (
        "contextual re-route did not fire — last_route did not bridge from the "
        "checkpoint into the fresh orchestrator (the silent-failure seam)."
    )
    assert cls2.confidence == pytest.approx(0.90), (
        "expected the contextual-reference confidence (0.90); a different value "
        "means the route came from a tier other than the contextual branch."
    )


@pytest.mark.asyncio
async def test_no_contextual_reroute_without_checkpointed_route(
    tmp_path: Path,
) -> None:
    """Negative control: no prior route → the contextual branch does NOT fire.

    Same "do that" input as the bridge test, but on a fresh thread with no
    checkpoint history. With ``state["last_route"]`` absent, the node hydrates
    ``_last_route = None``, the contextual branch is skipped, the fast path
    declines, and (with the LLM stubbed to error) the keyword fallback resolves
    to ``direct`` at 0.50 — NOT the contextual omen@0.90. This proves the bridge
    test above is actually exercising the checkpoint, not a coincidental match.
    """
    orch = _make_orch(tmp_path, tag="neg")

    def _raise(**_kw):
        raise RuntimeError("router LLM unavailable")

    orch._ollama_chat = _raise  # type: ignore[method-assign]
    node = make_router_node(orch)

    out = await node({"user_input": "do that", "last_route": None})

    cls = out["classification"]
    assert cls.confidence == pytest.approx(0.50)
    assert cls.target_module == "direct"
    assert cls.confidence != pytest.approx(0.90)


@pytest.mark.asyncio
async def test_router_node_routes_last_route_through_state_not_shared_attr(
    tmp_path: Path,
) -> None:
    """Route memory flows through ``state["last_route"]``, never the shared attr.

    Item-9 leak closed: the node passes ``state["last_route"]`` to the classifier
    as the ``last_route`` parameter (so the contextual re-route at
    ``orchestrator.py:2173`` fires off it), persists the new route back into
    ``state``, and **neither reads nor mutates** ``orchestrator._last_route``.
    Hand the node a state carrying ``last_route``; assert the contextual re-route
    fires AND the shared instance attribute stays ``None`` throughout.
    """
    orch = _make_orch(tmp_path)
    assert orch._last_route is None
    seeded = TaskClassification(
        task_type=TaskType.CREATION,
        complexity="moderate",
        target_module="omen",
        brain=BrainType.FAST,
        safety_flag=False,
        priority=1,
        confidence=0.85,
    )
    node = make_router_node(orch)

    out = await node({"user_input": "do that", "last_route": seeded})

    # The contextual branch fired off the per-thread state route → omen clone at 0.90.
    assert out["classification"].target_module == "omen"
    assert out["classification"].confidence == pytest.approx(0.90)
    # The new route is persisted to state for the next turn on this thread_id...
    assert out["last_route"] is out["classification"]
    # ...but the shared instance attribute is NEVER touched — the leak is closed.
    assert orch._last_route is None


@pytest.mark.asyncio
async def test_router_node_no_cross_thread_last_route_bleed(tmp_path: Path) -> None:
    """Item 9 / clause 4: two interleaved invocations on distinct thread_ids,
    each carrying its OWN ``state["last_route"]``, must not bleed across each
    other. Run concurrently via ``asyncio.gather``; each contextual re-route
    must resolve to its own seeded module, and the shared
    ``orchestrator._last_route`` must stay ``None`` (never mutated by the node).
    """
    orch = _make_orch(tmp_path)
    assert orch._last_route is None

    route_a = TaskClassification(
        task_type=TaskType.CREATION, complexity="moderate", target_module="omen",
        brain=BrainType.FAST, safety_flag=False, priority=1, confidence=0.85,
    )
    route_b = TaskClassification(
        task_type=TaskType.RESEARCH, complexity="moderate", target_module="reaper",
        brain=BrainType.FAST, safety_flag=False, priority=1, confidence=0.85,
    )
    node = make_router_node(orch)

    # "do that" + each thread's own last_route → real _fast_path_classify reads
    # the param (orchestrator.py contextual branch), returns a 0.90 clone.
    out_a, out_b = await asyncio.gather(
        node({"user_input": "do that", "last_route": route_a}),
        node({"user_input": "do that", "last_route": route_b}),
    )

    assert out_a["classification"].target_module == "omen"
    assert out_a["classification"].confidence == pytest.approx(0.90)
    assert out_b["classification"].target_module == "reaper"
    assert out_b["classification"].confidence == pytest.approx(0.90)
    # No bleed and no shared-attribute mutation — route memory lived only in state.
    assert out_a["last_route"] is out_a["classification"]
    assert out_b["last_route"] is out_b["classification"]
    assert orch._last_route is None


# ---------------------------------------------------------------------------
# Span parity
# ---------------------------------------------------------------------------


def test_router_node_module_is_span_silent() -> None:
    """The node adds no ``observed_span`` — matches the live classifier path.

    The only span over routing in the live path is the parent
    ``shadow.router_decision`` at ``orchestrator.py:1193``; the node must not
    introduce instrumentation the live path lacks.
    """
    import inspect

    from modules.shadow.graph import router_node as router_node_module

    src = inspect.getsource(router_node_module)
    # The docstring mentions observed_span by name; assert no *call* exists.
    assert "observed_span(" not in src
