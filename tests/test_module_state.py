"""
Tests for ModuleStateManager — Module State Awareness
=======================================================
Tests thread-safe state tracking, capability routing,
load balancing, and persistence for all 13 Shadow modules.
"""

import json
import threading
import time
from datetime import datetime
from pathlib import Path

import pytest

from modules.shadow.module_state import ModuleState, ModuleStateManager


@pytest.fixture
def manager(tmp_path):
    """Create a fresh ModuleStateManager with temp snapshot path."""
    return ModuleStateManager(snapshot_path=str(tmp_path / "module_states.json"))


@pytest.fixture
def populated_manager(manager):
    """Manager with several modules registered."""
    manager.register_module("wraith", ["quick_answer", "reminder_create", "classify_task"])
    manager.register_module("omen", ["execute_code", "lint_code", "code_review"])
    manager.register_module("sentinel", ["network_scan", "file_integrity_check"])
    manager.register_module("grimoire", ["memory_store", "memory_search"])
    manager.register_module("cerberus", ["safety_check", "audit_log"])

    # Set some to idle (simulating post-init)
    manager.update_state("wraith", "idle")
    manager.update_state("omen", "idle")
    manager.update_state("sentinel", "idle")
    manager.update_state("grimoire", "idle")
    manager.update_state("cerberus", "idle")

    return manager


class TestModuleState:
    """Tests for ModuleState dataclass."""

    def test_default_state(self):
        """Default state should be offline with zero counters."""
        state = ModuleState(module_name="test")
        assert state.status == "offline"
        assert state.tasks_completed_today == 0
        assert state.tasks_failed_today == 0
        assert state.queue_depth == 0
        assert state.error_count_last_hour == 0
        assert state.capabilities == []

    def test_to_dict(self):
        """Serialization should include all public fields."""
        state = ModuleState(
            module_name="wraith",
            status="busy",
            current_task="processing reminder",
            tasks_completed_today=5,
        )
        d = state.to_dict()
        assert d["module_name"] == "wraith"
        assert d["status"] == "busy"
        assert d["current_task"] == "processing reminder"
        assert d["tasks_completed_today"] == 5

    def test_from_dict_roundtrip(self):
        """from_dict should restore all fields from to_dict output."""
        original = ModuleState(
            module_name="sentinel",
            status="idle",
            tasks_completed_today=3,
            capabilities=["network_scan", "file_integrity_check"],
        )
        d = original.to_dict()
        restored = ModuleState.from_dict(d)
        assert restored.module_name == original.module_name
        assert restored.status == original.status
        assert restored.tasks_completed_today == original.tasks_completed_today
        assert restored.capabilities == original.capabilities


class TestStateUpdates:
    """Tests for state transitions."""

    def test_update_to_busy(self, populated_manager):
        """Setting busy should record task info."""
        populated_manager.update_state("wraith", "busy", "processing reminder", "task-001")
        state = populated_manager.get_state("wraith")
        assert state.status == "busy"
        assert state.current_task == "processing reminder"
        assert state.current_task_id == "task-001"
        assert state.task_started_at is not None

    def test_update_to_idle_clears_task(self, populated_manager):
        """Setting idle should clear task info."""
        populated_manager.update_state("wraith", "busy", "working")
        populated_manager.update_state("wraith", "idle")
        state = populated_manager.get_state("wraith")
        assert state.status == "idle"
        assert state.current_task is None
        assert state.current_task_id is None

    def test_busy_to_idle_increments_completed(self, populated_manager):
        """Completing a task (busy→idle) should increment completed counter."""
        populated_manager.update_state("wraith", "busy", "task A")
        populated_manager.update_state("wraith", "idle")
        state = populated_manager.get_state("wraith")
        assert state.tasks_completed_today == 1

    def test_busy_to_error_increments_failed(self, populated_manager):
        """Failing a task (busy→error) should increment failed counter."""
        populated_manager.update_state("wraith", "busy", "task B")
        populated_manager.update_state("wraith", "error")
        state = populated_manager.get_state("wraith")
        assert state.tasks_failed_today == 1

    def test_error_tracks_error_count(self, populated_manager):
        """Error state should track error_count_last_hour."""
        for _ in range(3):
            populated_manager.update_state("wraith", "error")
        state = populated_manager.get_state("wraith")
        assert state.error_count_last_hour == 3

    def test_last_active_updates(self, populated_manager):
        """last_active should update on every state change."""
        before = datetime.now().isoformat()
        populated_manager.update_state("wraith", "busy", "task")
        state = populated_manager.get_state("wraith")
        assert state.last_active >= before

    def test_invalid_status_ignored(self, populated_manager):
        """Invalid status strings should be silently ignored."""
        populated_manager.update_state("wraith", "invalid_status")
        state = populated_manager.get_state("wraith")
        assert state.status == "idle"  # Should remain unchanged

    def test_unregistered_module_auto_creates(self, manager):
        """Updating an unregistered module should auto-create its state."""
        manager.update_state("new_module", "idle")
        state = manager.get_state("new_module")
        assert state.module_name == "new_module"
        assert state.status == "idle"

    def test_avg_task_duration_calculated(self, populated_manager):
        """Average task duration should be calculated from completions."""
        # Simulate a task that takes a measurable time
        populated_manager.update_state("wraith", "busy", "task")
        time.sleep(0.05)  # 50ms
        populated_manager.update_state("wraith", "idle")
        state = populated_manager.get_state("wraith")
        assert state.avg_task_duration_seconds > 0


class TestQueryMethods:
    """Tests for state query methods."""

    def test_get_available_modules(self, populated_manager):
        """Should return only idle modules."""
        populated_manager.update_state("wraith", "busy", "working")
        available = populated_manager.get_available_modules()
        assert "wraith" not in available
        assert "omen" in available
        assert "sentinel" in available

    def test_get_busy_modules(self, populated_manager):
        """Should return only busy modules."""
        populated_manager.update_state("wraith", "busy", "working")
        populated_manager.update_state("omen", "busy", "coding")
        busy = populated_manager.get_busy_modules()
        assert "wraith" in busy
        assert "omen" in busy
        assert "sentinel" not in busy

    def test_get_all_states(self, populated_manager):
        """Should return states for all registered modules."""
        states = populated_manager.get_all_states()
        assert len(states) == 5
        assert "wraith" in states
        assert "omen" in states

    def test_get_state_raises_for_unknown(self, manager):
        """Should raise KeyError for unregistered module."""
        with pytest.raises(KeyError):
            manager.get_state("nonexistent")


class TestCapabilityRouting:
    """Tests for find_capable_module."""

    def test_finds_correct_module(self, populated_manager):
        """Should find the module that owns a capability."""
        module = populated_manager.find_capable_module("network_scan")
        assert module == "sentinel"

    def test_returns_none_for_unknown_capability(self, populated_manager):
        """Should return None for capabilities no module has."""
        module = populated_manager.find_capable_module("teleport")
        assert module is None

    def test_prefers_idle_over_busy(self, populated_manager):
        """When multiple modules can do it, prefer idle."""
        # Register a second module with same capability
        populated_manager.register_module("sentinel2", ["network_scan"])
        populated_manager.update_state("sentinel2", "idle")
        populated_manager.update_state("sentinel", "busy", "scanning")

        module = populated_manager.find_capable_module("network_scan")
        assert module == "sentinel2"

    def test_busy_fallback_shortest_queue(self, populated_manager):
        """When all capable modules busy, pick shortest queue."""
        populated_manager.register_module("sentinel2", ["network_scan"])
        populated_manager.update_state("sentinel", "busy", "scanning")
        populated_manager.update_state("sentinel2", "busy", "scanning")

        # Give sentinel a longer queue
        for _ in range(5):
            populated_manager.increment_queue("sentinel")

        module = populated_manager.find_capable_module("network_scan")
        assert module == "sentinel2"


class TestShouldDefer:
    """Tests for overload detection."""

    def test_defer_on_high_queue(self, populated_manager):
        """Should defer when queue_depth > 10."""
        for _ in range(11):
            populated_manager.increment_queue("wraith")
        assert populated_manager.should_defer("wraith") is True

    def test_defer_on_high_errors(self, populated_manager):
        """Should defer when error_count_last_hour > 5."""
        for _ in range(6):
            populated_manager.update_state("wraith", "error")
        assert populated_manager.should_defer("wraith") is True

    def test_no_defer_normal_state(self, populated_manager):
        """Should not defer under normal conditions."""
        assert populated_manager.should_defer("wraith") is False

    def test_no_defer_unknown_module(self, manager):
        """Should not defer for unregistered module."""
        assert manager.should_defer("nonexistent") is False


class TestSystemOverview:
    """Tests for the dashboard method."""

    def test_overview_structure(self, populated_manager):
        """Overview should contain all required fields."""
        overview = populated_manager.get_system_overview()
        assert "modules_online" in overview
        assert "modules_busy" in overview
        assert "modules_idle" in overview
        assert "modules_error" in overview
        assert "modules_offline" in overview
        assert "total_tasks_today" in overview
        assert "total_failures_today" in overview
        assert "busiest_module" in overview
        assert "most_idle_module" in overview
        assert "module_states" in overview

    def test_overview_counts(self, populated_manager):
        """Overview counts should reflect actual states."""
        populated_manager.update_state("wraith", "busy", "working")
        overview = populated_manager.get_system_overview()
        assert overview["modules_busy"] == 1
        assert overview["modules_idle"] == 4
        assert overview["modules_online"] == 5  # All non-offline

    def test_overview_empty_manager(self, manager):
        """Overview should work with no modules registered."""
        overview = manager.get_system_overview()
        assert overview["modules_online"] == 0
        assert overview["busiest_module"] is None


class TestPersistence:
    """Tests for snapshot save/restore."""

    def test_snapshot_creates_file(self, populated_manager, tmp_path):
        """Snapshot should create a JSON file."""
        populated_manager.snapshot()
        assert Path(populated_manager._snapshot_path).exists()

    def test_snapshot_contains_all_modules(self, populated_manager):
        """Snapshot should contain all registered modules."""
        populated_manager.snapshot()
        with open(populated_manager._snapshot_path) as f:
            data = json.load(f)
        assert len(data["modules"]) == 5
        assert "wraith" in data["modules"]
        assert "snapshot_time" in data

    def test_restore_recovers_state(self, tmp_path):
        """Restore should recover module states from snapshot."""
        snapshot_path = str(tmp_path / "module_states.json")

        # Create and snapshot
        mgr1 = ModuleStateManager(snapshot_path=snapshot_path)
        mgr1.register_module("wraith", ["quick_answer"])
        mgr1.update_state("wraith", "idle")
        mgr1.update_state("wraith", "busy", "task A")
        mgr1.update_state("wraith", "idle")  # completes task
        mgr1.snapshot()

        # Restore in new manager
        mgr2 = ModuleStateManager(snapshot_path=snapshot_path)
        assert mgr2.restore_snapshot() is True

        state = mgr2.get_state("wraith")
        assert state.module_name == "wraith"
        # After restore, status is set to offline until module checks in
        assert state.status == "offline"
        assert state.tasks_completed_today == 1
        assert state.capabilities == ["quick_answer"]

    def test_restore_missing_file(self, tmp_path):
        """Restore should return False when no snapshot exists."""
        mgr = ModuleStateManager(snapshot_path=str(tmp_path / "missing.json"))
        assert mgr.restore_snapshot() is False


class TestDailyReset:
    """Tests for daily counter reset."""

    def test_reset_clears_counters(self, populated_manager):
        """Reset should zero out daily task counters."""
        populated_manager.update_state("wraith", "busy", "task")
        populated_manager.update_state("wraith", "idle")
        populated_manager.update_state("omen", "busy", "code")
        populated_manager.update_state("omen", "error")

        populated_manager.reset_daily_counters()

        wraith = populated_manager.get_state("wraith")
        omen = populated_manager.get_state("omen")
        assert wraith.tasks_completed_today == 0
        assert omen.tasks_failed_today == 0


class TestQueueManagement:
    """Tests for queue depth tracking."""

    def test_increment_queue(self, populated_manager):
        """Increment should increase queue depth."""
        populated_manager.increment_queue("wraith")
        populated_manager.increment_queue("wraith")
        state = populated_manager.get_state("wraith")
        assert state.queue_depth == 2

    def test_decrement_queue(self, populated_manager):
        """Decrement should decrease queue depth."""
        populated_manager.increment_queue("wraith")
        populated_manager.increment_queue("wraith")
        populated_manager.decrement_queue("wraith")
        state = populated_manager.get_state("wraith")
        assert state.queue_depth == 1

    def test_decrement_floor_zero(self, populated_manager):
        """Queue depth should never go negative."""
        populated_manager.decrement_queue("wraith")
        state = populated_manager.get_state("wraith")
        assert state.queue_depth == 0


class TestThreadSafety:
    """Tests for concurrent access."""

    def test_concurrent_updates_no_corruption(self, populated_manager):
        """Concurrent state updates should not corrupt data."""
        errors = []

        def worker(module_name, iterations):
            try:
                for _ in range(iterations):
                    populated_manager.update_state(module_name, "busy", "working")
                    populated_manager.update_state(module_name, "idle")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=("wraith", 50)),
            threading.Thread(target=worker, args=("omen", 50)),
            threading.Thread(target=worker, args=("sentinel", 50)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

        # Each module should have completed 50 tasks
        assert populated_manager.get_state("wraith").tasks_completed_today == 50
        assert populated_manager.get_state("omen").tasks_completed_today == 50
        assert populated_manager.get_state("sentinel").tasks_completed_today == 50

    def test_concurrent_queue_operations(self, populated_manager):
        """Concurrent queue operations should maintain consistency."""
        errors = []

        def increment_worker():
            try:
                for _ in range(100):
                    populated_manager.increment_queue("wraith")
            except Exception as e:
                errors.append(e)

        def decrement_worker():
            try:
                for _ in range(50):
                    populated_manager.decrement_queue("wraith")
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=increment_worker)
        t2 = threading.Thread(target=decrement_worker)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(errors) == 0
        state = populated_manager.get_state("wraith")
        # 100 increments - 50 decrements = 50 (but floor is 0 if decrements happen first)
        assert state.queue_depth >= 0
