"""Cerberus sub-graph for the Track B cutover.

Single-node compiled :class:`StateGraph` that delegates each dispatch to the
live :meth:`Cerberus.execute` coroutine. Symmetric with
:mod:`modules.shadow.graph.grimoire_subgraph`, with one critical difference
covered below: Option-A delegation is more load-bearing for Cerberus than it
is for Grimoire because the daemon side of the system reads a side-effect
file that the live ``execute`` writes.

Design notes
============

Why delegate to ``Cerberus.execute`` instead of duplicating the 39-tool
dispatch table inside the sub-graph:

- ``Cerberus.execute("safety_check", ...)`` calls :meth:`Cerberus.send_heartbeat`
  as a side effect (`modules/cerberus/cerberus.py:238`). That heartbeat writes
  ``data/cerberus_heartbeat.json``; the external systemd-managed daemon at
  ``daemons/cerberus_watchdog/`` polls the file; if the file goes stale the
  daemon runs ``pkill -f shadow_core`` and sends a Telegram alert. A
  duplicating sub-graph that bypassed ``execute`` would silently sever that
  heartbeat link, the daemon would conclude Cerberus is dead, and Shadow
  would get force-killed. A real-I/O canary test guards the file write so
  any regression is caught immediately.
- ``execute`` also owns ``_record_call`` per branch, the lifecycle, and the
  uniform exception envelope. The dispatch-table duplication risk
  documented for Grimoire (Step 2) applies here too, with extra severity.

Topology
========

Single ``cerberus_dispatch`` node compiled as a sub-graph
(``START → dispatch → END``). The 39 tools are independent dispatch targets
that don't chain or share state, so per-tool nodes would inflate the
checkpoint graph for zero observability gain — same argument as Grimoire.

The short-circuit ORCHESTRATION (plan-gate node, conditional ``END(blocked)``
edge, per-tool hook handling that interprets ALLOW / DENY / MODIFY) lives in
the parent graph and lands with the dispatcher migration later in the
cutover sequence (design doc §4 item 5). The two safety-critical tools the
orchestration calls — ``safety_check`` and ``hook_pre_tool`` — are reachable
through this sub-graph today but no parent graph yet wires the short-circuit
edges. Step 3a's investigation document captures the proposed orchestration
shape.

Observability
=============

Zero ``observed_span`` calls inside the sub-graph. The live Cerberus path
has zero spans inside ``modules/cerberus/`` (verified by grep); the only
observation over a Cerberus call in the live path is the parent
``shadow.module_dispatch`` emitted by the orchestrator when Cerberus is
called from Step 5, or the surrounding Step-4 region for ``safety_check``
calls. Matching that exactly.

Naming-trap callout
===================

:attr:`TaskClassification.safety_flag` is **not** a Cerberus gate, despite
its name and the ``# does Cerberus need to pre-screen?`` comment on its
declaration. Cerberus runs on module presence
(``"cerberus" in registry and status == ONLINE``), not on the flag. This
module — and the eventual parent-graph orchestration — must not introduce
any conditional keyed on ``safety_flag``.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from modules.base import ToolResult
from modules.cerberus.cerberus import Cerberus


class CerberusCallState(TypedDict, total=False):
    """Sub-graph-local state for a single Cerberus tool call.

    ``tool_results`` uses the same ``Annotated[list[ToolResult], add]``
    reducer as :class:`modules.shadow.graph.skeleton.ShadowState`, so when
    the sub-graph is composed into a parent graph LangGraph merges the two
    append streams on the shared key without conflict.
    """

    tool_name: str
    params: dict[str, Any]
    tool_results: Annotated[list[ToolResult], add]


def build_cerberus_subgraph(cerberus_module: Cerberus) -> StateGraph:
    """Construct the Cerberus sub-graph builder (not compiled).

    The returned :class:`StateGraph` closes over ``cerberus_module`` so each
    invocation dispatches against the same module instance. Caller compiles
    with whatever checkpointer / interrupt configuration the use case needs.
    """

    async def cerberus_dispatch(state: CerberusCallState) -> CerberusCallState:
        tool_name = state["tool_name"]
        params = state.get("params", {}) or {}
        result = await cerberus_module.execute(tool_name, params)
        return {"tool_results": [result]}

    builder = StateGraph(CerberusCallState)
    builder.add_node("cerberus_dispatch", cerberus_dispatch)
    builder.add_edge(START, "cerberus_dispatch")
    builder.add_edge("cerberus_dispatch", END)
    return builder


def compile_cerberus_subgraph(
    cerberus_module: Cerberus,
    checkpointer: BaseCheckpointSaver | None = None,
):
    """Compile the Cerberus sub-graph with an optional async checkpointer.

    Pass a saver from
    :func:`modules.shadow.graph.serde.open_async_sqlite_saver` to get one
    that is already wired with the ``ToolResult``-aware msgpack allowlist.
    """
    builder = build_cerberus_subgraph(cerberus_module)
    if checkpointer is None:
        return builder.compile()
    return builder.compile(checkpointer=checkpointer)
