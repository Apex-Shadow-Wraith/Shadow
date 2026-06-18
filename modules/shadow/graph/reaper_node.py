"""Reaper delegating node for the Track B cutover.

A single delegating LangGraph *node* — **not** a sub-graph — that hands each
dispatch to the live :meth:`ReaperModule.execute` coroutine. ReaperModule is
a flat if/elif dispatch leaf (``modules/reaper/reaper_module.py:82``), so one
node delegating to ``execute`` captures the whole surface. Lives at
``modules/shadow/graph/reaper_node.py`` and is imported by exactly one caller
in the repo today — :mod:`tests.test_reaper_node`. Nothing on the
orchestrator path references it; physical separation is the feature flag.

Delegation
==========

Calls ``ReaperModule.execute(tool_name, params)`` and never reaches past it
into the inner :class:`~modules.reaper.reaper.Reaper` engine. That preserves
ReaperModule's full dispatch contract: the per-tool ``_record_call(True)``
updates, the uniform exception envelope (``reaper_module.py:192``), and the
``Unknown Reaper tool: {tool_name}`` else-branch failure ``ToolResult``
(``:181-190``).

Observability — the batch exception, read carefully
====================================================

This node is **span-silent at the node layer**, exactly like the other five
delegating nodes in this batch — there is **no** ``observed_span`` added
here. But Reaper differs from the rest underneath: the live inner engine
``modules/reaper/reaper.py`` emits its own spans on the ``search()`` path —
``reaper.search`` (``reaper.py:423``) wrapping per-backend
``reaper.search.attempt`` children (``reaper.py:549``) — and
``ReaperModule.execute`` routes the ``web_search`` tool *through* that engine
(``reaper_module.py:99`` calls ``self._reaper.search(...)``).

Because this node delegates to ``execute`` rather than duplicating dispatch,
those inner spans **survive**: dispatching ``web_search`` through the node
still produces the inner ``reaper.search.attempt`` span(s). Adding a span in
the node would double-instrument the search path; not delegating would bypass
the engine and silently drop the inner spans. Delegation is what keeps the
live observability shape intact.

The other two Reaper tools route to **unspanned** inner methods —
``web_fetch`` → ``Reaper.fetch_page`` (``reaper_module.py:127``) and
``youtube_transcribe`` → ``Reaper.youtube_transcribe`` (``:139``) — so they
produce no inner child span, which is correct and expected. The node does not
add one.

State / reducer
===============

Returns ``{"tool_results": [result]}`` so the
``Annotated[list[ToolResult], add]`` reducer on
:class:`modules.shadow.graph.skeleton.ShadowState` appends rather than
overwrites when composed into the parent graph.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from modules.reaper.reaper_module import ReaperModule

ReaperNode = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def make_reaper_node(reaper_module: ReaperModule) -> ReaperNode:
    """Build the Reaper delegating node (a single node, not a sub-graph).

    The returned coroutine closes over ``reaper_module`` so each invocation
    dispatches against the same instance. Wire it in with
    ``builder.add_node("reaper_dispatch", make_reaper_node(reaper))`` — no
    compile / sub-graph wrapper to call. Delegation routes ``web_search``
    through the spanned inner engine; the node adds no span of its own.

    Args:
        reaper_module: The live
            :class:`~modules.reaper.reaper_module.ReaperModule` instance to
            delegate dispatch to.

    Returns:
        An async LangGraph node that reads ``tool_name`` / ``params`` from
        state, delegates to :meth:`ReaperModule.execute`, and returns a
        partial update writing the resulting ``ToolResult`` onto the
        append-reducer ``tool_results`` key.
    """

    async def reaper_dispatch(state: dict[str, Any]) -> dict[str, Any]:
        tool_name = state["tool_name"]
        params = state.get("params", {}) or {}
        result = await reaper_module.execute(tool_name, params)
        return {"tool_results": [result]}

    return reaper_dispatch
