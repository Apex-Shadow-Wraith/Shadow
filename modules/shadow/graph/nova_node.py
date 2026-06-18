"""Nova delegating node for the Track B cutover.

A single delegating LangGraph *node* — **not** a sub-graph — that hands each
dispatch to the live :meth:`Nova.execute` coroutine. Nova is a flat
dict-dispatch leaf module (``modules/nova/nova.py:158``), so one node
delegating to ``execute`` captures the whole surface. Lives at
``modules/shadow/graph/nova_node.py`` and is imported by exactly one caller
in the repo today — :mod:`tests.test_nova_node`. Nothing on the orchestrator
path references it; physical separation is the feature flag.

Delegation
==========

Calls ``Nova.execute(tool_name, params)`` and never reaches past it into the
private ``_format_*`` / ``_template_*`` handlers. That preserves Nova's full
dispatch contract: the ``_record_call`` update on every dispatch — success or
failure (``nova.py:181`` and ``:186``) — the uniform exception envelope
(``:184``), and the ``Unknown tool: ...`` else-branch failure ``ToolResult``
at ``nova.py:172-176``.

State / reducer
===============

Returns ``{"tool_results": [result]}`` so the
``Annotated[list[ToolResult], add]`` reducer on
:class:`modules.shadow.graph.skeleton.ShadowState` appends rather than
overwrites when composed into the parent graph.

Observability
=============

Zero ``observed_span`` calls inside the node — matches the live span-silent
Nova path, which has zero observability surface inside ``modules/nova/``
(verified by grep). The parent ``shadow.module_dispatch`` span the
orchestrator emits is the only observation over a Nova call; this node sits
inside it unchanged.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from modules.nova.nova import Nova

NovaNode = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def make_nova_node(nova_module: Nova) -> NovaNode:
    """Build the Nova delegating node (a single node, not a sub-graph).

    The returned coroutine closes over ``nova_module`` so each invocation
    dispatches against the same instance. Wire it in with
    ``builder.add_node("nova_dispatch", make_nova_node(nova))`` — no compile /
    sub-graph wrapper to call.

    Args:
        nova_module: The live :class:`~modules.nova.nova.Nova` instance to
            delegate dispatch to.

    Returns:
        An async LangGraph node that reads ``tool_name`` / ``params`` from
        state, delegates to :meth:`Nova.execute`, and returns a partial
        update writing the resulting ``ToolResult`` onto the append-reducer
        ``tool_results`` key.
    """

    async def nova_dispatch(state: dict[str, Any]) -> dict[str, Any]:
        tool_name = state["tool_name"]
        params = state.get("params", {}) or {}
        result = await nova_module.execute(tool_name, params)
        return {"tool_results": [result]}

    return nova_dispatch
