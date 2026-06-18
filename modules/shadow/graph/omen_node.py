"""Omen delegating node for the Track B cutover.

A single delegating LangGraph *node* — **not** a sub-graph — that hands each
dispatch to the live :meth:`Omen.execute` coroutine. Omen is a flat
dict-dispatch leaf module (``modules/omen/omen.py:563``): a ~47-entry handler
table keyed by tool name, with no nested routing to model as a sub-graph. One
node delegating to ``execute`` captures the whole surface. Lives at
``modules/shadow/graph/omen_node.py`` and is imported by exactly one caller
in the repo today — :mod:`tests.test_omen_node`. Nothing on the orchestrator
path references it; physical separation is the feature flag.

Delegation
==========

Calls ``Omen.execute(tool_name, params)`` and never reaches past it into the
handler table. That matters more for Omen than for any other module in this
batch, because two live-path behaviours must be preserved exactly and are
*out of scope to "fix"* here:

- Omen's inner handlers are invoked **synchronously** —
  ``result = handler(params)`` at ``omen.py:637`` is not awaited even though
  ``execute`` is ``async``. The node awaits ``execute`` itself, which is
  correct; it does **not** reach in to add awaits to the handler calls. That
  is authoritative live-path behaviour.
- The ~47 tool entries are *not* 47 unique handlers: two are backward-compat
  aliases (``data_analyze`` → statistics, ``logic_verify`` → logic_check) and
  the Cipher tools delegate to ``self._cipher.*`` (``omen.py:619-627``). Tool
  count ≠ handler count; the aliases are live surface, not dropped tools.

Delegation preserves the ``_record_call`` update on every dispatch — success
or failure (``omen.py:640`` and ``:645``) — the uniform exception envelope
(``:643``), and the ``Unknown tool: ...`` else-branch failure ``ToolResult``
at ``omen.py:631-635``.

State / reducer
===============

Returns ``{"tool_results": [result]}`` so the
``Annotated[list[ToolResult], add]`` reducer on
:class:`modules.shadow.graph.skeleton.ShadowState` appends rather than
overwrites when composed into the parent graph.

Observability
=============

Zero ``observed_span`` calls inside the node — matches the live span-silent
Omen path, which has zero observability surface inside ``modules/omen/``
(verified by grep). The parent ``shadow.module_dispatch`` span the
orchestrator emits is the only observation over an Omen call; this node sits
inside it unchanged.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from modules.omen.omen import Omen

OmenNode = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def make_omen_node(omen_module: Omen) -> OmenNode:
    """Build the Omen delegating node (a single node, not a sub-graph).

    The returned coroutine closes over ``omen_module`` so each invocation
    dispatches against the same instance. Wire it in with
    ``builder.add_node("omen_dispatch", make_omen_node(omen))`` — no compile /
    sub-graph wrapper to call.

    Args:
        omen_module: The live :class:`~modules.omen.omen.Omen` instance to
            delegate dispatch to.

    Returns:
        An async LangGraph node that reads ``tool_name`` / ``params`` from
        state, delegates to :meth:`Omen.execute`, and returns a partial
        update writing the resulting ``ToolResult`` onto the append-reducer
        ``tool_results`` key.
    """

    async def omen_dispatch(state: dict[str, Any]) -> dict[str, Any]:
        tool_name = state["tool_name"]
        params = state.get("params", {}) or {}
        result = await omen_module.execute(tool_name, params)
        return {"tool_results": [result]}

    return omen_dispatch
