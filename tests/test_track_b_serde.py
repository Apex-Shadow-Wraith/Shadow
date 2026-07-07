"""Phase B / Track B — Step 1 serde tests (Task A).

Verifies that ``ToolResult`` round-trips through LangGraph's msgpack serde with
full dataclass identity, equal field values, and zero forward-compat warnings.

Pure in-process tests — no checkpointer, no graph compilation. The
cross-cutting end-to-end round-trip via ``AsyncSqliteSaver`` lives in
``tests/test_track_b_skeleton.py`` once the skeleton lands.
"""

from __future__ import annotations

import logging
import warnings

import pytest

from modules.base import ToolResult
from modules.shadow.graph import build_shadow_serde, shadow_serde


def _make_toolresult() -> ToolResult:
    return ToolResult(
        success=True,
        content={"hits": [{"id": "abc", "text": "memory body"}], "score": 0.91},
        tool_name="memory_search",
        module="grimoire",
        error=None,
        execution_time_ms=12.5,
        metadata={"k": "v", "nested": {"depth": 1}, "list": [1, 2, 3]},
    )


def test_shadow_serde_round_trips_toolresult_in_process() -> None:
    """In-process dumps_typed/loads_typed preserves type identity + fields."""
    serde = build_shadow_serde()
    tr = _make_toolresult()

    typ, blob = serde.dumps_typed(tr)
    restored = serde.loads_typed((typ, blob))

    assert typ == "msgpack"
    assert isinstance(restored, ToolResult)
    assert restored == tr
    assert restored.metadata == tr.metadata
    assert restored.content == tr.content


def test_shadow_serde_emits_no_unregistered_type_warnings(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """LangGraph's default serde fires a one-time warning per unknown dataclass.

    Shadow's serde registers ``ToolResult`` on the msgpack allowlist, so a
    fresh dumps/loads cycle must not log the unregistered-type warning that
    LangGraph emits via :pymod:`langgraph.checkpoint.serde.jsonplus`.
    """
    serde = build_shadow_serde()
    tr = _make_toolresult()

    caplog.set_level(logging.WARNING, logger="langgraph.checkpoint.serde.jsonplus")
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # turn any Python warning into an exception
        typ, blob = serde.dumps_typed(tr)
        restored = serde.loads_typed((typ, blob))

    assert isinstance(restored, ToolResult)
    offenders = [
        rec for rec in caplog.records
        if "Deserializing unregistered type" in rec.getMessage()
        and "modules.base.ToolResult" in rec.getMessage()
    ]
    assert offenders == [], (
        f"shadow_serde must not log unregistered-type warning for ToolResult; "
        f"saw: {[r.getMessage() for r in offenders]}"
    )


def test_shadow_serde_module_singleton_is_built_serializer() -> None:
    """``shadow_serde`` is the cached output of :func:`build_shadow_serde`."""
    assert shadow_serde is not None
    assert type(shadow_serde) is type(build_shadow_serde())
