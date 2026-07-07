"""Lazy graph-init lock (S54 F-3).

``_ensure_graph`` and the worker compile in ``run_deferred_through_graph``
were unlocked check-then-init: two concurrent first calls each opened their
own ``AsyncSqliteSaver`` context, and the loser's ``__aenter__`` leaked
unclosed. F-3 guards both inits with one ``asyncio.Lock`` (double-checked:
lock-free fast path once built, re-check under the lock before building).

Pins: (1) N concurrent first ``_ensure_graph`` calls open exactly ONE saver
and all receive the same compiled graph; (2) N concurrent first deferred
tasks compile exactly ONE worker graph.
"""

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

import modules.shadow.graph.serde as serde_module
from modules.shadow.orchestrator import Orchestrator


def _test_config(tmp_path: Path) -> dict[str, Any]:
    return {
        "system": {
            "state_file": str(tmp_path / "state.json"),
            "task_db": str(tmp_path / "tasks.db"),
            "growth_db": str(tmp_path / "growth.db"),
        },
        "models": {
            "ollama_base_url": "http://localhost:11434",
            "router": {"name": "phi4-mini"},
            "fast_brain": {"name": "phi4-mini"},
            "smart_brain": {"name": "phi4-mini"},
        },
        "decision_loop": {"context_memories": 3},
    }


@pytest.fixture
def tmp_config(tmp_path: Path) -> dict[str, Any]:
    return _test_config(tmp_path)


@pytest.mark.asyncio
async def test_concurrent_ensure_graph_opens_exactly_one_saver(tmp_config):
    orch = Orchestrator(tmp_config)

    real_open = serde_module.open_async_sqlite_saver
    calls = 0

    def counting_open(conn_string):
        nonlocal calls
        calls += 1
        return real_open(conn_string)

    # _ensure_graph does a local `from modules.shadow.graph.serde import
    # open_async_sqlite_saver` at call time, so patching the serde module
    # attribute intercepts every init attempt.
    with patch.object(serde_module, "open_async_sqlite_saver", counting_open):
        graphs = await asyncio.gather(*(orch._ensure_graph() for _ in range(10)))

    assert calls == 1, f"expected one saver open, got {calls}"
    assert all(g is graphs[0] for g in graphs), "callers got different graphs"
    assert orch._graph_saver is not None


@pytest.mark.asyncio
async def test_concurrent_worker_calls_compile_exactly_one_worker_graph(tmp_config):
    orch = Orchestrator(tmp_config)
    await orch._ensure_graph()

    real_compile = orch._graph_builder.compile
    compiles = 0

    def counting_compile(**kwargs):
        nonlocal compiles
        compiles += 1
        return real_compile(**kwargs)

    with patch.object(orch._graph_builder, "compile", counting_compile):
        await asyncio.gather(
            *(orch.run_deferred_through_graph("hello", source="autonomous")
              for _ in range(5))
        )

    assert compiles == 1, f"expected one worker compile, got {compiles}"
    assert orch._worker_graph is not None
