"""Phase B / Track B — LangGraph spike proofs (a–f).

These tests are runnable without the live Shadow stack. Proof (a) uses the
real Grimoire + Ollama embeddings when both are available, and skips
otherwise. Proofs (b)–(f) always run.

See ``spikes/langgraph_grimoire/README.md`` for the harness layout.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import warnings
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from modules.base import ToolResult
from spikes.langgraph_grimoire.graph import (
    InMemoryGrimoireFake,
    SpikeState,
    build_async_graph,
    build_graph,
)


# ---------------------------------------------------------------------------
# Proof (a): store/query round-trip through a compiled graph
# ---------------------------------------------------------------------------


def _ollama_with_embed_model_available() -> bool:
    """True iff Ollama is reachable and ``nomic-embed-text`` is loaded."""
    try:
        import urllib.request

        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as resp:
            import json

            data = json.load(resp)
            models = [m.get("name", "") for m in data.get("models", [])]
            return any("nomic-embed-text" in m for m in models)
    except Exception:
        return False


@pytest.mark.skipif(
    not _ollama_with_embed_model_available(),
    reason="Ollama + nomic-embed-text not reachable; run on Citadel for full proof.",
)
def test_proof_a_round_trip(tmp_path: Path) -> None:
    """A compiled graph stores via Grimoire and recalls the same content."""
    from modules.grimoire.grimoire import Grimoire

    db = tmp_path / "spike_memory.db"
    vec = tmp_path / "spike_vectors"
    cp = tmp_path / "checkpoints.db"
    vec.mkdir(parents=True, exist_ok=True)

    grimoire = Grimoire(db_path=str(db), vector_path=str(vec))
    try:
        builder = build_graph(
            store_fn=lambda c, _m: grimoire.remember(c),
            recall_fn=lambda q, n: grimoire.recall(q, n_results=n),
        )
        with SqliteSaver.from_conn_string(str(cp)) as saver:
            graph = builder.compile(checkpointer=saver)
            config = {"configurable": {"thread_id": "proof-a"}}
            result = graph.invoke(
                {
                    "content": "Spike-a sentinel: Citadel has 128 GB DDR5 and an RTX 5090.",
                    "query": "How much RAM and what GPU does Citadel use?",
                },
                config=config,
            )
            assert result["memory_id"]
            assert len(result["recall"]) >= 1
            top = result["recall"][0]
            assert "Citadel" in top["content"]
            assert top["relevance"] > 0
    finally:
        grimoire.close()


# ---------------------------------------------------------------------------
# Proof (b): pydantic config singleton resolves inside graph nodes
# ---------------------------------------------------------------------------


def test_proof_b_config_singleton(tmp_path: Path) -> None:
    """Reading ``shadow.config.config.grimoire.db_path`` from inside a node works."""
    seen: dict[str, Any] = {}

    def store_fn(content: str, _meta: dict[str, Any] | None) -> str:
        from shadow.config import config as singleton

        # Access inside the "node" — config singleton must resolve during
        # graph execution, not only at import time.
        seen["db_path"] = singleton.grimoire.db_path
        seen["vector_path"] = singleton.grimoire.vector_path
        seen["singleton_type"] = type(singleton).__name__
        return "fake-id"

    def recall_fn(_q: str, _n: int) -> list[dict[str, Any]]:
        return []

    builder = build_graph(store_fn=store_fn, recall_fn=recall_fn)
    with SqliteSaver.from_conn_string(str(tmp_path / "cp.db")) as saver:
        graph = builder.compile(checkpointer=saver)
        graph.invoke(
            {"content": "x", "query": "y"},
            config={"configurable": {"thread_id": "proof-b"}},
        )

    assert seen["singleton_type"] == "Settings"
    assert seen["db_path"]  # non-empty default from GrimoireSettings
    assert seen["vector_path"]


# ---------------------------------------------------------------------------
# Proof (c): SQLite checkpointing persists across actual process restarts
# ---------------------------------------------------------------------------


def test_proof_c_process_restart(tmp_path: Path) -> None:
    """Two separate Python processes resume from the same checkpoint."""
    db = tmp_path / "cp.db"
    thread = "proof-c"
    repo_root = Path(__file__).resolve().parents[1]

    write = subprocess.run(
        [
            sys.executable,
            "-m",
            "spikes.langgraph_grimoire.proof_checkpoint",
            "--phase=write",
            f"--db={db}",
            f"--thread={thread}",
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert write.returncode == 0, (
        f"write phase failed:\nstdout={write.stdout}\nstderr={write.stderr}"
    )
    assert db.exists()
    assert "interrupt next=('search',)" in write.stdout

    resume = subprocess.run(
        [
            sys.executable,
            "-m",
            "spikes.langgraph_grimoire.proof_checkpoint",
            "--phase=resume",
            f"--db={db}",
            f"--thread={thread}",
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert resume.returncode == 0, (
        f"resume phase failed:\nstdout={resume.stdout}\nstderr={resume.stderr}"
    )
    assert "resumed from checkpoint, state intact" in resume.stdout

    # Extract memory_ids from both phases — they must match.
    write_id = next(
        (line.split("=", 1)[1] for line in write.stdout.splitlines() if line.startswith("[write] memory_id=")),
        None,
    )
    resume_id = next(
        (line.split(": ", 1)[1] for line in resume.stdout.splitlines() if "memory_id from checkpoint:" in line),
        None,
    )
    assert write_id and resume_id and write_id == resume_id, (
        f"memory_id mismatch across processes: write={write_id!r} resume={resume_id!r}"
    )


# ---------------------------------------------------------------------------
# Proof (d): observed_span nests correctly inside graph nodes
# ---------------------------------------------------------------------------


def test_proof_d_observed_span_nesting(tmp_path: Path) -> None:
    """``observed_span`` is invoked from inside graph nodes without error.

    Langfuse is typically unreachable in CI, so ``observed_span`` yields
    ``None`` and is a no-op. We verify by patching the call site to count
    invocations — that proves the contract is exercised inside the graph,
    even when the backend is down.
    """
    fake = InMemoryGrimoireFake()
    builder = build_graph(
        store_fn=lambda c, _m: fake.remember(c),
        recall_fn=lambda q, n: fake.recall(q, n),
    )

    span_calls: list[str] = []
    from spikes.langgraph_grimoire import graph as spike_graph

    original = spike_graph.observed_span

    def spy(name: str, **metadata: Any):
        span_calls.append(name)
        return original(name, **metadata)

    with patch.object(spike_graph, "observed_span", spy):
        with SqliteSaver.from_conn_string(str(tmp_path / "cp.db")) as saver:
            graph = builder.compile(checkpointer=saver)
            graph.invoke(
                {"content": "proof-d content", "query": "proof-d"},
                config={"configurable": {"thread_id": "proof-d"}},
            )

    # Each node emits one span; ordering must be store-before-search to
    # mirror the parent->child semantics the cutover must preserve.
    assert span_calls == ["spike.grimoire.store", "spike.grimoire.search"], span_calls


# ---------------------------------------------------------------------------
# Proof (e): ToolResult passes through graph state unmodified
# ---------------------------------------------------------------------------


def test_proof_e_toolresult_passthrough(tmp_path: Path) -> None:
    """ToolResult dataclass survives the round-trip through graph state."""
    fake = InMemoryGrimoireFake()
    builder = build_graph(
        store_fn=lambda c, _m: fake.remember(c),
        recall_fn=lambda q, n: fake.recall(q, n),
    )

    with SqliteSaver.from_conn_string(str(tmp_path / "cp.db")) as saver:
        graph = builder.compile(checkpointer=saver)
        result = graph.invoke(
            {"content": "proof-e content blob", "query": "proof-e content"},
            config={"configurable": {"thread_id": "proof-e"}},
        )

    tool_results = result["tool_results"]
    assert len(tool_results) == 2  # one store + one search

    store_tr, search_tr = tool_results
    # Type-identity: still the same dataclass class, not a dict, not a Pydantic model.
    assert isinstance(store_tr, ToolResult)
    assert isinstance(search_tr, ToolResult)

    # Field-shape: matches modules/base.py:37-50 exactly.
    expected_fields = {
        "success",
        "content",
        "tool_name",
        "module",
        "error",
        "execution_time_ms",
        "metadata",
    }
    from dataclasses import fields

    assert {f.name for f in fields(store_tr)} == expected_fields

    # Values intact through state reducer.
    assert store_tr.tool_name == "memory_store"
    assert store_tr.module == "grimoire"
    assert store_tr.success is True
    assert store_tr.metadata["memory_id"] == result["memory_id"]
    assert search_tr.tool_name == "memory_search"
    assert search_tr.metadata["hits"] >= 1


# ---------------------------------------------------------------------------
# Proof (f): async execution compatible with Grimoire's sync surface
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_proof_f_async_compat(tmp_path: Path) -> None:
    """``graph.ainvoke`` wraps the sync Grimoire surface via asyncio.to_thread."""
    fake = InMemoryGrimoireFake()
    builder = build_async_graph(
        store_fn=lambda c, _m: fake.remember(c),
        recall_fn=lambda q, n: fake.recall(q, n),
    )

    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        async with AsyncSqliteSaver.from_conn_string(str(tmp_path / "cp.db")) as saver:
            graph = builder.compile(checkpointer=saver)
            result = await graph.ainvoke(
                {"content": "proof-f async content", "query": "proof-f"},
                config={"configurable": {"thread_id": "proof-f"}},
            )

    assert result["memory_id"]
    assert len(result["recall"]) == 1
    assert all(tr.metadata.get("variant") == "async" for tr in result["tool_results"])

    # Asyncio shouldn't have emitted any "coroutine never awaited" or
    # "blocking call" warnings — the to_thread wrapper handles that.
    blocking = [
        str(w.message)
        for w in recorded
        if "never awaited" in str(w.message) or "blocking" in str(w.message).lower()
    ]
    assert not blocking, f"unexpected async warnings: {blocking}"
