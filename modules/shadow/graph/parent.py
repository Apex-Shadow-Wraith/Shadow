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
                          └────────────► retry ─► END

This module is the **single composition point** (the one place that imports
across sibling node modules); the assembler reimplements **no** node. Each piece
delegates to live orchestrator code:

- ``router``       → :func:`make_router_node`        → ``Orchestrator._step2_classify``
- ``routable_gate``→ :func:`make_routable_gate`      → live ``registry.is_routable``
- ``plan``         → :func:`make_plan_node`          → ``Orchestrator._step4_plan``
- ``plan_gate``    → :data:`plan_gate`               → ``plan.cerberus_approved`` (orchestrator.py:4923)
- ``retry``        → :func:`make_orchestrator_retry_node` → ``Orchestrator._build_retry_closures`` + ``RetryEngine.attempt_task`` (whole-loop delegation; its ``execute_fn`` wraps ``_step5_execute``, so retry supersedes the bare single-attempt dispatch on the approved branch)
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

Scope (FLIP: the approved branch now wraps retry; response is caller-side)
==========================================================================

The approved-branch leg is now the **retry** node
(:func:`make_orchestrator_retry_node`), which builds the four closures from graph
state via ``Orchestrator._build_retry_closures`` and delegates the whole
``attempt_task`` loop — superseding the former bare single-attempt ``dispatch``
node (whose ``_step5_execute`` is re-entered *inside* the retry ``execute_fn``).
The **response / Step-6 leg** (retry-outcome resolution + confidence scoring +
self-review) runs **caller-side** in ``process_input``'s ``response_assembly``
segment, reading ``state["retry_result"]`` and calling
``Orchestrator._resolve_retry_outcome`` — so there is no ``response`` graph node
(the lowest-risk reading of cutover-backlog item 12; keeps the
``response_assembly`` span wrapping Steps 6.5/6.7 in one place).

At flip, ``Orchestrator.process_input`` drives this compiled graph via segmented
invoke. The pre-flip import-isolation grep is intentionally superseded by the
item-11 invariant: the live path imports the compiled parent graph from exactly
one entry point (``modules.shadow.graph.parent``); no node imports a sibling
node's internals; the orchestrator's ``_step*`` methods remain the delegated-to
source of truth.

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

from modules.shadow.graph.dispatch_graph import blocked_node, plan_gate
from modules.shadow.graph.morpheus_gate import dormant_node, make_routable_gate
from modules.shadow.graph.plan_node import make_plan_node
from modules.shadow.graph.retry_graph import make_orchestrator_retry_node
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
    builder.add_node("retry", make_orchestrator_retry_node(orchestrator))

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
    # reaches a module. Approved → retry, which delegates the whole 12-attempt
    # ``attempt_task`` loop (its ``execute_fn`` wraps ``_step5_execute``, so retry
    # supersedes the bare single-attempt dispatch on the approved branch). The
    # ``plan_gate`` predicate is unchanged; only its approved-branch target moves.
    builder.add_conditional_edges(
        "plan",
        plan_gate,
        {"blocked": "blocked", "dispatch": "retry"},
    )
    builder.add_edge("blocked", END)
    builder.add_edge("retry", END)

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
