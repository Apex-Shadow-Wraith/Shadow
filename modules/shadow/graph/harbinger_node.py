"""Harbinger delegating node for the Track B cutover.

A single delegating LangGraph *node* — **not** a sub-graph — that hands each
dispatch to the live :meth:`Harbinger.execute` coroutine. Harbinger is a
flat dict-dispatch leaf module (``modules/harbinger/harbinger.py:113``), so
one node delegating to ``execute`` captures the whole surface. Lives at
``modules/shadow/graph/harbinger_node.py`` and is imported by exactly one
caller in the repo today — :mod:`tests.test_harbinger_node`. Nothing on the
orchestrator path references it; physical separation is the feature flag.

Delegation
==========

Calls ``Harbinger.execute(tool_name, params)`` and never reaches past it into
the private ``_briefing_*`` / ``_notification_*`` / ``_decision_queue_*``
handlers. That preserves Harbinger's full dispatch contract: the
``_record_call`` update on every dispatch — success or failure
(``harbinger.py:153`` and ``:158``) — the uniform exception envelope
(``:156``), and the ``Unknown tool: ...`` else-branch failure ``ToolResult``
at ``harbinger.py:141-148``.

State / reducer
===============

Returns ``{"tool_results": [result]}`` so the
``Annotated[list[ToolResult], add]`` reducer on
:class:`modules.shadow.graph.skeleton.ShadowState` appends rather than
overwrites when composed into the parent graph.

Observability
=============

Zero ``observed_span`` calls inside the node — matches the live span-silent
Harbinger path, which has zero observability surface inside
``modules/harbinger/`` (verified by grep). The parent
``shadow.module_dispatch`` span the orchestrator emits is the only
observation over a Harbinger call; this node sits inside it unchanged.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from modules.harbinger.harbinger import Harbinger

HarbingerNode = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def make_harbinger_node(harbinger_module: Harbinger) -> HarbingerNode:
    """Build the Harbinger delegating node (a single node, not a sub-graph).

    The returned coroutine closes over ``harbinger_module`` so each
    invocation dispatches against the same instance. Wire it in with
    ``builder.add_node("harbinger_dispatch", make_harbinger_node(h))`` — no
    compile / sub-graph wrapper to call.

    Args:
        harbinger_module: The live
            :class:`~modules.harbinger.harbinger.Harbinger` instance to
            delegate dispatch to.

    Returns:
        An async LangGraph node that reads ``tool_name`` / ``params`` from
        state, delegates to :meth:`Harbinger.execute`, and returns a partial
        update writing the resulting ``ToolResult`` onto the append-reducer
        ``tool_results`` key.
    """

    async def harbinger_dispatch(state: dict[str, Any]) -> dict[str, Any]:
        tool_name = state["tool_name"]
        params = state.get("params", {}) or {}
        result = await harbinger_module.execute(tool_name, params)
        return {"tool_results": [result]}

    return harbinger_dispatch
