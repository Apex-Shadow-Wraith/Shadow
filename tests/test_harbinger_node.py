"""Phase B / Track B — Harbinger delegating node tests.

Covers the single delegating node at
:mod:`modules.shadow.graph.harbinger_node`. Harbinger is a flat dict-dispatch
leaf module, so these are node-level tests calling the node coroutine
directly; the final test compiles a throwaway parent graph to prove the
list-return appends through the shared ``add`` reducer.

Invariants pinned here mirror the Apex node suite: success round-trip,
unknown-tool envelope (``modules/harbinger/harbinger.py:141-148``),
``_call_count`` parity canary, params pass-through + default, reducer
composition.
"""

from __future__ import annotations

from operator import add
from pathlib import Path
from typing import Annotated, Any, TypedDict

import pytest
from langgraph.graph import END, START, StateGraph

from modules.base import ToolResult
from modules.harbinger.harbinger import Harbinger
from modules.shadow.graph import make_harbinger_node


def _make_harbinger(tmp_path: Path) -> Harbinger:
    """Harbinger with a temp queue file — no network, no shared state."""
    return Harbinger({"queue_file": str(tmp_path / "queue.json")})


@pytest.mark.asyncio
async def test_harbinger_node_success_path_round_trips_toolresult(
    tmp_path: Path,
) -> None:
    """``decision_queue_read`` returns a successful ToolResult through the node."""
    harbinger = _make_harbinger(tmp_path)
    await harbinger.initialize()
    node = make_harbinger_node(harbinger)

    out = await node({"tool_name": "decision_queue_read", "params": {}})

    tr = out["tool_results"][0]
    assert isinstance(tr, ToolResult)
    assert tr.success is True
    assert tr.module == "harbinger"
    assert tr.tool_name == "decision_queue_read"


@pytest.mark.asyncio
async def test_harbinger_node_emits_toolresult_for_unknown_tool(
    tmp_path: Path,
) -> None:
    """Unknown tool name flows through Harbinger.execute's else branch."""
    harbinger = _make_harbinger(tmp_path)
    node = make_harbinger_node(harbinger)

    out = await node({"tool_name": "not_a_real_tool", "params": {}})

    tr = out["tool_results"][0]
    assert isinstance(tr, ToolResult)
    assert tr.success is False
    assert tr.module == "harbinger"
    assert tr.tool_name == "not_a_real_tool"
    assert tr.error == "Unknown tool: not_a_real_tool"


@pytest.mark.asyncio
async def test_harbinger_node_records_call_count_via_execute_delegation(
    tmp_path: Path,
) -> None:
    """Side-effect parity canary — proves delegation through Harbinger.execute."""
    harbinger = _make_harbinger(tmp_path)
    node = make_harbinger_node(harbinger)

    before = harbinger._call_count
    await node({"tool_name": "not_a_real_tool", "params": {}})
    after = harbinger._call_count

    assert after == before + 1, (
        f"Harbinger._call_count did not advance via the node "
        f"(before={before}, after={after}). This usually means the node "
        f"started bypassing Harbinger.execute() — restore delegation."
    )


@pytest.mark.asyncio
async def test_harbinger_node_passes_params_through_to_execute(
    tmp_path: Path,
) -> None:
    """The node delivers ``tool_name`` / ``params`` to execute verbatim."""
    harbinger = _make_harbinger(tmp_path)
    captured: dict[str, Any] = {}

    async def capture_execute(tool_name: str, params: dict[str, Any]) -> ToolResult:
        captured["tool_name"] = tool_name
        captured["params"] = params
        return ToolResult(
            success=True, content="captured", tool_name=tool_name,
            module=harbinger.name,
        )

    harbinger.execute = capture_execute  # type: ignore[method-assign]
    node = make_harbinger_node(harbinger)

    await node({"tool_name": "notification_send", "params": {"message": "x", "severity": "info"}})

    assert captured == {
        "tool_name": "notification_send",
        "params": {"message": "x", "severity": "info"},
    }


@pytest.mark.asyncio
async def test_harbinger_node_defaults_missing_params_to_empty_dict(
    tmp_path: Path,
) -> None:
    """A state with no ``params`` key dispatches with ``{}`` — no KeyError."""
    harbinger = _make_harbinger(tmp_path)
    captured: dict[str, Any] = {}

    async def capture_execute(tool_name: str, params: dict[str, Any]) -> ToolResult:
        captured["params"] = params
        return ToolResult(
            success=True, content=None, tool_name=tool_name, module=harbinger.name,
        )

    harbinger.execute = capture_execute  # type: ignore[method-assign]
    node = make_harbinger_node(harbinger)

    await node({"tool_name": "decision_queue_read"})

    assert captured["params"] == {}


class _ProbeState(TypedDict, total=False):
    """Throwaway parent state mirroring ShadowState's ``tool_results`` reducer."""

    tool_name: str
    params: dict[str, Any]
    tool_results: Annotated[list[ToolResult], add]


@pytest.mark.asyncio
async def test_harbinger_node_tool_results_append_via_shadowstate_reducer(
    tmp_path: Path,
) -> None:
    """The node's list-return APPENDS under the ``add`` reducer."""
    harbinger = _make_harbinger(tmp_path)
    await harbinger.initialize()

    sentinel = ToolResult(
        success=True, content="seed", tool_name="seed", module="probe",
    )

    async def seed(state: _ProbeState) -> _ProbeState:
        return {"tool_results": [sentinel]}

    builder: StateGraph = StateGraph(_ProbeState)
    builder.add_node("seed", seed)
    builder.add_node("harbinger_dispatch", make_harbinger_node(harbinger))
    builder.add_edge(START, "seed")
    builder.add_edge("seed", "harbinger_dispatch")
    builder.add_edge("harbinger_dispatch", END)
    graph = builder.compile()

    result = await graph.ainvoke({"tool_name": "decision_queue_read", "params": {}})

    results = result["tool_results"]
    assert len(results) == 2, "add reducer should append, not overwrite"
    assert results[0] is sentinel
    assert results[1].tool_name == "decision_queue_read"
    assert results[1].success is True
