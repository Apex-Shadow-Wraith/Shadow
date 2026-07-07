"""LangGraph cutover package (Track B).

Additive scaffolding for the Phase B LangGraph migration. Nothing in this
package is imported by the live orchestrator path yet — it exists so each
migration step can land on the feature branch with its own tests behind a
stable namespace.

Public surface:
- ``shadow_serde`` — :class:`JsonPlusSerializer` with ``ToolResult`` registered
  on the msgpack allowlist, so checkpoints can carry a ``ToolResult`` without
  the forward-compat warning fired by the default permissive allowlist.
- ``open_async_sqlite_saver`` — async context manager that yields an
  ``AsyncSqliteSaver`` wired to ``shadow_serde``.
- ``ShadowState`` — TypedDict matching the design doc (§3.4 + ``last_route``
  checkpoint key from §3.6).
- ``build_skeleton`` / ``compile_skeleton`` — pass-through ``StateGraph`` that
  compiles and ``ainvoke``s end-to-end. Used only by skeleton tests.
- ``GrimoireCallState`` / ``build_grimoire_subgraph`` /
  ``compile_grimoire_subgraph`` — Grimoire sub-graph that delegates dispatch
  to the live :meth:`GrimoireModule.execute`. Additive; nothing on the
  orchestrator path imports it.
- ``CerberusCallState`` / ``build_cerberus_subgraph`` /
  ``compile_cerberus_subgraph`` — Cerberus sub-graph that delegates dispatch
  to the live :meth:`Cerberus.execute`. Same additive posture; delegation
  preserves the heartbeat side effect the external watchdog daemon depends
  on.
- ``ApexNode`` / ``make_apex_node`` — Apex *delegating node* (not a
  sub-graph) that hands dispatch to the live :meth:`Apex.execute`. Single
  node per design doc §4 (Apex is the fallback leg wired directly into the
  parent graph); no ``StateGraph`` / compile wrapper. Same additive posture.
- ``WraithNode`` / ``make_wraith_node``, ``ReaperNode`` /
  ``make_reaper_node``, ``HarbingerNode`` / ``make_harbinger_node``,
  ``NovaNode`` / ``make_nova_node``, ``OmenNode`` / ``make_omen_node``,
  ``ShadowModuleNode`` / ``make_shadow_module_node`` — six more *delegating
  nodes* (not sub-graphs) over the flat-dispatch leaf modules, each handing
  dispatch to the module's live ``execute``. All span-silent at the node
  layer; Reaper additionally preserves its inner-engine ``reaper.search``
  spans by delegating through ``execute`` rather than duplicating dispatch.
  Same additive posture — nothing on the orchestrator path imports them.
- ``RouterNode`` / ``make_router_node`` — router *delegating node* (not a
  sub-graph) that hands the route decision to the live
  :meth:`Orchestrator._step2_classify` and bridges cross-invocation route
  memory between ``Orchestrator._last_route`` and the checkpointed
  ``state["last_route"]``. Span-silent at the node layer; preserves the
  fast-path classifier, the Session-47 override, the LLM router, and the
  keyword fallback by delegation. Same additive posture.
- ``build_dispatch_subgraph`` / ``compile_dispatch_subgraph`` — dispatcher
  sub-graph that lifts the plan-level Cerberus short-circuit onto a conditional
  edge (``cerberus_approved=False`` → terminal ``blocked`` node, never reaching a
  module) and delegates the per-step loop to the live
  :meth:`Orchestrator._step5_execute`. Preserves the three-verdict per-tool hook,
  the heartbeat seam, and the async/post-hook surface by delegation. Same
  additive posture — nothing on the orchestrator path imports it.
- ``RetryCallState`` / ``make_retry_node`` / ``build_retry_subgraph`` /
  ``compile_retry_subgraph`` — retry *delegating node* (single ``retry`` node,
  ``START → retry → END``, **no self-edge**) that delegates the *whole* 12-attempt
  loop to live code via one :meth:`RetryEngine.attempt_task` call, forwarding the
  same ``execute_fn`` / ``evaluate_fn`` / ``grimoire_search_fn`` / ``notify_fn``
  closures the live path builds. Supersedes the prior self-edge node, which
  reimplemented the loop from lower-level primitives and dropped 5 behaviors
  (deterministic early-exit, fatigue counter, Grimoire preflight, progress
  notifications, ``_record_session``); whole-call delegation runs all of them
  inside the engine and preserves the live ``retry_attempt`` span. The node layer
  is span-silent. Same additive posture — nothing on the orchestrator path imports
  it.
- ``make_routable_gate`` / ``build_routable_gate_subgraph`` /
  ``compile_routable_gate_subgraph`` — routable-module reachability gate that
  lifts the live ``registry.is_routable()`` dormancy filter onto a conditional
  edge: a non-routable target (currently Morpheus when ``config.morpheus.enabled``
  is False) routes to a terminal ``dormant`` node and never reaches a module, while
  a routable target reaches a ``dispatch`` node that delegates the per-step loop to
  the live :meth:`Orchestrator._step5_execute`. General (any non-routable module),
  not Morpheus-special, and **defense-in-depth** over the router's upstream
  ``is_routable`` filtering. Span-silent. Same additive posture — nothing on the
  orchestrator path imports it.
"""

from __future__ import annotations

from modules.shadow.graph.apex_node import (
    ApexNode,
    make_apex_node,
)
from modules.shadow.graph.harbinger_node import (
    HarbingerNode,
    make_harbinger_node,
)
from modules.shadow.graph.nova_node import (
    NovaNode,
    make_nova_node,
)
from modules.shadow.graph.omen_node import (
    OmenNode,
    make_omen_node,
)
from modules.shadow.graph.reaper_node import (
    ReaperNode,
    make_reaper_node,
)
from modules.shadow.graph.router_node import (
    RouterNode,
    make_router_node,
)
from modules.shadow.graph.shadow_module_node import (
    ShadowModuleNode,
    make_shadow_module_node,
)
from modules.shadow.graph.wraith_node import (
    WraithNode,
    make_wraith_node,
)
from modules.shadow.graph.cerberus_subgraph import (
    CerberusCallState,
    build_cerberus_subgraph,
    compile_cerberus_subgraph,
)
from modules.shadow.graph.dispatch_graph import (
    blocked_node,
    build_dispatch_subgraph,
    compile_dispatch_subgraph,
    make_dispatch_node,
    plan_gate,
)
from modules.shadow.graph.grimoire_subgraph import (
    GrimoireCallState,
    build_grimoire_subgraph,
    compile_grimoire_subgraph,
)
from modules.shadow.graph.morpheus_gate import (
    build_routable_gate_subgraph,
    compile_routable_gate_subgraph,
    dormant_node,
    make_routable_gate,
)
from modules.shadow.graph.parent import (
    build_parent_graph,
    compile_parent_graph,
)
from modules.shadow.graph.plan_node import (
    PlanNode,
    make_plan_node,
)
from modules.shadow.graph.retry_graph import (
    RetryCallState,
    build_retry_subgraph,
    compile_retry_subgraph,
    make_retry_node,
)
from modules.shadow.graph.serde import (
    build_shadow_serde,
    open_async_sqlite_saver,
    shadow_serde,
)
from modules.shadow.graph.skeleton import (
    ShadowState,
    build_skeleton,
    compile_skeleton,
)

__all__ = [
    "ApexNode",
    "CerberusCallState",
    "GrimoireCallState",
    "HarbingerNode",
    "NovaNode",
    "OmenNode",
    "PlanNode",
    "ReaperNode",
    "RetryCallState",
    "RouterNode",
    "ShadowModuleNode",
    "ShadowState",
    "WraithNode",
    "blocked_node",
    "build_cerberus_subgraph",
    "build_dispatch_subgraph",
    "build_grimoire_subgraph",
    "build_parent_graph",
    "build_retry_subgraph",
    "build_routable_gate_subgraph",
    "build_shadow_serde",
    "build_skeleton",
    "compile_cerberus_subgraph",
    "compile_dispatch_subgraph",
    "compile_grimoire_subgraph",
    "compile_parent_graph",
    "compile_retry_subgraph",
    "compile_routable_gate_subgraph",
    "compile_skeleton",
    "dormant_node",
    "make_apex_node",
    "make_dispatch_node",
    "make_harbinger_node",
    "make_nova_node",
    "make_omen_node",
    "make_plan_node",
    "make_reaper_node",
    "make_retry_node",
    "make_routable_gate",
    "make_router_node",
    "make_shadow_module_node",
    "make_wraith_node",
    "open_async_sqlite_saver",
    "plan_gate",
    "shadow_serde",
]
