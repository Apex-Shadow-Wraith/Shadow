"""Phase B / Track B — Step 2 dispatcher migration tests.

Covers the dispatcher sub-graph at :mod:`modules.shadow.graph.dispatch_graph`,
which lifts the plan-level Cerberus short-circuit onto a conditional edge and
delegates the per-step loop to the live
:meth:`Orchestrator._step5_execute`. The load-bearing invariants, in order of
importance:

1. **Structural reachability (topology, not behavior).** A denied plan
   (``cerberus_approved=False``) must make the module-dispatch node *unreachable
   by graph topology* — proven by graph introspection + the gate predicate +
   the path-map binding, NOT by a runtime "no module ran" observation. This is
   the safety assertion of the whole cutover; ``cutover-backlog.md`` item 1.
2. **Behavioral canary (confirmation).** With the gate denied, no registered
   module's ``execute`` fires and the denial ``ToolResult`` appears; with the
   gate approved, the target module's ``execute`` does fire.
3. **Three-verdict MODIFY survives the dispatch path.** A real MODIFY verdict
   (PII strip) mutates the params that reach the tool — a two-verdict collapse
   would drop it.
4. **Heartbeat seam.** The per-tool hooks route through ``cerberus.execute``
   (the fragile seam). Recon correction: ``send_heartbeat()`` fires only in the
   ``safety_check`` branch (``cerberus.py:238``), NOT in the Step-5 hooks — so
   dispatch alone does not write the heartbeat; the link survives because the
   same ``cerberus.execute`` path the dispatcher uses for hooks is the one that
   writes the heartbeat for ``safety_check``. This test pins both halves.
5. **Checkpoint round-trip.** A dispatch-emitted ``ToolResult`` survives
   ``AsyncSqliteSaver`` via ``shadow_serde``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from modules.base import BaseModule, ModuleStatus, ToolResult
from modules.cerberus.cerberus import Cerberus
from modules.shadow.graph import (
    build_dispatch_subgraph,
    compile_dispatch_subgraph,
    open_async_sqlite_saver,
)
from modules.shadow.graph.dispatch_graph import _gate
from modules.shadow.orchestrator import (
    BrainType,
    ExecutionPlan,
    Orchestrator,
    TaskClassification,
    TaskType,
)
from tests.test_orchestrator import TEST_CONFIG


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_orch(tmp_path: Path, tag: str = "state") -> Orchestrator:
    """Lightweight Orchestrator (no Ollama boot), state file in tmp_path.

    Mirrors :func:`tests.test_router_node._make_orch` — cheap construction; the
    test registers only the modules it needs into ``orch.registry``.
    """
    cfg = dict(TEST_CONFIG)
    cfg["system"] = {"state_file": str(tmp_path / f"{tag}.json")}
    return Orchestrator(cfg)


async def _make_initialized_cerberus(tmp_path: Path) -> Cerberus:
    """Real Cerberus initialized against the live limits file.

    Heartbeat / audit / snapshot paths rerouted into ``tmp_path`` so the test
    asserts real I/O without touching production state. Rule eval is pure
    Python — no Ollama required. Mirrors the Step 3b sub-graph test helper.
    """
    cerberus = Cerberus(
        config={
            "limits_file": "config/cerberus_limits.yaml",
            "heartbeat_path": str(tmp_path / "cerberus_heartbeat.json"),
            "snapshot_dir": str(tmp_path / "snapshots"),
            "snapshot_db_path": str(tmp_path / "snapshots.db"),
            "db_path": str(tmp_path / "cerberus_audit.db"),
        },
    )
    await cerberus.initialize()
    return cerberus


class _CanaryModule(BaseModule):
    """Minimal ONLINE module that records whether — and with what params — its
    ``execute`` was reached. The "did I run" canary for the reachability proof.
    """

    def __init__(self, tool_name: str) -> None:
        super().__init__(name="canary", description="dispatch test canary")
        self.status = ModuleStatus.ONLINE
        self._tool_name = tool_name
        self.executed = False
        self.received_params: dict[str, Any] | None = None

    async def initialize(self) -> None:
        self.status = ModuleStatus.ONLINE

    async def shutdown(self) -> None:
        self.status = ModuleStatus.OFFLINE

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": self._tool_name,
                "description": "canary tool",
                "parameters": {},
                "permission_level": "safe",
            }
        ]

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        self.executed = True
        self.received_params = params
        self._record_call(True)
        return ToolResult(
            success=True, content="ran", tool_name=tool_name, module=self.name,
        )


def _classification(target: str = "canary") -> TaskClassification:
    return TaskClassification(
        task_type=TaskType.CREATION,
        complexity="simple",
        target_module=target,
        brain=BrainType.FAST,
        safety_flag=False,
        priority=1,
        confidence=0.85,
    )


def _plan(tool: str, params: dict[str, Any], approved: bool) -> ExecutionPlan:
    return ExecutionPlan(
        steps=[{"step": 1, "tool": tool, "params": params}],
        cerberus_approved=approved,
    )


# ---------------------------------------------------------------------------
# 1. Structural reachability — the load-bearing safety assertion
# ---------------------------------------------------------------------------


def test_gate_predicate_routes_denial_to_blocked() -> None:
    """The gate predicate binds ``cerberus_approved=False`` to ``"blocked"``.

    Pure-function half of the structural proof: it ties the denial *value* to
    the ``"blocked"`` branch label that the topology then routes away from
    dispatch. Missing / None / denied plan → ``"blocked"``; approved →
    ``"dispatch"``. Mirrors the guard at ``orchestrator.py:4923``.
    """
    assert _gate({"plan": _plan("web_search", {}, approved=False)}) == "blocked"
    assert _gate({"plan": None}) == "blocked"
    assert _gate({}) == "blocked"
    assert _gate({"plan": _plan("web_search", {}, approved=True)}) == "dispatch"


def test_dispatch_node_unreachable_from_denied_branch_by_topology(
    tmp_path: Path,
) -> None:
    """Denial makes ``dispatch`` structurally unreachable — proven by topology.

    This is the assertion the cutover hinges on, and per the approved plan it
    must be structural, not behavioral. Three deterministic checks compose the
    proof:

    * **Path-map binding** — the START conditional's ``ends`` map sends the
      ``"blocked"`` outcome to the ``blocked`` node (and ``"dispatch"`` to
      ``dispatch``). Combined with the gate predicate above, a denied plan
      reaches the ``blocked`` node.
    * **No edge from the denied branch to dispatch** — the ``blocked`` node's
      only successor is ``END``; there is no ``blocked → dispatch`` edge.
    * **Dispatch's sole predecessor is START** — the dispatch node is reachable
      only as the approved conditional target, never downstream of ``blocked``.

    Together: a denied plan lands on ``blocked`` and no edge path leads from
    there to ``dispatch`` ⇒ the module-dispatch node is unreachable past a
    denial.
    """
    orch = _make_orch(tmp_path)

    # Path-map binding (deterministic, from the builder's branch spec).
    builder = build_dispatch_subgraph(orch)
    ends = builder.branches["__start__"]["_gate"].ends
    assert ends == {"blocked": "blocked", "dispatch": "dispatch"}

    # Topology (from the compiled drawable graph).
    compiled = compile_dispatch_subgraph(orch)
    edges = [(e.source, e.target) for e in compiled.get_graph().edges]

    blocked_successors = {t for s, t in edges if s == "blocked"}
    assert blocked_successors == {"__end__"}, (
        f"the denied branch must terminate, not reach dispatch; got "
        f"successors {blocked_successors}"
    )
    assert ("blocked", "dispatch") not in edges

    dispatch_predecessors = {s for s, t in edges if t == "dispatch"}
    assert dispatch_predecessors == {"__start__"}, (
        f"dispatch must be reachable ONLY as the approved conditional target; "
        f"got predecessors {dispatch_predecessors}"
    )


# ---------------------------------------------------------------------------
# 2. Behavioral canary — confirmation (paired with the topology proof)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_denied_plan_never_reaches_module_and_emits_denial(
    tmp_path: Path,
) -> None:
    """Denied plan: the module canary never fires; the denial ToolResult appears.

    Behavioral confirmation of the structural proof above. The denial envelope
    is byte-for-byte parity with ``orchestrator.py:4924-4930``.
    """
    orch = _make_orch(tmp_path)
    canary = _CanaryModule("web_search")
    orch.registry.register(canary)
    graph = compile_dispatch_subgraph(orch)

    out = await graph.ainvoke(
        {
            "plan": _plan("web_search", {"query": "hi"}, approved=False),
            "classification": _classification(),
        },
    )

    assert canary.executed is False, "denied plan must never reach a module"
    trs = out["tool_results"]
    assert any(
        tr.error == "Plan was denied by Cerberus"
        and tr.tool_name == "plan"
        and tr.module == "orchestrator"
        for tr in trs
    ), trs


@pytest.mark.asyncio
async def test_approved_plan_reaches_module(tmp_path: Path) -> None:
    """Approved plan: the target module's ``execute`` fires and its result flows.

    The True-branch half of the reachability canary.
    """
    orch = _make_orch(tmp_path)
    canary = _CanaryModule("web_search")
    orch.registry.register(canary)
    graph = compile_dispatch_subgraph(orch)

    out = await graph.ainvoke(
        {
            "plan": _plan("web_search", {"query": "hi"}, approved=True),
            "classification": _classification(),
        },
    )

    assert canary.executed is True
    trs = out["tool_results"]
    assert any(tr.success and tr.content == "ran" for tr in trs), trs


# ---------------------------------------------------------------------------
# 3. Three-verdict MODIFY survives the dispatch path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_modify_verdict_mutates_params_that_reach_the_tool(
    tmp_path: Path,
) -> None:
    """A real MODIFY verdict rewrites the params delivered to the tool.

    PII (an email) in a ``web_search`` query triggers the ``pii_in_search``
    rule (``cerberus.py:1257-1263``) → ``SafetyVerdict.MODIFY``. The live hook
    at ``orchestrator.py:4978-4979`` rebinds ``params`` to ``modified_params``
    before the dispatch call at ``:5010``. Delegating the loop preserves this;
    a two-verdict collapse would silently drop MODIFY and the canary would see
    the raw email. The assertion is on what *actually reached the tool*.
    """
    orch = _make_orch(tmp_path)
    cerberus = await _make_initialized_cerberus(tmp_path)
    orch.registry.register(cerberus)
    canary = _CanaryModule("web_search")
    orch.registry.register(canary)
    graph = compile_dispatch_subgraph(orch)

    await graph.ainvoke(
        {
            "plan": _plan(
                "web_search",
                {"query": "contact me at user@example.com"},
                approved=True,
            ),
            "classification": _classification(),
        },
    )

    assert canary.executed is True
    received = canary.received_params or {}
    assert "[EMAIL]" in received.get("query", ""), received
    assert "user@example.com" not in received.get("query", ""), received


# ---------------------------------------------------------------------------
# 4. Heartbeat seam — the fragile delegation seam
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_heartbeat_seam_preserved_by_routing_hooks_through_execute(
    tmp_path: Path,
) -> None:
    """The dispatch path keeps the daemon heartbeat link intact via delegation.

    Recon correction (vs. the prompt's §C framing): ``send_heartbeat()`` is a
    ``safety_check`` side effect (``cerberus.py:238``) — it does NOT fire in the
    Step-5 ``hook_pre_tool`` / ``hook_post_tool`` branches. So this test pins
    both halves of the actual seam:

    * Dispatch routes its per-tool hooks **through ``cerberus.execute``**
      (``cerberus._call_count`` advances) — the seam a duplicating dispatcher
      would sever.
    * That same ``cerberus.execute`` path is the one that writes the heartbeat
      for ``safety_check``. Dispatch alone leaves no heartbeat (correct); a
      ``safety_check`` on the same instance writes it — proving the link the
      external ``daemons/cerberus_watchdog/`` depends on is preserved.
    """
    orch = _make_orch(tmp_path)
    cerberus = await _make_initialized_cerberus(tmp_path)
    orch.registry.register(cerberus)
    canary = _CanaryModule("memory_search")
    orch.registry.register(canary)
    graph = compile_dispatch_subgraph(orch)

    heartbeat = tmp_path / "cerberus_heartbeat.json"
    assert not heartbeat.exists(), "test precondition: no heartbeat yet"

    before = cerberus._call_count
    await graph.ainvoke(
        {
            "plan": _plan("memory_search", {"query": "harmless"}, approved=True),
            "classification": _classification(),
        },
    )

    # Seam half 1: the per-tool hooks went through cerberus.execute.
    assert cerberus._call_count > before, (
        "dispatch did not route hooks through cerberus.execute — the heartbeat "
        "seam (and _record_call) would be severed"
    )
    # Correction made explicit: Step-5 dispatch hooks do NOT write the heartbeat.
    assert not heartbeat.exists(), (
        "the heartbeat is a safety_check side effect, not a dispatch-hook one; "
        "dispatch alone must not have written it"
    )

    # Seam half 2: the same execute path writes the heartbeat for safety_check.
    result = await cerberus.execute(
        "safety_check",
        {
            "action_tool": "memory_search",
            "action_params": {"query": "harmless"},
            "requesting_module": "test",
        },
    )
    assert result.success is True
    assert heartbeat.exists(), (
        "safety_check via the same cerberus.execute the dispatcher uses did NOT "
        "write the heartbeat — the daemon link is broken"
    )
    payload = json.loads(heartbeat.read_text(encoding="utf-8"))
    assert payload["cerberus_status"] == "healthy"


# ---------------------------------------------------------------------------
# 5. Checkpoint round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_toolresult_round_trips_through_checkpoint(
    tmp_path: Path,
) -> None:
    """A dispatch-emitted ``ToolResult`` survives ``AsyncSqliteSaver`` losslessly.

    Mirrors the Cerberus sub-graph checkpoint test: Step 1's serde wiring
    carries the ``ToolResult`` through the checkpoint with full dataclass
    identity. (The ``plan`` / ``classification`` carriers in state round-trip via
    the permissive JsonPlus fallback — design doc §6.5; the assertion here is on
    the ``ToolResult``, whose lossless identity the allowlist guarantees.)
    """
    orch = _make_orch(tmp_path)
    canary = _CanaryModule("web_search")
    orch.registry.register(canary)
    db = tmp_path / "dispatch-checkpoint.sqlite"
    config = {"configurable": {"thread_id": "dispatch-cp"}}

    async with open_async_sqlite_saver(str(db)) as saver:
        graph = compile_dispatch_subgraph(orch, checkpointer=saver)
        out = await graph.ainvoke(
            {
                "plan": _plan("web_search", {"query": "hi"}, approved=True),
                "classification": _classification(),
            },
            config=config,
        )
        live_tr = out["tool_results"][-1]
        assert isinstance(live_tr, ToolResult)

    async with open_async_sqlite_saver(str(db)) as saver2:
        graph2 = compile_dispatch_subgraph(orch, checkpointer=saver2)
        snapshot = await graph2.aget_state(config)

    assert snapshot is not None
    persisted = snapshot.values["tool_results"][-1]
    assert isinstance(persisted, ToolResult), type(persisted)
    assert persisted == live_tr


# ---------------------------------------------------------------------------
# Span parity
# ---------------------------------------------------------------------------


def test_dispatch_graph_module_is_span_silent() -> None:
    """The dispatch nodes add no ``observed_span`` — matches the live Step-5 loop.

    The only span over Step 5 in the live path is the parent
    ``shadow.module_dispatch`` emitted from outside the loop
    (``orchestrator.py:1369-1372``); the nodes must not introduce
    instrumentation the live path lacks inside the loop.
    """
    import inspect

    from modules.shadow.graph import dispatch_graph as dispatch_graph_module

    src = inspect.getsource(dispatch_graph_module)
    assert "observed_span(" not in src
