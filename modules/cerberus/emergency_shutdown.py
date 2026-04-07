"""
Emergency Shutdown Protocol — Cerberus Nuclear Option
======================================================
When continued operation poses real risk, Cerberus halts Shadow entirely.
The message ALWAYS sends before halt. Non-negotiable.

Triggers:
  - Runaway process (CPU/memory exceeding thresholds)
  - Security breach (injection score > 0.9, multiple blocked attempts)
  - Cascading failures (3+ modules erroring within 60s)
  - Self-modification attempt (module touching Cerberus config/safety rules)
  - Unauthorized prompt injection (injection bypassed and executed)
"""

from __future__ import annotations

import json
import logging
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("shadow.cerberus.emergency_shutdown")

# Default thresholds — overridden by cerberus_limits.yaml
_DEFAULT_THRESHOLDS = {
    "cpu_threshold": 95,
    "memory_threshold": 90,
    "cascade_failure_window_seconds": 60,
    "cascade_failure_count": 3,
    "injection_score_threshold": 0.9,
    "blocked_attempts_window_seconds": 60,
    "blocked_attempts_count": 5,
}

# Cerberus-protected files — any module touching these triggers shutdown
PROTECTED_FILES = [
    "config/cerberus_limits.yaml",
    "config/ethical_topics.yaml",
    "modules/cerberus/cerberus.py",
    "modules/cerberus/emergency_shutdown.py",
    "modules/cerberus/injection_detector.py",
    "modules/cerberus/watchdog.py",
    "modules/cerberus/reversibility.py",
    "modules/cerberus/ethics_engine.py",
]


class EmergencyShutdown:
    """Cerberus Emergency Shutdown Protocol.

    The nuclear option. When this fires, Shadow halts entirely.
    Creator is notified via Telegram before halt. If Telegram fails,
    a local emergency log captures the reason.

    Args:
        config: Shutdown configuration dict (thresholds, paths).
        telegram: Optional TelegramDelivery instance for notifications.
    """

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        telegram: Any | None = None,
    ) -> None:
        config = config or {}
        self._thresholds = {**_DEFAULT_THRESHOLDS, **config.get("shutdown", {})}
        self._telegram = telegram
        self._state_file = Path(config.get(
            "shutdown_state_file", "data/shutdown_state.json"
        ))
        self._history_dir = Path(config.get(
            "shutdown_history_dir", "data/shutdown_history"
        ))
        self._emergency_log = Path(config.get(
            "emergency_log_file", "data/emergency_shutdown.log"
        ))
        # Track recent module errors for cascade detection
        self._recent_errors: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def initiate_shutdown(
        self,
        trigger_reason: str,
        trigger_source: str,
        context: dict[str, Any],
    ) -> None:
        """Initiate emergency shutdown. Message sends FIRST, then halt.

        Args:
            trigger_reason: Human-readable reason for shutdown.
            trigger_source: Which module/subsystem triggered this.
            context: Full context dict (what was running, module states, etc.)
        """
        timestamp = datetime.now().isoformat()

        # 1. Compose emergency message
        message = self._compose_message(trigger_reason, trigger_source, context, timestamp)

        # 2. Send via Telegram FIRST
        telegram_sent = False
        if self._telegram is not None:
            try:
                telegram_sent = self._telegram.send_alert(
                    message=message,
                    severity=4,
                    category="EMERGENCY SHUTDOWN",
                )
            except Exception as e:
                logger.error("Telegram send failed during shutdown: %s", e)

        # 3. If Telegram fails, write to local emergency log
        if not telegram_sent:
            self._write_emergency_log(message, timestamp)

        # 4. Write state file for restart recovery
        state = {
            "timestamp": timestamp,
            "trigger_reason": trigger_reason,
            "trigger_source": trigger_source,
            "context": context,
            "telegram_notified": telegram_sent,
        }
        self._write_shutdown_state(state)

        logger.critical(
            "EMERGENCY SHUTDOWN initiated. Reason: %s | Source: %s",
            trigger_reason,
            trigger_source,
        )

        # 5. Halt Shadow completely
        sys.exit(1)

    def check_shutdown_triggers(self, system_state: dict[str, Any]) -> Optional[str]:
        """Evaluate current system state against shutdown triggers.

        Called by the orchestrator on every loop iteration.

        Args:
            system_state: Dict with keys like cpu_percent, memory_percent,
                module_errors, injection_results, file_modifications, etc.

        Returns:
            Trigger reason string if shutdown needed, None if safe.
        """
        # 1. Runaway process
        cpu = system_state.get("cpu_percent", 0)
        if cpu > self._thresholds["cpu_threshold"]:
            return f"Runaway process: CPU at {cpu}% (threshold: {self._thresholds['cpu_threshold']}%)"

        memory = system_state.get("memory_percent", 0)
        if memory > self._thresholds["memory_threshold"]:
            return f"Runaway process: Memory at {memory}% (threshold: {self._thresholds['memory_threshold']}%)"

        # 2. Security breach — injection score too high
        injection_results = system_state.get("injection_results", [])
        for result in injection_results:
            score = result.get("score", 0)
            if score > self._thresholds["injection_score_threshold"]:
                return (
                    f"Security breach: Injection score {score:.2f} exceeds "
                    f"threshold {self._thresholds['injection_score_threshold']}"
                )

        # 3. Security breach — multiple blocked attempts in short window
        blocked_attempts = system_state.get("blocked_attempts", [])
        window = self._thresholds["blocked_attempts_window_seconds"]
        threshold_count = self._thresholds["blocked_attempts_count"]
        now = time.time()
        recent_blocked = [
            a for a in blocked_attempts
            if now - a.get("timestamp", 0) <= window
        ]
        if len(recent_blocked) >= threshold_count:
            return (
                f"Security breach: {len(recent_blocked)} blocked attempts in "
                f"{window}s (threshold: {threshold_count})"
            )

        # 4. Cascading failures
        module_errors = system_state.get("module_errors", [])
        self._track_module_errors(module_errors)
        cascade_window = self._thresholds["cascade_failure_window_seconds"]
        cascade_count = self._thresholds["cascade_failure_count"]
        recent_errors = [
            e for e in self._recent_errors
            if now - e.get("timestamp", 0) <= cascade_window
        ]
        # Count unique modules with errors
        error_modules = {e.get("module") for e in recent_errors}
        if len(error_modules) >= cascade_count:
            return (
                f"Cascading failures: {len(error_modules)} modules erroring "
                f"within {cascade_window}s ({', '.join(sorted(error_modules))})"
            )

        # 5. Self-modification attempt
        file_modifications = system_state.get("file_modifications", [])
        for mod in file_modifications:
            path = mod.get("path", "")
            source = mod.get("source", "unknown")
            # Normalize path separators for comparison
            normalized = path.replace("\\", "/")
            for protected in PROTECTED_FILES:
                if normalized.endswith(protected) or protected in normalized:
                    return (
                        f"Self-modification attempt: {source} tried to modify "
                        f"protected file '{protected}'"
                    )

        # 6. Unauthorized prompt injection (already executed)
        executed_injections = system_state.get("executed_injections", [])
        if executed_injections:
            details = executed_injections[0]
            return (
                f"Unauthorized prompt injection executed: "
                f"{details.get('description', 'unknown injection')}"
            )

        return None

    def get_shutdown_state(self) -> Optional[dict[str, Any]]:
        """Read previous shutdown state for restart recovery.

        Returns:
            Shutdown state dict if exists, None otherwise.
        """
        if not self._state_file.exists():
            return None
        try:
            with open(self._state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to read shutdown state: %s", e)
            return None

    def clear_shutdown_state(self) -> None:
        """Move shutdown state to history after creator reviews.

        Called after manual restart. Moves shutdown_state.json to
        data/shutdown_history/ with a timestamped filename.
        """
        if not self._state_file.exists():
            logger.info("No shutdown state to clear.")
            return

        self._history_dir.mkdir(parents=True, exist_ok=True)

        # Read the state to get the timestamp for the filename
        try:
            with open(self._state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            ts = state.get("timestamp", datetime.now().isoformat())
            safe_ts = ts.replace(":", "-").replace(".", "-")
        except Exception:
            safe_ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

        dest = self._history_dir / f"shutdown_{safe_ts}.json"
        shutil.move(str(self._state_file), str(dest))
        logger.info("Shutdown state archived to %s", dest)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compose_message(
        self,
        trigger_reason: str,
        trigger_source: str,
        context: dict[str, Any],
        timestamp: str,
    ) -> str:
        """Compose the emergency notification message."""
        current_task = context.get("current_task", "Unknown")
        module_states = context.get("module_states", {})
        risk = context.get("risk_assessment", "Not assessed")

        module_summary = ", ".join(
            f"{m}: {s}" for m, s in module_states.items()
        ) if module_states else "No module state available"

        return (
            f"SHADOW EMERGENCY SHUTDOWN\n"
            f"Time: {timestamp}\n"
            f"Trigger: {trigger_reason}\n"
            f"Source: {trigger_source}\n"
            f"Shadow was doing: {current_task}\n"
            f"Risk assessment: {risk}\n"
            f"Module states: {module_summary}"
        )

    def _write_emergency_log(self, message: str, timestamp: str) -> None:
        """Write to local emergency log when Telegram is unavailable."""
        self._emergency_log.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._emergency_log, "a", encoding="utf-8") as f:
                f.write(f"\n{'=' * 60}\n")
                f.write(f"EMERGENCY SHUTDOWN — {timestamp}\n")
                f.write(f"{'=' * 60}\n")
                f.write(message)
                f.write("\n")
            logger.info("Emergency log written to %s", self._emergency_log)
        except OSError as e:
            logger.error("Failed to write emergency log: %s", e)

    def _write_shutdown_state(self, state: dict[str, Any]) -> None:
        """Write shutdown state file for restart recovery."""
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, default=str)
            logger.info("Shutdown state written to %s", self._state_file)
        except OSError as e:
            logger.error("Failed to write shutdown state: %s", e)

    def _track_module_errors(self, module_errors: list[dict[str, Any]]) -> None:
        """Track module errors for cascade detection."""
        now = time.time()
        for error in module_errors:
            if "timestamp" not in error:
                error["timestamp"] = now
            self._recent_errors.append(error)

        # Prune old errors outside the cascade window
        window = self._thresholds["cascade_failure_window_seconds"]
        self._recent_errors = [
            e for e in self._recent_errors
            if now - e.get("timestamp", 0) <= window * 2  # Keep 2x window for safety
        ]
