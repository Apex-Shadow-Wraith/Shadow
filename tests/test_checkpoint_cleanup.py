"""Per-request checkpoint cleanup (S54 F-2 / ledger item 37 follow-on).

Every ``process_input`` call and every deferred worker task runs on a fresh
``thread_id`` against a process-lifetime ``AsyncSqliteSaver``. Without cleanup,
checkpoints accumulate unbounded on a 24/7 daemon (one thread per request,
never deleted). F-2 deletes the request's thread in a ``finally`` on every
exit path — normal return, fast-path early returns after segment 1, and
exceptions — and the worker path does the same per deferred task.

These tests pin: (1) the saver actually writes checkpoints for a thread (so
the zero-surviving-threads assertions below cannot pass vacuously), and
(2/3) both request paths leave zero surviving threads behind.

All external calls stay local: the greeting input rides the keyword fast-path
classifier (no Ollama), and the worker-path input terminates at a graph
terminal without dispatching any module.
"""

from pathlib import Path
from typing import Any

import pytest

from modules.base import BaseModule, ModuleStatus, ToolResult
from modules.shadow.orchestrator import Orchestrator


class _MockWraith(BaseModule):
    """Minimal Wraith so the greeting fast-path's temporal_record lands."""

    def __init__(self):
        super().__init__(name="wraith", description="Mock Wraith")

    async def initialize(self) -> None:
        self.status = ModuleStatus.ONLINE

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        return ToolResult(success=True, content="ok", tool_name=tool_name, module=self.name)

    async def shutdown(self) -> None:
        self.status = ModuleStatus.OFFLINE

    def get_tools(self) -> list[dict[str, Any]]:
        return [{"name": "temporal_record", "description": "Record temporal event",
                 "parameters": {}, "permission_level": "autonomous"}]


def _test_config(tmp_path: Path) -> dict[str, Any]:
    return {
        "system": {
            "state_file": str(tmp_path / "state.json"),
            "task_db": str(tmp_path / "tasks.db"),
            "growth_db": str(tmp_path / "growth.db"),
        },
        "models": {
            "ollama_base_url": "http://localhost:11434",
            "router": {"name": "phi4-mini"},
            "fast_brain": {"name": "phi4-mini"},
            "smart_brain": {"name": "phi4-mini"},
        },
        "decision_loop": {"context_memories": 3},
    }


@pytest.fixture
def tmp_config(tmp_path: Path) -> dict[str, Any]:
    return _test_config(tmp_path)


async def _surviving_thread_ids(orch: Orchestrator) -> set[str]:
    """Distinct thread_ids still present in the saver's checkpoint tables."""
    assert orch._graph_saver is not None, "graph saver not initialized"
    conn = orch._graph_saver.conn
    threads: set[str] = set()
    for table in ("checkpoints", "writes"):
        try:
            rows = await conn.execute_fetchall(
                f"SELECT DISTINCT thread_id FROM {table}"
            )
        except Exception:
            continue  # table absent in this saver version
        threads.update(r[0] for r in rows)
    return threads


@pytest.mark.asyncio
async def test_saver_writes_checkpoints_and_adelete_thread_removes_them(tmp_config):
    """Non-vacuous guard: a bare graph invoke DOES persist checkpoints, and
    adelete_thread removes exactly that thread. Without this test, the
    zero-surviving-threads assertions below could pass because nothing was
    ever written."""
    orch = Orchestrator(tmp_config)
    graph = await orch._ensure_graph()

    config = {"configurable": {"thread_id": "pin:manual-thread"}}
    # Runs to the router interrupt; the greeting rides the keyword fast-path
    # classifier, so no LLM is touched.
    await graph.ainvoke({"user_input": "hello", "source": "user"}, config)

    assert "pin:manual-thread" in await _surviving_thread_ids(orch), (
        "graph invoke persisted no checkpoints — the cleanup assertions "
        "in this module would be vacuous"
    )

    await orch._graph_saver.adelete_thread("pin:manual-thread")
    assert "pin:manual-thread" not in await _surviving_thread_ids(orch)


@pytest.mark.asyncio
async def test_process_input_leaves_no_surviving_threads(tmp_config):
    """Three requests through process_input → zero surviving thread_ids.

    The greeting exits via the fast-path early return after segment 1 — the
    trickiest exit for cleanup, since seg2/seg3 never run."""
    orch = Orchestrator(tmp_config)
    wraith = _MockWraith()
    await wraith.initialize()
    orch.registry.register(wraith)

    for _ in range(3):
        response = await orch.process_input("hello")
        assert response  # request itself succeeded

    assert await _surviving_thread_ids(orch) == set()


@pytest.mark.asyncio
async def test_worker_path_leaves_no_surviving_threads(tmp_config):
    """A deferred task through run_deferred_through_graph cleans up its
    thread even though it uses the separate non-interrupting compile."""
    orch = Orchestrator(tmp_config)

    state = await orch.run_deferred_through_graph("hello", source="autonomous")
    assert isinstance(state, dict)

    assert await _surviving_thread_ids(orch) == set()
