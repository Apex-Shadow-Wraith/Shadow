"""
Performance Benchmarks
======================
Measures tool execution time and memory usage for fast-path tools.
Flags pure-computation tools averaging >100ms.
Verifies shutdown() closes DB connections and no unbounded list growth.
"""

import sqlite3
import time
import tracemalloc
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

import pytest

from modules.base import ModuleRegistry, ToolResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _bench_tool(module, tool_name: str, params: dict[str, Any], n: int = 10):
    """Run a tool n times, return (avg_ms, memory_delta_bytes)."""
    tracemalloc.start()
    snap_before = tracemalloc.take_snapshot()

    times = []
    for _ in range(n):
        start = time.perf_counter()
        await module.execute(tool_name, params)
        times.append((time.perf_counter() - start) * 1000)

    snap_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    stats = snap_after.compare_to(snap_before, "lineno")
    mem_delta = sum(s.size_diff for s in stats)

    return sum(times) / len(times), mem_delta


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db(tmp_path):
    """Return a factory for temp DB paths."""
    def _make(name: str) -> str:
        return str(tmp_path / name)
    return _make


# ---------------------------------------------------------------------------
# Cerberus benchmark
# ---------------------------------------------------------------------------

class TestCerberusBenchmark:
    """Benchmark Cerberus safety_check tool."""

    @pytest.fixture
    def cerberus(self, tmp_path):
        import yaml
        from modules.cerberus.cerberus import Cerberus
        limits_path = tmp_path / "limits.yaml"
        limits_path.write_text(yaml.dump({
            "hard_limits": {"financial_access": {"allowed": False}},
            "tiers": {"tier_1_open": {"approval": "autonomous"}},
            "approval_required_tools": [],
            "autonomous_tools": ["safety_check"],
            "hooks": {"pre_tool": {"deny": [], "modify": []}, "post_tool": {"flag": []}},
        }))
        return Cerberus(config={
            "limits_file": str(limits_path),
            "db_path": str(tmp_path / "cerberus_audit.db"),
        })

    @pytest.mark.asyncio
    async def test_safety_check_speed(self, cerberus):
        await cerberus.initialize()
        avg_ms, _ = await _bench_tool(cerberus, "safety_check", {
            "action": "test_action",
            "tool": "test_tool",
            "module": "test_module",
        })
        assert avg_ms < 100, f"safety_check averaged {avg_ms:.1f}ms (threshold: 100ms)"

    @pytest.mark.asyncio
    async def test_shutdown_closes_connection(self, cerberus):
        await cerberus.initialize()
        await cerberus.shutdown()
        # Cerberus may not have a persistent _conn — check if it does
        if hasattr(cerberus, "_conn") and cerberus._conn is not None:
            with pytest.raises(Exception):
                cerberus._conn.execute("SELECT 1")


# ---------------------------------------------------------------------------
# Cipher benchmark
# ---------------------------------------------------------------------------

class TestCipherBenchmark:
    """Benchmark Cipher calculate tool."""

    @pytest.fixture
    def cipher(self):
        from modules.cipher.cipher import Cipher
        return Cipher()

    @pytest.mark.asyncio
    async def test_calculate_speed(self, cipher):
        await cipher.initialize()
        avg_ms, _ = await _bench_tool(cipher, "calculate", {
            "expression": "2 + 2 * 10",
        })
        assert avg_ms < 100, f"calculate averaged {avg_ms:.1f}ms (threshold: 100ms)"


# ---------------------------------------------------------------------------
# Wraith benchmark
# ---------------------------------------------------------------------------

class TestWraithBenchmark:
    """Benchmark Wraith reminder_list tool."""

    @pytest.fixture
    def wraith(self, tmp_path):
        from modules.wraith.wraith import Wraith
        return Wraith(config={
            "db_path": str(tmp_path / "wraith.db"),
        })

    @pytest.mark.asyncio
    async def test_reminder_list_speed(self, wraith):
        await wraith.initialize()
        avg_ms, _ = await _bench_tool(wraith, "reminder_list", {})
        assert avg_ms < 100, f"reminder_list averaged {avg_ms:.1f}ms (threshold: 100ms)"

    @pytest.mark.asyncio
    async def test_shutdown_closes_connection(self, wraith):
        await wraith.initialize()
        await wraith.shutdown()
        # Wraith uses TemporalTracker with _conn
        tracker = getattr(wraith, "_temporal_tracker", None)
        if tracker and hasattr(tracker, "_conn"):
            assert tracker._conn is None, "TemporalTracker._conn not closed after shutdown"


# ---------------------------------------------------------------------------
# Void benchmark
# ---------------------------------------------------------------------------

class TestVoidBenchmark:
    """Benchmark Void health_check tool."""

    @pytest.fixture
    def void_module(self, tmp_path):
        from modules.void.void import Void
        return Void(config={
            "db_path": str(tmp_path / "void.db"),
        })

    @pytest.mark.asyncio
    async def test_health_check_speed(self, void_module):
        await void_module.initialize()
        mock_psutil = MagicMock()
        mock_psutil.cpu_percent.return_value = 25.0
        mock_psutil.virtual_memory.return_value = MagicMock(
            total=32 * 1024**3, used=8 * 1024**3, percent=25.0
        )
        mock_psutil.disk_usage.return_value = MagicMock(
            total=1000 * 1024**3, used=450 * 1024**3, percent=45.0
        )
        import sys
        original = sys.modules.get("psutil")
        sys.modules["psutil"] = mock_psutil
        try:
            avg_ms, _ = await _bench_tool(void_module, "health_check", {})
        finally:
            if original is not None:
                sys.modules["psutil"] = original
            else:
                sys.modules.pop("psutil", None)
        assert avg_ms < 100, f"health_check averaged {avg_ms:.1f}ms (threshold: 100ms)"

    @pytest.mark.asyncio
    async def test_shutdown_closes_connection(self, void_module):
        await void_module.initialize()
        await void_module.shutdown()
        assert void_module._conn is None, "Void._conn not closed after shutdown"


# ---------------------------------------------------------------------------
# Nova benchmark
# ---------------------------------------------------------------------------

class TestNovaBenchmark:
    """Benchmark Nova format_document tool."""

    @pytest.fixture
    def nova(self):
        from modules.nova.nova import Nova
        return Nova()

    @pytest.mark.asyncio
    async def test_format_document_speed(self, nova):
        await nova.initialize()
        avg_ms, _ = await _bench_tool(nova, "format_document", {
            "content": "Test document content for benchmarking.",
            "format": "markdown",
        })
        assert avg_ms < 100, f"format_document averaged {avg_ms:.1f}ms (threshold: 100ms)"


# ---------------------------------------------------------------------------
# Shadow benchmark
# ---------------------------------------------------------------------------

class TestShadowBenchmark:
    """Benchmark ShadowModule task_list tool."""

    @pytest.fixture
    def shadow_mod(self, tmp_path):
        from modules.shadow.shadow_module import ShadowModule
        registry = ModuleRegistry()
        return ShadowModule(
            config={"db_path": str(tmp_path / "shadow_tasks.db")},
            registry=registry,
        )

    @pytest.mark.asyncio
    async def test_task_list_speed(self, shadow_mod):
        await shadow_mod.initialize()
        avg_ms, _ = await _bench_tool(shadow_mod, "task_list", {})
        assert avg_ms < 100, f"task_list averaged {avg_ms:.1f}ms (threshold: 100ms)"

    @pytest.mark.asyncio
    async def test_shutdown_closes_connection(self, shadow_mod):
        await shadow_mod.initialize()
        await shadow_mod.shutdown()
        assert shadow_mod._db is None, "ShadowModule._db not closed after shutdown"


# ---------------------------------------------------------------------------
# Morpheus benchmark
# ---------------------------------------------------------------------------

class TestMorpheusBenchmark:
    """Benchmark Morpheus experiment_list tool."""

    @pytest.fixture
    def morpheus(self, tmp_path):
        from modules.morpheus.morpheus import Morpheus
        return Morpheus(config={
            "db_path": str(tmp_path / "morpheus.db"),
        })

    @pytest.mark.asyncio
    async def test_experiment_list_speed(self, morpheus):
        await morpheus.initialize()
        avg_ms, _ = await _bench_tool(morpheus, "experiment_list", {})
        assert avg_ms < 100, f"experiment_list averaged {avg_ms:.1f}ms (threshold: 100ms)"

    @pytest.mark.asyncio
    async def test_shutdown_closes_connection(self, morpheus):
        await morpheus.initialize()
        await morpheus.shutdown()
        assert morpheus._conn is None, "Morpheus._conn not closed after shutdown"


# ---------------------------------------------------------------------------
# Unbounded growth check
# ---------------------------------------------------------------------------

class TestNoUnboundedGrowth:
    """Verify that 50 rapid calls don't cause unbounded list growth."""

    @pytest.fixture
    def cerberus(self, tmp_path):
        import yaml
        from modules.cerberus.cerberus import Cerberus
        limits_path = tmp_path / "limits.yaml"
        limits_path.write_text(yaml.dump({
            "hard_limits": {"financial_access": {"allowed": False}},
            "tiers": {"tier_1_open": {"approval": "autonomous"}},
            "approval_required_tools": [],
            "autonomous_tools": ["safety_check"],
            "hooks": {"pre_tool": {"deny": [], "modify": []}, "post_tool": {"flag": []}},
        }))
        return Cerberus(config={
            "limits_file": str(limits_path),
            "db_path": str(tmp_path / "cerberus_audit.db"),
        })

    @pytest.mark.asyncio
    async def test_no_memory_leak_cerberus(self, cerberus):
        await cerberus.initialize()
        for i in range(50):
            await cerberus.execute("safety_check", {
                "action": f"action_{i}",
                "tool": "test",
                "module": "test",
            })
        # Audit log in memory should not grow without bound
        # (it's OK if it has entries — just shouldn't be >50 in memory
        #  if there's a DB backend)
        if hasattr(cerberus, "_audit_log"):
            assert len(cerberus._audit_log) <= 100, (
                f"Audit log grew to {len(cerberus._audit_log)} entries in memory"
            )
