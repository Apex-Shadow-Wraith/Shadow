"""Retry delegating node + conditional self-edge for the Track B cutover (Step 3).

Translates the orchestrator's 12-attempt retry loop into a LangGraph fragment
whose **defining property is a conditional self-edge**: a single
``retry_attempt`` node that loops back onto itself while the engine's verdict
says "retry again" and exits to ``END`` on "succeeded" or "exhausted". Lives at
``modules/shadow/graph/retry_graph.py`` and is imported by exactly one caller in
the repo today — :mod:`tests.test_retry_graph`. Nothing on the orchestrator path
references this module, which is the strongest possible feature flag (physical
separation), identical to the posture of the Apex node and the dispatcher
sub-graph.

Rotation is data, not topology (design §3.5 / §6.4)
===================================================

The 12-strategy rotation table lives in :data:`RetryEngine.STRATEGY_CATEGORIES`
and is selected per attempt by
:meth:`RetryEngine.get_strategy_for_attempt` (``retry_engine.py:701``). This
node **delegates** that selection rather than encoding the rotation as graph
structure. There is deliberately **one** node, not an unrolled
``retry-1 → retry-2 → … → retry-12`` chain: forking the rotation into topology
would duplicate the strategy table + fatigue logic into graph edges, drift from
the engine, and break the 40 tests in ``tests/test_retry_engine.py`` that pin the
rotation contract. The loop *count* is therefore data — it comes from how many
times the engine's verdict says "retry", not from a fixed number of nodes.

The §6.4 decision is explicit: "keep ``RetryEngine`` as a class invoked from a
single graph node that loops via a conditional self-edge." This module is that
node. The live ``for attempt_num in range(...)`` loop inside
:meth:`RetryEngine.attempt_task` (``retry_engine.py:352``) becomes the graph's
self-edge; the *body* of one iteration becomes one node visit. Because
``attempt_task`` exhausts all 12 attempts internally and exposes no single-attempt
public primitive, the node drives one attempt per visit by composing the engine's
public surface — it never reimplements the rotation it delegates:

- **how to attempt** — :meth:`RetryEngine.get_strategy_for_attempt` (rotation)
  and :meth:`RetryEngine._build_strategy_context` (the exact context the live
  path hands ``execute_fn``); same delegating posture as ``dispatch_node`` calling
  the underscore-private :meth:`Orchestrator._step5_execute`.
- **failure classification** — the module-level :func:`classify_failure`.
- **whether to give up** — :meth:`RetryEngine.should_escalate`, which owns the
  "exhausted at max_attempts / hardware impossibility" decision
  (``retry_engine.py:727``).

State / reducer
===============

``RetryCallState.tool_results`` uses the same ``Annotated[list[ToolResult], add]``
reducer as :class:`modules.shadow.graph.skeleton.ShadowState`, so each attempt's
``ToolResult`` *accumulates* across the self-loop (design §3.4: "retry attempts
and multi-tool plans accumulate naturally") and merges cleanly when this fragment
is composed into a parent graph. ``attempts`` accumulates the engine's
:class:`Attempt` records under the same append reducer so
``get_strategy_for_attempt`` sees the full prior-attempt history on every visit —
that history is what makes the rotation non-repeating.

The node writes ``verdict`` once per visit; the conditional edge is a *thin read*
of that already-decided value (``_route``). The engine owns rotation and the
give-up decision; the edge owns nothing but the loop-or-exit branch.

Observability
=============

Unlike every other Track B node (all span-silent), this node **emits** the
``retry_attempt`` span — because the live per-attempt path emits it
(``retry_engine.py:358-364``) and updates its metadata afterward
(``retry_engine.py:425-432``). Span parity means preserving what live emits,
not stripping it: dropping the span here would lose per-attempt observability the
live loop has. The outer parent ``shadow.module_dispatch`` span the orchestrator
wraps Step 5 + retry with (``orchestrator.py:1369-1372``) is emitted from outside
this fragment, exactly as it nests over the live call.
"""

from __future__ import annotations

import logging
import time
from operator import add
from typing import Annotated, Any, Awaitable, Callable, Literal, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from modules.base import ToolResult
from modules.shadow.retry_engine import (
    Attempt,
    RetryEngine,
    RetrySession,
    classify_failure,
    observed_span,
)

logger = logging.getLogger("shadow.graph.retry_graph")

# Caller-supplied attempt + evaluation hooks, matching the live closures the
# orchestrator builds inside ``_step5_dispatch_with_retry`` and hands to
# ``RetryEngine.attempt_task`` (``orchestrator.py:4698-4709``).
ExecuteFn = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]
EvaluateFn = Callable[[dict[str, Any]], dict[str, Any]]
RetryNode = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class RetryCallState(TypedDict, total=False):
    """Sub-graph-local state for one retry session driven across the self-edge.

    ``attempts`` and ``tool_results`` both use the ``add`` reducer so each
    self-loop visit *appends* its :class:`Attempt` record and its
    :class:`ToolResult` rather than overwriting — the accumulation the rotation
    (non-repeating strategies) and design §3.4 both depend on. ``verdict`` /
    ``status`` are last-write-wins scalars: the latest visit's decision is the
    current one the conditional edge reads.
    """

    task: str
    module: str
    context: dict[str, Any]
    failure_context: str
    attempts: Annotated[list[Attempt], add]
    tool_results: Annotated[list[ToolResult], add]
    verdict: str
    status: str


def _route(state: RetryCallState) -> Literal["retry", "succeeded", "exhausted"]:
    """Conditional self-edge predicate — a thin read of the engine's verdict.

    The node already computed and stored the verdict (via
    :meth:`RetryEngine.should_escalate`); the edge owns nothing but mapping that
    value to "loop back onto the node" (``"retry"``) or "exit to END"
    (``"succeeded"`` / ``"exhausted"``). This is the load-bearing rotation-as-data
    property: the loop count is whatever the engine's verdicts produce, never a
    fixed topology.
    """
    return state.get("verdict", "exhausted")  # type: ignore[return-value]


def make_retry_node(
    engine: RetryEngine,
    execute_fn: ExecuteFn,
    evaluate_fn: EvaluateFn,
) -> RetryNode:
    """Build the retry delegating node (a single node, not an unrolled chain).

    The returned coroutine closes over the live ``engine`` plus the caller's
    ``execute_fn`` / ``evaluate_fn`` (the same per-request closures the
    orchestrator hands ``attempt_task``). Each invocation runs **one** attempt,
    delegating strategy rotation, context-building, failure classification, and
    the give-up decision to the engine, then writes the verdict the self-edge
    reads. Wire it into a graph with a conditional self-edge — see
    :func:`build_retry_subgraph`.

    Args:
        engine: The live :class:`~modules.shadow.retry_engine.RetryEngine` whose
            rotation and escalation surface the node delegates to.
        execute_fn: Async ``(task, strategy_context) -> result dict`` — one
            attempt's execution, identical to the live ``execute_fn`` closure.
        evaluate_fn: ``(result dict) -> {success, confidence, reason}`` — the
            success gate, identical to the live ``evaluate_fn`` closure.

    Returns:
        An async LangGraph node that performs one attempt and updates
        ``attempts`` / ``tool_results`` / ``verdict`` / ``status``.
    """

    async def retry_attempt(state: RetryCallState) -> RetryCallState:
        task = state["task"]
        module = state.get("module", "")
        context = state.get("context", {}) or {}
        failure_context = state.get("failure_context", "")
        prior_attempts: list[Attempt] = list(state.get("attempts", []))
        task_type = context.get("task_type", "general")

        attempt_num = len(prior_attempts) + 1

        # Delegated: rotation. The engine picks the next non-repeating strategy.
        strategy_name, strategy_desc = engine.get_strategy_for_attempt(
            attempt_num, prior_attempts
        )

        # Span parity: the live per-attempt path opens this exact span
        # (retry_engine.py:358-364). Span-silence here would drop observability
        # the live loop has.
        with observed_span(
            "retry_attempt",
            attempt_number=attempt_num,
            strategy=strategy_name,
            task_type=task_type,
            module=module,
        ) as retry_span:
            # Delegated: the engine builds the exact strategy context the live
            # path passes to execute_fn (history of prior failures included).
            strategy_context = engine._build_strategy_context(
                task=task,
                attempt_num=attempt_num,
                strategy_name=strategy_name,
                strategy_desc=strategy_desc,
                previous_attempts=prior_attempts,
                failure_context=failure_context,
                extra_context=context,
            )

            start_time = time.time()
            attempt = Attempt(
                attempt_number=attempt_num,
                strategy=strategy_name,
                approach_description=strategy_desc,
                tools_used=context.get("tools", []),
            )

            try:
                result = await execute_fn(task, strategy_context)
                attempt.duration_seconds = time.time() - start_time
                attempt.result = result
                evaluation = evaluate_fn(result)
                attempt.success = evaluation.get("success", False)
                if not attempt.success:
                    attempt.error = evaluation.get("reason", "Evaluation failed")
                    attempt.failure_type = classify_failure(
                        attempt.error, attempt.result
                    )
            except Exception as exc:  # mirror retry_engine.py:407-418
                attempt.duration_seconds = time.time() - start_time
                attempt.error = str(exc)
                attempt.success = False
                attempt.failure_type = classify_failure(str(exc))
                logger.warning(
                    "Retry attempt %d (%s) raised exception: %s",
                    attempt_num, strategy_name, exc,
                )

            # Span metadata parity with retry_engine.py:425-432.
            if retry_span is not None:
                try:
                    retry_span.update(metadata={
                        "failure_type": attempt.failure_type,
                        "attempt_duration_ms": round(attempt.duration_seconds * 1000),
                        "success": attempt.success,
                        "error": attempt.error[:200] if attempt.error else None,
                    })
                except Exception as span_err:
                    logger.debug("retry_span update failed: %s", span_err)

        # Verdict: success short-circuits; otherwise the engine owns the
        # give-up decision (max_attempts reached / hardware impossibility).
        # Build a session carrying the full attempt history so should_escalate
        # sees the real count — the node decides nothing the engine doesn't.
        session = RetrySession(
            original_task=task,
            task_type=task_type,
            module=module,
            attempts=prior_attempts + [attempt],
        )
        if attempt.success:
            verdict = "succeeded"
        elif engine.should_escalate(session):
            verdict = "exhausted"
        else:
            verdict = "retry"

        tool_result = ToolResult(
            success=attempt.success,
            content=attempt.result,
            tool_name="retry_attempt",
            module="retry_engine",
            error=attempt.error,
        )

        return {
            "attempts": [attempt],
            "tool_results": [tool_result],
            "verdict": verdict,
            "status": verdict,
        }

    return retry_attempt


def build_retry_subgraph(
    engine: RetryEngine,
    execute_fn: ExecuteFn,
    evaluate_fn: EvaluateFn,
) -> StateGraph:
    """Construct the retry sub-graph builder (not compiled).

    The defining structure is the conditional **self-edge** out of
    ``retry_attempt``: ``"retry"`` loops back onto the same node, ``"succeeded"``
    and ``"exhausted"`` route to ``END``. The engine's verdict — not a fixed node
    count — decides how many times the loop fires.
    """
    node = make_retry_node(engine, execute_fn, evaluate_fn)

    builder = StateGraph(RetryCallState)
    builder.add_node("retry_attempt", node)
    builder.add_edge(START, "retry_attempt")
    builder.add_conditional_edges(
        "retry_attempt",
        _route,
        {"retry": "retry_attempt", "succeeded": END, "exhausted": END},
    )
    return builder


def compile_retry_subgraph(
    engine: RetryEngine,
    execute_fn: ExecuteFn,
    evaluate_fn: EvaluateFn,
    checkpointer: BaseCheckpointSaver | None = None,
):
    """Compile the retry sub-graph with an optional async checkpointer.

    Pass a saver from
    :func:`modules.shadow.graph.serde.open_async_sqlite_saver` to get one that is
    already wired with the ``ToolResult``-aware msgpack allowlist.
    """
    builder = build_retry_subgraph(engine, execute_fn, evaluate_fn)
    if checkpointer is None:
        return builder.compile()
    return builder.compile(checkpointer=checkpointer)
