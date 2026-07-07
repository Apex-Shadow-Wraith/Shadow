"""Phase B / Track B — Step 2 Grimoire sub-graph tests.

Covers the delegating sub-graph that lives at
:mod:`modules.shadow.graph.grimoire_subgraph`:

- ToolResult envelope flows through the sub-graph for both happy and sad
  paths (uninitialized module, unknown tool name).
- Side-effect parity canary — ``_call_count`` increments via the delegated
  :meth:`GrimoireModule.execute` call, proving the sub-graph did not bypass
  it to reach ``_grimoire`` directly. (Catches accidental future drift into
  a duplicating dispatch table.)
- Inherited live blocking — the sub-graph carries the pre-existing
  event-loop blocking that ``GrimoireModule.execute`` has today for sync
  tools. Asserted explicitly rather than masked.
- Real-Grimoire round-trip + async-tool dispatch — skipped when Ollama +
  ``nomic-embed-text`` isn't reachable (CI without that stack still passes).
- Checkpoint round-trip — the Step 1 serde wiring carries a real
  Grimoire-emitted ``ToolResult`` through ``AsyncSqliteSaver`` losslessly.
"""

from __future__ import annotations

import asyncio
import json
import time
import urllib.request
from typing import Any

import pytest

from modules.base import ToolResult
from modules.grimoire.grimoire_module import GrimoireModule
from modules.shadow.graph import (
    compile_grimoire_subgraph,
    open_async_sqlite_saver,
)


# ---------------------------------------------------------------------------
# Skip predicates
# ---------------------------------------------------------------------------


def _ollama_with_embed_model_available() -> bool:
    """True iff Ollama is reachable and ``nomic-embed-text`` is loaded."""
    try:
        with urllib.request.urlopen(
            "http://localhost:11434/api/tags", timeout=2,
        ) as resp:
            data = json.load(resp)
            models = [m.get("name", "") for m in data.get("models", [])]
            return any("nomic-embed-text" in m for m in models)
    except Exception:
        return False


def _failure_pattern_db_available() -> bool:
    try:
        from modules.shadow.failure_patterns import FailurePatternDB  # noqa: F401

        return True
    except Exception:
        return False


_OLLAMA_AVAILABLE = _ollama_with_embed_model_available()
_FAILURE_PATTERN_DB_AVAILABLE = _failure_pattern_db_available()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_module() -> GrimoireModule:
    """Fresh GrimoireModule with no Grimoire instance attached."""
    return GrimoireModule(config={"db_path": ":memory:", "vector_path": "/tmp/nope"})


def _attach_fake_grimoire(module: GrimoireModule) -> None:
    """Bypass :meth:`GrimoireModule.initialize` for tests that exercise the
    dispatch table but do not need real Grimoire I/O.

    The dispatch table early-returns at ``grimoire_module.py:104`` when
    ``_grimoire is None``. Setting any non-None placeholder lets execution
    fall through to the per-tool branches. Tests that need a specific tool's
    underlying call to do something attach a richer fake.
    """
    module._grimoire = object()


# ---------------------------------------------------------------------------
# Envelope + side-effect tests (no Ollama required)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_grimoire_subgraph_emits_toolresult_for_uninitialized_module() -> None:
    """Compiles, ainvokes, and the early-return ``ToolResult`` reaches state."""
    module = _make_module()  # _grimoire is None
    graph = compile_grimoire_subgraph(module)

    result = await graph.ainvoke(
        {"tool_name": "memory_store", "params": {"content": "anything"}},
    )

    assert "tool_results" in result
    assert len(result["tool_results"]) == 1
    tr = result["tool_results"][0]
    assert isinstance(tr, ToolResult)
    assert tr.success is False
    assert tr.tool_name == "memory_store"
    assert tr.module == "grimoire"
    assert tr.error == "Grimoire not initialized"


@pytest.mark.asyncio
async def test_grimoire_subgraph_unknown_tool_returns_failure_toolresult() -> None:
    """Unknown tool name flows through the ``else`` branch at module.py:291."""
    module = _make_module()
    _attach_fake_grimoire(module)
    graph = compile_grimoire_subgraph(module)

    result = await graph.ainvoke(
        {"tool_name": "not_a_real_tool", "params": {}},
    )

    tr = result["tool_results"][0]
    assert tr.success is False
    assert tr.tool_name == "not_a_real_tool"
    assert "Unknown Grimoire tool" in tr.error


@pytest.mark.asyncio
async def test_grimoire_subgraph_records_call_count_via_execute_delegation() -> None:
    """Side-effect parity canary.

    ``GrimoireModule.execute`` increments ``self._call_count`` via
    ``_record_call`` on every branch. If the sub-graph ever stops delegating
    to ``execute`` and instead reaches into ``_grimoire`` directly, this
    counter will not move and the test will fail — catching the regression
    before silent drift damages module health metrics.

    Uses the unknown-tool branch (which calls ``_record_call(False)`` at
    module.py:292) so the test does not require Ollama or an initialized
    Grimoire.
    """
    module = _make_module()
    _attach_fake_grimoire(module)
    graph = compile_grimoire_subgraph(module)

    before = module._call_count
    await graph.ainvoke({"tool_name": "not_a_real_tool", "params": {}})
    after = module._call_count

    assert after == before + 1, (
        f"GrimoireModule._call_count did not advance via the sub-graph "
        f"(before={before}, after={after}). This usually means the sub-graph "
        f"started bypassing GrimoireModule.execute() — restore delegation."
    )


@pytest.mark.asyncio
async def test_grimoire_subgraph_inherits_live_blocking_for_sync_tools() -> None:
    """Documents that the sub-graph carries the pre-existing live blocking.

    ``GrimoireModule.execute`` calls ``Grimoire.remember`` (sync) without
    ``asyncio.to_thread``; the event loop blocks for the duration of the
    sync call. The sub-graph delegates to ``execute`` and therefore inherits
    that behavior — the asyncio-to_thread wrap from the spike does NOT apply
    here, by design (see grimoire_subgraph.py module docstring).

    This test asserts the wall-clock cost of a ``time.sleep(0.1)``-bound
    Grimoire call instead of pretending the sub-graph unblocks the loop.
    Future async-embeddings work in Grimoire itself will tighten this.
    """

    class _BlockingGrimoire:
        def remember(self, **_kwargs: Any) -> str:
            time.sleep(0.1)
            return "fake-memory-id"

    module = _make_module()
    module._grimoire = _BlockingGrimoire()
    graph = compile_grimoire_subgraph(module)

    start = time.monotonic()
    result = await graph.ainvoke(
        {
            "tool_name": "memory_store",
            "params": {"content": "blocking-test"},
        },
    )
    wall = time.monotonic() - start

    tr = result["tool_results"][0]
    assert tr.success is True
    assert wall >= 0.1, (
        f"sync Grimoire call took {wall:.3f}s, expected >= 0.1s — either the "
        f"fake's sleep was skipped or execute() stopped invoking the sync "
        f"method synchronously."
    )
    assert wall < 1.0, f"sub-graph took {wall:.3f}s — suspiciously slow."


@pytest.mark.asyncio
async def test_grimoire_subgraph_passes_params_through_to_execute() -> None:
    """Sub-graph delivers ``params`` to :meth:`GrimoireModule.execute` verbatim.

    Captures the ``execute`` call args to confirm the sub-graph node does not
    munge the payload before delegation. Belt-and-braces alongside the
    side-effect parity test.
    """
    module = _make_module()
    captured: dict[str, Any] = {}

    async def capture_execute(tool_name: str, params: dict[str, Any]) -> ToolResult:
        captured["tool_name"] = tool_name
        captured["params"] = params
        return ToolResult(
            success=True, content="captured", tool_name=tool_name,
            module=module.name,
        )

    module.execute = capture_execute  # type: ignore[method-assign]
    graph = compile_grimoire_subgraph(module)

    await graph.ainvoke(
        {
            "tool_name": "memory_search",
            "params": {"query": "hello", "n_results": 7},
        },
    )

    assert captured == {
        "tool_name": "memory_search",
        "params": {"query": "hello", "n_results": 7},
    }


# ---------------------------------------------------------------------------
# Real-Grimoire integration (skipped when Ollama is unreachable)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _OLLAMA_AVAILABLE,
    reason="Ollama + nomic-embed-text not reachable; run on Citadel for full proof.",
)
async def test_grimoire_subgraph_round_trip_with_real_grimoire(tmp_path) -> None:
    """Real Grimoire stores via the sub-graph and recalls via the sub-graph."""
    config = {
        "db_path": str(tmp_path / "subgraph_memory.db"),
        "vector_path": str(tmp_path / "subgraph_vectors"),
    }
    (tmp_path / "subgraph_vectors").mkdir(parents=True, exist_ok=True)
    module = GrimoireModule(config=config)
    await module.initialize()
    graph = compile_grimoire_subgraph(module)

    sentinel = "track-b step 2 sentinel: sub-graph round trip"

    store_result = await graph.ainvoke(
        {"tool_name": "memory_store", "params": {"content": sentinel}},
    )
    assert store_result["tool_results"][-1].success is True

    search_result = await graph.ainvoke(
        {
            "tool_name": "memory_search",
            "params": {"query": "track-b step 2 sentinel", "n_results": 5},
        },
    )
    tr = search_result["tool_results"][-1]
    assert tr.success is True
    hits = tr.content
    assert isinstance(hits, list) and hits, "expected at least one recall hit"
    matched = any(
        sentinel in (h.get("content", "") if isinstance(h, dict) else str(h))
        for h in hits
    )
    assert matched, f"sentinel not in any recall hit; hits={hits!r}"

    await module.shutdown()


@pytest.mark.asyncio
@pytest.mark.skipif(
    not (_OLLAMA_AVAILABLE and _FAILURE_PATTERN_DB_AVAILABLE),
    reason="async tool path needs both Ollama and FailurePatternDB.",
)
async def test_grimoire_subgraph_async_tool_dispatches_via_failure_pattern_db(
    tmp_path,
) -> None:
    """The 3 async tools (``store_failure_pattern`` et al.) ``await`` cleanly."""
    config = {
        "db_path": str(tmp_path / "async_tool_memory.db"),
        "vector_path": str(tmp_path / "async_tool_vectors"),
    }
    (tmp_path / "async_tool_vectors").mkdir(parents=True, exist_ok=True)
    module = GrimoireModule(config=config)
    await module.initialize()
    graph = compile_grimoire_subgraph(module)

    result = await graph.ainvoke(
        {
            "tool_name": "store_failure_pattern",
            "params": {
                "task": "track-b async-tool dispatch smoke",
                "task_type": "test",
                "mistake": "called execute synchronously",
                "correct_approach": "awaited execute via sub-graph",
                "source": "track-b-test",
                "trust_level": 0.5,
            },
        },
    )
    tr = result["tool_results"][-1]
    assert tr.success is True
    assert tr.tool_name == "store_failure_pattern"

    await module.shutdown()


# ---------------------------------------------------------------------------
# Checkpoint round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_grimoire_toolresult_round_trips_through_subgraph_checkpoint(
    tmp_path,
) -> None:
    """Step 1's serde wiring carries a Grimoire-emitted ``ToolResult`` through
    ``AsyncSqliteSaver`` losslessly.

    Uses the unknown-tool branch so the test does not require Ollama —
    purpose is to verify checkpoint serde, not Grimoire I/O.
    """
    db = tmp_path / "subgraph-checkpoint.sqlite"
    module = _make_module()
    _attach_fake_grimoire(module)

    config = {"configurable": {"thread_id": "subgraph-checkpoint"}}

    async with open_async_sqlite_saver(str(db)) as saver:
        graph = compile_grimoire_subgraph(module, checkpointer=saver)
        result = await graph.ainvoke(
            {"tool_name": "not_a_real_tool", "params": {}},
            config=config,
        )
        live_tr = result["tool_results"][-1]
        assert isinstance(live_tr, ToolResult)

    async with open_async_sqlite_saver(str(db)) as saver2:
        graph2 = compile_grimoire_subgraph(module, checkpointer=saver2)
        snapshot = await graph2.aget_state(config)

    assert snapshot is not None
    persisted = snapshot.values["tool_results"][-1]
    assert isinstance(persisted, ToolResult), type(persisted)
    assert persisted == live_tr
