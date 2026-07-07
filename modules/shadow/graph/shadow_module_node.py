"""ShadowModule delegating node for the Track B cutover.

A single delegating LangGraph *node* — **not** a sub-graph — that hands each
dispatch to the live :meth:`ShadowModule.execute` coroutine. ShadowModule is
the router-facing task-tracking / module-health BaseModule peer (distinct
from the Shadow *orchestrator* class); it is a flat if/elif dispatch leaf
(``modules/shadow/shadow_module.py:92``), so one node delegating to
``execute`` captures the whole surface. Lives at
``modules/shadow/graph/shadow_module_node.py`` and is imported by exactly one
caller in the repo today — :mod:`tests.test_shadow_module_node`. Nothing on
the orchestrator path references it; physical separation is the feature flag.

Delegation
==========

Calls ``ShadowModule.execute(tool_name, params)`` and never reaches past it
into the private ``_task_*`` / ``_module_health`` handlers. That preserves
ShadowModule's full dispatch contract: the ``_record_call`` update on every
dispatch — success or failure (``shadow_module.py:116`` / ``:120``) — and the
unknown-tool branch. Note ShadowModule's unknown-tool envelope differs in two
ways from the dict-dispatch modules and is preserved verbatim by delegating:
it records the call (``_record_call(False)`` at ``:105``) and **early-returns**
its own failure ``ToolResult`` with the distinct message
``"Unknown Shadow tool: {tool_name}"`` (``:106-113``), rather than falling
through a shared post-dispatch tail.

State / reducer
===============

Returns ``{"tool_results": [result]}`` so the
``Annotated[list[ToolResult], add]`` reducer on
:class:`modules.shadow.graph.skeleton.ShadowState` appends rather than
overwrites when composed into the parent graph.

Observability
=============

Zero ``observed_span`` calls inside the node — matches the live span-silent
ShadowModule path, which has zero observability surface inside
``shadow_module.py`` (verified by grep). The parent ``shadow.module_dispatch``
span the orchestrator emits is the only observation over a ShadowModule call;
this node sits inside it unchanged.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from modules.shadow.shadow_module import ShadowModule

ShadowModuleNode = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def make_shadow_module_node(shadow_module: ShadowModule) -> ShadowModuleNode:
    """Build the ShadowModule delegating node (a single node, not a sub-graph).

    The returned coroutine closes over ``shadow_module`` so each invocation
    dispatches against the same instance. Wire it in with
    ``builder.add_node("shadow_module_dispatch", make_shadow_module_node(sm))``
    — no compile / sub-graph wrapper to call.

    Args:
        shadow_module: The live
            :class:`~modules.shadow.shadow_module.ShadowModule` instance to
            delegate dispatch to.

    Returns:
        An async LangGraph node that reads ``tool_name`` / ``params`` from
        state, delegates to :meth:`ShadowModule.execute`, and returns a
        partial update writing the resulting ``ToolResult`` onto the
        append-reducer ``tool_results`` key.
    """

    async def shadow_module_dispatch(state: dict[str, Any]) -> dict[str, Any]:
        tool_name = state["tool_name"]
        params = state.get("params", {}) or {}
        result = await shadow_module.execute(tool_name, params)
        return {"tool_results": [result]}

    return shadow_module_dispatch
