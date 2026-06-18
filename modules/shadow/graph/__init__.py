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
"""

from __future__ import annotations

from modules.shadow.graph.apex_node import (
    ApexNode,
    make_apex_node,
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
    "ShadowState",
    "build_cerberus_subgraph",
    "build_grimoire_subgraph",
    "build_shadow_serde",
    "build_skeleton",
    "compile_cerberus_subgraph",
    "compile_grimoire_subgraph",
    "compile_skeleton",
    "make_apex_node",
    "open_async_sqlite_saver",
    "shadow_serde",
]
