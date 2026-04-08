"""Operational State Modeling — Shadow tracks his own work/rest/explore cycles.

State is OBSERVATION and RECOMMENDATION — never blocks task execution.
SQLite-backed persistence so state survives restarts.
"""

import logging
import sqlite3
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class StateSnapshot:
    """A point-in-time snapshot of Shadow's operational state."""

    timestamp: float
    frustration: float          # 0.0 = calm, 1.0 = maximum frustration
    confidence_momentum: float  # 0.0 = no streak, 1.0 = long success streak
    curiosity: float            # 0.0 = no discoveries, 1.0 = active exploration
    fatigue: float              # 0.0 = fresh, 1.0 = needs cooldown
    overall_health: float       # weighted composite score


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp a value to [lo, hi]."""
    return max(lo, min(hi, value))


def _compute_health(frustration: float, fatigue: float,
                    confidence_momentum: float, curiosity: float) -> float:
    """Compute overall health from state dimensions."""
    raw = 1.0 - (frustration * 0.3 + fatigue * 0.4
                 - confidence_momentum * 0.2 - curiosity * 0.1)
    return _clamp(raw)


class OperationalState:
    """Tracks Shadow's operational state and recommends behavioral adjustments.

    State dimensions (each 0.0-1.0):
    - frustration: accumulated from failures, relieved by success/escalation
    - confidence_momentum: streak of high-confidence successes
    - curiosity: elevated by novel tasks and Morpheus discoveries
    - fatigue: slowly accumulates, reduced by cooldown periods
    - overall_health: weighted composite of all dimensions
    """

    _DEFAULT_CONFIG = {
        "frustration_decay_on_success": 0.7,
        "frustration_increment_on_failure": 0.15,
        "frustration_increment_on_repeated_failure": 0.25,
        "frustration_decay_on_escalation": 0.5,
        "momentum_increment_high": 0.1,
        "momentum_increment_mid": 0.05,
        "momentum_decay_on_failure": 0.5,
        "curiosity_increment_discovery": 0.2,
        "curiosity_increment_novel": 0.1,
        "curiosity_decay_routine": 0.95,
        "fatigue_increment_task": 0.02,
        "fatigue_increment_long_task": 0.05,
        "fatigue_decay_cooldown": 0.5,
        "fatigue_increment_quality_degradation": 0.1,
        "long_task_threshold_seconds": 60.0,
        "cooldown_threshold_minutes": 30.0,
        "recent_task_window": 20,
    }

    def __init__(self, db_path: str = "data/operational_state.db",
                 config: dict = None) -> None:
        try:
            self._db_path = Path(db_path)
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._config = {**self._DEFAULT_CONFIG, **(config or {})}
            self._recent_task_types: list[str] = []
            self._last_task_types: dict[str, int] = {}  # task_type -> consecutive failures
            self._init_db()
            self._load_recent_context()
        except Exception as e:
            logger.error("OperationalState init failed: %s", e)
            raise

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS state_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    frustration REAL NOT NULL,
                    confidence_momentum REAL NOT NULL,
                    curiosity REAL NOT NULL,
                    fatigue REAL NOT NULL,
                    overall_health REAL NOT NULL,
                    event_type TEXT DEFAULT 'task_update'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    task_type TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    confidence REAL NOT NULL
                )
            """)
            conn.commit()

    def _load_recent_context(self) -> None:
        """Load recent task types and failure counts from DB for continuity."""
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                window = self._config["recent_task_window"]
                rows = conn.execute(
                    "SELECT task_type, success FROM task_history "
                    "ORDER BY id DESC LIMIT ?",
                    (window,),
                ).fetchall()
                # Reverse to chronological order
                rows.reverse()
                self._recent_task_types = [r[0] for r in rows]

                # Rebuild consecutive failure counts from recent history
                for task_type, success in rows:
                    if not success:
                        self._last_task_types[task_type] = (
                            self._last_task_types.get(task_type, 0) + 1
                        )
                    else:
                        self._last_task_types[task_type] = 0
        except Exception as e:
            logger.debug("Failed to load recent context: %s", e)

    def _get_latest_snapshot(self) -> StateSnapshot | None:
        """Get the most recent state snapshot from DB."""
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                row = conn.execute(
                    "SELECT timestamp, frustration, confidence_momentum, "
                    "curiosity, fatigue, overall_health "
                    "FROM state_snapshots ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if row:
                    return StateSnapshot(*row)
        except Exception as e:
            logger.debug("Failed to get latest snapshot: %s", e)
        return None

    def _save_snapshot(self, snapshot: StateSnapshot,
                       event_type: str = "task_update") -> None:
        """Persist a state snapshot to DB."""
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute(
                    "INSERT INTO state_snapshots "
                    "(timestamp, frustration, confidence_momentum, curiosity, "
                    "fatigue, overall_health, event_type) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (snapshot.timestamp, snapshot.frustration,
                     snapshot.confidence_momentum, snapshot.curiosity,
                     snapshot.fatigue, snapshot.overall_health, event_type),
                )
                conn.commit()
        except Exception as e:
            logger.error("Failed to save state snapshot: %s", e)

    def _save_task(self, task_type: str, success: bool,
                   confidence: float) -> None:
        """Record a task in the history table."""
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute(
                    "INSERT INTO task_history (timestamp, task_type, success, confidence) "
                    "VALUES (?, ?, ?, ?)",
                    (time.time(), task_type, int(success), confidence),
                )
                conn.commit()
        except Exception as e:
            logger.debug("Failed to save task history: %s", e)

    def get_current_state(self) -> StateSnapshot:
        """Return current state values, applying time-based fatigue decay.

        If no state exists, returns defaults (all 0.0 except overall_health = 1.0).
        """
        snapshot = self._get_latest_snapshot()
        if snapshot is None:
            return StateSnapshot(
                timestamp=time.time(),
                frustration=0.0,
                confidence_momentum=0.0,
                curiosity=0.0,
                fatigue=0.0,
                overall_health=1.0,
            )

        # Apply time-based fatigue decay (cooldown effect for idle time)
        now = time.time()
        elapsed_minutes = (now - snapshot.timestamp) / 60.0
        cooldown_threshold = self._config["cooldown_threshold_minutes"]

        if elapsed_minutes >= cooldown_threshold:
            fatigue = snapshot.fatigue * self._config["fatigue_decay_cooldown"]
            health = _compute_health(
                snapshot.frustration, fatigue,
                snapshot.confidence_momentum, snapshot.curiosity,
            )
            return StateSnapshot(
                timestamp=now,
                frustration=snapshot.frustration,
                confidence_momentum=snapshot.confidence_momentum,
                curiosity=snapshot.curiosity,
                fatigue=_clamp(fatigue),
                overall_health=health,
            )

        return snapshot

    def update_after_task(self, task_result: dict) -> StateSnapshot:
        """Update state after a task completes.

        Args:
            task_result: dict with keys:
                success (bool), confidence (float), task_type (str),
                duration (float), was_escalated (bool), was_retry (bool)
        """
        try:
            current = self.get_current_state()
            cfg = self._config

            success = task_result.get("success", False)
            confidence = task_result.get("confidence", 0.0)
            task_type = task_result.get("task_type", "unknown")
            duration = task_result.get("duration", 0.0)
            was_escalated = task_result.get("was_escalated", False)
            was_retry = task_result.get("was_retry", False)

            frustration = current.frustration
            momentum = current.confidence_momentum
            curiosity = current.curiosity
            fatigue = current.fatigue

            # --- Frustration ---
            if success:
                frustration *= cfg["frustration_decay_on_success"]
            else:
                # Check for repeated failure on same task type
                consecutive = self._last_task_types.get(task_type, 0)
                if consecutive > 0:
                    frustration += cfg["frustration_increment_on_repeated_failure"]
                else:
                    frustration += cfg["frustration_increment_on_failure"]

            if was_escalated:
                frustration *= cfg["frustration_decay_on_escalation"]

            # --- Confidence Momentum ---
            if success:
                if confidence > 0.8:
                    momentum += cfg["momentum_increment_high"]
                elif confidence >= 0.5:
                    momentum += cfg["momentum_increment_mid"]
            else:
                momentum *= cfg["momentum_decay_on_failure"]

            # --- Curiosity ---
            window = cfg["recent_task_window"]
            recent_types = self._recent_task_types[-window:]
            if task_type == "morpheus_discovery":
                curiosity += cfg["curiosity_increment_discovery"]
            elif task_type not in recent_types:
                curiosity += cfg["curiosity_increment_novel"]
            else:
                curiosity *= cfg["curiosity_decay_routine"]

            # --- Fatigue ---
            fatigue += cfg["fatigue_increment_task"]
            if duration > cfg["long_task_threshold_seconds"]:
                fatigue += cfg["fatigue_increment_long_task"]

            # Quality degradation: check if confidence is trending down
            if self._detect_quality_degradation():
                fatigue += cfg["fatigue_increment_quality_degradation"]

            # Clamp all values
            frustration = _clamp(frustration)
            momentum = _clamp(momentum)
            curiosity = _clamp(curiosity)
            fatigue = _clamp(fatigue)
            health = _compute_health(frustration, fatigue, momentum, curiosity)

            snapshot = StateSnapshot(
                timestamp=time.time(),
                frustration=frustration,
                confidence_momentum=momentum,
                curiosity=curiosity,
                fatigue=fatigue,
                overall_health=health,
            )

            # Update tracking
            self._recent_task_types.append(task_type)
            if len(self._recent_task_types) > window:
                self._recent_task_types = self._recent_task_types[-window:]

            if success:
                self._last_task_types[task_type] = 0
            else:
                self._last_task_types[task_type] = (
                    self._last_task_types.get(task_type, 0) + 1
                )

            # Persist
            self._save_snapshot(snapshot)
            self._save_task(task_type, success, confidence)

            return snapshot

        except Exception as e:
            logger.error("update_after_task failed: %s", e)
            return self.get_current_state()

    def _detect_quality_degradation(self) -> bool:
        """Check if confidence is trending down over recent tasks."""
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                rows = conn.execute(
                    "SELECT confidence FROM task_history "
                    "ORDER BY id DESC LIMIT 5"
                ).fetchall()
                if len(rows) < 3:
                    return False
                confidences = [r[0] for r in reversed(rows)]
                # Degradation if each recent confidence is lower than the previous
                declining = all(
                    confidences[i] < confidences[i - 1]
                    for i in range(1, len(confidences))
                )
                return declining
        except Exception:
            return False

    def get_behavioral_adjustments(self) -> dict:
        """Return recommended behavior modifications based on current state."""
        state = self.get_current_state()

        # Defaults
        escalation_modifier = 0.0
        ambition = "normal"
        morpheus_allocation = 0.1
        should_cooldown = False
        cooldown_minutes = 0
        retry_patience = 12

        # Frustration effects
        if state.frustration > 0.7:
            escalation_modifier = -4.0  # escalate at attempt 8 instead of 12
            retry_patience = 8

        # Confidence momentum effects
        if state.confidence_momentum > 0.7:
            ambition = "ambitious"
        elif state.confidence_momentum < 0.3 and state.frustration > 0.5:
            ambition = "conservative"

        # Curiosity effects
        if state.curiosity > 0.6:
            morpheus_allocation = min(0.3, 0.1 + state.curiosity * 0.3)

        # Fatigue effects
        if state.fatigue > 0.8:
            should_cooldown = True
            cooldown_minutes = 30
        elif state.fatigue > 0.6:
            cooldown_minutes = 15

        return {
            "escalation_threshold_modifier": escalation_modifier,
            "task_ambition_level": ambition,
            "morpheus_time_allocation": round(morpheus_allocation, 2),
            "should_cooldown": should_cooldown,
            "cooldown_duration_minutes": cooldown_minutes,
            "retry_patience": retry_patience,
        }

    def record_cooldown(self, duration_minutes: int) -> StateSnapshot:
        """Apply cooldown effect and log it.

        Reduces fatigue by 70% and frustration by 20%.
        """
        try:
            current = self.get_current_state()

            fatigue = _clamp(current.fatigue * 0.3)
            frustration = _clamp(current.frustration * 0.8)
            health = _compute_health(
                frustration, fatigue,
                current.confidence_momentum, current.curiosity,
            )

            snapshot = StateSnapshot(
                timestamp=time.time(),
                frustration=frustration,
                confidence_momentum=current.confidence_momentum,
                curiosity=current.curiosity,
                fatigue=fatigue,
                overall_health=health,
            )

            self._save_snapshot(snapshot, event_type=f"cooldown_{duration_minutes}m")
            return snapshot

        except Exception as e:
            logger.error("record_cooldown failed: %s", e)
            return self.get_current_state()

    def get_state_history(self, hours: int = 24) -> list[StateSnapshot]:
        """Return state snapshots over the given time period."""
        try:
            cutoff = time.time() - (hours * 3600)
            with sqlite3.connect(str(self._db_path)) as conn:
                rows = conn.execute(
                    "SELECT timestamp, frustration, confidence_momentum, "
                    "curiosity, fatigue, overall_health "
                    "FROM state_snapshots WHERE timestamp >= ? "
                    "ORDER BY timestamp ASC",
                    (cutoff,),
                ).fetchall()
                return [StateSnapshot(*row) for row in rows]
        except Exception as e:
            logger.error("get_state_history failed: %s", e)
            return []

    def get_state_summary(self) -> str:
        """Plain-English summary for daily briefing."""
        try:
            state = self.get_current_state()
            parts = []

            # Overall assessment
            if state.overall_health >= 0.8:
                parts.append("Shadow is operating well.")
            elif state.overall_health >= 0.5:
                parts.append("Shadow is operating at moderate capacity.")
            else:
                parts.append("Shadow is in a degraded state.")

            # Confidence momentum
            if state.confidence_momentum > 0.7:
                # Count recent successes
                try:
                    with sqlite3.connect(str(self._db_path)) as conn:
                        rows = conn.execute(
                            "SELECT success FROM task_history "
                            "ORDER BY id DESC LIMIT 20"
                        ).fetchall()
                        streak = 0
                        for (s,) in rows:
                            if s:
                                streak += 1
                            else:
                                break
                        parts.append(
                            f"Confidence momentum is high after "
                            f"{streak} consecutive successes."
                        )
                except Exception:
                    parts.append("Confidence momentum is high.")
            elif state.confidence_momentum < 0.2:
                parts.append("Confidence momentum is low.")

            # Curiosity
            if state.curiosity > 0.6:
                parts.append(
                    "Curiosity elevated from recent discoveries."
                )

            # Frustration
            if state.frustration > 0.5:
                # Find what's causing it
                top_failures = []
                for tt, count in self._last_task_types.items():
                    if count > 0:
                        top_failures.append((tt, count))
                top_failures.sort(key=lambda x: x[1], reverse=True)

                if top_failures:
                    cause = top_failures[0][0]
                    parts.append(
                        f"Frustration is elevated ({state.frustration:.2f}) "
                        f"after repeated {cause} task failures. "
                        f"Recommend targeted knowledge document."
                    )
                else:
                    parts.append(
                        f"Frustration is elevated ({state.frustration:.2f})."
                    )

            # Fatigue
            if state.fatigue > 0.8:
                parts.append(
                    f"Fatigue is high ({state.fatigue:.2f}) — "
                    f"cooldown period strongly recommended."
                )
            elif state.fatigue > 0.6:
                parts.append(
                    f"Fatigue moderate ({state.fatigue:.2f}) — "
                    f"cooldown period recommended."
                )
            elif state.fatigue < 0.2:
                parts.append("No fatigue concerns.")

            return " ".join(parts)

        except Exception as e:
            logger.error("get_state_summary failed: %s", e)
            return "Unable to generate state summary."

    def reset_state(self) -> StateSnapshot:
        """Reset all states to defaults. For manual reset by Patrick."""
        try:
            snapshot = StateSnapshot(
                timestamp=time.time(),
                frustration=0.0,
                confidence_momentum=0.0,
                curiosity=0.0,
                fatigue=0.0,
                overall_health=1.0,
            )
            self._save_snapshot(snapshot, event_type="manual_reset")
            self._recent_task_types.clear()
            self._last_task_types.clear()
            return snapshot
        except Exception as e:
            logger.error("reset_state failed: %s", e)
            return StateSnapshot(
                timestamp=time.time(),
                frustration=0.0,
                confidence_momentum=0.0,
                curiosity=0.0,
                fatigue=0.0,
                overall_health=1.0,
            )
