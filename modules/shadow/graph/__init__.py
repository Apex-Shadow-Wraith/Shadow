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
"""

from __future__ import annotations

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
    "ShadowState",
    "build_shadow_serde",
    "build_skeleton",
    "compile_skeleton",
    "open_async_sqlite_saver",
    "shadow_serde",
]
