"""Parent graph assembler for the Track B cutover (parent-graph wiring step).

Wires the inert Track B nodes/sub-graphs into ONE compiled ``StateGraph`` that
reproduces the safety-critical spine of the live decision loop:

::

    START → router → routable_gate ─dormant──► dormant_node ─► END
                          │dispatch
                          ▼
                        plan ─plan_gate ─blocked──► blocked_node ─► END
                          │              │dispatch
                          │              ▼
                          └────────────► dispatch ─► END

This module is the **single composition point** (the one place that imports
across sibling node modules); the assembler reimplements **no** node. Each piece
delegates to live orchestrator code:

- ``router``       → :func:`make_router_node`        → ``Orchestrator._step2_classify``
- ``routable_gate``→ :func:`make_routable_gate`      → live ``registry.is_routable``
- ``plan``         → :func:`make_plan_node`          → ``Orchestrator._step4_plan``
- ``plan_gate``    → :data:`plan_gate`               → ``plan.cerberus_approved`` (orchestrator.py:4923)
- ``dispatch``     → :func:`make_dispatch_node`      → ``Orchestrator._step5_execute``
- ``dormant_node`` / ``blocked_node`` — shared terminal denial nodes.

Two load-bearing safety properties, each a *structural* (topology) guarantee, not
a runtime check:

1. **Cerberus denial unreachable.** With ``plan.cerberus_approved is False`` the
   ``plan_gate`` conditional routes to the terminal ``blocked`` node; ``dispatch``
   is reachable only via the approved branch. Mirrors the live early-return at
   ``orchestrator.py:4923``.
2. **Dormant target unreachable.** With ``registry.is_routable(target) is False``
   the ``routable_gate`` conditional routes to the terminal ``dormant`` node;
   neither ``plan`` nor ``dispatch`` is reachable. Defense-in-depth over the
   router's upstream ``is_routable`` filter.

``tests.test_parent_graph`` proves both by graph introspection
(``compiled.get_graph()``), exactly as the per-fragment tests do.

Scope (this dispatch is wiring + assertion, NOT the flip)
=========================================================

The approved-branch leg here is the bare ``dispatch`` node (delegates
``_step5_execute``). The **retry** wrap and the **response** (Step-6) leg are NOT
wired: both need the per-request closures / Step-3 context the orchestrator builds
*inside* ``_step5_with_retry`` (``orchestrator.py:4515-4709``), which are not
exposed without touching ``orchestrator.py`` — explicitly a flip-step concern
(retry_graph.py:54: "the orchestrator at cutover builds them"). Wiring them now
would mean either a reimplemented driver or an orchestrator edit; both are out of
scope. Tracked in ``cutover-backlog.md``.

Nothing here is imported by the live orchestrator path: building this graph does
NOT flip the cutover. ``Orchestrator.process_input`` stays authoritative, and the
pre-flip import-isolation grep
(``grep -rn 'modules.shadow.graph' modules/ main.py | grep -v 'modules/shadow/graph/'``)
stays empty because this module lives inside the ``graph/`` package.

Observability
=============

Span-silent: this assembler emits no ``observed_span``, and every node it wires is
span-silent. The caller-level spans (``shadow.router_decision`` /
``module_dispatch`` / ``response_assembly``, ``orchestrator.py:1193`` / ``:1369`` /
``:1428``) belong to the future live caller and fire nothing while
``process_input`` is unwired — no caller enters this graph yet.
"""

from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from modules.shadow.graph.dispatch_graph import (
    blocked_node,
    make_dispatch_node,
    plan_gate,
)
from modules.shadow.graph.morpheus_gate import dormant_node, make_routable_gate
from modules.shadow.graph.plan_node import make_plan_node
from modules.shadow.graph.router_node import make_router_node
from modules.shadow.graph.skeleton import ShadowState
from modules.shadow.orchestrator import Orchestrator


def build_parent_graph(orchestrator: Orchestrator) -> StateGraph:
    """Construct the parent graph builder (not compiled).

    Closes over the live ``orchestrator`` so every node delegates against the
    same instance — its registry (router ``is_routable`` + Cerberus hooks + the
    heartbeat seam), classifier, planner, and dispatch loop. Caller compiles with
    whatever checkpointer / interrupt configuration the use case needs.

    Args:
        orchestrator: The live :class:`~modules.shadow.orchestrator.Orchestrator`
            the assembled nodes delegate to.
    """
    builder = StateGraph(ShadowState)

    builder.add_node("router", make_router_node(orchestrator))
    builder.add_node("plan", make_plan_node(orchestrator))
    builder.add_node("dormant", dormant_node)
    builder.add_node("blocked", blocked_node)
    builder.add_node("dispatch", make_dispatch_node(orchestrator))

    builder.add_edge(START, "router")

    # Dormancy gate (defense-in-depth): a non-routable target terminates at
    # ``dormant`` and never reaches the planner or a module. Routable → plan.
    builder.add_conditional_edges(
        "router",
        make_routable_gate(orchestrator.registry),
        {"dormant": "dormant", "dispatch": "plan"},
    )
    builder.add_edge("dormant", END)

    # Cerberus plan-gate: a denied plan terminates at ``blocked`` and never
    # reaches a module. Approved → dispatch.
    builder.add_conditional_edges(
        "plan",
        plan_gate,
        {"blocked": "blocked", "dispatch": "dispatch"},
    )
    builder.add_edge("blocked", END)
    builder.add_edge("dispatch", END)

    return builder


def compile_parent_graph(
    orchestrator: Orchestrator,
    checkpointer: BaseCheckpointSaver | None = None,
):
    """Compile the parent graph with an optional async checkpointer.

    Pass a saver from
    :func:`modules.shadow.graph.serde.open_async_sqlite_saver` to get one already
    wired with the ``ToolResult``-aware msgpack allowlist.
    """
    builder = build_parent_graph(orchestrator)
    if checkpointer is None:
        return builder.compile()
    return builder.compile(checkpointer=checkpointer)
