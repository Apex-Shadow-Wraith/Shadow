"""Phase B / Track B — Apex delegating node tests.

Covers the single delegating node at :mod:`modules.shadow.graph.apex_node`.
Apex lands as a *node*, not a sub-graph (design doc §4 wires the fallback leg
directly into the parent graph), so these are node-level tests: they call the
node coroutine directly rather than compiling a ``StateGraph`` wrapper. The
one composition test below builds a throwaway parent graph to prove the
node's list-return appends through the shared ``add`` reducer.

Invariants pinned here:

- Success path — a network-free tool (``apex_cost_report``) round-trips a
  successful ``ToolResult`` through the node.
- Unknown-tool / else-branch envelope — Apex has **no** Grimoire-style
  uninitialized early-return; an unknown tool falls through the dispatch
  table's ``handler is None`` else-branch at ``modules/apex/apex.py:416-420``
  and returns a failure ``ToolResult``. Quoted from source, not assumed.
- ``_call_count`` parity canary — delegation increments Apex's call count
  +1, proving the node routes *through* ``Apex.execute`` (which calls
  ``_record_call`` at ``apex.py:425``/``:430``) and not around it.
- Params pass-through — ``params`` reach ``execute`` verbatim.
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
from pydantic import SecretStr

from modules.apex.apex import Apex
from modules.apex.config import ApexSettings
from modules.base import ToolResult
from modules.shadow.graph import make_apex_node


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_apex(tmp_path: Path) -> Apex:
    """Apex with a fixture key and ``initialize()`` NOT called.

    The node tests below only exercise network-free handlers
    (``apex_cost_report``) and the unknown-tool else-branch, neither of which
    needs the API clients that ``initialize()`` wires up. The log file is
    rerouted into ``tmp_path`` so nothing touches real state.
    """
    settings = ApexSettings(
        log_file=str(tmp_path / "apex_log.json"),
        dry_run=False,
        anthropic_api_key=SecretStr("sk-test-fixture"),
    )
    return Apex(settings)


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apex_node_success_path_round_trips_toolresult(
    tmp_path: Path,
) -> None:
    """A network-free tool returns a successful ToolResult through the node.

    ``apex_cost_report`` aggregates the in-memory ``_call_log`` (empty on a
    fresh instance) — no API client, no ``initialize()`` required — so it is
    the clean success-path probe.
    """
    apex = _make_apex(tmp_path)
    node = make_apex_node(apex)

    out = await node({"tool_name": "apex_cost_report", "params": {}})

    tr = out["tool_results"][0]
    assert isinstance(tr, ToolResult)
    assert tr.success is True
    assert tr.module == "apex"
    assert tr.tool_name == "apex_cost_report"


# ---------------------------------------------------------------------------
# Unknown-tool / else-branch envelope
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apex_node_emits_toolresult_for_unknown_tool(
    tmp_path: Path,
) -> None:
    """Unknown tool name flows through Apex.execute's else branch.

    Apex does NOT early-return on uninitialized state the way Grimoire does.
    Its dispatch table looks the tool up in a handler map and, when
    ``handler is None``, builds a failure ``ToolResult`` in the else branch
    (``modules/apex/apex.py:415-420``):

        handler = handlers.get(tool_name)
        if handler is None:
            result = ToolResult(
                success=False, content=None, tool_name=tool_name,
                module=self.name, error=f"Unknown tool: {tool_name}",
            )

    The result still flows through ``_record_call`` and gets an
    ``execution_time_ms`` stamp — it is not a bare early return.
    """
    apex = _make_apex(tmp_path)
    node = make_apex_node(apex)

    out = await node({"tool_name": "not_a_real_tool", "params": {}})

    tr = out["tool_results"][0]
    assert isinstance(tr, ToolResult)
    assert tr.success is False
    assert tr.module == "apex"
    assert tr.tool_name == "not_a_real_tool"
    assert tr.error == "Unknown tool: not_a_real_tool"


# ---------------------------------------------------------------------------
# _call_count parity canary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apex_node_records_call_count_via_execute_delegation(
    tmp_path: Path,
) -> None:
    """Side-effect parity canary — proves delegation through Apex.execute.

    ``Apex.execute`` calls ``self._record_call(...)`` on every dispatch
    (``apex.py:425`` success, ``:430`` exception), incrementing the inherited
    ``BaseModule._call_count`` (base.py:128). If a future refactor reaches
    past ``execute`` into private handlers, this counter stops advancing and
    the test fails — catching silent drift before it corrupts module-health
    metrics.
    """
    apex = _make_apex(tmp_path)
    node = make_apex_node(apex)

    before = apex._call_count
    await node({"tool_name": "not_a_real_tool", "params": {}})
    after = apex._call_count

    assert after == before + 1, (
        f"Apex._call_count did not advance via the node "
        f"(before={before}, after={after}). This usually means the node "
        f"started bypassing Apex.execute() — restore delegation."
    )


# ---------------------------------------------------------------------------
# Params pass-through
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apex_node_passes_params_through_to_execute(
    tmp_path: Path,
) -> None:
    """The node delivers ``tool_name`` / ``params`` to Apex.execute verbatim."""
    apex = _make_apex(tmp_path)
    captured: dict[str, Any] = {}

    async def capture_execute(tool_name: str, params: dict[str, Any]) -> ToolResult:
        captured["tool_name"] = tool_name
        captured["params"] = params
        return ToolResult(
            success=True, content="captured", tool_name=tool_name,
            module=apex.name,
        )

    apex.execute = capture_execute  # type: ignore[method-assign]
    node = make_apex_node(apex)

    await node(
        {"tool_name": "apex_query", "params": {"task": "x", "model_preference": "y"}},
    )

    assert captured == {
        "tool_name": "apex_query",
        "params": {"task": "x", "model_preference": "y"},
    }


@pytest.mark.asyncio
async def test_apex_node_defaults_missing_params_to_empty_dict(
    tmp_path: Path,
) -> None:
    """A state with no ``params`` key dispatches with ``{}`` — no KeyError."""
    apex = _make_apex(tmp_path)
    captured: dict[str, Any] = {}

    async def capture_execute(tool_name: str, params: dict[str, Any]) -> ToolResult:
        captured["params"] = params
        return ToolResult(
            success=True, content=None, tool_name=tool_name, module=apex.name,
        )

    apex.execute = capture_execute  # type: ignore[method-assign]
    node = make_apex_node(apex)

    await node({"tool_name": "apex_cost_report"})

    assert captured["params"] == {}


# ---------------------------------------------------------------------------
# Reducer composition
# ---------------------------------------------------------------------------


class _ProbeState(TypedDict, total=False):
    """Throwaway parent state mirroring ShadowState's ``tool_results`` reducer.

    Carries the dispatch-scoped ``tool_name`` / ``params`` channels the node
    reads, plus the same ``Annotated[list[ToolResult], add]`` key as
    :class:`modules.shadow.graph.skeleton.ShadowState`. Used only to prove
    the node composes — it is NOT an ``ApexCallState`` shipped in the module.
    """

    tool_name: str
    params: dict[str, Any]
    tool_results: Annotated[list[ToolResult], add]


@pytest.mark.asyncio
async def test_apex_node_tool_results_append_via_shadowstate_reducer(
    tmp_path: Path,
) -> None:
    """The node's list-return APPENDS under the ``add`` reducer.

    Builds a two-node parent graph: a seed node writes one sentinel
    ``ToolResult``, then the Apex node writes its own. Under the
    ``Annotated[list[ToolResult], add]`` reducer the two accumulate rather
    than the second overwriting the first — proving the node's
    ``{"tool_results": [result]}`` shape composes with ShadowState's reducer.
    """
    apex = _make_apex(tmp_path)

    sentinel = ToolResult(
        success=True, content="seed", tool_name="seed", module="probe",
    )

    async def seed(state: _ProbeState) -> _ProbeState:
        return {"tool_results": [sentinel]}

    builder: StateGraph = StateGraph(_ProbeState)
    builder.add_node("seed", seed)
    builder.add_node("apex_dispatch", make_apex_node(apex))
    builder.add_edge(START, "seed")
    builder.add_edge("seed", "apex_dispatch")
    builder.add_edge("apex_dispatch", END)
    graph = builder.compile()

    result = await graph.ainvoke(
        {"tool_name": "apex_cost_report", "params": {}},
    )

    results = result["tool_results"]
    assert len(results) == 2, "add reducer should append, not overwrite"
    assert results[0] is sentinel
    assert results[1].tool_name == "apex_cost_report"
    assert results[1].success is True
