"""Routable-module reachability gate for the Track B cutover (Morpheus dormancy).

Makes module **dormancy** explicit in the graph topology. A dormant module —
currently Morpheus (``config.morpheus.enabled is False``) — must not be reachable
as a dispatch target. This fragment lifts the live ``is_routable()`` filter onto a
conditional edge so that ``registry.is_routable(target) is False`` makes the
dispatch node *unreachable by graph topology*, not merely skipped at runtime —
the same structural posture as :mod:`modules.shadow.graph.dispatch_graph` (whose
gate keys on ``plan.cerberus_approved``; this one keys on ``is_routable`` instead).

The gate is **general, not Morpheus-special**. It reads
``registry.is_routable(state["classification"].target_module)`` for whatever
module the route names; Morpheus is just the current occupant of "dormant." A
future dormant module is covered with no code change here.

Where the live enforcement lives (mirror, don't reimplement)
============================================================

Dormancy is enforced **upstream, in the router**, not at dispatch. Every routing
surface in ``Orchestrator._step2_classify`` filters through ``is_routable()`` so a
dormant module never even appears as a route:

- the LLM-router module list (``orchestrator.py:1944-1947``);
- the Morpheus-phrase early guard (``orchestrator.py:2798``);
- the bare-module-word matcher (``orchestrator.py:2631-2634``);
- the explicit-phrase matcher (``orchestrator.py:2656``);
- the Priority-7 Morpheus fast-path (``orchestrator.py:2879``).

``is_routable`` itself is ``ModuleRegistry.is_routable`` (``modules/base.py:467``):
``True`` iff the module is registered, ``ONLINE``, and not config-disabled
(``bool(settings.enabled)`` when the settings class has an ``enabled`` attr).
Morpheus's dormancy flag is ``MorpheusSettings.enabled = False``
(``modules/morpheus/config.py:16``); when False, ``main.py`` does not instantiate
Morpheus, so it is absent from the registry and ``is_routable("morpheus")`` is
``False``.

Because the router already refuses to *produce* a route to a dormant module, this
dispatch-side gate is **defense-in-depth**, not the primary guard — precisely the
role the dispatcher's plan-gate plays over the live ``:4923`` early return. It does
not invent a new dormancy rule; it reads the same live ``is_routable()`` predicate
and asserts the structural consequence the topology must preserve.

Topology
========

::

    START
     └─(gate: registry.is_routable(state["classification"].target_module))
         ├─ "dormant"  ─► dormant_node  ─► END   # appends a not-routable ToolResult
         └─ "dispatch" ─► dispatch_node ─► END   # delegates to live _step5_execute

The conditional edge out of ``START`` is the load-bearing assertion: a
non-routable target routes to a terminal node that never touches a module, and
``dispatch_node`` is reachable only via the ``"dispatch"`` branch.
``tests.test_morpheus_gate`` proves this by graph introspection
(``compiled.get_graph()``), not by a behavioral "it didn't run" observation.

Delegation
==========

On the routable branch ``dispatch_node`` delegates the whole per-step loop to
``orchestrator._step5_execute(...)`` — identical to
:func:`modules.shadow.graph.dispatch_graph.build_dispatch_subgraph`'s dispatch
node — so the three-verdict hook, the Cerberus heartbeat seam, the async-queue
branch, and the exception envelope are preserved byte-for-byte rather than
reimplemented.

The ``dormant_node`` has **no live byte-for-byte counterpart**: in production the
router never emits a route to a dormant module, so the live dispatch loop never
sees one. The node therefore synthesizes a denial ``ToolResult`` describing the
non-routable target — a defense-in-depth terminal that documents the structural
invariant rather than copying a live envelope.

State / reducer
===============

Operates over :class:`modules.shadow.graph.skeleton.ShadowState` directly — no new
state class. It reads ``classification`` / ``plan`` / ``source`` (populated by the
router and planner migrations) and writes onto the ``Annotated[list[ToolResult],
add]`` ``tool_results`` key, the same append reducer every other Track B node uses.

Observability
=============

Zero ``observed_span`` calls — matches the span-silent live classifier and the
span-silent ``dispatch_graph`` loop. Any span that eventually wraps routing/
dispatch nests over this fragment from outside, exactly as it does over the live
call.
"""

from __future__ import annotations

from typing import Callable, Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from modules.base import ModuleRegistry, ToolResult
from modules.shadow.graph.skeleton import ShadowState
from modules.shadow.orchestrator import Orchestrator


def _target_module(state: ShadowState) -> str | None:
    """The module the route names, or ``None`` when no classification is present.

    Reads ``state["classification"].target_module`` defensively so a missing or
    malformed classification degrades to the safe ``"dormant"`` branch rather
    than raising inside the conditional edge.
    """
    classification = state.get("classification")
    return getattr(classification, "target_module", None)


def make_routable_gate(
    registry: ModuleRegistry,
) -> Callable[[ShadowState], Literal["dormant", "dispatch"]]:
    """Build the conditional-edge predicate, closed over the live ``registry``.

    The returned predicate reads the **live** ``registry.is_routable(target)`` for
    whatever module the classification names — it does not reimplement or cache the
    dormancy rule, so a config change to ``enabled`` (or a module going offline) is
    reflected immediately. Returns ``"dispatch"`` only when the target is named and
    routable; ``"dormant"`` for a missing target or any non-routable one. This is
    the predicate that makes a dormant module structurally unreachable past the
    gate, mirroring ``dispatch_graph._gate`` but keyed on ``is_routable`` instead of
    ``cerberus_approved``.
    """

    def gate(state: ShadowState) -> Literal["dormant", "dispatch"]:
        target = _target_module(state)
        if target is not None and registry.is_routable(target):
            return "dispatch"
        return "dormant"

    return gate


def build_routable_gate_subgraph(orchestrator: Orchestrator) -> StateGraph:
    """Construct the routable-module reachability sub-graph builder (not compiled).

    Closes over ``orchestrator`` so the gate consults that instance's live
    ``registry.is_routable`` and the dispatch branch delegates against the same
    instance's :meth:`~modules.shadow.orchestrator.Orchestrator._step5_execute`
    (preserving its registry, Cerberus hooks, async queue, and heartbeat seam).

    Args:
        orchestrator: The live orchestrator whose ``registry`` supplies the
            ``is_routable`` predicate and whose ``_step5_execute`` the dispatch
            node delegates to.
    """

    gate = make_routable_gate(orchestrator.registry)

    async def dormant_node(state: ShadowState) -> ShadowState:
        # Defense-in-depth terminal: the live router never emits a route to a
        # dormant module, so there is no live envelope to copy. Synthesize a
        # denial that names the non-routable target. Never touches a module.
        target = _target_module(state)
        return {
            "tool_results": [
                ToolResult(
                    success=False,
                    content=None,
                    tool_name="route",
                    module="orchestrator",
                    error=f"Module {target!r} is not routable (dormant or disabled)",
                )
            ]
        }

    async def dispatch_node(state: ShadowState) -> ShadowState:
        # Routable target: delegate the entire per-step loop to live code, exactly
        # as dispatch_graph.dispatch_node does — three-verdict hook, heartbeat seam,
        # async-queue branch, post-hook, and exception envelope all preserved.
        results = await orchestrator._step5_execute(
            state["plan"],
            state["classification"],
            state.get("source", "user"),
        )
        return {"tool_results": results}

    builder = StateGraph(ShadowState)
    builder.add_node("dormant", dormant_node)
    builder.add_node("dispatch", dispatch_node)
    builder.add_conditional_edges(
        START,
        gate,
        {"dormant": "dormant", "dispatch": "dispatch"},
    )
    builder.add_edge("dormant", END)
    builder.add_edge("dispatch", END)
    return builder


def compile_routable_gate_subgraph(
    orchestrator: Orchestrator,
    checkpointer: BaseCheckpointSaver | None = None,
):
    """Compile the routable-module reachability sub-graph with an optional saver.

    Pass a saver from
    :func:`modules.shadow.graph.serde.open_async_sqlite_saver` for one already
    wired with the ``ToolResult``-aware msgpack allowlist.
    """
    builder = build_routable_gate_subgraph(orchestrator)
    if checkpointer is None:
        return builder.compile()
    return builder.compile(checkpointer=checkpointer)
