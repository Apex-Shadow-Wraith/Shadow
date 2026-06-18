"""Apex delegating node for the Track B cutover.

A single delegating LangGraph *node* — **not** a sub-graph — that hands each
dispatch to the live :meth:`Apex.execute` coroutine. Lives at
``modules/shadow/graph/apex_node.py`` and is imported by exactly one caller
in the repo today — :mod:`tests.test_apex_node`. Nothing on the orchestrator
path references it, which is the strongest possible feature flag (physical
separation), identical to the posture of the Grimoire and Cerberus
sub-graphs.

Why a node, not a sub-graph
===========================

Grimoire (Step 2) and Cerberus (Step 3b) landed as single-node *compiled
sub-graphs* (``build_*`` / ``compile_*`` returning a ``StateGraph``). Apex is
the fallback leg the parent router drops into when a primary module fails;
design doc §4 wires it directly as one node inside the parent ``ShadowState``
graph with no nested ``StateGraph`` / compile boundary. Wrapping it in a
sub-graph here would add a checkpoint-graph nesting level the §4 topology
does not call for, for zero observability or resumability gain. So this
module exposes the bare node callable through a factory; the parent graph
adds it with ``builder.add_node(...)`` when the dispatcher migration lands.
There is deliberately no ``ApexCallState`` / ``build_apex_subgraph`` /
``compile_apex_subgraph`` surface — the §4 node shape composes directly onto
``ShadowState``, so a dedicated sub-graph state class would be dead weight.

Delegation
==========

Calls ``Apex.execute(tool_name, params)`` and never reaches past it into
private handlers. That preserves Apex's whole lifecycle surface: the
``_record_call`` increment on every dispatch — success or failure
(``modules/apex/apex.py:425`` and ``:430``) — the uniform exception envelope,
and the ``Unknown tool: ...`` else-branch failure ``ToolResult`` at
``modules/apex/apex.py:416-420``. A duplicating dispatcher would create a
second drift-prone copy of that contract and silently skip the call
accounting that module-health metrics depend on.

State / reducer
===============

The node returns ``{"tool_results": [result]}`` — a single-element list — so
the ``Annotated[list[ToolResult], add]`` reducer on
:class:`modules.shadow.graph.skeleton.ShadowState` appends rather than
overwrites when the node is composed into the parent graph. It reads the
dispatch-scoped ``tool_name`` / ``params`` keys the parent populates ahead of
the call. Matching that reducer exactly is what lets retry attempts and
multi-tool plans accumulate without clobbering each other.

Observability
=============

Zero ``observed_span`` calls inside the node — matches the live Apex path,
which has zero observability surface inside ``modules/apex/`` (no
span/langfuse/observ/trace; verified by grep). The only observation over an
Apex call in the live path is the parent ``shadow.module_dispatch`` span the
orchestrator emits; when this node is wired in, that parent span wraps the
node invocation as outer, matching live exactly.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from modules.apex.apex import Apex

ApexNode = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def make_apex_node(apex_module: Apex) -> ApexNode:
    """Build the Apex delegating node (a single node, not a sub-graph).

    The returned coroutine closes over ``apex_module`` so each invocation
    dispatches against the same instance. Wire it into a parent graph with
    ``builder.add_node("apex_dispatch", make_apex_node(apex))`` — there is no
    compile / sub-graph wrapper to call.

    Args:
        apex_module: The live :class:`~modules.apex.apex.Apex` instance to
            delegate dispatch to.

    Returns:
        An async LangGraph node that reads ``tool_name`` / ``params`` from
        state, delegates to :meth:`Apex.execute`, and returns a partial
        update writing the resulting ``ToolResult`` onto the append-reducer
        ``tool_results`` key.
    """

    async def apex_dispatch(state: dict[str, Any]) -> dict[str, Any]:
        tool_name = state["tool_name"]
        params = state.get("params", {}) or {}
        result = await apex_module.execute(tool_name, params)
        return {"tool_results": [result]}

    return apex_dispatch
