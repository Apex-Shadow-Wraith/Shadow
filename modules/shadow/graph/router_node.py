"""Router delegating node for the Track B cutover.

A single delegating LangGraph *node* — **not** a sub-graph — that hands the
route decision to the live :meth:`Orchestrator._step2_classify` coroutine,
passing the per-``thread_id`` route memory from the checkpointed
``state["last_route"]`` graph key straight through as the ``last_route``
parameter. Lives at ``modules/shadow/graph/router_node.py``. At the flip it is
wired into the parent graph as the ``router`` node and is also exercised
standalone by :mod:`tests.test_router_node`.

Why a node, not a sub-graph
===========================

The route decision is a single classification step that writes
``state["classification"]`` and ``state["last_route"]`` directly onto
``ShadowState``; there is no internal fan-out to wrap. Like the Apex fallback
leg, it composes onto the parent ``ShadowState`` graph as one
``builder.add_node(...)`` with no nested ``StateGraph`` / compile boundary, so a
dedicated ``RouterCallState`` / ``build_router_subgraph`` surface would be dead
weight.

Delegation
==========

The node calls ``orchestrator._step2_classify(user_input)`` and never
reimplements classification. That preserves the whole route-decision surface
byte-for-byte:

- the fast-path classifier (``_fast_path_classify``), including the eight
  command-prefix escape hatches, the contextual-reference re-route, and the
  Session-47 informational-guard override at
  ``modules/shadow/orchestrator.py:2736-2741``;
- the LLM router (``_ollama_chat`` at ``orchestrator.py:1975``) at
  ``confidence=0.70``;
- the keyword fallback (``_fallback_classify``) at ``confidence=0.50``,
  defaulting to ``target_module="direct"``.

A duplicating router would create a second drift-prone copy of all three tiers
and silently lose the override the moment either side changed.

Route memory flows purely through state (item-9 leak closed at the flip)
========================================================================

The contextual-reference re-route (``orchestrator.py:2173`` — "do that" / "yes
proceed" returns a clone of the previous route at ``confidence=0.90``) now reads
the ``last_route`` **parameter** the classifier receives, not the shared
``self._last_route`` attribute. Cross-invocation route memory is carried in the
checkpointed ``state["last_route"]`` keyed by ``thread_id`` (``skeleton.py``).
So the node:

1. **Delegate** — ``await orchestrator._step2_classify(state["user_input"],
   last_route=state.get("last_route"))``, passing the per-``thread_id`` route
   memory explicitly. ``_step2_classify`` forwards it to ``_fast_path_classify``,
   whose contextual branch reads the parameter (``orchestrator.py``), never the
   shared attribute.
2. **Persist OUT** — return ``{"classification": ..., "last_route": ...}`` so the
   checkpoint carries the new route to the next invocation on this ``thread_id``.

Because the node neither reads nor writes ``orchestrator._last_route``, the
former cross-``thread_id`` leak (backlog item 9) is closed: concurrent
invocations on distinct ``thread_id``s each pass their own checkpointed
``last_route`` and cannot observe each other's route memory. The sentinel
default on ``_step2_classify`` / ``_fast_path_classify`` distinguishes "caller
passed ``last_route`` explicitly" (graph path — used verbatim, even ``None``)
from "omitted" (legacy single-threaded callers + direct-classify tests — fall
back to ``self._last_route``). ``tests.test_router_node`` pins the
cross-invocation behavior by resuming a fresh orchestrator from the same
checkpoint.

Observability
=============

Zero ``observed_span`` calls inside the node — matches the live route path,
which has zero spans inside ``_step2_classify`` / ``_fast_path_classify`` /
``_fallback_classify`` (verified by grep). The only span over routing in the
live path is the parent ``shadow.router_decision`` the orchestrator emits at
``orchestrator.py:1193``; when this node is wired into a parent graph, that
parent span wraps the node invocation as outer, matching live exactly. Adding a
span inside the node would be instrumentation the live path lacks.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from modules.shadow.orchestrator import Orchestrator

RouterNode = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def make_router_node(orchestrator: Orchestrator) -> RouterNode:
    """Build the router delegating node (a single node, not a sub-graph).

    The returned coroutine closes over ``orchestrator`` so each invocation
    classifies against the same instance. Wire it into a parent graph with
    ``builder.add_node("router", make_router_node(orch))`` — there is no
    compile / sub-graph wrapper to call.

    Args:
        orchestrator: The live :class:`~modules.shadow.orchestrator.Orchestrator`
            instance to delegate the route decision to. The node passes the
            per-``thread_id`` ``state["last_route"]`` to the classifier as a
            parameter; it never reads or mutates the shared ``_last_route``
            attribute (item-9 leak closed — see module docstring).

    Returns:
        An async LangGraph node that reads ``user_input`` and ``last_route``
        from state, delegates the route decision to
        :meth:`Orchestrator._step2_classify`, and returns a partial update
        writing ``classification`` and the checkpointed ``last_route``.
    """

    async def router_node(state: dict[str, Any]) -> dict[str, Any]:
        # Delegate to the live classifier, passing the per-``thread_id`` route
        # memory from checkpointed state EXPLICITLY. The shared
        # ``orchestrator._last_route`` attribute is neither hydrated nor mirrored
        # here — so concurrent invocations on distinct ``thread_id``s cannot leak
        # route memory across each other (item 9 closed). The fast-path
        # classifier, the Session-47 override, the LLM router, and the keyword
        # fallback are preserved byte-for-byte; only the route-memory source moves
        # from the shared attribute to per-thread state.
        classification = await orchestrator._step2_classify(
            state["user_input"], last_route=state.get("last_route")
        )

        # Persist the new route into checkpointed state so the next invocation on
        # this ``thread_id`` resumes with it. Route memory lives only in state.
        return {"classification": classification, "last_route": classification}

    return router_node
