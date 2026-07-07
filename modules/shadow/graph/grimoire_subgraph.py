"""Grimoire sub-graph for the Track B cutover.

Single-node compiled :class:`StateGraph` that delegates each dispatch to the
live :meth:`GrimoireModule.execute` coroutine. Lives at
``modules/shadow/graph/grimoire_subgraph.py`` and is imported by exactly one
caller in the repo today — :mod:`tests.test_grimoire_subgraph`. Nothing on the
orchestrator path references this module, which is the strongest possible
feature flag (physical separation).

Design notes
============

Why delegate to ``GrimoireModule.execute`` instead of duplicating the 9-branch
dispatch table inside the sub-graph:

- ``execute`` already owns Grimoire's lifecycle and side-effect surface:
  ``_record_call`` per branch, the uniform exception envelope, the
  ``Grimoire not initialized`` early-return, and (post-init) the
  ``staged_retrieval._grimoire`` wire-up. A duplicating dispatcher would
  silently skip all of those and create two drift-prone surfaces for the same
  contract.
- The spike's ``asyncio.to_thread`` wrap targeted *sync callables*
  (``grimoire.remember``); the production async surface (``execute``) has
  already absorbed that role. You cannot ``to_thread`` a coroutine, and
  pushing sync calls onto a worker thread inside the sub-graph would not
  actually unblock the loop — the blocking ``requests.post`` to Ollama at
  ``grimoire.py:626`` still blocks, just on a different thread. The real fix
  is async embeddings inside Grimoire itself, which is out of scope for
  Step 2.

Topology
========

A single ``grimoire_dispatch`` node compiled as a sub-graph
(``START → dispatch → END``). The 9 tools are independent leaf operations
that don't chain or share state, so 9 per-tool nodes with a fan-out entry
edge would inflate the checkpoint graph for zero observability or
resumability gain. The single-node shape stays the seam for later expansion
without touching parent graphs.

Observability
=============

Zero ``observed_span`` calls inside the sub-graph. The live Grimoire path has
zero spans inside ``modules/grimoire/``; the only observation over a Grimoire
call is the parent ``shadow.module_dispatch`` emitted by the orchestrator.
When this sub-graph is wired into a parent graph in a later step, the
parent's dispatch span wraps the sub-graph invocation as outer — matching
live exactly.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from modules.base import ToolResult
from modules.grimoire.grimoire_module import GrimoireModule


class GrimoireCallState(TypedDict, total=False):
    """Sub-graph-local state for a single Grimoire tool call.

    ``tool_results`` uses the same ``Annotated[list[ToolResult], add]``
    reducer as :class:`modules.shadow.graph.skeleton.ShadowState`, so when the
    sub-graph is composed into a parent graph LangGraph merges the two append
    streams on the shared key without conflict.
    """

    tool_name: str
    params: dict[str, Any]
    tool_results: Annotated[list[ToolResult], add]


def build_grimoire_subgraph(grimoire_module: GrimoireModule) -> StateGraph:
    """Construct the Grimoire sub-graph builder (not compiled).

    The returned :class:`StateGraph` closes over ``grimoire_module`` so each
    invocation dispatches against the same module instance. Caller compiles
    with whatever checkpointer / interrupt configuration the use case needs.
    """

    async def grimoire_dispatch(state: GrimoireCallState) -> GrimoireCallState:
        tool_name = state["tool_name"]
        params = state.get("params", {}) or {}
        result = await grimoire_module.execute(tool_name, params)
        return {"tool_results": [result]}

    builder = StateGraph(GrimoireCallState)
    builder.add_node("grimoire_dispatch", grimoire_dispatch)
    builder.add_edge(START, "grimoire_dispatch")
    builder.add_edge("grimoire_dispatch", END)
    return builder


def compile_grimoire_subgraph(
    grimoire_module: GrimoireModule,
    checkpointer: BaseCheckpointSaver | None = None,
):
    """Compile the Grimoire sub-graph with an optional async checkpointer.

    Pass a saver from
    :func:`modules.shadow.graph.serde.open_async_sqlite_saver` to get one that
    is already wired with the ``ToolResult``-aware msgpack allowlist.
    """
    builder = build_grimoire_subgraph(grimoire_module)
    if checkpointer is None:
        return builder.compile()
    return builder.compile(checkpointer=checkpointer)
