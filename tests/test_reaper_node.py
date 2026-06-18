"""Phase B / Track B — Reaper delegating node tests.

Covers the single delegating node at :mod:`modules.shadow.graph.reaper_node`.
ReaperModule is a flat if/elif dispatch leaf, so most of this is the standard
node-level suite (success round-trip, unknown-tool envelope, ``_call_count``
parity, params pass-through, reducer composition).

The distinctive Reaper invariant — **span survival through delegation**
=====================================================================

Reaper is the batch's observability exception. The node itself is
span-silent (no ``observed_span`` added), exactly like the other five nodes.
But the live inner engine ``modules/reaper/reaper.py`` emits its own spans on
the ``search()`` path — ``reaper.search`` (``reaper.py:423``) wrapping
per-backend ``reaper.search.attempt`` children (``reaper.py:549``) — and
``ReaperModule.execute`` routes ``web_search`` *through* that engine
(``reaper_module.py:99``). Because the node delegates to ``execute`` rather
than duplicating dispatch, those inner spans must survive.

These tests spy on ``modules.reaper.reaper.observed_span`` (the contextmanager
the engine actually calls) and assert:

- dispatching ``web_search`` through the node still produces the inner
  ``reaper.search.attempt`` span — delegation does not bypass the spanned
  engine; and
- dispatching ``web_fetch`` through the node produces **no** inner search
  span, because it routes to the unspanned ``Reaper.fetch_page``
  (``reaper_module.py:127``) — expected, and the node must not invent one.

Network leaf methods are stubbed so no real request is made; the spy patches
the span contextmanager, not the dispatch path, so the routing under test is
the real one.
"""

from __future__ import annotations

from contextlib import contextmanager
from operator import add
from pathlib import Path
from typing import Annotated, Any, TypedDict
from unittest import mock

import pytest
from langgraph.graph import END, START, StateGraph

import modules.reaper.reaper as reaper_engine
from modules.base import ToolResult
from modules.reaper.reaper import Reaper
from modules.reaper.reaper_module import ReaperModule
from modules.shadow.graph import make_reaper_node


def _make_reaper_module(tmp_path: Path) -> ReaperModule:
    """ReaperModule wired to a real inner Reaper engine, network leaves stubbed.

    Mirrors the live construction (``ReaperModule(config, grimoire)`` then
    ``module._reaper = Reaper(...)``) used by the existing Reaper test suite,
    so dispatch routes through the genuine engine — only the leaf backend /
    fetch methods are replaced to keep the test offline.
    """
    module = ReaperModule(config={}, grimoire_instance=mock.MagicMock())
    reaper = Reaper(grimoire=mock.MagicMock(), data_dir=str(tmp_path / "research"))
    # Force the cascade onto DDG and stub the leaf so no real request is made.
    reaper._searxng_is_available = lambda: False  # type: ignore[method-assign]
    reaper.ddg_available = True
    reaper.bing_available = False
    reaper.brave_available = False
    reaper._search_ddg = lambda query, max_results: [  # type: ignore[method-assign]
        {
            "title": "Python docs",
            "url": "https://docs.python.org/3/",
            "snippet": "stub",
            "engine": "ddg",
        }
    ]
    reaper.fetch_page = lambda url: {"url": url, "text": "stub"}  # type: ignore[method-assign]
    module._reaper = reaper
    return module


@contextmanager
def _spy_observed_span(recorded: list[str]):
    """Patch the engine's ``observed_span`` to record span names.

    Yields a no-op-ish span (a MagicMock) so the engine's ``span.update(...)``
    calls are harmless. Recording the *name* lets the tests assert which inner
    spans the delegated dispatch produced.
    """

    @contextmanager
    def fake_span(name, **metadata):
        recorded.append(name)
        yield mock.MagicMock()

    with mock.patch.object(reaper_engine, "observed_span", fake_span):
        yield


# ---------------------------------------------------------------------------
# Span survival through delegation — the Reaper-specific invariant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reaper_node_web_search_preserves_inner_search_attempt_span(
    tmp_path: Path,
) -> None:
    """Dispatching ``web_search`` through the node keeps the inner spans.

    Delegation routes ``web_search`` through ``Reaper.search`` (spanned), so
    both the parent ``reaper.search`` span and at least one child
    ``reaper.search.attempt`` span must fire. If a future refactor stopped
    delegating and duplicated dispatch, the engine would be bypassed and these
    inner spans would vanish — this test catches that.
    """
    module = _make_reaper_module(tmp_path)
    node = make_reaper_node(module)

    recorded: list[str] = []
    with _spy_observed_span(recorded):
        out = await node(
            {"tool_name": "web_search", "params": {"query": "python", "max_results": 3}},
        )

    tr = out["tool_results"][0]
    assert tr.success is True
    assert tr.module == "reaper"
    assert tr.tool_name == "web_search"
    assert "reaper.search.attempt" in recorded, (
        f"inner reaper.search.attempt span did not fire through the node "
        f"(recorded={recorded}). Delegation must route web_search through the "
        f"spanned engine, not around it."
    )
    assert "reaper.search" in recorded


@pytest.mark.asyncio
async def test_reaper_node_web_fetch_produces_no_inner_search_span(
    tmp_path: Path,
) -> None:
    """``web_fetch`` routes to the unspanned ``fetch_page`` — no inner span.

    The node must not invent a span for tools whose live inner path has none.
    """
    module = _make_reaper_module(tmp_path)
    node = make_reaper_node(module)

    recorded: list[str] = []
    with _spy_observed_span(recorded):
        out = await node(
            {"tool_name": "web_fetch", "params": {"url": "https://example.com"}},
        )

    tr = out["tool_results"][0]
    assert tr.success is True
    assert tr.module == "reaper"
    assert tr.tool_name == "web_fetch"
    assert not any(name.startswith("reaper.search") for name in recorded), (
        f"web_fetch should not produce a reaper.search* span (recorded={recorded})"
    )


# ---------------------------------------------------------------------------
# Standard node suite
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reaper_node_success_path_round_trips_toolresult(
    tmp_path: Path,
) -> None:
    """``web_search`` returns a successful ToolResult through the node."""
    module = _make_reaper_module(tmp_path)
    node = make_reaper_node(module)

    out = await node({"tool_name": "web_search", "params": {"query": "python"}})

    tr = out["tool_results"][0]
    assert isinstance(tr, ToolResult)
    assert tr.success is True
    assert tr.module == "reaper"
    assert tr.tool_name == "web_search"


@pytest.mark.asyncio
async def test_reaper_node_emits_toolresult_for_unknown_tool(
    tmp_path: Path,
) -> None:
    """Unknown tool name flows through ReaperModule.execute's else branch."""
    module = _make_reaper_module(tmp_path)
    node = make_reaper_node(module)

    out = await node({"tool_name": "not_a_real_tool", "params": {}})

    tr = out["tool_results"][0]
    assert isinstance(tr, ToolResult)
    assert tr.success is False
    assert tr.module == "reaper"
    assert tr.tool_name == "not_a_real_tool"
    assert tr.error == "Unknown Reaper tool: not_a_real_tool"


@pytest.mark.asyncio
async def test_reaper_node_records_call_count_via_execute_delegation(
    tmp_path: Path,
) -> None:
    """Side-effect parity canary — proves delegation through ReaperModule.execute."""
    module = _make_reaper_module(tmp_path)
    node = make_reaper_node(module)

    before = module._call_count
    await node({"tool_name": "not_a_real_tool", "params": {}})
    after = module._call_count

    assert after == before + 1, (
        f"ReaperModule._call_count did not advance via the node "
        f"(before={before}, after={after}). This usually means the node "
        f"started bypassing ReaperModule.execute() — restore delegation."
    )


@pytest.mark.asyncio
async def test_reaper_node_passes_params_through_to_execute(
    tmp_path: Path,
) -> None:
    """The node delivers ``tool_name`` / ``params`` to execute verbatim."""
    module = _make_reaper_module(tmp_path)
    captured: dict[str, Any] = {}

    async def capture_execute(tool_name: str, params: dict[str, Any]) -> ToolResult:
        captured["tool_name"] = tool_name
        captured["params"] = params
        return ToolResult(
            success=True, content="captured", tool_name=tool_name,
            module=module.name,
        )

    module.execute = capture_execute  # type: ignore[method-assign]
    node = make_reaper_node(module)

    await node({"tool_name": "web_search", "params": {"query": "x", "max_results": 7}})

    assert captured == {
        "tool_name": "web_search",
        "params": {"query": "x", "max_results": 7},
    }


@pytest.mark.asyncio
async def test_reaper_node_defaults_missing_params_to_empty_dict(
    tmp_path: Path,
) -> None:
    """A state with no ``params`` key dispatches with ``{}`` — no KeyError."""
    module = _make_reaper_module(tmp_path)
    captured: dict[str, Any] = {}

    async def capture_execute(tool_name: str, params: dict[str, Any]) -> ToolResult:
        captured["params"] = params
        return ToolResult(
            success=True, content=None, tool_name=tool_name, module=module.name,
        )

    module.execute = capture_execute  # type: ignore[method-assign]
    node = make_reaper_node(module)

    await node({"tool_name": "web_search"})

    assert captured["params"] == {}


class _ProbeState(TypedDict, total=False):
    """Throwaway parent state mirroring ShadowState's ``tool_results`` reducer."""

    tool_name: str
    params: dict[str, Any]
    tool_results: Annotated[list[ToolResult], add]


@pytest.mark.asyncio
async def test_reaper_node_tool_results_append_via_shadowstate_reducer(
    tmp_path: Path,
) -> None:
    """The node's list-return APPENDS under the ``add`` reducer."""
    module = _make_reaper_module(tmp_path)

    sentinel = ToolResult(
        success=True, content="seed", tool_name="seed", module="probe",
    )

    async def seed(state: _ProbeState) -> _ProbeState:
        return {"tool_results": [sentinel]}

    builder: StateGraph = StateGraph(_ProbeState)
    builder.add_node("seed", seed)
    builder.add_node("reaper_dispatch", make_reaper_node(module))
    builder.add_edge(START, "seed")
    builder.add_edge("seed", "reaper_dispatch")
    builder.add_edge("reaper_dispatch", END)
    graph = builder.compile()

    result = await graph.ainvoke(
        {"tool_name": "web_search", "params": {"query": "python"}},
    )

    results = result["tool_results"]
    assert len(results) == 2, "add reducer should append, not overwrite"
    assert results[0] is sentinel
    assert results[1].tool_name == "web_search"
    assert results[1].success is True
