"""LangGraph cutover package (Track B).

Additive scaffolding for the Phase B LangGraph migration. Nothing in this
package is imported by the live orchestrator path yet — it exists so each
migration step can land on the feature branch with its own tests behind a
stable namespace.

Public surface (Step 1 — serde wiring):
- ``shadow_serde`` — :class:`JsonPlusSerializer` with ``ToolResult`` registered
  on the msgpack allowlist, so checkpoints can carry a ``ToolResult`` without
  the forward-compat warning fired by the default permissive allowlist.
- ``open_async_sqlite_saver`` — async context manager that yields an
  ``AsyncSqliteSaver`` wired to ``shadow_serde``.
"""

from __future__ import annotations

from modules.shadow.graph.serde import (
    build_shadow_serde,
    open_async_sqlite_saver,
    shadow_serde,
)

__all__ = [
    "build_shadow_serde",
    "open_async_sqlite_saver",
    "shadow_serde",
]
