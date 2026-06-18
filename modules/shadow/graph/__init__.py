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
from modules.shadow.graph.grimoire_subgraph import (
    GrimoireCallState,
    build_grimoire_subgraph,
    compile_grimoire_subgraph,
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
    "ReaperNode",
    "RouterNode",
    "ShadowModuleNode",
    "ShadowState",
    "WraithNode",
    "build_cerberus_subgraph",
    "build_grimoire_subgraph",
    "build_shadow_serde",
    "build_skeleton",
    "compile_cerberus_subgraph",
    "compile_grimoire_subgraph",
    "compile_skeleton",
    "make_apex_node",
    "make_harbinger_node",
    "make_nova_node",
    "make_omen_node",
    "make_reaper_node",
    "make_router_node",
    "make_shadow_module_node",
    "make_wraith_node",
    "open_async_sqlite_saver",
    "shadow_serde",
]
