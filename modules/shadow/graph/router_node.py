"""Router delegating node for the Track B cutover.

A single delegating LangGraph *node* — **not** a sub-graph — that hands the
route decision to the live :meth:`Orchestrator._step2_classify` coroutine and
bridges cross-invocation route memory between the orchestrator's private
``_last_route`` attribute and the checkpointed ``state["last_route"]`` graph
key. Lives at ``modules/shadow/graph/router_node.py`` and is imported by
exactly one caller in the repo today — :mod:`tests.test_router_node`. Nothing
on the orchestrator path references it, which is the strongest possible feature
flag (physical separation), identical to the posture of every other Track B
node and sub-graph.

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

The ``last_route`` bridge (the load-bearing seam)
=================================================

The live contextual-reference re-route reads ``self._last_route``
(``orchestrator.py:2173`` — "do that" / "yes proceed" returns a clone of the
previous route at ``confidence=0.90``). Cross-invocation route memory, however,
is carried in the checkpointed ``state["last_route"]`` keyed by ``thread_id``
(``skeleton.py:12-14``), and a fresh orchestrator always starts with
``self._last_route = None`` (``orchestrator.py:370``). So the node must bridge
the two on every invocation:

1. **Hydrate IN** — ``orchestrator._last_route = state.get("last_route")``
   *before* delegating, so the pre-graph contextual read sees the prior turn's
   route even on a fresh orchestrator resuming from a checkpoint.
2. **Delegate** — ``classification = await orchestrator._step2_classify(...)``.
3. **Mirror the live write** — ``orchestrator._last_route = classification``
   (parity with the write at ``orchestrator.py:1201``).
4. **Persist OUT** — return ``{"classification": ..., "last_route": ...}`` so
   the checkpoint carries the new route to the next invocation.

Miss step 1 and the failure is silent: invocation N+1's
``_fast_path_classify`` sees ``self._last_route = None``, the contextual branch
never fires, the input falls through to keyword matching, and route memory
appears to "not work" with no error anywhere. ``tests.test_router_node`` pins
this with a cross-invocation test that resumes a fresh orchestrator from the
same checkpoint.

Concurrency hazard (documented, deferred)
=========================================

Steps 1 and 3 mutate the shared ``orchestrator._last_route`` instance
attribute. This is correct under sequential invocation, but under concurrent
node execution across distinct ``thread_id``s it becomes a cross-``thread_id``
route-memory leak (the per-thread ``state["last_route"]`` checkpoint is fine;
the shared live attribute is the leak). The pure-state fix — make the
contextual read at ``orchestrator.py:2173`` consume ``state["last_route"]``
instead of ``self._last_route`` — requires touching ``_fast_path_classify`` and
is therefore blocked by the orchestrator-untouched constraint of this additive
step. Tracked as ``docs/phase-b/track-b/cutover-backlog.md`` item 9, deferred to
the parent-graph integration step.

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
            instance to delegate the route decision to. The node reads and
            mutates its private ``_last_route`` attribute to bridge
            cross-invocation route memory (see module docstring).

    Returns:
        An async LangGraph node that reads ``user_input`` and ``last_route``
        from state, delegates the route decision to
        :meth:`Orchestrator._step2_classify`, and returns a partial update
        writing ``classification`` and the checkpointed ``last_route``.
    """

    async def router_node(state: dict[str, Any]) -> dict[str, Any]:
        # 1. Bridge IN: hydrate the live attribute from checkpointed graph
        #    state so the contextual-reference re-route sees the prior turn's
        #    route even on a fresh orchestrator resuming from a checkpoint.
        orchestrator._last_route = state.get("last_route")

        # 2. Delegate to the live classifier — preserves the fast-path
        #    classifier, the Session-47 override, the LLM router, and the
        #    keyword fallback byte-for-byte.
        classification = await orchestrator._step2_classify(state["user_input"])

        # 3. Mirror the live write (parity with orchestrator.py:1201).
        orchestrator._last_route = classification

        # 4. Bridge OUT: persist the new route into checkpointed state so the
        #    next invocation on this thread_id resumes with it.
        return {"classification": classification, "last_route": classification}

    return router_node
