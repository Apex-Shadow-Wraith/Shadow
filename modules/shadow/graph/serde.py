"""Checkpoint serde wiring for the LangGraph cutover.

LangGraph's default :class:`JsonPlusSerializer` is permissive — it round-trips
any dataclass but logs a one-time forward-compat warning per unregistered type:

    Deserializing unregistered type modules.base.ToolResult from checkpoint.
    This will be blocked in a future version.

Track B's cutover lands well before that future version, but the warning is a
real signal: when LangGraph flips the default to strict, an unregistered
``ToolResult`` will silently degrade to a plain ``dict`` on resume and break
every node that does attribute access. Registering it now is the cheap fix.

This module exposes a pre-configured serializer (:data:`shadow_serde`) and an
:func:`open_async_sqlite_saver` async context manager so callers don't have to
re-thread the allowlist at every construction site.

Scope: serde wiring only. The :class:`ToolResult` schema is owned by Phase D.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import aiosqlite
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from modules.base import ToolResult

# Types that must round-trip through checkpoints with full dataclass identity.
# Add new entries here when a module exposes its own state-carrier dataclass to
# the graph; do NOT widen this to a module prefix — the allowlist is exact-match
# by design (see LangGraph GHSA-fjqc-hq36-qh5p for the reasoning).
_ALLOWED_MSGPACK_TYPES: tuple[type, ...] = (ToolResult,)


def build_shadow_serde() -> JsonPlusSerializer:
    """Return a serializer with Shadow's checkpointable types pre-registered.

    A fresh instance is cheap; callers that need an extended allowlist can call
    ``.with_msgpack_allowlist([...])`` on the returned serializer.
    """
    return JsonPlusSerializer().with_msgpack_allowlist(_ALLOWED_MSGPACK_TYPES)


# Module-level singleton — checkpoint savers can share one serializer instance.
shadow_serde: JsonPlusSerializer = build_shadow_serde()


@asynccontextmanager
async def open_async_sqlite_saver(
    conn_string: str,
) -> AsyncIterator[AsyncSqliteSaver]:
    """Open an :class:`AsyncSqliteSaver` wired to :data:`shadow_serde`.

    Mirrors ``AsyncSqliteSaver.from_conn_string`` but injects Shadow's serde.
    The underlying ``aiosqlite`` connection is closed when the context exits.

    Use ``":memory:"`` for ephemeral state in tests; a filesystem path for
    cross-process persistence.
    """
    async with aiosqlite.connect(conn_string) as conn:
        yield AsyncSqliteSaver(conn, serde=shadow_serde)
