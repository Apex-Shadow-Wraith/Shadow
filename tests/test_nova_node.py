"""Phase B / Track B — Nova delegating node tests.

Covers the single delegating node at :mod:`modules.shadow.graph.nova_node`.
Nova is a flat dict-dispatch leaf module, so these are node-level tests
calling the node coroutine directly; the final test compiles a throwaway
parent graph to prove the list-return appends through the shared ``add``
reducer.

Invariants pinned here mirror the Apex node suite: success round-trip,
unknown-tool envelope (``modules/nova/nova.py:172-176``), ``_call_count``
parity canary, params pass-through + default, reducer composition.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

import pytest
from langgraph.graph import END, START, StateGraph

from modules.base import ToolResult
from modules.nova.nova import Nova
from modules.shadow.graph import make_nova_node


def _make_nova() -> Nova:
    """Nova with an empty config — ``template_list`` is network-free."""
    return Nova({})


@pytest.mark.asyncio
async def test_nova_node_success_path_round_trips_toolresult() -> None:
    """``template_list`` returns a successful ToolResult through the node."""
    nova = _make_nova()
    node = make_nova_node(nova)

    out = await node({"tool_name": "template_list", "params": {}})

    tr = out["tool_results"][0]
    assert isinstance(tr, ToolResult)
    assert tr.success is True
    assert tr.module == "nova"
    assert tr.tool_name == "template_list"


@pytest.mark.asyncio
async def test_nova_node_emits_toolresult_for_unknown_tool() -> None:
    """Unknown tool name flows through Nova.execute's else branch."""
    nova = _make_nova()
    node = make_nova_node(nova)

    out = await node({"tool_name": "not_a_real_tool", "params": {}})

    tr = out["tool_results"][0]
    assert isinstance(tr, ToolResult)
    assert tr.success is False
    assert tr.module == "nova"
    assert tr.tool_name == "not_a_real_tool"
    assert tr.error == "Unknown tool: not_a_real_tool"


@pytest.mark.asyncio
async def test_nova_node_records_call_count_via_execute_delegation() -> None:
    """Side-effect parity canary — proves delegation through Nova.execute."""
    nova = _make_nova()
    node = make_nova_node(nova)

    before = nova._call_count
    await node({"tool_name": "not_a_real_tool", "params": {}})
    after = nova._call_count

    assert after == before + 1, (
        f"Nova._call_count did not advance via the node "
        f"(before={before}, after={after}). This usually means the node "
        f"started bypassing Nova.execute() — restore delegation."
    )


@pytest.mark.asyncio
async def test_nova_node_passes_params_through_to_execute() -> None:
    """The node delivers ``tool_name`` / ``params`` to execute verbatim."""
    nova = _make_nova()
    captured: dict[str, Any] = {}

    async def capture_execute(tool_name: str, params: dict[str, Any]) -> ToolResult:
        captured["tool_name"] = tool_name
        captured["params"] = params
        return ToolResult(
            success=True, content="captured", tool_name=tool_name,
            module=nova.name,
        )

    nova.execute = capture_execute  # type: ignore[method-assign]
    node = make_nova_node(nova)

    await node({"tool_name": "template_apply", "params": {"template": "x", "data": {}}})

    assert captured == {
        "tool_name": "template_apply",
        "params": {"template": "x", "data": {}},
    }


@pytest.mark.asyncio
async def test_nova_node_defaults_missing_params_to_empty_dict() -> None:
    """A state with no ``params`` key dispatches with ``{}`` — no KeyError."""
    nova = _make_nova()
    captured: dict[str, Any] = {}

    async def capture_execute(tool_name: str, params: dict[str, Any]) -> ToolResult:
        captured["params"] = params
        return ToolResult(
            success=True, content=None, tool_name=tool_name, module=nova.name,
        )

    nova.execute = capture_execute  # type: ignore[method-assign]
    node = make_nova_node(nova)

    await node({"tool_name": "template_list"})

    assert captured["params"] == {}


class _ProbeState(TypedDict, total=False):
    """Throwaway parent state mirroring ShadowState's ``tool_results`` reducer."""

    tool_name: str
    params: dict[str, Any]
    tool_results: Annotated[list[ToolResult], add]


@pytest.mark.asyncio
async def test_nova_node_tool_results_append_via_shadowstate_reducer() -> None:
    """The node's list-return APPENDS under the ``add`` reducer."""
    nova = _make_nova()

    sentinel = ToolResult(
        success=True, content="seed", tool_name="seed", module="probe",
    )

    async def seed(state: _ProbeState) -> _ProbeState:
        return {"tool_results": [sentinel]}

    builder: StateGraph = StateGraph(_ProbeState)
    builder.add_node("seed", seed)
    builder.add_node("nova_dispatch", make_nova_node(nova))
    builder.add_edge(START, "seed")
    builder.add_edge("seed", "nova_dispatch")
    builder.add_edge("nova_dispatch", END)
    graph = builder.compile()

    result = await graph.ainvoke({"tool_name": "template_list", "params": {}})

    results = result["tool_results"]
    assert len(results) == 2, "add reducer should append, not overwrite"
    assert results[0] is sentinel
    assert results[1].tool_name == "template_list"
    assert results[1].success is True
