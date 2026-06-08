"""Phase B / Track B — Step 1 skeleton tests (Task B).

End-to-end smoke that the bare graph skeleton compiles on
``AsyncSqliteSaver``, ``ainvoke``s without modifying state, and persists state
to disk so a fresh saver can read it back. Also covers the cross-cutting
checkpoint round-trip of a ``ToolResult`` through the graph's state — the
serde wiring proven in ``tests/test_track_b_serde.py`` carrying real graph
state, not just a direct serializer call.
"""

from __future__ import annotations

import pytest

from modules.base import ToolResult
from modules.shadow.graph import (
    ShadowState,
    compile_skeleton,
    open_async_sqlite_saver,
)


@pytest.mark.asyncio
async def test_skeleton_compiles_and_ainvokes_passthrough(tmp_path) -> None:
    """Skeleton compiles on AsyncSqliteSaver, ainvokes, returns state unchanged."""
    db = tmp_path / "track-b-skeleton.sqlite"

    async with open_async_sqlite_saver(str(db)) as saver:
        graph = compile_skeleton(saver)
        config = {"configurable": {"thread_id": "skeleton-smoke"}}

        seed: ShadowState = {
            "user_input": "hello shadow",
            "response": None,
        }
        result = await graph.ainvoke(seed, config=config)

    assert result["user_input"] == "hello shadow"
    assert result["response"] is None


@pytest.mark.asyncio
async def test_skeleton_checkpoint_persists_state_across_resaver(
    tmp_path,
) -> None:
    """Checkpoint survives saver teardown — proves persistence is on disk."""
    db = tmp_path / "track-b-persist.sqlite"
    thread = "skeleton-persist"
    config = {"configurable": {"thread_id": thread}}
    seed_input = "persisted across processes (well, savers)"

    async with open_async_sqlite_saver(str(db)) as saver:
        graph = compile_skeleton(saver)
        await graph.ainvoke({"user_input": seed_input}, config=config)

    async with open_async_sqlite_saver(str(db)) as saver2:
        graph2 = compile_skeleton(saver2)
        snapshot = await graph2.aget_state(config)

    assert snapshot is not None
    assert snapshot.values["user_input"] == seed_input


@pytest.mark.asyncio
async def test_toolresult_round_trips_through_async_sqlite_checkpoint(
    tmp_path,
) -> None:
    """End-to-end: AsyncSqliteSaver writes + reads ``ToolResult`` losslessly."""
    db = tmp_path / "track-b-serde.sqlite"
    tr = ToolResult(
        success=True,
        content={"hits": [{"id": "abc", "text": "memory body"}], "score": 0.91},
        tool_name="memory_search",
        module="grimoire",
        error=None,
        execution_time_ms=12.5,
        metadata={"k": "v", "nested": {"depth": 1}, "list": [1, 2, 3]},
    )

    async with open_async_sqlite_saver(str(db)) as saver:
        graph = compile_skeleton(saver)
        config = {"configurable": {"thread_id": "serde-round-trip"}}

        result = await graph.ainvoke(
            {"user_input": "round-trip", "tool_results": [tr]},
            config=config,
        )

        assert result["tool_results"] == [tr]
        assert isinstance(result["tool_results"][0], ToolResult)

        snapshot = await graph.aget_state(config)
        assert snapshot.values["tool_results"] == [tr]
        restored = snapshot.values["tool_results"][0]
        assert isinstance(restored, ToolResult), type(restored)
        assert restored == tr
