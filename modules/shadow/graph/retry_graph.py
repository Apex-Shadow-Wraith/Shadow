"""Retry delegating node for the Track B cutover (Step 3 — rebuild).

Single node, **no self-edge**, that delegates the *whole* 12-attempt retry loop
to live code by calling :meth:`RetryEngine.attempt_task` once per visit. Lives at
``modules/shadow/graph/retry_graph.py`` and is imported by exactly one caller in
the repo today — :mod:`tests.test_retry_graph`. Nothing on the orchestrator path
references this module, which is the strongest possible feature flag (physical
separation), identical to the posture of the dispatcher sub-graph and the leaf
delegating nodes.

Supersession (why this replaces the self-edge node)
===================================================

The first retry-graph commit drove its *own* attempt loop from ``attempt_task``'s
lower-level primitives (``get_strategy_for_attempt`` / ``_build_strategy_context``
/ ``classify_failure`` / ``should_escalate``) across a conditional self-edge,
bypassing the live ``for attempt_num in range(...)`` loop at
``retry_engine.py:352`` entirely. That reimplementation silently dropped five
behaviors that live *inside* ``attempt_task`` and are not reachable from those
primitives alone:

1. **Deterministic-failure early-exit** (``retry_engine.py:476-489``) — escalates
   a deterministic failure at attempt 1 instead of looping to exhaustion.
2. **Fatigue counter** (``retry_engine.py:404-405`` / ``:413-414``) — feeds the
   rotation; skipping it drifts long runs from the tested loop.
3. **Grimoire preflight** (``retry_engine.py:329-350``) — loads prior failure
   lessons before the loop via ``grimoire_search_fn``.
4. **Progress notifications** (``retry_engine.py:502-503``) — fired via
   ``notify_fn`` at attempts 4 / 8 / 12.
5. **``_record_session``** (``retry_engine.py:444`` / ``:465`` / ``:521`` …) —
   appends the session to ``RetryEngine._session_history`` on every exit path.

The 40 tests in ``tests/test_retry_engine.py`` call ``attempt_task`` directly, so
they guarded the live loop, **not** the self-edge node's driver. The pre-decision
"retry = one node + conditional self-edge, rotation as data" assumed a per-attempt
public primitive; ``attempt_task`` exposes none — it owns the whole loop. So
per-attempt topology necessarily forks the driver. That pre-decision is superseded
for retry.

Delegation boundary
===================

``attempt_task`` is the seam, not the higher ``Orchestrator._step5_with_retry``.
``_step5_with_retry`` is the live unit that *wires the closures and calls
``attempt_task``*, but delegating to it would pull in concerns outside the retry
loop: its ``execute_fn`` re-wraps ``Orchestrator._step5_execute`` — the exact
method ``dispatch_node`` already delegates (``dispatch_graph.py:144``) — plus Apex
escalation, pre-escalation decomposition, and ``_pending_escalation`` book-keeping
(``orchestrator.py:4711-4772``), and it returns a response ``str`` rather than
graph state. So the node delegates one level down, to ``attempt_task``, and
**forwards the same five closures the live path builds** at
``orchestrator.py:4698-4709`` (``execute_fn`` / ``evaluate_fn`` /
``grimoire_search_fn`` / ``notify_fn``). The node reconstructs none of them — the
caller (tests today, the orchestrator at cutover) builds them, exactly as
``make_grimoire_subgraph`` receives a live module rather than rebuilding one. All
of fatigue / preflight / early-exits / notify / ``_record_session`` run *inside*
the delegated call, on the path the 40 tests certify.

Topology
========

::

    START → retry → END

One node, no self-edge, no per-attempt graph re-entry. The engine's internal
``for`` loop at ``retry_engine.py:352`` runs untouched. The loop *count* stays
data — it is whatever the engine's rotation + give-up logic produce — but that
data now lives entirely inside the engine, not in graph topology.

State / reducer
===============

``RetryCallState.tool_results`` uses the same ``Annotated[list[ToolResult], add]``
reducer as :class:`modules.shadow.graph.skeleton.ShadowState`, so the per-attempt
``ToolResult``\\s the node materializes from the returned session accumulate across
a multi-tool plan and merge cleanly when this fragment is composed into a parent
graph (design §3.4). The full ``attempt_task`` result dict is surfaced verbatim on
``retry_result`` for the downstream escalation / response-assembly the parent graph
will own.

Observability
=============

Span-silent **at the node layer** — unlike the superseded self-edge node, this
node opens no ``observed_span`` of its own. The ``retry_attempt`` span the live
per-attempt path emits (``retry_engine.py:358-364``, metadata updated at
``:425-432``) now fires from *inside* the delegated ``attempt_task`` call, once per
real attempt, exactly as live. Whole-call delegation preserves the span
automatically; re-emitting it here would double it. The outer parent
``shadow.module_dispatch`` span (``orchestrator.py:1369-1372``) nests over this
fragment from outside, as it nests over the live call.
"""

from __future__ import annotations

from operator import add
from typing import TYPE_CHECKING, Annotated, Any, Awaitable, Callable, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from modules.base import ToolResult
from modules.shadow.graph.skeleton import ShadowState
from modules.shadow.retry_engine import RetryEngine

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from modules.shadow.orchestrator import Orchestrator

# Caller-supplied attempt + evaluation hooks, matching the live closures the
# orchestrator builds inside ``_step5_with_retry`` and hands to
# ``RetryEngine.attempt_task`` (``orchestrator.py:4698-4709``). The node forwards
# them verbatim; it never reconstructs them.
ExecuteFn = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]
EvaluateFn = Callable[[dict[str, Any]], dict[str, Any]]
GrimoireSearchFn = Callable[[str], list[dict[str, Any]]]
NotifyFn = Callable[[str], Awaitable[None]]
RetryNode = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class RetryCallState(TypedDict, total=False):
    """Sub-graph-local state for one whole-loop retry unit.

    Inputs (``task`` / ``module`` / ``context``) mirror the positional arguments
    the live path passes to ``attempt_task`` (``orchestrator.py:4699-4704``).
    ``tool_results`` uses the ``add`` reducer so each attempt's ``ToolResult``
    *appends* rather than overwrites — the accumulation design §3.4 depends on —
    and merges cleanly when this fragment is composed into a parent graph.
    ``retry_result`` carries the full ``attempt_task`` session dict (status,
    final_result, attempts, exhaustion/escalation flags) for downstream
    consumption; ``status`` is the last-write-wins scalar the parent graph reads.
    """

    task: str
    module: str
    context: dict[str, Any]
    tool_results: Annotated[list[ToolResult], add]
    retry_result: dict[str, Any]
    status: str


def make_retry_node(
    engine: RetryEngine,
    execute_fn: ExecuteFn,
    evaluate_fn: EvaluateFn,
    grimoire_search_fn: GrimoireSearchFn | None = None,
    notify_fn: NotifyFn | None = None,
) -> RetryNode:
    """Build the retry delegating node (one node, whole-loop delegation).

    The returned coroutine closes over the live ``engine`` plus the caller's
    closures — the same per-request closures the orchestrator hands
    ``attempt_task`` (``orchestrator.py:4698-4709``). Each invocation runs the
    **entire** 12-attempt retry loop by delegating to
    :meth:`RetryEngine.attempt_task` once; it reimplements no part of the loop, so
    strategy rotation, the fatigue counter, the Grimoire preflight, the
    deterministic / impossibility / empty-loader early-exits, progress
    notifications, and ``_record_session`` all run inside the delegated call. Wire
    it into a graph with a plain ``START → retry → END`` edge — see
    :func:`build_retry_subgraph`.

    Args:
        engine: The live :class:`~modules.shadow.retry_engine.RetryEngine` whose
            ``attempt_task`` loop the node delegates to.
        execute_fn: Async ``(task, strategy_context) -> result dict`` — one
            attempt's execution, identical to the live ``execute_fn`` closure.
        evaluate_fn: ``(result dict) -> {success, confidence, reason}`` — the
            success gate, identical to the live ``evaluate_fn`` closure.
        grimoire_search_fn: Optional ``(query) -> list[dict]`` failure-pattern
            lookup, forwarded so the engine's pre-flight lesson loading runs.
        notify_fn: Optional async ``(msg) -> None`` progress callback, forwarded so
            the engine's attempt 4 / 8 / 12 notifications fire.

    Returns:
        An async LangGraph node that delegates the whole retry loop and writes
        ``tool_results`` / ``retry_result`` / ``status``.
    """

    async def retry(state: RetryCallState) -> RetryCallState:
        # Delegate the WHOLE retry loop to live code. The engine's internal
        # ``for`` loop (retry_engine.py:352) runs untouched: rotation, fatigue,
        # Grimoire preflight, early-exits, notifications, _record_session, and the
        # per-attempt ``retry_attempt`` span all live inside this one call. The
        # node forwards the caller's closures and reimplements none of it.
        retry_result = await engine.attempt_task(
            task=state["task"],
            module=state.get("module", ""),
            context=state.get("context", {}) or {},
            evaluate_fn=evaluate_fn,
            execute_fn=execute_fn,
            grimoire_search_fn=grimoire_search_fn,
            notify_fn=notify_fn,
        )

        # Materialize one ToolResult per real attempt the engine drove, so the
        # append reducer accumulates the attempt trail (design §3.4). The engine
        # returns attempts as dicts via ``_session_to_dict`` (retry_engine.py:888).
        tool_results = [
            ToolResult(
                success=attempt.get("success", False),
                content=attempt.get("result"),
                tool_name="retry_attempt",
                module="retry_engine",
                error=attempt.get("error"),
            )
            for attempt in retry_result.get("attempts", [])
        ]

        return {
            "tool_results": tool_results,
            "retry_result": retry_result,
            "status": retry_result.get("status", "exhausted"),
        }

    return retry


def make_orchestrator_retry_node(orchestrator: "Orchestrator") -> RetryNode:
    """Build the retry node for the parent graph (orchestrator-driven, state-fed).

    Same whole-loop delegation posture as :func:`make_retry_node`, but instead of
    receiving pre-built closures it builds them *at call time from graph state* via
    ``orchestrator._build_retry_closures`` — the **same** method the live
    ``_step5_with_retry`` calls (orchestrator.py), so the closures are
    byte-identical given identical inputs. This is the form the parent graph wires
    on the approved branch (item 12); the closure-arg :func:`make_retry_node` stays
    for the standalone sub-graph + its tests.

    Reads ``user_input`` / ``plan`` / ``classification`` / ``context`` / ``source``
    from state; delegates the whole 12-attempt loop to ``attempt_task`` (rotation,
    fatigue, preflight, early-exits, notifications, ``_record_session`` and the
    per-attempt ``retry_attempt`` span all run inside the one call); writes
    ``tool_results`` / ``retry_result`` / ``status``.

    Args:
        orchestrator: The live orchestrator whose ``_build_retry_closures`` and
            ``_retry_engine`` the node delegates to.
    """

    async def retry(state: ShadowState) -> ShadowState:
        classification = state["classification"]
        plan = state["plan"]

        # Degraded fallback (retry engine unavailable on import): single attempt,
        # mirroring the live ``_retry_engine is None`` branch — delegate to
        # ``_step5_execute`` + ``_step6_evaluate``, wrap as a succeeded session so
        # the caller's ``_resolve_retry_outcome`` returns the response uniformly.
        if orchestrator._retry_engine is None:
            results = await orchestrator._step5_execute(
                plan, classification, state.get("source", "user")
            )
            response = await orchestrator._step6_evaluate(
                state["user_input"], classification, results,
                state.get("context", []) or [],
            )
            return {
                "tool_results": results,
                "retry_result": {
                    "status": "succeeded",
                    "final_result": {"response": response},
                    "attempts": [],
                },
                "status": "succeeded",
            }

        # Build the four closures from graph state — same method the live path
        # uses, so execute_fn/evaluate_fn/grimoire_search_fn/notify_fn match.
        execute_fn, evaluate_fn, grimoire_search_fn, notify_fn = (
            orchestrator._build_retry_closures(
                plan,
                classification,
                state.get("context", []) or [],
                state.get("source", "user"),
            )
        )

        # Delegate the WHOLE loop to live code, building the engine context dict
        # exactly as the live path does (orchestrator.py _step5_with_retry).
        retry_result = await orchestrator._retry_engine.attempt_task(
            task=state["user_input"],
            module=classification.target_module,
            context={
                "task_type": classification.task_type.value,
                "tools": [s.get("tool", "") for s in plan.steps if s.get("tool")],
            },
            evaluate_fn=evaluate_fn,
            execute_fn=execute_fn,
            grimoire_search_fn=grimoire_search_fn,
            notify_fn=notify_fn,
        )

        # Materialize one ToolResult per real attempt (append reducer, design §3.4).
        tool_results = [
            ToolResult(
                success=attempt.get("success", False),
                content=attempt.get("result"),
                tool_name="retry_attempt",
                module="retry_engine",
                error=attempt.get("error"),
            )
            for attempt in retry_result.get("attempts", [])
        ]

        return {
            "tool_results": tool_results,
            "retry_result": retry_result,
            "status": retry_result.get("status", "exhausted"),
        }

    return retry


def build_retry_subgraph(
    engine: RetryEngine,
    execute_fn: ExecuteFn,
    evaluate_fn: EvaluateFn,
    grimoire_search_fn: GrimoireSearchFn | None = None,
    notify_fn: NotifyFn | None = None,
) -> StateGraph:
    """Construct the retry sub-graph builder (not compiled).

    A single ``retry`` node on a plain ``START → retry → END`` path. There is no
    conditional self-edge and no per-attempt topology: the 12-attempt loop is data
    owned by the engine, run whole inside the delegated ``attempt_task`` call. The
    builder closes over the live ``engine`` and the caller's closures so each
    invocation delegates against the same instance — preserving rotation, fatigue,
    preflight, early-exits, notifications, and session recording.
    """
    node = make_retry_node(engine, execute_fn, evaluate_fn, grimoire_search_fn, notify_fn)

    builder = StateGraph(RetryCallState)
    builder.add_node("retry", node)
    builder.add_edge(START, "retry")
    builder.add_edge("retry", END)
    return builder


def compile_retry_subgraph(
    engine: RetryEngine,
    execute_fn: ExecuteFn,
    evaluate_fn: EvaluateFn,
    grimoire_search_fn: GrimoireSearchFn | None = None,
    notify_fn: NotifyFn | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
):
    """Compile the retry sub-graph with an optional async checkpointer.

    Pass a saver from
    :func:`modules.shadow.graph.serde.open_async_sqlite_saver` to get one that is
    already wired with the ``ToolResult``-aware msgpack allowlist.
    """
    builder = build_retry_subgraph(
        engine, execute_fn, evaluate_fn, grimoire_search_fn, notify_fn
    )
    if checkpointer is None:
        return builder.compile()
    return builder.compile(checkpointer=checkpointer)
