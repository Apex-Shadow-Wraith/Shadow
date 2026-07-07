"""Phase B / Track B — Omen delegating node tests.

Covers the single delegating node at :mod:`modules.shadow.graph.omen_node`.
Omen is a flat dict-dispatch leaf module (a ~47-entry handler table), so these
are node-level tests calling the node coroutine directly; the final test
compiles a throwaway parent graph to prove the list-return appends through the
shared ``add`` reducer.

Invariants pinned here mirror the Apex node suite, plus two Omen-specific
ones called out in the node docstring:

- Success round-trip via a network-free tool (``calculate``, which routes
  through the absorbed Cipher surface ``self._cipher.calculate`` at
  ``modules/omen/omen.py:619`` yet still returns ``module == "omen"``).
- Alias parity — the backward-compat aliases ``data_analyze`` and
  ``logic_verify`` (``omen.py:625``/``:627``) dispatch successfully through
  the node exactly as their canonical names do; they are live surface, not
  dropped tools, so the node must not treat them as unknown.
- Unknown-tool envelope (``omen.py:631-635``), ``_call_count`` parity canary,
  params pass-through + default, reducer composition.
"""

from __future__ import annotations

from operator import add
from pathlib import Path
from typing import Annotated, Any, TypedDict

import pytest
from langgraph.graph import END, START, StateGraph

from modules.base import ToolResult
from modules.omen.omen import Omen
from modules.shadow.graph import make_omen_node


def _make_omen(tmp_path: Path) -> Omen:
    """Omen rooted in tmp_path — ``calculate`` is pure / network-free."""
    return Omen({"project_root": str(tmp_path), "teaching_mode": False})


@pytest.mark.asyncio
async def test_omen_node_success_path_round_trips_toolresult(
    tmp_path: Path,
) -> None:
    """``calculate`` returns a successful ToolResult through the node."""
    omen = _make_omen(tmp_path)
    node = make_omen_node(omen)

    out = await node({"tool_name": "calculate", "params": {"expression": "2 + 2"}})

    tr = out["tool_results"][0]
    assert isinstance(tr, ToolResult)
    assert tr.success is True
    assert tr.module == "omen"
    assert tr.tool_name == "calculate"


@pytest.mark.asyncio
async def test_omen_node_dispatches_backward_compat_aliases(
    tmp_path: Path,
) -> None:
    """The ``data_analyze`` / ``logic_verify`` aliases dispatch, not 404.

    These map onto ``statistics`` / ``logic_check`` in the handler table
    (``omen.py:625``/``:627``). They are live surface; the node must route
    them through ``execute`` like any canonical tool. The Cipher handler
    stamps the *canonical* ``tool_name`` on its result, so a successful
    dispatch with ``tool_name == "statistics"`` / ``"logic_check"`` is the
    direct proof the alias resolved through the handler table rather than
    falling into the ``Unknown tool: ...`` branch.
    """
    omen = _make_omen(tmp_path)
    node = make_omen_node(omen)

    da = await node({"tool_name": "data_analyze", "params": {"data": [1, 2, 3, 4]}})
    tr_da = da["tool_results"][0]
    assert tr_da.success is True
    assert tr_da.module == "omen"
    assert tr_da.tool_name == "statistics"  # alias resolved to canonical handler

    lv = await node(
        {
            "tool_name": "logic_verify",
            "params": {"premises": ["all A are B", "x is A"], "conclusion": "x is B"},
        },
    )
    tr_lv = lv["tool_results"][0]
    assert tr_lv.success is True
    assert tr_lv.module == "omen"
    assert tr_lv.tool_name == "logic_check"  # alias resolved to canonical handler


@pytest.mark.asyncio
async def test_omen_node_emits_toolresult_for_unknown_tool(
    tmp_path: Path,
) -> None:
    """Unknown tool name flows through Omen.execute's handler-is-None branch."""
    omen = _make_omen(tmp_path)
    node = make_omen_node(omen)

    out = await node({"tool_name": "not_a_real_tool", "params": {}})

    tr = out["tool_results"][0]
    assert isinstance(tr, ToolResult)
    assert tr.success is False
    assert tr.module == "omen"
    assert tr.tool_name == "not_a_real_tool"
    assert tr.error == "Unknown tool: not_a_real_tool"


@pytest.mark.asyncio
async def test_omen_node_records_call_count_via_execute_delegation(
    tmp_path: Path,
) -> None:
    """Side-effect parity canary — proves delegation through Omen.execute."""
    omen = _make_omen(tmp_path)
    node = make_omen_node(omen)

    before = omen._call_count
    await node({"tool_name": "not_a_real_tool", "params": {}})
    after = omen._call_count

    assert after == before + 1, (
        f"Omen._call_count did not advance via the node "
        f"(before={before}, after={after}). This usually means the node "
        f"started bypassing Omen.execute() — restore delegation."
    )


@pytest.mark.asyncio
async def test_omen_node_passes_params_through_to_execute(
    tmp_path: Path,
) -> None:
    """The node delivers ``tool_name`` / ``params`` to execute verbatim."""
    omen = _make_omen(tmp_path)
    captured: dict[str, Any] = {}

    async def capture_execute(tool_name: str, params: dict[str, Any]) -> ToolResult:
        captured["tool_name"] = tool_name
        captured["params"] = params
        return ToolResult(
            success=True, content="captured", tool_name=tool_name,
            module=omen.name,
        )

    omen.execute = capture_execute  # type: ignore[method-assign]
    node = make_omen_node(omen)

    await node({"tool_name": "calculate", "params": {"expression": "7 * 6"}})

    assert captured == {
        "tool_name": "calculate",
        "params": {"expression": "7 * 6"},
    }


@pytest.mark.asyncio
async def test_omen_node_defaults_missing_params_to_empty_dict(
    tmp_path: Path,
) -> None:
    """A state with no ``params`` key dispatches with ``{}`` — no KeyError."""
    omen = _make_omen(tmp_path)
    captured: dict[str, Any] = {}

    async def capture_execute(tool_name: str, params: dict[str, Any]) -> ToolResult:
        captured["params"] = params
        return ToolResult(
            success=True, content=None, tool_name=tool_name, module=omen.name,
        )

    omen.execute = capture_execute  # type: ignore[method-assign]
    node = make_omen_node(omen)

    await node({"tool_name": "calculate"})

    assert captured["params"] == {}


class _ProbeState(TypedDict, total=False):
    """Throwaway parent state mirroring ShadowState's ``tool_results`` reducer."""

    tool_name: str
    params: dict[str, Any]
    tool_results: Annotated[list[ToolResult], add]


@pytest.mark.asyncio
async def test_omen_node_tool_results_append_via_shadowstate_reducer(
    tmp_path: Path,
) -> None:
    """The node's list-return APPENDS under the ``add`` reducer."""
    omen = _make_omen(tmp_path)

    sentinel = ToolResult(
        success=True, content="seed", tool_name="seed", module="probe",
    )

    async def seed(state: _ProbeState) -> _ProbeState:
        return {"tool_results": [sentinel]}

    builder: StateGraph = StateGraph(_ProbeState)
    builder.add_node("seed", seed)
    builder.add_node("omen_dispatch", make_omen_node(omen))
    builder.add_edge(START, "seed")
    builder.add_edge("seed", "omen_dispatch")
    builder.add_edge("omen_dispatch", END)
    graph = builder.compile()

    result = await graph.ainvoke(
        {"tool_name": "calculate", "params": {"expression": "1 + 1"}},
    )

    results = result["tool_results"]
    assert len(results) == 2, "add reducer should append, not overwrite"
    assert results[0] is sentinel
    assert results[1].tool_name == "calculate"
    assert results[1].success is True
