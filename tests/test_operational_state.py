"""Tests for Shadow Operational State Modeling."""

import tempfile
import time
from pathlib import Path

import pytest

from modules.shadow.operational_state import (
    OperationalState,
    StateSnapshot,
    _clamp,
    _compute_health,
)


@pytest.fixture
def state_db(tmp_path):
    """Return a temp DB path for each test."""
    return str(tmp_path / "test_state.db")


@pytest.fixture
def ops(state_db):
    """Return an OperationalState with a temp DB."""
    return OperationalState(db_path=state_db)


def _task(success=True, confidence=0.9, task_type="question",
          duration=5.0, was_escalated=False, was_retry=False):
    """Helper to build a task_result dict."""
    return {
        "success": success,
        "confidence": confidence,
        "task_type": task_type,
        "duration": duration,
        "was_escalated": was_escalated,
        "was_retry": was_retry,
    }


# ─── State Update: Frustration ─────────────────────────────────────────

class TestFrustration:
    """Frustration update rules."""

    def test_success_reduces_frustration(self, ops):
        """Success decays frustration toward 0."""
        # Build up frustration first
        ops.update_after_task(_task(success=False, task_type="a"))
        s1 = ops.get_current_state()
        assert s1.frustration > 0

        s2 = ops.update_after_task(_task(success=True, task_type="b"))
        assert s2.frustration < s1.frustration

    def test_failure_increases_frustration(self, ops):
        """Failure increases frustration."""
        s = ops.update_after_task(_task(success=False))
        assert s.frustration > 0

    def test_repeated_same_type_failure_increases_more(self, ops):
        """Repeated failure on same task type adds more frustration."""
        s1 = ops.update_after_task(_task(success=False, task_type="cuda"))
        f_after_first = s1.frustration

        s2 = ops.update_after_task(_task(success=False, task_type="cuda"))
        increment_second = s2.frustration - f_after_first

        # Second same-type failure should use the larger increment (0.25 vs 0.15)
        assert increment_second >= 0.24  # ~0.25

    def test_escalation_reduces_frustration(self, ops):
        """Escalation halves frustration (relief — problem handed off)."""
        ops.update_after_task(_task(success=False, task_type="a"))
        ops.update_after_task(_task(success=False, task_type="b"))
        before = ops.get_current_state().frustration

        s = ops.update_after_task(_task(success=False, was_escalated=True, task_type="c"))
        # Escalation applies decay after the failure increment,
        # but should still be less than without escalation
        assert s.frustration < before + 0.15  # less than just a failure addition


# ─── State Update: Confidence Momentum ──────────────────────────────────

class TestConfidenceMomentum:
    """Confidence momentum update rules."""

    def test_high_confidence_success_builds_momentum(self, ops):
        """Success with confidence > 0.8 adds 0.1 momentum."""
        s = ops.update_after_task(_task(success=True, confidence=0.9))
        assert s.confidence_momentum == pytest.approx(0.1, abs=0.01)

    def test_mid_confidence_success_builds_less_momentum(self, ops):
        """Success with confidence 0.5-0.8 adds 0.05 momentum."""
        s = ops.update_after_task(_task(success=True, confidence=0.6))
        assert s.confidence_momentum == pytest.approx(0.05, abs=0.01)

    def test_failure_breaks_momentum(self, ops):
        """Failure halves momentum (streak broken)."""
        # Build up momentum
        for _ in range(5):
            ops.update_after_task(_task(success=True, confidence=0.9))
        before = ops.get_current_state().confidence_momentum

        s = ops.update_after_task(_task(success=False))
        assert s.confidence_momentum == pytest.approx(before * 0.5, abs=0.01)


# ─── State Update: Curiosity ────────────────────────────────────────────

class TestCuriosity:
    """Curiosity update rules."""

    def test_morpheus_discovery_boosts_curiosity(self, ops):
        """Morpheus discovery adds 0.2 curiosity."""
        s = ops.update_after_task(_task(task_type="morpheus_discovery"))
        assert s.curiosity == pytest.approx(0.2, abs=0.01)

    def test_novel_task_boosts_curiosity(self, ops):
        """Task type not in recent window adds 0.1 curiosity."""
        s = ops.update_after_task(_task(task_type="never_seen_before"))
        assert s.curiosity == pytest.approx(0.1, abs=0.01)

    def test_routine_task_decays_curiosity(self, ops):
        """Routine (seen recently) task decays curiosity by 0.95."""
        # First: novel → builds curiosity
        ops.update_after_task(_task(task_type="routine_type"))

        # Second: same type → now routine, decays
        s = ops.update_after_task(_task(task_type="routine_type"))
        # Curiosity from first was 0.1, now 0.1 * 0.95 = 0.095
        assert s.curiosity < 0.1


# ─── State Update: Fatigue ──────────────────────────────────────────────

class TestFatigue:
    """Fatigue update rules."""

    def test_every_task_increases_fatigue(self, ops):
        """Every task adds 0.02 fatigue."""
        s = ops.update_after_task(_task(duration=1.0))
        assert s.fatigue >= 0.02

    def test_long_task_increases_fatigue_more(self, ops):
        """Task > 60s adds extra 0.05 fatigue."""
        s_short = ops.update_after_task(_task(duration=5.0, task_type="a"))
        ops_long = OperationalState(
            db_path=str(Path(ops._db_path).parent / "long.db")
        )
        s_long = ops_long.update_after_task(_task(duration=120.0, task_type="a"))
        assert s_long.fatigue > s_short.fatigue

    def test_states_clamped_to_bounds(self, ops):
        """All states must stay within 0.0-1.0."""
        # Drive frustration and fatigue up
        for i in range(50):
            ops.update_after_task(
                _task(success=False, task_type=f"type_{i % 3}",
                      duration=120.0, confidence=0.1)
            )

        s = ops.get_current_state()
        for field in ["frustration", "confidence_momentum", "curiosity",
                      "fatigue", "overall_health"]:
            val = getattr(s, field)
            assert 0.0 <= val <= 1.0, f"{field} = {val} out of bounds"


# ─── Behavioral Adjustments ─────────────────────────────────────────────

class TestBehavioralAdjustments:
    """get_behavioral_adjustments() recommendations."""

    def test_high_frustration_lowers_escalation(self, ops):
        """Frustration > 0.7 → lower escalation threshold."""
        for i in range(20):
            ops.update_after_task(_task(success=False, task_type=f"t{i}"))

        adj = ops.get_behavioral_adjustments()
        state = ops.get_current_state()
        if state.frustration > 0.7:
            assert adj["escalation_threshold_modifier"] < 0
            assert adj["retry_patience"] < 12

    def test_high_momentum_ambitious(self, ops):
        """Confidence momentum > 0.7 → ambitious."""
        for _ in range(10):
            ops.update_after_task(_task(success=True, confidence=0.95))

        state = ops.get_current_state()
        if state.confidence_momentum > 0.7:
            adj = ops.get_behavioral_adjustments()
            assert adj["task_ambition_level"] == "ambitious"

    def test_high_curiosity_more_morpheus(self, ops):
        """Curiosity > 0.6 → increased Morpheus allocation."""
        for _ in range(5):
            ops.update_after_task(_task(task_type="morpheus_discovery"))

        state = ops.get_current_state()
        if state.curiosity > 0.6:
            adj = ops.get_behavioral_adjustments()
            assert adj["morpheus_time_allocation"] > 0.1

    def test_high_fatigue_cooldown(self, ops):
        """Fatigue > 0.8 → should_cooldown = True."""
        for i in range(60):
            ops.update_after_task(_task(duration=120.0, task_type=f"t{i}"))

        state = ops.get_current_state()
        if state.fatigue > 0.8:
            adj = ops.get_behavioral_adjustments()
            assert adj["should_cooldown"] is True
            assert adj["cooldown_duration_minutes"] == 30

    def test_default_behavior_low_state(self, ops):
        """Fresh state → normal defaults."""
        adj = ops.get_behavioral_adjustments()
        assert adj["task_ambition_level"] == "normal"
        assert adj["should_cooldown"] is False
        assert adj["escalation_threshold_modifier"] == 0.0
        assert adj["retry_patience"] == 12


# ─── Cooldown ───────────────────────────────────────────────────────────

class TestCooldown:
    """record_cooldown behavior."""

    def test_cooldown_reduces_fatigue_and_frustration(self, ops):
        """Cooldown reduces fatigue by 70% and frustration by 20%."""
        for i in range(20):
            ops.update_after_task(
                _task(success=False, duration=120.0, task_type=f"t{i}")
            )

        before = ops.get_current_state()
        after = ops.record_cooldown(30)

        assert after.fatigue < before.fatigue
        assert after.frustration < before.frustration
        assert after.fatigue == pytest.approx(before.fatigue * 0.3, abs=0.02)
        assert after.frustration == pytest.approx(before.frustration * 0.8, abs=0.02)

    def test_cooldown_logged_in_history(self, ops):
        """Cooldown event appears in state history."""
        ops.update_after_task(_task())
        ops.record_cooldown(15)

        import sqlite3
        with sqlite3.connect(str(ops._db_path)) as conn:
            rows = conn.execute(
                "SELECT event_type FROM state_snapshots "
                "WHERE event_type LIKE 'cooldown_%'"
            ).fetchall()
        assert len(rows) >= 1


# ─── History and Reporting ──────────────────────────────────────────────

class TestHistoryAndReporting:
    """State history and summary reporting."""

    def test_history_returns_snapshots(self, ops):
        """get_state_history returns snapshots for the period."""
        for _ in range(3):
            ops.update_after_task(_task())

        history = ops.get_state_history(hours=1)
        assert len(history) == 3
        assert all(isinstance(s, StateSnapshot) for s in history)

    def test_summary_returns_string(self, ops):
        """get_state_summary returns a non-empty string."""
        summary = ops.get_state_summary()
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_summary_reflects_good_state(self, ops):
        """Healthy state → positive summary."""
        for _ in range(5):
            ops.update_after_task(_task(success=True, confidence=0.95))

        summary = ops.get_state_summary()
        assert "operating well" in summary.lower() or "high" in summary.lower()

    def test_summary_reflects_bad_state(self, ops):
        """Degraded state → warning summary."""
        for i in range(15):
            ops.update_after_task(
                _task(success=False, task_type="cuda", duration=120.0)
            )

        summary = ops.get_state_summary()
        assert "frustration" in summary.lower() or "fatigue" in summary.lower()


# ─── Persistence ────────────────────────────────────────────────────────

class TestPersistence:
    """SQLite persistence and state roundtrip."""

    def test_state_survives_roundtrip(self, state_db):
        """State persists across OperationalState instances."""
        ops1 = OperationalState(db_path=state_db)
        ops1.update_after_task(_task(success=False))
        s1 = ops1.get_current_state()

        ops2 = OperationalState(db_path=state_db)
        s2 = ops2.get_current_state()
        assert s2.frustration == pytest.approx(s1.frustration, abs=0.01)

    def test_default_state_when_empty(self, ops):
        """No history → default state."""
        s = ops.get_current_state()
        assert s.frustration == 0.0
        assert s.confidence_momentum == 0.0
        assert s.curiosity == 0.0
        assert s.fatigue == 0.0
        assert s.overall_health == 1.0

    def test_reset_returns_to_defaults(self, ops):
        """reset_state clears everything."""
        for i in range(10):
            ops.update_after_task(_task(success=False, task_type=f"t{i}"))

        s = ops.reset_state()
        assert s.frustration == 0.0
        assert s.confidence_momentum == 0.0
        assert s.curiosity == 0.0
        assert s.fatigue == 0.0
        assert s.overall_health == 1.0


# ─── Edge Cases ─────────────────────────────────────────────────────────

class TestEdgeCases:
    """Edge case handling."""

    def test_missing_fields_graceful(self, ops):
        """update_after_task with empty dict → graceful defaults."""
        s = ops.update_after_task({})
        assert isinstance(s, StateSnapshot)
        assert 0.0 <= s.overall_health <= 1.0

    def test_rapid_updates_no_corruption(self, ops):
        """Multiple rapid updates produce valid state."""
        for i in range(100):
            ops.update_after_task(
                _task(success=(i % 3 != 0), confidence=0.5 + (i % 5) * 0.1,
                      task_type=f"type_{i % 7}")
            )

        s = ops.get_current_state()
        for field in ["frustration", "confidence_momentum", "curiosity",
                      "fatigue", "overall_health"]:
            val = getattr(s, field)
            assert 0.0 <= val <= 1.0, f"{field} = {val} out of bounds"

    def test_overall_health_calculation(self, ops):
        """Overall health formula is correct."""
        h = _compute_health(
            frustration=0.5, fatigue=0.5,
            confidence_momentum=0.5, curiosity=0.5,
        )
        expected = 1.0 - (0.5 * 0.3 + 0.5 * 0.4 - 0.5 * 0.2 - 0.5 * 0.1)
        assert h == pytest.approx(expected, abs=0.001)

    def test_clamp_function(self):
        """_clamp enforces bounds."""
        assert _clamp(-0.5) == 0.0
        assert _clamp(1.5) == 1.0
        assert _clamp(0.5) == 0.5


# ─── Fatigue Decay (Continuous) ────────────────────────────────────────

class TestFatigueDecay:
    """Fatigue should decay continuously over time, not just at a 30-min cliff."""

    def test_fatigue_decays_after_short_idle(self, state_db, monkeypatch):
        """Fatigue decays even after a short idle period (< cooldown threshold)."""
        ops = OperationalState(db_path=state_db)

        # Build up fatigue
        for i in range(10):
            ops.update_after_task(_task(duration=120.0, task_type=f"t{i}"))
        high_fatigue = ops.get_current_state().fatigue
        assert high_fatigue > 0.3, "Precondition: fatigue should be significant"

        # Simulate 5 minutes passing (well under 30-min threshold)
        import modules.shadow.operational_state as os_mod
        original_time = time.time
        monkeypatch.setattr(os_mod.time, "time", lambda: original_time() + 300)

        state = ops.get_current_state()
        assert state.fatigue < high_fatigue, (
            f"Fatigue should decay after 5 min idle: was {high_fatigue}, "
            f"now {state.fatigue}"
        )

    def test_fatigue_decays_proportionally_to_time(self, state_db, monkeypatch):
        """Longer idle = more decay. 10 min idle decays more than 2 min idle."""
        import modules.shadow.operational_state as os_mod
        base_time = time.time()

        ops = OperationalState(db_path=state_db)

        # Build up fatigue with a known base time
        monkeypatch.setattr(os_mod.time, "time", lambda: base_time)
        for i in range(15):
            ops.update_after_task(_task(duration=120.0, task_type=f"t{i}"))
        high_fatigue = ops.get_current_state().fatigue

        # Read after 2 minutes
        monkeypatch.setattr(os_mod.time, "time", lambda: base_time + 120)
        fatigue_2min = ops.get_current_state().fatigue

        # Read after 10 minutes
        monkeypatch.setattr(os_mod.time, "time", lambda: base_time + 600)
        fatigue_10min = ops.get_current_state().fatigue

        assert fatigue_2min < high_fatigue, "2 min should show some decay"
        assert fatigue_10min < fatigue_2min, "10 min should decay more than 2 min"

    def test_fatigue_at_threshold_matches_config(self, state_db, monkeypatch):
        """At exactly cooldown_threshold_minutes, decay matches fatigue_decay_cooldown."""
        import modules.shadow.operational_state as os_mod
        base_time = time.time()

        ops = OperationalState(db_path=state_db)
        decay_factor = ops._config["fatigue_decay_cooldown"]  # 0.5
        threshold_min = ops._config["cooldown_threshold_minutes"]  # 30

        # Set a known fatigue level
        monkeypatch.setattr(os_mod.time, "time", lambda: base_time)
        for i in range(20):
            ops.update_after_task(_task(duration=120.0, task_type=f"t{i}"))
        high_fatigue = ops.get_current_state().fatigue

        # Read at exactly threshold minutes later
        monkeypatch.setattr(
            os_mod.time, "time", lambda: base_time + threshold_min * 60
        )
        decayed = ops.get_current_state().fatigue
        expected = high_fatigue * decay_factor

        assert decayed == pytest.approx(expected, abs=0.02), (
            f"At {threshold_min} min, fatigue should be ~{expected:.3f}, "
            f"got {decayed:.3f}"
        )

    def test_benchmark_scenario_fatigue_stays_manageable(self, state_db, monkeypatch):
        """Simulate 50-task benchmark (~18s per task). Fatigue should not hit 1.0."""
        import modules.shadow.operational_state as os_mod
        base_time = time.time()
        current_time = base_time

        ops = OperationalState(db_path=state_db)

        max_fatigue = 0.0
        for i in range(50):
            # Each task takes ~15s, with ~3s between tasks
            current_time += 18.0
            t = current_time  # capture for lambda
            monkeypatch.setattr(os_mod.time, "time", lambda _t=t: _t)

            result = ops.update_after_task(
                _task(success=True, confidence=0.85, task_type="benchmark",
                      duration=15.0)
            )
            max_fatigue = max(max_fatigue, result.fatigue)

        final = ops.get_current_state()
        # With continuous decay, fatigue should plateau well below 1.0
        assert final.fatigue < 1.0, (
            f"Fatigue hit {final.fatigue} during 50-task benchmark — "
            f"continuous decay should prevent saturation"
        )
        assert max_fatigue < 1.0, (
            f"Max fatigue during benchmark was {max_fatigue} — should stay < 1.0"
        )

    def test_fatigue_decreases_during_cooldown_period(self, state_db, monkeypatch):
        """After tasks stop, fatigue should continuously decrease over time."""
        import modules.shadow.operational_state as os_mod
        base_time = time.time()

        ops = OperationalState(db_path=state_db)

        # Build up fatigue
        monkeypatch.setattr(os_mod.time, "time", lambda: base_time)
        for i in range(20):
            ops.update_after_task(_task(duration=120.0, task_type=f"t{i}"))

        readings = []
        # Sample fatigue at 0, 1, 5, 15, 30 minutes
        for minutes in [0, 1, 5, 15, 30]:
            monkeypatch.setattr(
                os_mod.time, "time", lambda m=minutes: base_time + m * 60
            )
            readings.append((minutes, ops.get_current_state().fatigue))

        # Each reading should be less than or equal to the previous
        for i in range(1, len(readings)):
            assert readings[i][1] <= readings[i - 1][1], (
                f"Fatigue should decrease: at {readings[i][0]} min "
                f"({readings[i][1]:.3f}) > at {readings[i-1][0]} min "
                f"({readings[i-1][1]:.3f})"
            )
