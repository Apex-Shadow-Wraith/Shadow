"""Tests for ProactiveEngine — trigger-based initiative system."""

import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from modules.shadow.proactive_engine import (
    ProactiveEngine,
    ProactiveTrigger,
    _LightEventBus,
    _parse_cron_time,
    _parse_interval_seconds,
)


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def event_bus() -> _LightEventBus:
    return _LightEventBus()


@pytest.fixture
def engine(tmp_path: Path, event_bus: _LightEventBus) -> ProactiveEngine:
    return ProactiveEngine(event_system=event_bus, data_dir=tmp_path)


# ── Schedule Parsing ─────────────────────────────────────────────────

class TestScheduleParsing:
    def test_parse_interval_hours(self):
        assert _parse_interval_seconds("every 6 hours") == 21600

    def test_parse_interval_minutes(self):
        assert _parse_interval_seconds("every 5 minutes") == 300

    def test_parse_interval_seconds(self):
        assert _parse_interval_seconds("every 30 seconds") == 30

    def test_parse_interval_singular(self):
        assert _parse_interval_seconds("every 1 hour") == 3600

    def test_parse_interval_invalid(self):
        assert _parse_interval_seconds("run daily") is None

    def test_parse_cron_time(self):
        assert _parse_cron_time("cron 08:30") == (8, 30)

    def test_parse_cron_time_invalid(self):
        assert _parse_cron_time("every 5 minutes") is None


# ── LightEventBus ────────────────────────────────────────────────────

class TestLightEventBus:
    def test_subscribe_and_emit(self, event_bus: _LightEventBus):
        received = []
        event_bus.subscribe("mod_a", "test_event", lambda name, data: received.append(data))
        count = event_bus.emit_sync("test_event", {"key": "value"})
        assert count == 1
        assert received == [{"key": "value"}]

    def test_unsubscribe(self, event_bus: _LightEventBus):
        received = []
        event_bus.subscribe("mod_a", "test_event", lambda name, data: received.append(data))
        event_bus.unsubscribe("mod_a", "test_event")
        count = event_bus.emit_sync("test_event", {"key": "value"})
        assert count == 0
        assert received == []

    def test_bad_callback_doesnt_break_others(self, event_bus: _LightEventBus):
        results = []

        def bad_cb(name, data):
            raise ValueError("boom")

        def good_cb(name, data):
            results.append("ok")

        event_bus.subscribe("mod_a", "test_event", bad_cb)
        event_bus.subscribe("mod_b", "test_event", good_cb)
        count = event_bus.emit_sync("test_event", {})
        assert count == 1  # Only good_cb succeeded
        assert results == ["ok"]

    def test_no_subscribers(self, event_bus: _LightEventBus):
        count = event_bus.emit_sync("nonexistent_event", {})
        assert count == 0


# ── Trigger Registration ─────────────────────────────────────────────

class TestTriggerRegistration:
    def test_register_returns_id(self, engine: ProactiveEngine):
        trigger = ProactiveTrigger(
            module_name="sentinel",
            trigger_type="schedule",
            description="Test trigger",
            schedule="every 1 hours",
            action="Do something",
        )
        tid = engine.register_trigger(trigger)
        assert tid == trigger.trigger_id
        assert len(engine.get_active_triggers()) == 1

    def test_unregister_removes_trigger(self, engine: ProactiveEngine):
        trigger = ProactiveTrigger(
            module_name="sentinel",
            trigger_type="schedule",
            description="Test trigger",
            schedule="every 1 hours",
            action="Do something",
        )
        tid = engine.register_trigger(trigger)
        engine.unregister_trigger(tid)
        assert len(engine.get_active_triggers()) == 0

    def test_unregister_nonexistent_is_noop(self, engine: ProactiveEngine):
        engine.unregister_trigger("nonexistent-id")  # Should not raise

    def test_event_trigger_subscribes_to_event_bus(
        self, engine: ProactiveEngine, event_bus: _LightEventBus,
    ):
        trigger = ProactiveTrigger(
            module_name="sentinel",
            trigger_type="event",
            description="Security alert handler",
            event_name="SECURITY_ALERT",
            action="Investigate",
        )
        engine.register_trigger(trigger)
        # Emit the event — should populate pending fires
        event_bus.emit_sync("SECURITY_ALERT", {"source": "test"})
        tasks = engine.check_triggers()
        assert len(tasks) == 1
        assert tasks[0]["assigned_module"] == "sentinel"


# ── Schedule Triggers ─────────────────────────────────────────────────

class TestScheduleTriggers:
    def test_fires_when_interval_elapsed(self, engine: ProactiveEngine):
        trigger = ProactiveTrigger(
            module_name="void",
            trigger_type="schedule",
            description="Health check",
            schedule="every 1 hours",
            action="Check health",
            last_fired=datetime.now() - timedelta(hours=2),
        )
        engine.register_trigger(trigger)
        tasks = engine.check_triggers()
        assert len(tasks) == 1
        assert tasks[0]["description"] == "Check health"

    def test_does_not_fire_when_not_due(self, engine: ProactiveEngine):
        trigger = ProactiveTrigger(
            module_name="void",
            trigger_type="schedule",
            description="Health check",
            schedule="every 6 hours",
            action="Check health",
            last_fired=datetime.now() - timedelta(hours=1),
        )
        engine.register_trigger(trigger)
        tasks = engine.check_triggers()
        assert len(tasks) == 0

    def test_fires_immediately_if_never_fired(self, engine: ProactiveEngine):
        trigger = ProactiveTrigger(
            module_name="void",
            trigger_type="schedule",
            description="First run",
            schedule="every 6 hours",
            action="Initial check",
            last_fired=None,
        )
        engine.register_trigger(trigger)
        tasks = engine.check_triggers()
        assert len(tasks) == 1


# ── Condition Triggers ────────────────────────────────────────────────

class TestConditionTriggers:
    def test_fires_when_condition_true(self, engine: ProactiveEngine):
        trigger = ProactiveTrigger(
            module_name="void",
            trigger_type="condition",
            description="Disk alert",
            action="Alert disk full",
            condition=lambda: True,
        )
        engine.register_trigger(trigger)
        tasks = engine.check_triggers()
        assert len(tasks) == 1

    def test_does_not_fire_when_condition_false(self, engine: ProactiveEngine):
        trigger = ProactiveTrigger(
            module_name="void",
            trigger_type="condition",
            description="Disk alert",
            action="Alert disk full",
            condition=lambda: False,
        )
        engine.register_trigger(trigger)
        tasks = engine.check_triggers()
        assert len(tasks) == 0

    def test_condition_exception_is_caught(self, engine: ProactiveEngine):
        trigger = ProactiveTrigger(
            module_name="void",
            trigger_type="condition",
            description="Bad condition",
            action="Should not fire",
            condition=lambda: 1 / 0,  # ZeroDivisionError
        )
        engine.register_trigger(trigger)
        tasks = engine.check_triggers()
        assert len(tasks) == 0  # Exception caught, does not fire


# ── Disabled Triggers ─────────────────────────────────────────────────

class TestDisabledTriggers:
    def test_disabled_trigger_does_not_fire(self, engine: ProactiveEngine):
        trigger = ProactiveTrigger(
            module_name="void",
            trigger_type="condition",
            description="Disabled trigger",
            action="Should not fire",
            condition=lambda: True,
            enabled=False,
        )
        engine.register_trigger(trigger)
        tasks = engine.check_triggers()
        assert len(tasks) == 0

    def test_enable_disable_toggle(self, engine: ProactiveEngine):
        trigger = ProactiveTrigger(
            module_name="void",
            trigger_type="condition",
            description="Toggle trigger",
            action="Maybe fire",
            condition=lambda: True,
        )
        tid = engine.register_trigger(trigger)

        # Disable
        engine.disable_trigger(tid)
        assert engine.check_triggers() == []

        # Re-enable
        engine.enable_trigger(tid)
        tasks = engine.check_triggers()
        assert len(tasks) == 1


# ── Max Frequency ─────────────────────────────────────────────────────

class TestMaxFrequency:
    def test_max_frequency_prevents_rapid_fire(self, engine: ProactiveEngine):
        trigger = ProactiveTrigger(
            module_name="sentinel",
            trigger_type="condition",
            description="Frequency test",
            action="Do something",
            condition=lambda: True,
            max_frequency=3600,  # 1 hour minimum
        )
        engine.register_trigger(trigger)

        # First fire — should succeed
        tasks1 = engine.check_triggers()
        assert len(tasks1) == 1

        # Second fire — should be blocked by max_frequency
        tasks2 = engine.check_triggers()
        assert len(tasks2) == 0


# ── Task Dict Shape ──────────────────────────────────────────────────

class TestTaskDictShape:
    def test_task_dict_has_required_fields(self, engine: ProactiveEngine):
        trigger = ProactiveTrigger(
            module_name="omen",
            trigger_type="condition",
            description="Code check",
            action="Review code quality",
            priority=3,
            condition=lambda: True,
            requires_approval=True,
        )
        engine.register_trigger(trigger)
        tasks = engine.check_triggers()
        assert len(tasks) == 1

        task = tasks[0]
        assert task["description"] == "Review code quality"
        assert task["assigned_module"] == "omen"
        assert task["priority"] == 3
        assert task["source"] == "proactive"
        assert task["trigger_id"] == trigger.trigger_id
        assert task["requires_approval"] is True
        assert task["requires_safety_check"] is True


# ── Rate Limiting ─────────────────────────────────────────────────────

class TestRateLimiting:
    def test_global_rate_limit(self, tmp_path: Path, event_bus: _LightEventBus):
        engine = ProactiveEngine(
            event_system=event_bus,
            data_dir=tmp_path,
            rate_limit_per_hour=5,
        )

        # Register 10 condition triggers that always fire
        for i in range(10):
            engine.register_trigger(ProactiveTrigger(
                module_name="void",
                trigger_type="condition",
                description=f"Rate test {i}",
                action=f"Task {i}",
                condition=lambda: True,
            ))

        tasks = engine.check_triggers()
        assert len(tasks) == 5  # Only 5 fire due to rate limit

    def test_auto_disable_spam_trigger(self, tmp_path: Path, event_bus: _LightEventBus):
        engine = ProactiveEngine(
            event_system=event_bus,
            data_dir=tmp_path,
            rate_limit_per_hour=100,
            spam_threshold_per_hour=3,
        )

        trigger = ProactiveTrigger(
            module_name="void",
            trigger_type="condition",
            description="Spammy trigger",
            action="Spam task",
            condition=lambda: True,
        )
        tid = engine.register_trigger(trigger)

        # Fire 3 times — should auto-disable on the 4th check
        for _ in range(3):
            engine.check_triggers()

        # 4th check — trigger should now be auto-disabled
        tasks = engine.check_triggers()
        assert len(tasks) == 0
        assert engine._triggers[tid].enabled is False
        assert tid in engine._spam_disabled_triggers


# ── Idle Work Cycle ──────────────────────────────────────────────────

class TestIdleWorkCycle:
    def test_returns_first_waterfall_task(self, engine: ProactiveEngine):
        task = engine.idle_work_cycle()
        assert task is not None
        assert task["assigned_module"] == "shadow"
        assert task["priority"] == 4
        assert task["source"] == "idle_cycle"

    def test_returns_none_when_stopped(self, engine: ProactiveEngine):
        engine.stop_all_background()
        assert engine.idle_work_cycle() is None


# ── Background Control ───────────────────────────────────────────────

class TestBackgroundControl:
    def test_stop_all_background(self, engine: ProactiveEngine):
        trigger = ProactiveTrigger(
            module_name="void",
            trigger_type="condition",
            description="BG trigger",
            action="Background work",
            condition=lambda: True,
        )
        engine.register_trigger(trigger)

        engine.stop_all_background()
        assert engine.check_triggers() == []
        assert engine.idle_work_cycle() is None

    def test_resume_all_background(self, engine: ProactiveEngine):
        trigger = ProactiveTrigger(
            module_name="void",
            trigger_type="condition",
            description="BG trigger",
            action="Background work",
            condition=lambda: True,
        )
        engine.register_trigger(trigger)

        engine.stop_all_background()
        assert engine.check_triggers() == []

        engine.resume_all_background()
        tasks = engine.check_triggers()
        assert len(tasks) == 1


# ── Initiative Report ────────────────────────────────────────────────

class TestInitiativeReport:
    def test_report_structure(self, engine: ProactiveEngine):
        engine.register_trigger(ProactiveTrigger(
            module_name="sentinel",
            trigger_type="schedule",
            description="Report test 1",
            schedule="every 1 hours",
            action="Task 1",
        ))
        engine.register_trigger(ProactiveTrigger(
            module_name="void",
            trigger_type="condition",
            description="Report test 2",
            action="Task 2",
            condition=lambda: True,
            enabled=False,
        ))

        report = engine.get_initiative_report()
        assert report["total_triggers"] == 2
        assert report["active_triggers"] == 1
        assert report["disabled_triggers"] == 1
        assert report["background_stopped"] is False
        assert "sentinel" in report["by_module"]
        assert "void" in report["by_module"]
        assert len(report["triggers"]) == 2


# ── Persistence ──────────────────────────────────────────────────────

class TestPersistence:
    def test_save_and_load(self, tmp_path: Path, event_bus: _LightEventBus):
        engine1 = ProactiveEngine(event_system=event_bus, data_dir=tmp_path)
        engine1.register_trigger(ProactiveTrigger(
            module_name="sentinel",
            trigger_type="schedule",
            description="Persist test",
            schedule="every 6 hours",
            action="Scan logs",
            priority=4,
        ))
        engine1.save_triggers()

        # Load into a fresh engine
        engine2 = ProactiveEngine(event_system=event_bus, data_dir=tmp_path)
        triggers = engine2.get_active_triggers()
        assert len(triggers) == 1
        assert triggers[0].description == "Persist test"
        assert triggers[0].schedule == "every 6 hours"
        assert triggers[0].module_name == "sentinel"

    def test_condition_skipped_in_persistence(self, tmp_path: Path, event_bus: _LightEventBus):
        engine1 = ProactiveEngine(event_system=event_bus, data_dir=tmp_path)
        engine1.register_trigger(ProactiveTrigger(
            module_name="void",
            trigger_type="condition",
            description="Condition persist",
            action="Check disk",
            condition=lambda: True,
        ))
        engine1.save_triggers()

        engine2 = ProactiveEngine(event_system=event_bus, data_dir=tmp_path)
        triggers = engine2.get_active_triggers()
        assert len(triggers) == 1
        assert triggers[0].condition is None  # Callable not serialized

    def test_fire_history_persisted(self, tmp_path: Path, event_bus: _LightEventBus):
        engine1 = ProactiveEngine(event_system=event_bus, data_dir=tmp_path)
        engine1.register_trigger(ProactiveTrigger(
            module_name="void",
            trigger_type="condition",
            description="History test",
            action="Test action",
            condition=lambda: True,
        ))
        engine1.check_triggers()  # Fire once to create history
        engine1.save_triggers()

        engine2 = ProactiveEngine(event_system=event_bus, data_dir=tmp_path)
        assert len(engine2._fire_history) == 1


# ── Default Trigger Registration ─────────────────────────────────────

class TestDefaultTriggers:
    def test_register_default_triggers(self, engine: ProactiveEngine):
        engine.register_default_triggers()
        triggers = list(engine._triggers.values())
        # Should have triggers for all modules
        modules_with_triggers = {t.module_name for t in triggers}
        expected = {
            "sentinel", "omen", "reaper", "wraith", "void",
            "harbinger", "grimoire", "cerberus", "apex", "nova",
            "morpheus", "cipher",
        }
        assert expected == modules_with_triggers
        # Check we have a good number of triggers
        assert len(triggers) >= 30

    def test_register_default_triggers_idempotent(self, engine: ProactiveEngine):
        engine.register_default_triggers()
        count1 = len(engine._triggers)
        engine.register_default_triggers()
        count2 = len(engine._triggers)
        assert count1 == count2  # No duplicates

    def test_default_triggers_have_valid_types(self, engine: ProactiveEngine):
        engine.register_default_triggers()
        valid_types = {"event", "schedule", "condition", "discovery"}
        for trigger in engine._triggers.values():
            assert trigger.trigger_type in valid_types

    def test_event_triggers_have_event_names(self, engine: ProactiveEngine):
        engine.register_default_triggers()
        for trigger in engine._triggers.values():
            if trigger.trigger_type == "event":
                assert trigger.event_name is not None
                assert len(trigger.event_name) > 0

    def test_schedule_triggers_have_valid_schedules(self, engine: ProactiveEngine):
        engine.register_default_triggers()
        for trigger in engine._triggers.values():
            if trigger.trigger_type == "schedule":
                assert trigger.schedule is not None
                # Should be parseable
                interval = _parse_interval_seconds(trigger.schedule)
                cron = _parse_cron_time(trigger.schedule)
                assert interval is not None or cron is not None, (
                    f"Unparseable schedule: {trigger.schedule}"
                )


# ── Get Active Triggers Filter ───────────────────────────────────────

class TestGetActiveTriggers:
    def test_filter_by_module(self, engine: ProactiveEngine):
        engine.register_trigger(ProactiveTrigger(
            module_name="sentinel",
            trigger_type="schedule",
            description="Sentinel trigger",
            schedule="every 1 hours",
            action="Scan",
        ))
        engine.register_trigger(ProactiveTrigger(
            module_name="void",
            trigger_type="schedule",
            description="Void trigger",
            schedule="every 5 minutes",
            action="Health",
        ))

        sentinel_triggers = engine.get_active_triggers(module_name="sentinel")
        assert len(sentinel_triggers) == 1
        assert sentinel_triggers[0].module_name == "sentinel"

        all_triggers = engine.get_active_triggers()
        assert len(all_triggers) == 2


# ── Integration: Event → Trigger → Task ─────────────────────────────

class TestEventIntegration:
    def test_full_event_flow(self, tmp_path: Path):
        """Event fires → trigger activates → task dict produced."""
        bus = _LightEventBus()
        engine = ProactiveEngine(event_system=bus, data_dir=tmp_path)

        trigger = ProactiveTrigger(
            module_name="sentinel",
            trigger_type="event",
            description="Security response",
            event_name="SECURITY_ALERT",
            action="Investigate threat",
            priority=2,
        )
        engine.register_trigger(trigger)

        # Simulate event emission
        bus.emit_sync("SECURITY_ALERT", {"threat": "port_scan"})

        # Check triggers — should pick up the event
        tasks = engine.check_triggers()
        assert len(tasks) == 1
        assert tasks[0]["assigned_module"] == "sentinel"
        assert tasks[0]["priority"] == 2
        assert tasks[0]["description"] == "Investigate threat"
        assert tasks[0]["source"] == "proactive"

    def test_event_without_subscribers_produces_no_tasks(self, tmp_path: Path):
        bus = _LightEventBus()
        engine = ProactiveEngine(event_system=bus, data_dir=tmp_path)

        # Emit event with no triggers registered
        bus.emit_sync("SECURITY_ALERT", {"threat": "test"})
        tasks = engine.check_triggers()
        assert len(tasks) == 0
