"""Grimoire-as-sub-graph spike.

Builds a tiny LangGraph StateGraph with two nodes that wrap Grimoire's
``remember`` / ``recall`` surface. The graph is parameterised by store/recall
callables so tests can inject in-memory fakes (no Ollama required) while
``run_spike.py`` and the on-Citadel proofs use the real Grimoire instance.

Nothing here is wired into the live orchestrator. Importable only under the
``spikes.langgraph_grimoire`` namespace.
"""

from __future__ import annotations

import asyncio
import time
from operator import add
from typing import Annotated, Any, Awaitable, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from modules.base import ToolResult
from modules.shadow.observability import observed_span

StoreFn = Callable[[str, dict[str, Any] | None], str]
RecallFn = Callable[[str, int], list[dict[str, Any]]]


class SpikeState(TypedDict, total=False):
    """Graph state for the spike.

    ``tool_results`` uses an ``add`` reducer so nodes can append ToolResults
    without overwriting each other — mirrors how the cutover will carry a
    multi-tool plan's outputs through state.
    """

    content: str
    query: str
    memory_id: str | None
    recall: list[dict[str, Any]]
    tool_results: Annotated[list[ToolResult], add]


def build_graph(
    *,
    store_fn: StoreFn,
    recall_fn: RecallFn,
    n_results: int = 5,
) -> Any:
    """Construct the spike builder (not compiled — caller wires checkpointer).

    Returns a ``StateGraph`` builder. The caller calls ``.compile(...)`` with
    whatever checkpointer / interrupt configuration the proof needs.
    """

    def store_node(state: SpikeState) -> SpikeState:
        start = time.time()
        with observed_span("spike.grimoire.store", content_len=len(state["content"])) as span:
            memory_id = store_fn(state["content"], None)
            if span is not None:
                span.update(metadata={"memory_id": memory_id})
        return {
            "memory_id": memory_id,
            "tool_results": [
                ToolResult(
                    success=True,
                    content=f"Memory stored: {memory_id}",
                    tool_name="memory_store",
                    module="grimoire",
                    execution_time_ms=(time.time() - start) * 1000,
                    metadata={"memory_id": memory_id},
                )
            ],
        }

    def search_node(state: SpikeState) -> SpikeState:
        start = time.time()
        with observed_span("spike.grimoire.search", query_len=len(state["query"])) as span:
            results = recall_fn(state["query"], n_results)
            if span is not None:
                span.update(metadata={"hits": len(results)})
        return {
            "recall": results,
            "tool_results": [
                ToolResult(
                    success=True,
                    content=results,
                    tool_name="memory_search",
                    module="grimoire",
                    execution_time_ms=(time.time() - start) * 1000,
                    metadata={"hits": len(results)},
                )
            ],
        }

    builder = StateGraph(SpikeState)
    builder.add_node("store", store_node)
    builder.add_node("search", search_node)
    builder.add_edge(START, "store")
    builder.add_edge("store", "search")
    builder.add_edge("search", END)
    return builder


def build_async_graph(
    *,
    store_fn: StoreFn,
    recall_fn: RecallFn,
    n_results: int = 5,
) -> Any:
    """Async variant: wraps sync Grimoire methods in ``asyncio.to_thread``.

    This is the recommended cutover pattern — the real ``Grimoire.remember`` /
    ``Grimoire.recall`` are synchronous and block on ``requests.post`` for
    embeddings. Proof (f) runs this through ``graph.ainvoke``.
    """

    async def store_node(state: SpikeState) -> SpikeState:
        start = time.time()
        with observed_span("spike.grimoire.store_async") as span:
            memory_id = await asyncio.to_thread(store_fn, state["content"], None)
            if span is not None:
                span.update(metadata={"memory_id": memory_id})
        return {
            "memory_id": memory_id,
            "tool_results": [
                ToolResult(
                    success=True,
                    content=f"Memory stored: {memory_id}",
                    tool_name="memory_store",
                    module="grimoire",
                    execution_time_ms=(time.time() - start) * 1000,
                    metadata={"memory_id": memory_id, "variant": "async"},
                )
            ],
        }

    async def search_node(state: SpikeState) -> SpikeState:
        start = time.time()
        with observed_span("spike.grimoire.search_async") as span:
            results = await asyncio.to_thread(recall_fn, state["query"], n_results)
            if span is not None:
                span.update(metadata={"hits": len(results)})
        return {
            "recall": results,
            "tool_results": [
                ToolResult(
                    success=True,
                    content=results,
                    tool_name="memory_search",
                    module="grimoire",
                    execution_time_ms=(time.time() - start) * 1000,
                    metadata={"hits": len(results), "variant": "async"},
                )
            ],
        }

    builder = StateGraph(SpikeState)
    builder.add_node("store", store_node)
    builder.add_node("search", search_node)
    builder.add_edge(START, "store")
    builder.add_edge("store", "search")
    builder.add_edge("search", END)
    return builder


class InMemoryGrimoireFake:
    """Substitute for the real Grimoire when Ollama isn't available.

    Lets tests exercise the graph topology, checkpointer, ToolResult flow,
    and observability nesting without spinning up embeddings. The real
    Grimoire's ``remember`` / ``recall`` signatures are preserved.
    """

    def __init__(self) -> None:
        import uuid

        self._uuid = uuid
        self._store: dict[str, str] = {}

    def remember(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        mid = str(self._uuid.uuid4())
        self._store[mid] = content
        return mid

    def recall(self, query: str, n_results: int = 5) -> list[dict[str, Any]]:
        # Substring match — good enough to prove round-trip; real Grimoire
        # uses semantic vector search.
        hits = []
        for mid, content in self._store.items():
            if any(tok.lower() in content.lower() for tok in query.split()):
                hits.append(
                    {
                        "id": mid,
                        "content": content,
                        "relevance": 1.0,
                        "trust_level": 0.5,
                    }
                )
                if len(hits) >= n_results:
                    break
        return hits
