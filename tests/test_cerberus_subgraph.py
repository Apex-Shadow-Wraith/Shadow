"""Phase B / Track B — Step 3b Cerberus sub-graph tests.

Mirrors :mod:`tests.test_grimoire_subgraph` for the safety gate. Covers the
delegating sub-graph at :mod:`modules.shadow.graph.cerberus_subgraph` plus
the load-bearing invariants surfaced in the Step 3a investigation:

- Envelope + side-effect parity (uninitialized early-return, unknown tool,
  ``_call_count`` increments via delegation).
- **Heartbeat canary** — real file write to a tmp dir, proving the daemon
  link is not silently severed. This is the single most important test in
  the file: a duplicating sub-graph would skip ``Cerberus.send_heartbeat()``
  and the external systemd daemon would force-kill Shadow.
- SafetyVerdict.DENY round-trip (via ``safety_check`` with shell
  metacharacters — the rule-engine DENY path at cerberus.py:1132).
- SafetyVerdict.MODIFY round-trip (via ``hook_pre_tool`` with PII in a
  ``web_search`` query — the pre-hook MODIFY path at cerberus.py:1257-1263).
- Real-Cerberus integration smoke (no Ollama dependency; rule eval is pure
  Python).
- Checkpoint round-trip carrying a Cerberus-emitted ``ToolResult`` through
  ``AsyncSqliteSaver``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from modules.base import ToolResult
from modules.cerberus.cerberus import (
    Cerberus,
    SafetyCheckResult,
    SafetyVerdict,
)
from modules.shadow.graph import (
    compile_cerberus_subgraph,
    open_async_sqlite_saver,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_uninitialized_cerberus(tmp_path: Path) -> Cerberus:
    """Cerberus with config but ``initialize()`` NOT called.

    Useful for envelope + parity tests that don't need rule data loaded.
    The heartbeat path is rerouted into ``tmp_path`` so any accidental write
    stays out of the repo's real ``data/`` directory.
    """
    return Cerberus(
        config={
            "limits_file": str(tmp_path / "noop_limits.yaml"),
            "heartbeat_path": str(tmp_path / "heartbeat.json"),
            "snapshot_dir": str(tmp_path / "snapshots"),
            "snapshot_db_path": str(tmp_path / "snapshots.db"),
        },
    )


async def _make_initialized_cerberus(tmp_path: Path) -> Cerberus:
    """Real Cerberus initialized against the live limits file.

    Heartbeat / audit / snapshot paths rerouted into ``tmp_path`` so the test
    can assert real I/O without touching production state. Rule eval is pure
    Python — no Ollama required.
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


# ---------------------------------------------------------------------------
# Envelope + side-effect parity (no rule data needed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cerberus_subgraph_emits_toolresult_for_unknown_tool(
    tmp_path: Path,
) -> None:
    """Unknown tool name flows through Cerberus.execute's else branch.

    Cerberus does not early-return on uninitialized state the way Grimoire
    does — its dispatch table has no ``if self._limits is None`` guard.
    Unknown tools fall through the if/elif and return a failure ToolResult
    from the else branch. Verified by reading
    ``modules/cerberus/cerberus.py:227-501``.
    """
    cerberus = _make_uninitialized_cerberus(tmp_path)
    graph = compile_cerberus_subgraph(cerberus)

    result = await graph.ainvoke(
        {"tool_name": "not_a_real_tool", "params": {}},
    )

    tr = result["tool_results"][0]
    assert isinstance(tr, ToolResult)
    assert tr.success is False
    assert tr.module == "cerberus"
    assert tr.tool_name == "not_a_real_tool"


@pytest.mark.asyncio
async def test_cerberus_subgraph_records_call_count_via_execute_delegation(
    tmp_path: Path,
) -> None:
    """Side-effect parity canary — same shape as the Grimoire test.

    Proves the sub-graph dispatches through :meth:`Cerberus.execute` and
    therefore picks up the per-branch ``_record_call`` increments. If a
    future refactor reaches past ``execute`` into private internals, this
    counter stops moving and the test fails — catching the regression before
    silent drift damages module health metrics OR severs the daemon
    heartbeat (which the next test guards more directly).
    """
    cerberus = _make_uninitialized_cerberus(tmp_path)
    graph = compile_cerberus_subgraph(cerberus)

    before = cerberus._call_count
    await graph.ainvoke({"tool_name": "not_a_real_tool", "params": {}})
    after = cerberus._call_count

    assert after == before + 1, (
        f"Cerberus._call_count did not advance via the sub-graph "
        f"(before={before}, after={after}). This usually means the sub-graph "
        f"started bypassing Cerberus.execute() — restore delegation. The "
        f"heartbeat canary below depends on the same delegation contract."
    )


@pytest.mark.asyncio
async def test_cerberus_subgraph_passes_params_through_to_execute(
    tmp_path: Path,
) -> None:
    """Sub-graph delivers ``params`` to Cerberus.execute verbatim."""
    cerberus = _make_uninitialized_cerberus(tmp_path)
    captured: dict[str, Any] = {}

    async def capture_execute(tool_name: str, params: dict[str, Any]) -> ToolResult:
        captured["tool_name"] = tool_name
        captured["params"] = params
        return ToolResult(
            success=True, content="captured", tool_name=tool_name,
            module=cerberus.name,
        )

    cerberus.execute = capture_execute  # type: ignore[method-assign]
    graph = compile_cerberus_subgraph(cerberus)

    await graph.ainvoke(
        {
            "tool_name": "safety_check",
            "params": {"action_tool": "x", "action_params": {"a": 1}},
        },
    )

    assert captured == {
        "tool_name": "safety_check",
        "params": {"action_tool": "x", "action_params": {"a": 1}},
    }


# ---------------------------------------------------------------------------
# Heartbeat canary — REAL file write
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cerberus_subgraph_safety_check_writes_real_heartbeat_file(
    tmp_path: Path,
) -> None:
    """The heartbeat canary. Mandatory per Step 3a's load-bearing finding.

    ``Cerberus.execute("safety_check", ...)`` calls
    :meth:`Cerberus.send_heartbeat` at ``cerberus.py:238``, which writes
    ``data/cerberus_heartbeat.json``. The external systemd daemon at
    ``daemons/cerberus_watchdog/`` polls that file; if it goes stale the
    daemon runs ``pkill -f shadow_core``. A duplicating sub-graph that
    skipped ``execute`` would sever this link silently.

    This test reroutes ``heartbeat_path`` into ``tmp_path``, dispatches
    ``safety_check`` through the sub-graph, and asserts that the heartbeat
    JSON actually appeared on disk with a valid payload. Real I/O — no
    mock of ``send_heartbeat``.
    """
    cerberus = await _make_initialized_cerberus(tmp_path)
    heartbeat_path = tmp_path / "cerberus_heartbeat.json"
    assert not heartbeat_path.exists(), "test precondition: no heartbeat yet"

    graph = compile_cerberus_subgraph(cerberus)

    result = await graph.ainvoke(
        {
            "tool_name": "safety_check",
            "params": {
                "action_tool": "memory_search",
                "action_params": {"query": "harmless probe"},
                "requesting_module": "test",
            },
        },
    )

    assert result["tool_results"][0].success is True
    assert heartbeat_path.exists(), (
        "safety_check via sub-graph did NOT write the heartbeat file — "
        "delegation must be broken. The external watchdog daemon depends on "
        "this file existing and being fresh; missing it triggers "
        "emergency_response() and pkill -f shadow_core."
    )
    payload = json.loads(heartbeat_path.read_text(encoding="utf-8"))
    assert payload["cerberus_status"] == "healthy"
    assert isinstance(payload["timestamp"], (int, float))
    assert payload["last_check_id"]


# ---------------------------------------------------------------------------
# Verdict round-trips (DENY + MODIFY)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cerberus_subgraph_safety_check_deny_verdict_round_trip(
    tmp_path: Path,
) -> None:
    """A real DENY verdict survives the sub-graph intact.

    ``safety_check`` on ``bash_execute`` with a shell metacharacter triggers
    the hard-limit rule at ``cerberus.py:1126-1140`` and returns
    ``SafetyVerdict.DENY``. The verdict lives inside ``ToolResult.content``
    (a :class:`SafetyCheckResult` dataclass) — NOT on the envelope. The
    parent-graph orchestration must read ``.content.verdict`` to honour the
    short-circuit; this test pins that shape.
    """
    cerberus = await _make_initialized_cerberus(tmp_path)
    graph = compile_cerberus_subgraph(cerberus)

    result = await graph.ainvoke(
        {
            "tool_name": "safety_check",
            "params": {
                "action_tool": "bash_execute",
                "action_params": {"command": "ls; rm -rf /tmp/probe"},
                "requesting_module": "test",
                "trusted_source": False,
            },
        },
    )

    tr = result["tool_results"][0]
    assert tr.success is True, "the dispatch itself succeeds; the verdict is in content"
    verdict = tr.content
    assert isinstance(verdict, SafetyCheckResult)
    assert verdict.verdict == SafetyVerdict.DENY
    assert verdict.rule_matched == "shell_metacharacters"


@pytest.mark.asyncio
async def test_cerberus_subgraph_hook_pre_tool_modify_verdict_round_trip(
    tmp_path: Path,
) -> None:
    """A real MODIFY verdict survives the sub-graph with ``modified_params``.

    ``hook_pre_tool`` on ``web_search`` with PII (email) in the query
    triggers the ``pii_in_search`` rule at ``cerberus.py:1253-1263`` and
    returns ``SafetyVerdict.MODIFY`` with cleaned params. The third verdict
    is the easy-to-miss one — the parent-graph orchestration must mutate
    the dispatch payload to ``modified_params`` before calling the target
    module; this test pins that the field is reachable.
    """
    cerberus = await _make_initialized_cerberus(tmp_path)
    graph = compile_cerberus_subgraph(cerberus)

    result = await graph.ainvoke(
        {
            "tool_name": "hook_pre_tool",
            "params": {
                "tool_name": "web_search",
                "tool_params": {"query": "contact me at user@example.com"},
                "trusted_source": False,
            },
        },
    )

    tr = result["tool_results"][0]
    assert tr.success is True
    verdict = tr.content
    assert isinstance(verdict, SafetyCheckResult)
    assert verdict.verdict == SafetyVerdict.MODIFY
    assert verdict.rule_matched == "pii_in_search"
    assert verdict.modified_params is not None
    assert "[EMAIL]" in verdict.modified_params["query"]
    assert "user@example.com" not in verdict.modified_params["query"]


@pytest.mark.asyncio
async def test_cerberus_subgraph_safety_check_allow_round_trip(
    tmp_path: Path,
) -> None:
    """Smoke: a benign safety_check returns ``SafetyVerdict.ALLOW``."""
    cerberus = await _make_initialized_cerberus(tmp_path)
    graph = compile_cerberus_subgraph(cerberus)

    result = await graph.ainvoke(
        {
            "tool_name": "safety_check",
            "params": {
                "action_tool": "memory_search",
                "action_params": {"query": "harmless"},
                "requesting_module": "test",
            },
        },
    )
    verdict = result["tool_results"][0].content
    assert isinstance(verdict, SafetyCheckResult)
    assert verdict.verdict == SafetyVerdict.ALLOW


# ---------------------------------------------------------------------------
# Checkpoint round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cerberus_toolresult_round_trips_through_subgraph_checkpoint(
    tmp_path: Path,
) -> None:
    """Step 1's serde wiring carries a Cerberus-emitted ``ToolResult``
    through ``AsyncSqliteSaver`` losslessly.

    Uses the unknown-tool branch (no Ollama, no real safety state needed) —
    purpose is to verify checkpoint serde, not Cerberus rule eval.
    """
    db = tmp_path / "cerberus-subgraph-checkpoint.sqlite"
    cerberus = _make_uninitialized_cerberus(tmp_path)
    config = {"configurable": {"thread_id": "cerberus-subgraph-checkpoint"}}

    async with open_async_sqlite_saver(str(db)) as saver:
        graph = compile_cerberus_subgraph(cerberus, checkpointer=saver)
        result = await graph.ainvoke(
            {"tool_name": "not_a_real_tool", "params": {}},
            config=config,
        )
        live_tr = result["tool_results"][-1]
        assert isinstance(live_tr, ToolResult)

    async with open_async_sqlite_saver(str(db)) as saver2:
        graph2 = compile_cerberus_subgraph(cerberus, checkpointer=saver2)
        snapshot = await graph2.aget_state(config)

    assert snapshot is not None
    persisted = snapshot.values["tool_results"][-1]
    assert isinstance(persisted, ToolResult), type(persisted)
    assert persisted == live_tr
