"""Phase B / Track B — parent-graph wiring + assertion tests.

Covers the assembled parent graph at :mod:`modules.shadow.graph.parent`, which
wires the inert Track B nodes into one compiled ``StateGraph`` reproducing the
safety-critical spine of the live decision loop::

    START → router → routable_gate ─dormant─► dormant_node ─► END
                          │dispatch
                          ▼
                        plan ─plan_gate ─blocked─► blocked_node ─► END
                          │              │dispatch
                          └────────────► dispatch ─► END

Load-bearing assertions, in order of importance:

1. **Structural reachability (topology, not behavior).** Re-asserts, across the
   *full* parent graph, the two properties proven in isolation for the
   sub-graphs: a denied plan (``cerberus_approved=False``) and a dormant target
   (``is_routable=False``) each make the dispatch node *unreachable by graph
   topology*. Proven by graph introspection + the gate path-maps.
2. **plan_node side-effect surface (Amendment A).** ``plan_node`` is the only
   genuinely-new node this dispatch; it must carry the COMPLETE side-effect
   surface of ``_step4_plan`` (transitive Cerberus ``safety_check`` → heartbeat,
   the ``cerberus_approved`` verdict, ``_background`` injection), proven one
   assertion per side effect + a one-call delegation canary.
3. **Behavioral canaries.** With a denied / dormant route no module fires and the
   denial appears; with an approved + routable route the module fires.
4. **Span-silence (Amendment B).** No node — and no caller-level span — fires
   during an ``ainvoke``; ``process_input`` is unwired, so no caller exists.
5. **Item-9 sequential confirmation.** The graph runs nodes sequentially within
   one ``ainvoke`` (single linear path; no parallel fan-in to dispatch).
"""

from __future__ import annotations

import contextlib
import inspect
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from modules.base import BaseModule, ModuleStatus, ToolResult
from modules.cerberus.cerberus import Cerberus, SafetyVerdict
from modules.shadow.graph import (
    build_parent_graph,
    compile_parent_graph,
    make_plan_node,
)
from modules.shadow.orchestrator import (
    BrainType,
    Orchestrator,
    TaskClassification,
    TaskType,
)
from tests.test_orchestrator import TEST_CONFIG


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_orch(tmp_path: Path, tag: str = "state") -> Orchestrator:
    """Lightweight Orchestrator (no Ollama boot), state file in tmp_path."""
    cfg = dict(TEST_CONFIG)
    cfg["system"] = {"state_file": str(tmp_path / f"{tag}.json")}
    return Orchestrator(cfg)


async def _make_initialized_cerberus(tmp_path: Path) -> Cerberus:
    """Real Cerberus initialized against the live limits file, I/O in tmp_path.

    Mirrors :func:`tests.test_dispatch_graph._make_initialized_cerberus`. Rule
    eval is pure Python — no Ollama required.
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


class _LeafModule(BaseModule):
    """ONLINE module registered under a real planner-branch name (e.g. grimoire)
    that advertises the tool ``_step4_plan`` will emit, and records whether its
    ``execute`` was reached. The "did I run" canary.
    """

    def __init__(self, name: str, tool: str) -> None:
        super().__init__(name=name, description="parent graph test leaf")
        self.status = ModuleStatus.ONLINE
        self._tool = tool
        self.executed = False

    async def initialize(self) -> None:
        self.status = ModuleStatus.ONLINE

    async def shutdown(self) -> None:
        self.status = ModuleStatus.OFFLINE

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": self._tool,
                "description": "leaf tool",
                "parameters": {},
                "permission_level": "safe",
            }
        ]

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        self.executed = True
        self._record_call(True)
        return ToolResult(
            success=True, content="ran", tool_name=tool_name, module=self.name,
        )


class _DenyCerberus(BaseModule):
    """Stub Cerberus that DENIES every ``safety_check`` — drives the real
    ``_step4_plan`` DENY branch (``orchestrator.py:4453-4464``) deterministically
    without depending on the rule engine (covered by ``tests/test_cerberus.py``).
    """

    def __init__(self) -> None:
        super().__init__(name="cerberus", description="deny stub")
        self.status = ModuleStatus.ONLINE

    async def initialize(self) -> None:
        self.status = ModuleStatus.ONLINE

    async def shutdown(self) -> None:
        self.status = ModuleStatus.OFFLINE

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "safety_check",
                "description": "stub",
                "parameters": {},
                "permission_level": "safe",
            }
        ]

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        import types

        return ToolResult(
            success=True,
            content=types.SimpleNamespace(
                verdict=SafetyVerdict.DENY, reason="stub deny"
            ),
            tool_name=tool_name,
            module="cerberus",
        )


def _classification(target: str = "grimoire") -> TaskClassification:
    return TaskClassification(
        task_type=TaskType.QUESTION,
        complexity="simple",
        target_module=target,
        brain=BrainType.FAST,
        safety_flag=False,
        priority=1,
        confidence=0.85,
    )


def _pin_classification(orch: Orchestrator, target: str) -> None:
    """Force the router node's delegate to a fixed classification.

    The router node delegates to ``_step2_classify``, which would hit Ollama. The
    classifier is covered by ``tests/test_router_node``; here we only need a
    deterministic classification to drive the gates, so we pin it.
    """

    async def fake_classify(user_input: str) -> TaskClassification:
        return _classification(target)

    orch._step2_classify = fake_classify  # type: ignore[assignment]


# ===========================================================================
# 1. Structural reachability — the load-bearing safety assertions
# ===========================================================================


def test_cerberus_denial_unreachable_by_topology(tmp_path: Path) -> None:
    """A denied plan makes ``dispatch`` structurally unreachable across the parent.

    Path-map binding + edge introspection: ``plan_gate`` routes ``"blocked"`` to
    the terminal ``blocked`` node, ``dispatch`` is reachable only via the approved
    branch, and there is no ``blocked → dispatch`` edge.
    """
    orch = _make_orch(tmp_path)

    builder = build_parent_graph(orch)
    plan_ends = builder.branches["plan"]["_gate"].ends
    assert plan_ends == {"blocked": "blocked", "dispatch": "dispatch"}

    compiled = compile_parent_graph(orch)
    edges = [(e.source, e.target) for e in compiled.get_graph().edges]

    assert {t for s, t in edges if s == "blocked"} == {"__end__"}
    assert ("blocked", "dispatch") not in edges
    # Dispatch is reachable ONLY as the approved plan-gate target.
    assert {s for s, t in edges if t == "dispatch"} == {"plan"}


def test_dormant_target_unreachable_by_topology(tmp_path: Path) -> None:
    """A dormant target makes both ``plan`` and ``dispatch`` unreachable.

    The routable gate routes ``"dormant"`` to the terminal ``dormant`` node;
    ``plan`` (and therefore ``dispatch`` downstream of it) is reachable only via
    the routable branch out of ``router``.
    """
    orch = _make_orch(tmp_path)

    builder = build_parent_graph(orch)
    router_ends = builder.branches["router"]["gate"].ends
    assert router_ends == {"dormant": "dormant", "dispatch": "plan"}

    compiled = compile_parent_graph(orch)
    edges = [(e.source, e.target) for e in compiled.get_graph().edges]

    assert {t for s, t in edges if s == "dormant"} == {"__end__"}
    assert ("dormant", "plan") not in edges
    assert ("dormant", "dispatch") not in edges
    # Plan (the only path to dispatch) is reachable ONLY via the routable branch.
    assert {s for s, t in edges if t == "plan"} == {"router"}


def test_item9_single_linear_path_per_invocation(tmp_path: Path) -> None:
    """Item 9: the graph runs nodes sequentially within one ``ainvoke``.

    No node fans into ``dispatch`` in parallel (in-degree 1), and the only
    multi-target sources are the two *mutually exclusive* conditional gates — so
    a single invocation walks one linear path. This is the evidence that the
    cross-``thread_id`` ``_last_route`` hazard (backlog item 9) cannot bite via
    intra-invocation concurrency; the residual concurrent-invocation hazard is
    deferred to the flip (it requires touching ``orchestrator.py:2173``).
    """
    orch = _make_orch(tmp_path)
    compiled = compile_parent_graph(orch)
    edges = [(e.source, e.target) for e in compiled.get_graph().edges]

    # dispatch has exactly one predecessor — no parallel fan-in.
    assert {s for s, t in edges if t == "dispatch"} == {"plan"}
    # plan has exactly one predecessor.
    assert {s for s, t in edges if t == "plan"} == {"router"}
    # The two gates are the only branch points, and each branch is exclusive.
    builder = build_parent_graph(orch)
    assert set(builder.branches.keys()) == {"router", "plan"}


# ===========================================================================
# 2. plan_node side-effect surface (Amendment A) — the only new node
# ===========================================================================


@pytest.mark.asyncio
async def test_plan_node_heartbeat_canary_fires_through_delegation(
    tmp_path: Path,
) -> None:
    """plan_node carries side effect #1: the transitive Cerberus heartbeat write.

    A tool-bearing route (grimoire/``memory_search``) + a real ONLINE Cerberus →
    ``_step4_plan`` runs ``safety_check`` per step, which writes
    ``cerberus_heartbeat.json`` via ``send_heartbeat()`` (``cerberus.py:238``) —
    the file the external watchdog daemon polls. A thinner planner that skipped
    the ``safety_check`` loop would silently sever it.
    """
    orch = _make_orch(tmp_path)
    cerberus = await _make_initialized_cerberus(tmp_path)
    orch.registry.register(cerberus)
    orch.registry.register(_LeafModule("grimoire", "memory_search"))

    heartbeat = tmp_path / "cerberus_heartbeat.json"
    assert not heartbeat.exists(), "precondition: no heartbeat yet"

    plan_node = make_plan_node(orch)
    out = await plan_node(
        {"user_input": "search for cats", "classification": _classification("grimoire")}
    )

    assert heartbeat.exists(), (
        "plan_node did not fire the transitive Cerberus safety_check — the "
        "heartbeat the external daemon depends on was not written"
    )
    payload = json.loads(heartbeat.read_text(encoding="utf-8"))
    assert payload["cerberus_status"] == "healthy"
    # side effect #2 (allowed): verdict write True.
    assert out["plan"].cerberus_approved is True


@pytest.mark.asyncio
async def test_plan_node_verdict_write_false_on_deny(tmp_path: Path) -> None:
    """plan_node carries side effect #2: the ``cerberus_approved=False`` verdict.

    A DENY from Cerberus on a planned step must flow through to
    ``plan.cerberus_approved is False`` (``orchestrator.py:4463``), the value the
    downstream plan-gate reads.
    """
    orch = _make_orch(tmp_path)
    orch.registry.register(_DenyCerberus())
    orch.registry.register(_LeafModule("grimoire", "memory_search"))

    plan_node = make_plan_node(orch)
    out = await plan_node(
        {"user_input": "search for cats", "classification": _classification("grimoire")}
    )

    assert out["plan"].cerberus_approved is False


@pytest.mark.asyncio
async def test_plan_node_injects_background_flag(tmp_path: Path) -> None:
    """plan_node carries side effect #3: ``_background`` param injection.

    Background-intent input ("... in the background") must produce
    ``plan.steps[].params["_background"] is True`` (``orchestrator.py:4477-4481``)
    — dropped by any planner that stops at the gate flag.
    """
    orch = _make_orch(tmp_path)
    orch.registry.register(_LeafModule("grimoire", "memory_search"))

    plan_node = make_plan_node(orch)
    out = await plan_node(
        {
            "user_input": "search for cats in the background",
            "classification": _classification("grimoire"),
        }
    )

    tool_steps = [s for s in out["plan"].steps if s.get("tool")]
    assert tool_steps, "expected a tool-bearing step"
    assert all(s["params"].get("_background") is True for s in tool_steps)


@pytest.mark.asyncio
async def test_plan_node_delegates_step4_plan_exactly_once(tmp_path: Path) -> None:
    """Delegation canary: plan_node invokes ``_step4_plan`` exactly once.

    Proves whole-method delegation — the node reconstructs no thinner Step 4 and
    drives ``_step4_plan`` (not its lower-level primitives) once per visit.
    """
    orch = _make_orch(tmp_path)
    orch.registry.register(_LeafModule("grimoire", "memory_search"))

    plan_node = make_plan_node(orch)
    with patch.object(orch, "_step4_plan", wraps=orch._step4_plan) as spy:
        await plan_node(
            {
                "user_input": "search for cats",
                "classification": _classification("grimoire"),
            }
        )
    assert spy.call_count == 1


# Out-of-harness side effects (enumerated, not asserted, with reason):
# - External watchdog daemon reaction: we assert the heartbeat *file* write
#   above, not the systemd daemon (out of process).
# - Cerberus ``_record_call`` counter: Cerberus-internal, covered by
#   ``tests/test_cerberus.py``.
# - Logging (DENY / APPROVAL_REQUIRED / background-intent): observable, no
#   behavioral contract.
# - APPROVAL_REQUIRED Telegram workflow: a log-only Phase-1 stub
#   (``orchestrator.py:4471-4472``), not implemented.


# ===========================================================================
# 3. Behavioral canaries — confirmation paired with the topology proofs
# ===========================================================================


@pytest.mark.asyncio
async def test_denied_route_never_reaches_module(tmp_path: Path) -> None:
    """Denied plan: the module canary never fires; the denial ToolResult appears."""
    orch = _make_orch(tmp_path)
    _pin_classification(orch, "grimoire")
    orch.registry.register(_DenyCerberus())
    leaf = _LeafModule("grimoire", "memory_search")
    orch.registry.register(leaf)

    graph = compile_parent_graph(orch)
    out = await graph.ainvoke({"user_input": "search for cats"})

    assert leaf.executed is False, "denied plan must never reach a module"
    assert any(
        tr.error == "Plan was denied by Cerberus" and tr.tool_name == "plan"
        for tr in out["tool_results"]
    ), out["tool_results"]


@pytest.mark.asyncio
async def test_dormant_route_never_reaches_module(tmp_path: Path) -> None:
    """Dormant target: the canary never fires; a 'not routable' denial appears."""
    orch = _make_orch(tmp_path)
    _pin_classification(orch, "morpheus")  # not registered → not routable
    leaf = _LeafModule("grimoire", "memory_search")
    orch.registry.register(leaf)
    assert orch.registry.is_routable("morpheus") is False  # precondition

    graph = compile_parent_graph(orch)
    out = await graph.ainvoke({"user_input": "dream something up"})

    assert leaf.executed is False, "a dormant target must never reach a module"
    assert any(
        tr.success is False
        and tr.tool_name == "route"
        and "not routable" in (tr.error or "")
        and "morpheus" in (tr.error or "")
        for tr in out["tool_results"]
    ), out["tool_results"]


@pytest.mark.asyncio
async def test_approved_routable_reaches_module(tmp_path: Path) -> None:
    """Approved + routable: the target module's ``execute`` fires end-to-end."""
    orch = _make_orch(tmp_path)
    _pin_classification(orch, "grimoire")
    leaf = _LeafModule("grimoire", "memory_search")
    orch.registry.register(leaf)  # no cerberus registered → plan approved

    graph = compile_parent_graph(orch)
    out = await graph.ainvoke({"user_input": "search for cats"})

    assert leaf.executed is True
    assert any(tr.success and tr.content == "ran" for tr in out["tool_results"]), (
        out["tool_results"]
    )


# ===========================================================================
# 4. Span-silence (Amendment B) — defined-but-dormant caller-level spans
# ===========================================================================


def test_parent_graph_module_is_span_silent() -> None:
    """The assembler and plan_node add no ``observed_span`` (source-level proof)."""
    from modules.shadow.graph import parent as parent_module
    from modules.shadow.graph import plan_node as plan_node_module

    assert "observed_span(" not in inspect.getsource(parent_module)
    assert "observed_span(" not in inspect.getsource(plan_node_module)


@pytest.mark.asyncio
async def test_no_caller_level_span_fires_during_invoke(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No caller-level span emits during a full ``ainvoke``.

    ``process_input`` is unwired, so the ``router_decision`` / ``module_dispatch``
    / ``response_assembly`` spans have no caller to fire them. A span emitting here
    would be a partial-flip tell. We replace ``observed_span`` with a counting
    context manager and assert it is never entered.
    """
    fired: list[str] = []

    @contextlib.contextmanager
    def counting_span(name, **kwargs):
        fired.append(name)
        yield None

    monkeypatch.setattr(
        "modules.shadow.orchestrator.observed_span", counting_span
    )

    orch = _make_orch(tmp_path)
    _pin_classification(orch, "grimoire")
    orch.registry.register(_LeafModule("grimoire", "memory_search"))

    graph = compile_parent_graph(orch)
    await graph.ainvoke({"user_input": "search for cats"})

    assert fired == [], f"a caller-level span fired from a half-wired caller: {fired}"
