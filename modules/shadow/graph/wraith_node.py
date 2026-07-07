"""Wraith delegating node for the Track B cutover.

A single delegating LangGraph *node* — **not** a sub-graph — that hands each
dispatch to the live :meth:`Wraith.execute` coroutine. Wraith is a flat
if/elif dispatch leaf module (``modules/wraith/wraith.py:383``), so there is
no nested routing to model as a sub-graph; one node delegating to ``execute``
captures the whole surface. Lives at ``modules/shadow/graph/wraith_node.py``
and is imported by exactly one caller in the repo today —
:mod:`tests.test_wraith_node`. Nothing on the orchestrator path references
it; physical separation is the feature flag, identical to the Apex node.

Delegation
==========

Calls ``Wraith.execute(tool_name, params)`` and never reaches past it into
the private ``_quick_answer`` / ``_reminder_*`` / ``_temporal_*`` handlers.
That preserves Wraith's full dispatch contract: the ``_record_call`` update
on every dispatch — success or failure (``wraith.py:429`` and ``:434``) — the
uniform exception envelope (``:432``), and the ``Unknown tool: ...``
else-branch failure ``ToolResult`` at ``wraith.py:419-426``. A duplicating
dispatcher would fork that contract and skip the call accounting that
module-health metrics depend on.

State / reducer
===============

Returns ``{"tool_results": [result]}`` — a single-element list — so the
``Annotated[list[ToolResult], add]`` reducer on
:class:`modules.shadow.graph.skeleton.ShadowState` appends rather than
overwrites when the node is composed into the parent graph.

Observability
=============

Zero ``observed_span`` calls inside the node — matches the live span-silent
Wraith path, which has zero observability surface inside
``modules/wraith/`` (no span/langfuse/trace; verified by grep). The only
observation over a Wraith call in the live path is the parent
``shadow.module_dispatch`` span the orchestrator emits; when this node is
wired in, that parent span wraps the node invocation as outer, matching
live exactly.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from modules.wraith.wraith import Wraith

WraithNode = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def make_wraith_node(wraith_module: Wraith) -> WraithNode:
    """Build the Wraith delegating node (a single node, not a sub-graph).

    The returned coroutine closes over ``wraith_module`` so each invocation
    dispatches against the same instance. Wire it into a parent graph with
    ``builder.add_node("wraith_dispatch", make_wraith_node(wraith))`` — there
    is no compile / sub-graph wrapper to call.

    Args:
        wraith_module: The live :class:`~modules.wraith.wraith.Wraith`
            instance to delegate dispatch to.

    Returns:
        An async LangGraph node that reads ``tool_name`` / ``params`` from
        state, delegates to :meth:`Wraith.execute`, and returns a partial
        update writing the resulting ``ToolResult`` onto the append-reducer
        ``tool_results`` key.
    """

    async def wraith_dispatch(state: dict[str, Any]) -> dict[str, Any]:
        tool_name = state["tool_name"]
        params = state.get("params", {}) or {}
        result = await wraith_module.execute(tool_name, params)
        return {"tool_results": [result]}

    return wraith_dispatch
