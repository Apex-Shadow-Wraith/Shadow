"""Phase B / Track B — Wraith delegating node tests.

Covers the single delegating node at :mod:`modules.shadow.graph.wraith_node`.
Wraith lands as a *node*, not a sub-graph (it is a flat if/elif dispatch leaf
module), so these are node-level tests: they call the node coroutine directly
rather than compiling a ``StateGraph`` wrapper. The one composition test
builds a throwaway parent graph to prove the node's list-return appends
through the shared ``add`` reducer.

Invariants pinned here:

- Success path — a network-free tool (``reminder_list``) round-trips a
  successful ``ToolResult`` through the node.
- Unknown-tool / else-branch envelope — an unknown tool falls through the
  if/elif chain's else branch at ``modules/wraith/wraith.py:419-426`` and
  returns a failure ``ToolResult`` with ``error == "Unknown tool: ..."``.
- ``_call_count`` parity canary — delegation increments Wraith's call count
  +1, proving the node routes *through* ``Wraith.execute`` (which calls
  ``_record_call`` at ``wraith.py:429``/``:434``) and not around it.
- Params pass-through — ``params`` reach ``execute`` verbatim, and a missing
  ``params`` key defaults to ``{}``.
- Reducer composition — the node's ``{"tool_results": [result]}`` appends
  via the ``Annotated[list[ToolResult], add]`` reducer that matches
  :class:`modules.shadow.graph.skeleton.ShadowState`.
"""

from __future__ import annotations

from operator import add
from pathlib import Path
from typing import Annotated, Any, TypedDict

import pytest
from langgraph.graph import END, START, StateGraph

from modules.base import ToolResult
from modules.shadow.graph import make_wraith_node
from modules.wraith.wraith import Wraith


def _make_wraith(tmp_path: Path) -> Wraith:
    """Wraith with a temp reminder file — no network, no shared state."""
    return Wraith({"reminder_file": str(tmp_path / "reminders.json")})


@pytest.mark.asyncio
async def test_wraith_node_success_path_round_trips_toolresult(
    tmp_path: Path,
) -> None:
    """``reminder_list`` returns a successful ToolResult through the node."""
    wraith = _make_wraith(tmp_path)
    await wraith.initialize()
    node = make_wraith_node(wraith)

    out = await node({"tool_name": "reminder_list", "params": {}})

    tr = out["tool_results"][0]
    assert isinstance(tr, ToolResult)
    assert tr.success is True
    assert tr.module == "wraith"
    assert tr.tool_name == "reminder_list"


@pytest.mark.asyncio
async def test_wraith_node_emits_toolresult_for_unknown_tool(
    tmp_path: Path,
) -> None:
    """Unknown tool name flows through Wraith.execute's else branch."""
    wraith = _make_wraith(tmp_path)
    node = make_wraith_node(wraith)

    out = await node({"tool_name": "not_a_real_tool", "params": {}})

    tr = out["tool_results"][0]
    assert isinstance(tr, ToolResult)
    assert tr.success is False
    assert tr.module == "wraith"
    assert tr.tool_name == "not_a_real_tool"
    assert tr.error == "Unknown tool: not_a_real_tool"


@pytest.mark.asyncio
async def test_wraith_node_records_call_count_via_execute_delegation(
    tmp_path: Path,
) -> None:
    """Side-effect parity canary — proves delegation through Wraith.execute.

    ``Wraith.execute`` calls ``self._record_call(...)`` on every dispatch
    (``wraith.py:429`` success, ``:434`` exception), incrementing the
    inherited ``BaseModule._call_count``. If a future refactor reaches past
    ``execute`` into private handlers, this counter stops advancing.
    """
    wraith = _make_wraith(tmp_path)
    node = make_wraith_node(wraith)

    before = wraith._call_count
    await node({"tool_name": "not_a_real_tool", "params": {}})
    after = wraith._call_count

    assert after == before + 1, (
        f"Wraith._call_count did not advance via the node "
        f"(before={before}, after={after}). This usually means the node "
        f"started bypassing Wraith.execute() — restore delegation."
    )


@pytest.mark.asyncio
async def test_wraith_node_passes_params_through_to_execute(
    tmp_path: Path,
) -> None:
    """The node delivers ``tool_name`` / ``params`` to Wraith.execute verbatim."""
    wraith = _make_wraith(tmp_path)
    captured: dict[str, Any] = {}

    async def capture_execute(tool_name: str, params: dict[str, Any]) -> ToolResult:
        captured["tool_name"] = tool_name
        captured["params"] = params
        return ToolResult(
            success=True, content="captured", tool_name=tool_name,
            module=wraith.name,
        )

    wraith.execute = capture_execute  # type: ignore[method-assign]
    node = make_wraith_node(wraith)

    await node({"tool_name": "reminder_create", "params": {"content": "x", "importance": 3}})

    assert captured == {
        "tool_name": "reminder_create",
        "params": {"content": "x", "importance": 3},
    }


@pytest.mark.asyncio
async def test_wraith_node_defaults_missing_params_to_empty_dict(
    tmp_path: Path,
) -> None:
    """A state with no ``params`` key dispatches with ``{}`` — no KeyError."""
    wraith = _make_wraith(tmp_path)
    captured: dict[str, Any] = {}

    async def capture_execute(tool_name: str, params: dict[str, Any]) -> ToolResult:
        captured["params"] = params
        return ToolResult(
            success=True, content=None, tool_name=tool_name, module=wraith.name,
        )

    wraith.execute = capture_execute  # type: ignore[method-assign]
    node = make_wraith_node(wraith)

    await node({"tool_name": "reminder_list"})

    assert captured["params"] == {}


class _ProbeState(TypedDict, total=False):
    """Throwaway parent state mirroring ShadowState's ``tool_results`` reducer."""

    tool_name: str
    params: dict[str, Any]
    tool_results: Annotated[list[ToolResult], add]


@pytest.mark.asyncio
async def test_wraith_node_tool_results_append_via_shadowstate_reducer(
    tmp_path: Path,
) -> None:
    """The node's list-return APPENDS under the ``add`` reducer."""
    wraith = _make_wraith(tmp_path)
    await wraith.initialize()

    sentinel = ToolResult(
        success=True, content="seed", tool_name="seed", module="probe",
    )

    async def seed(state: _ProbeState) -> _ProbeState:
        return {"tool_results": [sentinel]}

    builder: StateGraph = StateGraph(_ProbeState)
    builder.add_node("seed", seed)
    builder.add_node("wraith_dispatch", make_wraith_node(wraith))
    builder.add_edge(START, "seed")
    builder.add_edge("seed", "wraith_dispatch")
    builder.add_edge("wraith_dispatch", END)
    graph = builder.compile()

    result = await graph.ainvoke({"tool_name": "reminder_list", "params": {}})

    results = result["tool_results"]
    assert len(results) == 2, "add reducer should append, not overwrite"
    assert results[0] is sentinel
    assert results[1].tool_name == "reminder_list"
    assert results[1].success is True
