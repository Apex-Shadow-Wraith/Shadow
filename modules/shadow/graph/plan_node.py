"""Planner delegating node for the Track B cutover (parent-graph wiring step).

A single delegating LangGraph *node* — **not** a sub-graph — that hands the
whole Step-4 plan generation (and its embedded Cerberus safety gate) to the live
:meth:`Orchestrator._step4_plan` coroutine and writes the resulting
:class:`ExecutionPlan` onto ``state["plan"]``. Lives at
``modules/shadow/graph/plan_node.py``; nothing on the orchestrator path imports
it (physical-separation feature flag, identical to every other Track B node).

Why a node, not a sub-graph
===========================

Plan generation is a single step that writes ``state["plan"]`` directly onto
:class:`~modules.shadow.graph.skeleton.ShadowState`; there is no internal
fan-out to wrap. Like the router node, it composes onto the parent graph as one
``builder.add_node(...)`` with no nested ``StateGraph`` / compile boundary.

Whole-method delegation (why this hands the *entire* ``_step4_plan`` to live code)
=================================================================================

``_step4_plan`` (``orchestrator.py:3850-4483``) is ~94% pure keyword→``steps``
construction, but it carries a side-effect surface a thinner reconstruction would
silently drop — the same "thin delegator drops behavior" trap that the retry
self-edge node hit (``cutover-backlog.md`` item 10). The node therefore delegates
the **whole** method in one call and reconstructs nothing. The complete surface
that runs *inside* the delegated call:

1. **Transitive Cerberus dispatch** — ``await cerberus.execute("safety_check", ...)``
   per tool-bearing step (``orchestrator.py:4445-4452``). This transitively fires,
   inside Cerberus: the **heartbeat write** ``data/cerberus_heartbeat.json`` via
   ``send_heartbeat()`` (``cerberus.py:238``) that the external
   ``daemons/cerberus_watchdog/`` polls — a duplicating planner that skipped the
   ``safety_check`` loop would sever it — and the ``_record_call`` increment.
2. **``cerberus_approved`` verdict write** — ``False`` on the first DENY
   (``orchestrator.py:4463``, short-circuit ``return``), ``True`` after the loop
   (``:4474``), ``True`` early for the ``direct`` route (``:3870``). This is the
   value the parent's plan-gate (``dispatch_graph.plan_gate``) reads.
3. **``_background`` param injection** — when ``_detect_background_intent`` is true,
   ``plan.steps[].params["_background"]=True`` (``orchestrator.py:4477-4481``).
4. Logging (DENY / APPROVAL_REQUIRED / background-intent) and the read-only
   internal helpers (``_build_apex_context``, ``_extract_search_query``,
   ``_detect_background_intent``, ``self._smart_brain``).

Verified ABSENT from ``_step4_plan`` (so the node need not preserve them
separately): no ``_record_session``, no ``notify_fn`` / progress notifications, no
Grimoire write, no ``observed_span``, no ``_last_route`` touch, no ``_pending_*``
mutation (APPROVAL_REQUIRED is a log-only Phase-1 stub at ``:4471-4472`` — it does
**not** set ``cerberus_approved=False``; the plan still ends approved).

``context`` passthrough
=======================

``_step4_plan`` takes a ``context`` argument but does not read it in any branch
(it plans from ``user_input`` + ``classification`` only); it is threaded for
signature parity. Step-3 context loading is not yet a graph node, so the node
forwards ``state.get("context", [])`` — empty by default — which is behavior-
identical for ``_step4_plan`` today. (The full Step-3 → Step-6 context path is a
flip-step concern; see ``cutover-backlog.md``.)

Observability
=============

Zero ``observed_span`` calls inside the node — matches the live ``_step4_plan``,
which opens no span (the only spans over the decision loop are the caller-level
``shadow.router_decision`` / ``module_dispatch`` / ``response_assembly`` the
orchestrator emits from ``process_input``, not from the step methods).
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from modules.shadow.orchestrator import Orchestrator

PlanNode = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def make_plan_node(orchestrator: Orchestrator) -> PlanNode:
    """Build the planner delegating node (a single node, not a sub-graph).

    The returned coroutine closes over ``orchestrator`` so each invocation plans
    against the same instance — preserving its registry (and therefore the
    embedded per-step Cerberus ``safety_check`` loop and heartbeat seam). Wire it
    into a parent graph with ``builder.add_node("plan", make_plan_node(orch))``;
    there is no compile / sub-graph wrapper to call.

    Args:
        orchestrator: The live :class:`~modules.shadow.orchestrator.Orchestrator`
            whose :meth:`~modules.shadow.orchestrator.Orchestrator._step4_plan`
            the node delegates to.

    Returns:
        An async LangGraph node that reads ``user_input`` / ``classification``
        (and optional ``context``) from state, delegates the whole Step-4 plan
        generation to :meth:`Orchestrator._step4_plan`, and returns a partial
        update writing ``plan``.
    """

    async def plan_node(state: dict[str, Any]) -> dict[str, Any]:
        # Delegate the WHOLE Step-4 plan generation to live code. The per-step
        # Cerberus safety_check loop (heartbeat seam + cerberus_approved verdict)
        # and the _background param injection all run inside this one call; the
        # node reconstructs none of it.
        plan = await orchestrator._step4_plan(
            state["user_input"],
            state["classification"],
            state.get("context", []) or [],
        )
        return {"plan": plan}

    return plan_node
