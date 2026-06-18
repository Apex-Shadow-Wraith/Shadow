"""Phase B / Track B — ShadowModule delegating node tests.

Covers the single delegating node at
:mod:`modules.shadow.graph.shadow_module_node`. ShadowModule is the
router-facing task-tracking / module-health BaseModule peer (distinct from
the Shadow orchestrator class), a flat if/elif dispatch leaf. These are
node-level tests calling the node coroutine directly; the final test compiles
a throwaway parent graph to prove the list-return appends through the shared
``add`` reducer.

Invariants pinned here mirror the Apex node suite, with one ShadowModule
specific: the unknown-tool envelope uses the distinct message
``"Unknown Shadow tool: ..."`` and early-returns after recording the call
(``modules/shadow/shadow_module.py:105-113``) — both preserved by delegating
to ``execute`` rather than re-implementing dispatch.
"""

from __future__ import annotations

from operator import add
from pathlib import Path
from typing import Annotated, Any, TypedDict

import pytest
from langgraph.graph import END, START, StateGraph

from modules.base import ModuleRegistry, ToolResult
from modules.shadow.graph import make_shadow_module_node
from modules.shadow.shadow_module import ShadowModule


def _make_shadow_module(tmp_path: Path) -> ShadowModule:
    """ShadowModule with a temp task DB and an empty registry."""
    return ShadowModule({"db_path": str(tmp_path / "shadow_tasks.db")}, ModuleRegistry())


@pytest.mark.asyncio
async def test_shadow_module_node_success_path_round_trips_toolresult(
    tmp_path: Path,
) -> None:
    """``task_list`` returns a successful ToolResult through the node."""
    sm = _make_shadow_module(tmp_path)
    await sm.initialize()
    node = make_shadow_module_node(sm)

    out = await node({"tool_name": "task_list", "params": {}})

    tr = out["tool_results"][0]
    assert isinstance(tr, ToolResult)
    assert tr.success is True
    assert tr.module == "shadow"
    assert tr.tool_name == "task_list"


@pytest.mark.asyncio
async def test_shadow_module_node_emits_toolresult_for_unknown_tool(
    tmp_path: Path,
) -> None:
    """Unknown tool name flows through the distinct early-return else branch."""
    sm = _make_shadow_module(tmp_path)
    await sm.initialize()
    node = make_shadow_module_node(sm)

    out = await node({"tool_name": "not_a_real_tool", "params": {}})

    tr = out["tool_results"][0]
    assert isinstance(tr, ToolResult)
    assert tr.success is False
    assert tr.module == "shadow"
    assert tr.tool_name == "not_a_real_tool"
    assert tr.error == "Unknown Shadow tool: not_a_real_tool"


@pytest.mark.asyncio
async def test_shadow_module_node_records_call_count_via_execute_delegation(
    tmp_path: Path,
) -> None:
    """Side-effect parity canary — proves delegation through ShadowModule.execute.

    The unknown-tool branch records the call (``_record_call(False)`` at
    ``shadow_module.py:105``) before its early return, so the counter still
    advances +1 — proving the node routed through ``execute``.
    """
    sm = _make_shadow_module(tmp_path)
    await sm.initialize()
    node = make_shadow_module_node(sm)

    before = sm._call_count
    await node({"tool_name": "not_a_real_tool", "params": {}})
    after = sm._call_count

    assert after == before + 1, (
        f"ShadowModule._call_count did not advance via the node "
        f"(before={before}, after={after}). This usually means the node "
        f"started bypassing ShadowModule.execute() — restore delegation."
    )


@pytest.mark.asyncio
async def test_shadow_module_node_passes_params_through_to_execute(
    tmp_path: Path,
) -> None:
    """The node delivers ``tool_name`` / ``params`` to execute verbatim."""
    sm = _make_shadow_module(tmp_path)
    captured: dict[str, Any] = {}

    async def capture_execute(tool_name: str, params: dict[str, Any]) -> ToolResult:
        captured["tool_name"] = tool_name
        captured["params"] = params
        return ToolResult(
            success=True, content="captured", tool_name=tool_name,
            module=sm.name,
        )

    sm.execute = capture_execute  # type: ignore[method-assign]
    node = make_shadow_module_node(sm)

    await node({"tool_name": "task_create", "params": {"title": "x", "priority": 2}})

    assert captured == {
        "tool_name": "task_create",
        "params": {"title": "x", "priority": 2},
    }


@pytest.mark.asyncio
async def test_shadow_module_node_defaults_missing_params_to_empty_dict(
    tmp_path: Path,
) -> None:
    """A state with no ``params`` key dispatches with ``{}`` — no KeyError."""
    sm = _make_shadow_module(tmp_path)
    captured: dict[str, Any] = {}

    async def capture_execute(tool_name: str, params: dict[str, Any]) -> ToolResult:
        captured["params"] = params
        return ToolResult(
            success=True, content=None, tool_name=tool_name, module=sm.name,
        )

    sm.execute = capture_execute  # type: ignore[method-assign]
    node = make_shadow_module_node(sm)

    await node({"tool_name": "task_list"})

    assert captured["params"] == {}


class _ProbeState(TypedDict, total=False):
    """Throwaway parent state mirroring ShadowState's ``tool_results`` reducer."""

    tool_name: str
    params: dict[str, Any]
    tool_results: Annotated[list[ToolResult], add]


@pytest.mark.asyncio
async def test_shadow_module_node_tool_results_append_via_shadowstate_reducer(
    tmp_path: Path,
) -> None:
    """The node's list-return APPENDS under the ``add`` reducer."""
    sm = _make_shadow_module(tmp_path)
    await sm.initialize()

    sentinel = ToolResult(
        success=True, content="seed", tool_name="seed", module="probe",
    )

    async def seed(state: _ProbeState) -> _ProbeState:
        return {"tool_results": [sentinel]}

    builder: StateGraph = StateGraph(_ProbeState)
    builder.add_node("seed", seed)
    builder.add_node("shadow_module_dispatch", make_shadow_module_node(sm))
    builder.add_edge(START, "seed")
    builder.add_edge("seed", "shadow_module_dispatch")
    builder.add_edge("shadow_module_dispatch", END)
    graph = builder.compile()

    result = await graph.ainvoke({"tool_name": "task_list", "params": {}})

    results = result["tool_results"]
    assert len(results) == 2, "add reducer should append, not overwrite"
    assert results[0] is sentinel
    assert results[1].tool_name == "task_list"
    assert results[1].success is True
