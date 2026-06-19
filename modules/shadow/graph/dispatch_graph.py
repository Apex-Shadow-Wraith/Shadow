"""Dispatcher sub-graph for the Track B cutover (Step 2 — dispatcher migration).

Translates the orchestrator's :meth:`Orchestrator._step5_execute` dispatch loop
into a LangGraph fragment whose **defining property is structural**: when a plan
is denied by Cerberus (``plan.cerberus_approved is False``), the module-dispatch
node is *unreachable by graph topology*, not merely skipped at runtime. The live
loop encodes this as an early ``return`` at the top of ``_step5_execute``
(``modules/shadow/orchestrator.py:4923-4931``); a graph that preserved the guard
only as an inner runtime check would be a latent safety hole — a missed guard
means an unsafe request reaches a module that executes it. So the plan-level
guard is lifted onto a conditional edge, and the dispatch node sits exclusively
on its approved branch.

Topology
========

::

    START
     └─(gate: state["plan"].cerberus_approved)
         ├─ "blocked"  ─► blocked_node  ─► END   # appends the denial ToolResult
         └─ "dispatch" ─► dispatch_node ─► END   # delegates to live _step5_execute

The conditional edge out of ``START`` is the load-bearing safety assertion: its
``"blocked"`` branch routes a denied plan to a terminal node that never touches a
module, and ``dispatch_node`` is reachable only via the ``"dispatch"`` branch.
``tests.test_dispatch_graph`` proves this by graph introspection
(``compiled.get_graph()``), not by a behavioral "no module ran" observation.

Delegation (why the dispatch node hands the whole loop to live code)
===================================================================

``dispatch_node`` calls ``orchestrator._step5_execute(...)`` and never
reimplements the per-step loop. That preserves, byte-for-byte:

- the **three-verdict per-tool hook** (``orchestrator.py:4962-4979``): ALLOW
  (fall-through), DENY (``continue`` — skips one tool, plan keeps running), and
  **MODIFY** (``params = pre_hook.content.modified_params or params``, consumed by
  the dispatch call at ``orchestrator.py:5010``). A node that re-implemented the
  loop could silently collapse to two verdicts and drop MODIFY (e.g. the PII
  strip rule at ``cerberus.py:1257-1263``) into a no-op;
- the **Cerberus heartbeat seam**. ``send_heartbeat()`` fires *only* inside the
  ``safety_check`` branch (``cerberus.py:238``), **not** in ``hook_pre_tool`` /
  ``hook_post_tool``. Step-5 dispatch therefore does not itself write the
  heartbeat; the link survives because the per-tool hooks route through
  ``cerberus.execute`` (preserving ``_record_call`` and the lifecycle) and the
  planner's upstream ``safety_check`` does the write. Any refactor that reached
  past ``cerberus.execute`` would sever the file the external
  ``daemons/cerberus_watchdog/`` polls and trigger ``pkill -f shadow_core``;
- the async-queue branch (``orchestrator.py:4982``), the post-tool hook
  (``:5035``), the per-call timing, and the uniform exception envelope.

The live guard at ``orchestrator.py:4923`` still runs *inside* the delegated
call. On the approved branch that re-check is a harmless no-op (defense in
depth); the graph edge is the structural guard the cutover must preserve.

State / reducer
===============

Operates over :class:`modules.shadow.graph.skeleton.ShadowState` directly — no
new state class. It reads ``plan`` / ``classification`` (populated by the planner
and router migrations) and writes onto the ``Annotated[list[ToolResult], add]``
``tool_results`` key, so dispatch results accumulate under the same append
reducer every other Track B node uses.

Naming-trap callout
===================

:attr:`TaskClassification.safety_flag` is **not** a dispatch gate despite its
``# does Cerberus need to pre-screen?`` comment. The only plan-level gate is
``ExecutionPlan.cerberus_approved``; ``safety_flag`` is set/logged but never read
as a dispatch conditional (``orchestrator.py:318``, :1097, :1198, :1222). The
gate predicate here keys on ``cerberus_approved`` alone.

Observability
=============

Zero ``observed_span`` calls inside either node. The only span over Step 5 in the
live path is the parent ``shadow.module_dispatch`` emitted from *outside* the
loop (``orchestrator.py:1369-1372``); adding a span here would be instrumentation
the live path lacks. When a parent graph eventually wraps this fragment, that
outer span nests over the node invocation exactly as it nests over the live call.
"""

from __future__ import annotations

from typing import Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from modules.base import ToolResult
from modules.shadow.graph.skeleton import ShadowState
from modules.shadow.orchestrator import Orchestrator


def _gate(state: ShadowState) -> Literal["blocked", "dispatch"]:
    """Plan-level Cerberus short-circuit, as a conditional-edge predicate.

    Mirrors the early-return guard at ``orchestrator.py:4923``. Returns
    ``"blocked"`` when the plan is missing or denied, ``"dispatch"`` only when
    ``cerberus_approved`` is truthy. This predicate is what makes the dispatch
    node structurally unreachable past a denial.
    """
    plan = state.get("plan")
    if plan is None or not getattr(plan, "cerberus_approved", False):
        return "blocked"
    return "dispatch"


def build_dispatch_subgraph(orchestrator: Orchestrator) -> StateGraph:
    """Construct the dispatcher sub-graph builder (not compiled).

    The returned :class:`StateGraph` closes over ``orchestrator`` so each
    dispatch delegates against the same live instance — preserving its registry,
    Cerberus hooks, async queue, and heartbeat seam. Caller compiles with
    whatever checkpointer / interrupt configuration the use case needs.

    Args:
        orchestrator: The live :class:`~modules.shadow.orchestrator.Orchestrator`
            whose :meth:`~modules.shadow.orchestrator.Orchestrator._step5_execute`
            the dispatch node delegates to.
    """

    async def blocked_node(state: ShadowState) -> ShadowState:
        # Byte-for-byte parity with the denial ToolResult at
        # orchestrator.py:4924-4930. Terminal — never touches a module.
        return {
            "tool_results": [
                ToolResult(
                    success=False,
                    content=None,
                    tool_name="plan",
                    module="orchestrator",
                    error="Plan was denied by Cerberus",
                )
            ]
        }

    async def dispatch_node(state: ShadowState) -> ShadowState:
        # Delegate the entire per-step loop to live code. This carries the
        # three-verdict hook, the heartbeat seam (hooks via cerberus.execute),
        # the async-queue branch, the post-hook, and the exception envelope.
        results = await orchestrator._step5_execute(
            state["plan"],
            state["classification"],
            state.get("source", "user"),
        )
        return {"tool_results": results}

    builder = StateGraph(ShadowState)
    builder.add_node("blocked", blocked_node)
    builder.add_node("dispatch", dispatch_node)
    builder.add_conditional_edges(
        START,
        _gate,
        {"blocked": "blocked", "dispatch": "dispatch"},
    )
    builder.add_edge("blocked", END)
    builder.add_edge("dispatch", END)
    return builder


def compile_dispatch_subgraph(
    orchestrator: Orchestrator,
    checkpointer: BaseCheckpointSaver | None = None,
):
    """Compile the dispatcher sub-graph with an optional async checkpointer.

    Pass a saver from
    :func:`modules.shadow.graph.serde.open_async_sqlite_saver` to get one that is
    already wired with the ``ToolResult``-aware msgpack allowlist.
    """
    builder = build_dispatch_subgraph(orchestrator)
    if checkpointer is None:
        return builder.compile()
    return builder.compile(checkpointer=checkpointer)
