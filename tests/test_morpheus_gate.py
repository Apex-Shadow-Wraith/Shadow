"""Phase B / Track B — Morpheus dormancy gate tests.

Covers the routable-module reachability gate at
:mod:`modules.shadow.graph.morpheus_gate`, which lifts the live
``registry.is_routable()`` dormancy filter onto a conditional edge so a dormant
module is *structurally* unreachable as a dispatch target. The invariants, in
order of importance:

1. **Structural reachability (topology, not behavior).** A non-routable target
   (``is_routable() is False``) makes the dispatch node *unreachable by graph
   topology* — proven by graph introspection + the gate predicate + the
   path-map binding, NOT by a runtime "it didn't run" observation. This mirrors
   the dispatcher's reachability proof in ``tests.test_dispatch_graph``.
2. **Inverse.** A *routable* module IS reachable — proving the gate keys on
   ``is_routable`` and is not just blocking everything.
3. **General, not Morpheus-special.** The gate uses ``is_routable`` for *any*
   module, so a future dormant module is covered with no code change.
4. **Delegation / parity.** The gate reads the live ``registry.is_routable`` and
   does not reimplement the dormancy predicate — flip the live predicate and the
   branch follows.

Recon anchors (quoted in the gate's module docstring): ``is_routable`` is
``ModuleRegistry.is_routable`` (``modules/base.py:467``); Morpheus dormancy is
``MorpheusSettings.enabled = False`` (``modules/morpheus/config.py:16``); the
router already filters every routing surface through ``is_routable``
(``orchestrator.py:1944-1947`` / ``:2798`` / ``:2631-2634`` / ``:2656`` /
``:2879``), so this dispatch-side gate is defense-in-depth.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from modules.base import BaseModule, ModuleStatus, ToolResult
from modules.shadow.graph import (
    build_routable_gate_subgraph,
    compile_routable_gate_subgraph,
    make_routable_gate,
)
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

    Mirrors :func:`tests.test_dispatch_graph._make_orch` — cheap construction;
    the test registers only the modules it needs into ``orch.registry``.
    """
    cfg = dict(TEST_CONFIG)
    cfg["system"] = {"state_file": str(tmp_path / f"{tag}.json")}
    return Orchestrator(cfg)


class _LeafModule(BaseModule):
    """A minimal ONLINE module registered under a chosen codename. Records whether
    its ``execute`` was reached — the "did I run" canary for the reachability proof.

    Routability is *not* set on this object: ``ModuleRegistry.is_routable`` reads
    the global ``shadow.config`` singleton by module name (``base.py:482``), not the
    module's own attributes. Tests therefore drive routability through the real
    mechanisms — registering under ``"morpheus"`` (whose ``config.morpheus.enabled``
    is ``False``), or monkeypatching ``config.<name>.enabled`` for a stand-in
    future-dormant module.
    """

    def __init__(self, name: str) -> None:
        super().__init__(name=name, description="dormancy test module")
        self.status = ModuleStatus.ONLINE
        self.executed = False

    async def initialize(self) -> None:
        self.status = ModuleStatus.ONLINE

    async def shutdown(self) -> None:
        self.status = ModuleStatus.OFFLINE

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "noop",
                "description": "dormancy test tool",
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


class _StubRegistry:
    """Minimal registry exposing only ``is_routable`` — lets the predicate test
    flip routability per-name without standing up real modules. Proves the gate
    consults the live predicate rather than hardcoding ``"morpheus"``.
    """

    def __init__(self, routable: dict[str, bool]) -> None:
        self._routable = routable
        self.calls: list[str] = []

    def is_routable(self, name: str) -> bool:
        self.calls.append(name)
        return self._routable.get(name, False)


def _classification(target: str) -> TaskClassification:
    return TaskClassification(
        task_type=TaskType.CREATION,
        complexity="simple",
        target_module=target,
        brain=BrainType.FAST,
        safety_flag=False,
        priority=1,
        confidence=0.85,
    )


def _plan() -> ExecutionPlan:
    return ExecutionPlan(
        steps=[{"step": 1, "tool": "noop", "params": {}}],
        cerberus_approved=True,
    )


# ---------------------------------------------------------------------------
# 1. Structural reachability — the load-bearing assertion
# ---------------------------------------------------------------------------


def test_gate_predicate_routes_dormant_to_dormant_branch() -> None:
    """The predicate binds a non-routable target to ``"dormant"``, routable to
    ``"dispatch"`` — and consults the live ``is_routable`` for the *named* module.

    Pure-function half of the structural proof: it ties the dormant *value* to the
    ``"dormant"`` branch label the topology then routes away from dispatch. A
    missing classification also degrades to ``"dormant"`` (safe default).
    """
    registry = _StubRegistry({"morpheus": False, "omen": True})
    gate = make_routable_gate(registry)

    assert gate({"classification": _classification("morpheus")}) == "dormant"
    assert gate({"classification": _classification("omen")}) == "dispatch"
    # Missing / malformed classification → safe default.
    assert gate({}) == "dormant"
    assert gate({"classification": None}) == "dormant"

    # The predicate asked the registry about the *named* module — not a hardcoded
    # "morpheus" — proving generality and live delegation.
    assert "morpheus" in registry.calls
    assert "omen" in registry.calls


def test_dispatch_node_unreachable_from_dormant_branch_by_topology(
    tmp_path: Path,
) -> None:
    """A dormant target makes ``dispatch`` structurally unreachable — by topology.

    Mirrors ``tests.test_dispatch_graph`` reachability proof. Three deterministic
    checks compose it:

    * **Path-map binding** — the START conditional's ``ends`` map sends ``"dormant"``
      to the ``dormant`` node and ``"dispatch"`` to ``dispatch``.
    * **No edge from the dormant branch to dispatch** — ``dormant``'s only successor
      is ``END``.
    * **Dispatch's sole predecessor is START** — reachable only as the routable
      conditional target, never downstream of ``dormant``.
    """
    orch = _make_orch(tmp_path)

    builder = build_routable_gate_subgraph(orch)
    ends = builder.branches["__start__"]["gate"].ends
    assert ends == {"dormant": "dormant", "dispatch": "dispatch"}

    compiled = compile_routable_gate_subgraph(orch)
    edges = [(e.source, e.target) for e in compiled.get_graph().edges]

    dormant_successors = {t for s, t in edges if s == "dormant"}
    assert dormant_successors == {"__end__"}, (
        f"the dormant branch must terminate, not reach dispatch; got "
        f"successors {dormant_successors}"
    )
    assert ("dormant", "dispatch") not in edges

    dispatch_predecessors = {s for s, t in edges if t == "dispatch"}
    assert dispatch_predecessors == {"__start__"}, (
        f"dispatch must be reachable ONLY as the routable conditional target; "
        f"got predecessors {dispatch_predecessors}"
    )


# ---------------------------------------------------------------------------
# 2. Behavioral confirmation — dormant never runs, routable does
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dormant_target_never_reaches_module_and_emits_denial(
    tmp_path: Path,
) -> None:
    """A dormant (non-routable) target: its module never fires; a denial appears.

    Behavioral confirmation of the structural proof. The denial names the
    non-routable target — the defense-in-depth terminal with no live counterpart.
    """
    orch = _make_orch(tmp_path)
    dormant = _LeafModule("morpheus")
    orch.registry.register(dormant)
    # Real dormancy mechanism: config.morpheus.enabled is False
    # (modules/morpheus/config.py:16) → is_routable("morpheus") is False.
    assert orch.registry.is_routable("morpheus") is False  # precondition

    graph = compile_routable_gate_subgraph(orch)
    out = await graph.ainvoke(
        {"plan": _plan(), "classification": _classification("morpheus")},
    )

    assert dormant.executed is False, "a dormant module must never be dispatched"
    trs = out["tool_results"]
    assert any(
        tr.success is False
        and tr.tool_name == "route"
        and tr.module == "orchestrator"
        and "not routable" in (tr.error or "")
        and "morpheus" in (tr.error or "")
        for tr in trs
    ), trs


@pytest.mark.asyncio
async def test_routable_target_reaches_module(tmp_path: Path) -> None:
    """The inverse: a routable module IS reachable and its ``execute`` fires.

    Proves the gate keys on ``is_routable`` and is not blocking everything.
    """
    orch = _make_orch(tmp_path)
    routable = _LeafModule("omen")
    orch.registry.register(routable)
    # config.omen has no `enabled` attr → is_routable defaults to True.
    assert orch.registry.is_routable("omen") is True  # precondition

    graph = compile_routable_gate_subgraph(orch)
    out = await graph.ainvoke(
        {"plan": _plan(), "classification": _classification("omen")},
    )

    assert routable.executed is True
    trs = out["tool_results"]
    assert any(tr.success and tr.content == "ran" for tr in trs), trs


# ---------------------------------------------------------------------------
# 3. General, not Morpheus-special
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gate_is_general_any_dormant_module_is_unreachable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gate gates by ``is_routable`` for ANY module, not just Morpheus.

    A *future* dormant module — here Nova flipped dormant via the **same config
    mechanism** Morpheus uses (``config.nova.enabled = False``) — is held out
    identically, so a future dormancy is covered without touching this file.
    """
    from shadow.config import config

    orch = _make_orch(tmp_path)
    future_dormant = _LeafModule("nova")
    orch.registry.register(future_dormant)
    # Future dormancy via the identical config flag Morpheus uses.
    monkeypatch.setattr(config.nova, "enabled", False, raising=False)
    assert orch.registry.is_routable("nova") is False  # precondition

    graph = compile_routable_gate_subgraph(orch)
    out = await graph.ainvoke(
        {"plan": _plan(), "classification": _classification("nova")},
    )

    assert future_dormant.executed is False
    trs = out["tool_results"]
    assert any(
        "not routable" in (tr.error or "") and "nova" in (tr.error or "")
        for tr in trs
    ), trs


# ---------------------------------------------------------------------------
# 4. Delegation / parity — gate reads the live predicate, never reimplements it
# ---------------------------------------------------------------------------


def test_gate_delegates_to_live_is_routable_and_follows_it(tmp_path: Path) -> None:
    """Flipping the live ``is_routable`` outcome flips the branch — the gate reads
    the predicate live, it does not snapshot or reimplement the dormancy rule.

    Same module name, two registry states: dormant → ``"dormant"``, enabled →
    ``"dispatch"``. If the gate hardcoded the dormancy rule (e.g. checked the name
    or a cached flag), the branch would not track the registry.
    """
    state = {"classification": _classification("morpheus")}

    dormant_reg = _StubRegistry({"morpheus": False})
    assert make_routable_gate(dormant_reg)(state) == "dormant"
    assert dormant_reg.calls == ["morpheus"], "gate must consult registry.is_routable"

    enabled_reg = _StubRegistry({"morpheus": True})
    assert make_routable_gate(enabled_reg)(state) == "dispatch"
    assert enabled_reg.calls == ["morpheus"]


# ---------------------------------------------------------------------------
# Span parity
# ---------------------------------------------------------------------------


def test_morpheus_gate_module_is_span_silent() -> None:
    """The gate adds no ``observed_span`` — matches the live classifier and the
    span-silent ``dispatch_graph`` loop.
    """
    import inspect

    from modules.shadow.graph import morpheus_gate as morpheus_gate_module

    src = inspect.getsource(morpheus_gate_module)
    assert "observed_span(" not in src
