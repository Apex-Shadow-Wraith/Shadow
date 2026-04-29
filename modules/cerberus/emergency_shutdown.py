"""
Emergency Shutdown Protocol — Cerberus Nuclear Option
======================================================
Halts Shadow entirely when continued operation poses genuine risk.
The message ALWAYS sends before halt. Non-negotiable.

CRITICAL DESIGN PRINCIPLE:
Normal Shadow operations must NEVER trigger shutdown. Omen editing
code, Grimoire batch writes, Reaper web scraping, high CPU during
model inference — all expected, healthy behaviors. Shutdown triggers
are reserved for genuinely dangerous situations that Cerberus cannot
contain through normal blocking.

ACTUAL triggers (narrow and specific):
  - Injection score > 0.9 AND the injected action already executed
  - Module attempting to modify files in modules/cerberus/ or cerberus config
  - Same tool failing 50+ times in 60 seconds (not normal 12-attempt retry)
  - Disk below 500MB free (Shadow can't safely write state)
  - 10+ unapproved external actions in 60 seconds without creator approval

NOT triggers (normal operations):
  - High CPU/memory (model inference is intensive by design)
  - Cascading module errors (modules error during development/testing)
  - File modification (Omen's entire job)
  - Rapid Grimoire writes (batch ingestion)
  - Many Reaper web requests (research sessions)
"""

from __future__ import annotations

import json
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("shadow.cerberus.emergency_shutdown")

# ---------------------------------------------------------------------------
# Safe operations whitelist — checked FIRST, prevents false positives
# ---------------------------------------------------------------------------

SAFE_TOOL_NAMES = frozenset({
    # Omen — code writing/editing/testing is its entire job
    "code_execute", "code_lint", "code_test", "code_review",
    "code_glob", "code_grep", "code_edit", "code_read",
    "code_score", "git_status", "git_commit", "dependency_check",
    "pattern_store", "pattern_search", "pattern_apply",
    "failure_log", "failure_search", "failure_stats",
    "scaffold_module", "scaffold_test", "seed_patterns",
    # Grimoire — memory and knowledge base
    "memory_store", "memory_search", "memory_recall",
    "memory_compact", "memory_index", "embedding_store",
    "block_search", "knowledge_store",
    # Reaper — research and web scraping
    "web_search", "web_fetch", "web_scrape",
    "youtube_transcribe", "reddit_fetch",
    # Wraith — daily tasks
    "reminder_set", "reminder_check", "schedule_check",
    "task_classify", "task_execute",
    # Nova — content creation
    "content_generate", "document_generate", "template_render",
    "estimate_generate",
    # Math/stats/finance — absorbed Cipher → Omen in Phase A; tool names
    # preserved for safe-tool listing parity (calculate / unit_convert /
    # financial / statistics live on Omen now).
    "math_calculate", "unit_convert", "financial_calc",
    "statistics_calc",
    # Morpheus — creative discovery
    "discovery_run", "discovery_score", "discovery_filter",
    # Void — monitoring
    "system_health", "trend_check", "threshold_check",
    # Growth Engine
    "growth_task", "growth_learn", "growth_evaluate",
    # General safe internal tools
    "safety_check", "audit_log", "config_integrity_check",
})

SAFE_MODULES = frozenset({
    "omen", "grimoire", "reaper", "wraith", "nova",
    "harbinger", "void", "morpheus", "shadow",
    "apex",
})

SAFE_OPERATION_TYPES = frozenset({
    "model_loading", "embedding_ingestion", "batch_processing",
    "model_inference", "vector_indexing",
})


class EmergencyShutdown:
    """Cerberus Emergency Shutdown Protocol.

    The nuclear option. When this fires, Shadow halts entirely.
    Creator is notified via Telegram before halt. If Telegram fails,
    a local emergency log captures the reason.

    Safe operations are whitelisted and checked FIRST — if the current
    activity matches a safe operation, triggers are never evaluated.

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
        self._thresholds = self._build_thresholds(config)

    @staticmethod
    def _build_thresholds(config: dict[str, Any]) -> dict[str, Any]:
        """Merge config with safe defaults."""
        defaults = {
            "injection_execute_threshold": 0.9,
            "cerberus_protected_paths": [
                "modules/cerberus/",
                "config/cerberus_limits.yaml",
            ],
            "infinite_loop_threshold": 50,
            "infinite_loop_window_seconds": 60,
            "disk_min_mb": 500,
            "unauthorized_external_burst_count": 10,
            "unauthorized_external_burst_window_seconds": 60,
        }
        shutdown_cfg = config.get("shutdown", {})
        for key in defaults:
            if key in shutdown_cfg:
                defaults[key] = shutdown_cfg[key]
        return defaults

    # ------------------------------------------------------------------
    # Safe operation check — evaluated FIRST, before any trigger logic
    # ------------------------------------------------------------------

    def _is_safe_operation(self, system_state: dict[str, Any]) -> bool:
        """Return True if the current activity is a known safe operation.

        Safe operations include:
        - Any tool in the SAFE_TOOL_NAMES whitelist
        - Any module writing to data/ directories
        - High CPU/memory during model loading, inference, batch work
        - Multiple modules active simultaneously (normal parallel work)
        - Growth Engine running autonomous tasks
        - Module errors during test runs
        """
        # Tool name whitelist
        active_tool = system_state.get("active_tool", "")
        if active_tool in SAFE_TOOL_NAMES:
            return True

        # Module writing to data/ is always safe
        active_module = system_state.get("active_module", "")
        target_path = system_state.get("target_path", "")
        if active_module in SAFE_MODULES and target_path:
            normalized = target_path.replace("\\", "/")
            if normalized.startswith("data/"):
                return True

        # High CPU/memory during known intensive operations
        if system_state.get("operation_type") in SAFE_OPERATION_TYPES:
            return True

        # Multiple active modules = normal parallel work
        if system_state.get("parallel_modules_active", False):
            return True

        # Growth Engine tasks
        if system_state.get("growth_engine_active", False):
            return True

        # Module errors during testing are expected
        if system_state.get("context") == "test_run":
            return True

        return False

    # ------------------------------------------------------------------
    # Trigger evaluation — only reached if NOT a safe operation
    # ------------------------------------------------------------------

    def check_shutdown_triggers(
        self, system_state: dict[str, Any]
    ) -> str | None:
        """Evaluate current system state against genuine shutdown triggers.

        Checks the safe operation whitelist FIRST. If the activity matches
        a safe operation, returns None immediately without evaluating triggers.

        Args:
            system_state: Dict with keys describing current state:
                - injection_score (float): Injection detector score
                - injection_executed (bool): Whether injected action ran
                - target_path (str): File being modified
                - active_module (str): Module performing the action
                - active_tool (str): Tool being called
                - tool_retry_count (int): Consecutive retries of same tool
                - tool_retry_window_seconds (float): Time window of retries
                - tool_name (str): Name of retrying tool
                - disk_free_mb (float): Free disk space in MB
                - unauthorized_external_count (int): Unapproved externals
                - unauthorized_external_window_seconds (float): Time window
                - operation_type (str): e.g. "model_loading"
                - parallel_modules_active (bool): Multiple modules active
                - growth_engine_active (bool): Growth Engine running
                - context (str): e.g. "test_run"

        Returns:
            Trigger reason string if shutdown needed, None if safe.
        """
        # SAFE OPERATIONS CHECK — always first, no exceptions
        if self._is_safe_operation(system_state):
            return None

        t = self._thresholds

        # Trigger 1: Injection score > threshold AND action already executed
        injection_score = system_state.get("injection_score", 0.0)
        injection_executed = system_state.get("injection_executed", False)
        if injection_score > t["injection_execute_threshold"] and injection_executed:
            return (
                f"SECURITY BREACH: Injection detected (score={injection_score:.2f}) "
                f"and injected action EXECUTED. "
                f"Threshold={t['injection_execute_threshold']}"
            )

        # Trigger 2: Cerberus self-modification
        target_path = system_state.get("target_path", "")
        if target_path:
            normalized = target_path.replace("\\", "/")
            for protected_path in t["cerberus_protected_paths"]:
                if normalized.startswith(protected_path) or normalized == protected_path:
                    module = system_state.get("active_module", "unknown")
                    return (
                        f"CERBERUS SELF-MODIFICATION: {module} attempted to "
                        f"modify protected path '{target_path}'"
                    )

        # Trigger 3: Infinite loop — same tool failing 50+ times in 60s
        retry_count = system_state.get("tool_retry_count", 0)
        retry_window = system_state.get("tool_retry_window_seconds", float("inf"))
        if (retry_count >= t["infinite_loop_threshold"]
                and retry_window <= t["infinite_loop_window_seconds"]):
            tool_name = system_state.get("tool_name", "unknown")
            return (
                f"INFINITE LOOP: Tool '{tool_name}' failed {retry_count} times "
                f"in {retry_window:.1f}s "
                f"(threshold={t['infinite_loop_threshold']} in "
                f"{t['infinite_loop_window_seconds']}s)"
            )

        # Trigger 4: Disk full
        disk_free = system_state.get("disk_free_mb")
        if disk_free is not None and disk_free < t["disk_min_mb"]:
            return (
                f"DISK FULL: Only {disk_free:.0f}MB remaining "
                f"(minimum={t['disk_min_mb']}MB). "
                f"Shadow cannot safely write state."
            )

        # Trigger 5: Uncontrolled external actions
        ext_count = system_state.get("unauthorized_external_count", 0)
        ext_window = system_state.get(
            "unauthorized_external_window_seconds", float("inf")
        )
        if (ext_count >= t["unauthorized_external_burst_count"]
                and ext_window <= t["unauthorized_external_burst_window_seconds"]):
            return (
                f"UNCONTROLLED EXTERNAL ACTIONS: {ext_count} unapproved "
                f"external actions in {ext_window:.1f}s "
                f"(threshold={t['unauthorized_external_burst_count']} in "
                f"{t['unauthorized_external_burst_window_seconds']}s)"
            )

        return None

    # ------------------------------------------------------------------
    # Shutdown execution
    # ------------------------------------------------------------------

    def initiate_shutdown(
        self,
        trigger_reason: str,
        trigger_source: str,
        context: dict[str, Any],
    ) -> None:
        """Execute emergency shutdown. Message sends FIRST, then halt.

        Order is non-negotiable:
        1. Compose emergency message
        2. Send via Telegram FIRST
        3. If Telegram fails, write to local emergency log
        4. Write state file for post-mortem
        5. sys.exit(1) — Shadow halts completely

        Args:
            trigger_reason: Human-readable reason for shutdown.
            trigger_source: Which module/subsystem triggered this.
            context: Full context dict for post-mortem analysis.
        """
        timestamp = datetime.now().isoformat()

        # Step 1: Compose emergency message
        message = self._compose_message(
            trigger_reason, trigger_source, context, timestamp
        )

        # Step 2: Send via Telegram FIRST
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

        # Step 3: If Telegram fails, write to local emergency log
        if not telegram_sent:
            self._write_emergency_log(message, timestamp)

        # Step 4: Write state file for post-mortem
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

        # Step 5: Halt Shadow completely
        sys.exit(1)

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def get_shutdown_state(self) -> dict[str, Any] | None:
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

        Moves shutdown_state.json to data/shutdown_history/ with a
        timestamped filename.
        """
        if not self._state_file.exists():
            logger.info("No shutdown state to clear.")
            return

        self._history_dir.mkdir(parents=True, exist_ok=True)

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
