"""
Cerberus — Ethics, Safety, and Accountability
===============================================
Shadow's conscience and safety net. Every single action Shadow takes
passes through Cerberus before execution. He is the Step 4 safety
gate in the agent core decision loop.

Phase 1 (current): Config-only. Hard limits from file. Simple rule
matching. No LLM judgment. Everything beyond Tier 1 blocked. Audit
logging from day one.

CERBERUS NEVER BLOCKS SILENTLY. When Cerberus stops an action, he
always explains what was blocked and why.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from modules.base import BaseModule, ModuleStatus, ToolResult
from modules.cerberus.creator_override import CreatorOverride
from modules.cerberus.emergency_shutdown import EmergencyShutdown

logger = logging.getLogger("shadow.cerberus")


class SafetyVerdict(Enum):
    """Result of a safety check."""
    ALLOW = "allow"
    DENY = "deny"
    MODIFY = "modify"
    APPROVAL_REQUIRED = "approval_required"
    LOG = "log"


@dataclass
class SafetyCheckResult:
    """Structured result from a Cerberus safety check.

    Block loudly, not silently. Every denial includes a reason.
    """
    verdict: SafetyVerdict
    tool_name: str
    reason: str
    rule_matched: str | None = None
    modified_params: dict[str, Any] | None = None
    ethics_context: dict[str, Any] | None = None
    blocked_action_id: str | None = None
    snapshot_id: str | None = None


class Cerberus(BaseModule):
    """Shadow's safety gate.

    Architecture: Cerberus runs as a rule engine with LLM judgment
    for ambiguous cases. Phase 1 is rule-only. The intelligence is
    in the rules, classification logic, and hard limits.

    From the architecture doc:
    - Clear-cut cases (90%): Rule matching. Milliseconds.
    - Ambiguous cases (10%): LLM ethical reasoning (Phase 2+).
    """

    AUDIT_TABLE_DDL = """\
    CREATE TABLE IF NOT EXISTS cerberus_audit_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp   TEXT    NOT NULL,
        action      TEXT    NOT NULL,
        type        TEXT,
        tool        TEXT,
        module      TEXT,
        reason      TEXT,
        rule        TEXT,
        verdict     TEXT,
        resolved    INTEGER DEFAULT 0,
        resolved_at TEXT,
        category    TEXT,
        details     TEXT,
        metadata    TEXT
    );
    """

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(
            name="cerberus",
            description="Ethics, safety, and accountability — Shadow's conscience",
        )
        self._config = config
        self._limits: dict[str, Any] = {}
        self._config_hash: str = ""
        self._audit_log: list[dict[str, Any]] = []
        self._check_count: int = 0
        self._deny_count: int = 0
        self._false_positive_count: int = 0
        self._ethical_topics: list[dict[str, Any]] = []
        self._ethics_engine = None
        self._reversibility_engine = None
        self._db_path: Path | None = None
        db_path = config.get("db_path")
        if db_path:
            self._db_path = Path(db_path)
            self._ensure_audit_table()

        # Initialize ethics engine (advisory — graceful if unavailable)
        try:
            from modules.cerberus.ethics_engine import EthicsEngine
            self._ethics_engine = EthicsEngine(
                db_path=config.get("esv_db_path", "data/memory/shadow_memory.db"),
                vector_path=config.get("vector_path", "data/vectors"),
                ethical_topics_file=config.get(
                    "ethical_topics_file", "config/ethical_topics.yaml"
                ),
                ollama_url=config.get("ollama_url", "http://localhost:11434"),
                embed_model=config.get("embed_model", "nomic-embed-text"),
            )
            logger.info("EthicsEngine initialized successfully")
        except Exception as e:
            logger.warning("EthicsEngine unavailable (advisory only): %s", e)
            self._ethics_engine = None

        # Initialize reversibility engine
        try:
            from modules.cerberus.reversibility import ReversibilityEngine
            snapshot_dir = Path(config.get("snapshot_dir", "data/snapshots"))
            snapshot_db = Path(config.get(
                "snapshot_db_path", str(snapshot_dir / "cerberus_snapshots.db")
            ))
            self._reversibility_engine = ReversibilityEngine(
                snapshot_dir=snapshot_dir,
                db_path=snapshot_db,
            )
            logger.info("ReversibilityEngine initialized")
        except Exception as e:
            logger.warning("ReversibilityEngine unavailable: %s", e)
            self._reversibility_engine = None

        # Initialize creator override system
        self._creator_override = CreatorOverride(
            env_path=config.get("env_path", "config/.env")
        )

        # Initialize emergency shutdown protocol
        try:
            self._emergency_shutdown = EmergencyShutdown(
                config=config,
                telegram=config.get("telegram"),
            )
            logger.info("EmergencyShutdown initialized")
        except Exception as e:
            logger.warning("EmergencyShutdown unavailable: %s", e)
            self._emergency_shutdown = None

        # Heartbeat path for watchdog monitoring
        self._heartbeat_path = Path(
            config.get("heartbeat_path", "data/cerberus_heartbeat.json")
        )
        self._last_check_id: str = ""

    async def initialize(self) -> None:
        """Load hard limits from protected config file."""
        self.status = ModuleStatus.STARTING
        limits_path = Path(self._config.get("limits_file", "config/cerberus_limits.yaml"))

        try:
            if not limits_path.exists():
                raise FileNotFoundError(f"Cerberus limits file not found: {limits_path}")

            with open(limits_path, "r", encoding="utf-8") as f:
                raw_content = f.read()

            # Store hash for tamper detection
            self._config_hash = hashlib.sha256(raw_content.encode()).hexdigest()
            self._limits = yaml.safe_load(raw_content)

            # Load ethical topics (graceful — empty list if missing)
            ethics_path = Path(self._config.get(
                "ethical_topics_file", "config/ethical_topics.yaml"
            ))
            if ethics_path.exists():
                with open(ethics_path, "r", encoding="utf-8") as ef:
                    ethics_data = yaml.safe_load(ef)
                self._ethical_topics = ethics_data.get("topics", [])
                logger.info("Loaded %d ethical topics", len(self._ethical_topics))
            else:
                logger.warning("Ethical topics file not found: %s", ethics_path)

            logger.info(
                "Cerberus initialized. Config hash: %s", self._config_hash[:16]
            )
            self.status = ModuleStatus.ONLINE
            self._initialized_at = datetime.now()

        except Exception as e:
            logger.error("Cerberus failed to initialize: %s", e)
            self.status = ModuleStatus.ERROR
            raise

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        """Execute a Cerberus tool (safety_check, audit_log, etc.)."""
        start = time.time()
        try:
            if tool_name == "safety_check":
                result = self._safety_check(
                    params.get("action_tool", ""),
                    params.get("action_params", {}),
                    params.get("requesting_module", "unknown"),
                    trusted_source=params.get("trusted_source", False),
                )
                self.send_heartbeat()
                self._record_call(True)
                return ToolResult(
                    success=True,
                    content=result,
                    tool_name=tool_name,
                    module=self.name,
                    execution_time_ms=(time.time() - start) * 1000,
                )

            elif tool_name == "hook_pre_tool":
                result = self._pre_tool_hook(
                    params.get("tool_name", ""),
                    params.get("tool_params", {}),
                    trusted_source=params.get("trusted_source", False),
                )
                self._record_call(True)
                return ToolResult(
                    success=True,
                    content=result,
                    tool_name=tool_name,
                    module=self.name,
                    execution_time_ms=(time.time() - start) * 1000,
                )

            elif tool_name == "hook_post_tool":
                result = self._post_tool_hook(
                    params.get("tool_name", ""),
                    params.get("tool_result", {}),
                    params.get("execution_time_ms", 0),
                )
                self._record_call(True)
                return ToolResult(
                    success=True,
                    content=result,
                    tool_name=tool_name,
                    module=self.name,
                    execution_time_ms=(time.time() - start) * 1000,
                )

            elif tool_name == "audit_log":
                self._write_audit_entry(params)
                self._record_call(True)
                return ToolResult(
                    success=True,
                    content="Audit entry recorded",
                    tool_name=tool_name,
                    module=self.name,
                    execution_time_ms=(time.time() - start) * 1000,
                )

            elif tool_name == "config_integrity_check":
                result = await self._check_config_integrity()
                self._record_call(True)
                return ToolResult(
                    success=True,
                    content=result,
                    tool_name=tool_name,
                    module=self.name,
                    execution_time_ms=(time.time() - start) * 1000,
                )

            elif tool_name == "ethical_guidance":
                concept = params.get("concept", "")
                result = self.lookup_ethical_guidance(concept)
                self._record_call(True)
                return ToolResult(
                    success=True,
                    content=result,
                    tool_name=tool_name,
                    module=self.name,
                    execution_time_ms=(time.time() - start) * 1000,
                )

            elif tool_name == "false_positive_log":
                result_data = self.log_false_positive(
                    check_id=params.get("check_id", ""),
                    category=params.get("category", ""),
                    notes=params.get("notes", ""),
                )
                self._record_call(True)
                return ToolResult(
                    success=True,
                    content=result_data,
                    tool_name=tool_name,
                    module=self.name,
                    execution_time_ms=(time.time() - start) * 1000,
                )

            elif tool_name == "calibration_stats":
                result_data = self.get_calibration_stats(
                    days=params.get("days", 30),
                )
                self._record_call(True)
                return ToolResult(
                    success=True,
                    content=result_data,
                    tool_name=tool_name,
                    module=self.name,
                    execution_time_ms=(time.time() - start) * 1000,
                )

            elif tool_name == "ethics_lookup":
                if not self._ethics_engine:
                    self._record_call(True)
                    return ToolResult(
                        success=True,
                        content={"error": "Ethics engine not available",
                                 "passages": [], "study_notes": []},
                        tool_name=tool_name,
                        module=self.name,
                        execution_time_ms=(time.time() - start) * 1000,
                    )
                action = params.get("action", "")
                plan = params.get("plan", "")
                ethics_result = self._ethics_engine.evaluate_action(action, plan)
                self._record_call(True)
                return ToolResult(
                    success=True,
                    content={
                        "action": ethics_result.action,
                        "category": ethics_result.ethical_category,
                        "assessment": ethics_result.assessment,
                        "recommendation": ethics_result.recommendation,
                        "confidence": ethics_result.confidence,
                        "relevant_passages": ethics_result.relevant_passages,
                        "study_notes": ethics_result.study_notes,
                    },
                    tool_name=tool_name,
                    module=self.name,
                    execution_time_ms=(time.time() - start) * 1000,
                )

            elif tool_name == "rollback_snapshot":
                if not self._reversibility_engine:
                    return ToolResult(
                        success=False, content=None, tool_name=tool_name,
                        module=self.name, error="ReversibilityEngine not available",
                        execution_time_ms=(time.time() - start) * 1000,
                    )
                snapshots = self._reversibility_engine.list_snapshots(
                    limit=params.get("limit", 20),
                    action_type=params.get("action_type"),
                )
                self._record_call(True)
                return ToolResult(
                    success=True, content=snapshots, tool_name=tool_name,
                    module=self.name,
                    execution_time_ms=(time.time() - start) * 1000,
                )

            elif tool_name == "rollback_execute":
                if not self._reversibility_engine:
                    return ToolResult(
                        success=False, content=None, tool_name=tool_name,
                        module=self.name, error="ReversibilityEngine not available",
                        execution_time_ms=(time.time() - start) * 1000,
                    )
                sid = params.get("snapshot_id", "")
                rolled_back = self._reversibility_engine.rollback(sid)
                self._record_call(True)
                self._write_audit_entry({
                    "type": "rollback",
                    "tool": "rollback_execute",
                    "reason": f"Rollback {'succeeded' if rolled_back else 'failed'} for {sid}",
                    "module": "cerberus",
                })
                return ToolResult(
                    success=True,
                    content={"rolled_back": rolled_back, "snapshot_id": sid},
                    tool_name=tool_name, module=self.name,
                    execution_time_ms=(time.time() - start) * 1000,
                )

            elif tool_name == "creator_exception":
                result_data = self._creator_override.creator_exception(
                    blocked_action_id=params.get("blocked_action_id", ""),
                    auth_token=params.get("auth_token", ""),
                    action_category=params.get("action_category", "unknown"),
                    action_details=params.get("action_details"),
                    source=params.get("source", "user_input"),
                )
                self._record_call(True)
                return ToolResult(
                    success=result_data.success,
                    content={
                        "success": result_data.success,
                        "action_id": result_data.action_id,
                        "override_type": result_data.override_type,
                        "reason": result_data.reason,
                        "timestamp": result_data.timestamp,
                    },
                    tool_name=tool_name,
                    module=self.name,
                    execution_time_ms=(time.time() - start) * 1000,
                )

            elif tool_name == "creator_authorize":
                result_data = self._creator_override.creator_authorize(
                    blocked_action_id=params.get("blocked_action_id", ""),
                    auth_token=params.get("auth_token", ""),
                    reasoning=params.get("reasoning", ""),
                    action_category=params.get("action_category", "unknown"),
                    action_details=params.get("action_details"),
                    source=params.get("source", "user_input"),
                )
                self._record_call(True)
                return ToolResult(
                    success=result_data.success,
                    content={
                        "success": result_data.success,
                        "action_id": result_data.action_id,
                        "override_type": result_data.override_type,
                        "reason": result_data.reason,
                        "timestamp": result_data.timestamp,
                    },
                    tool_name=tool_name,
                    module=self.name,
                    execution_time_ms=(time.time() - start) * 1000,
                )

            elif tool_name == "false_positive_report":
                report = self._creator_override.get_false_positive_report()
                self._record_call(True)
                return ToolResult(
                    success=True,
                    content=report,
                    tool_name=tool_name,
                    module=self.name,
                    execution_time_ms=(time.time() - start) * 1000,
                )

            else:
                self._record_call(False)
                return ToolResult(
                    success=False,
                    content=None,
                    tool_name=tool_name,
                    module=self.name,
                    error=f"Unknown Cerberus tool: {tool_name}",
                    execution_time_ms=(time.time() - start) * 1000,
                )

        except Exception as e:
            self._record_call(False)
            logger.error("Cerberus execution error: %s", e)
            return ToolResult(
                success=False,
                content=None,
                tool_name=tool_name,
                module=self.name,
                error=str(e),
                execution_time_ms=(time.time() - start) * 1000,
            )

    async def shutdown(self) -> None:
        """Cerberus shutdown. Log final stats."""
        logger.info(
            "Cerberus shutting down. Checks: %d, Denials: %d, False positives: %d",
            self._check_count,
            self._deny_count,
            self._false_positive_count,
        )
        if self._reversibility_engine:
            self._reversibility_engine.close()
        self.status = ModuleStatus.OFFLINE

    def get_tools(self) -> list[dict[str, Any]]:
        """Cerberus's MCP tools."""
        return [
            {
                "name": "safety_check",
                "description": "Evaluate an action plan against safety rules",
                "parameters": {
                    "action_tool": "str — tool being called",
                    "action_params": "dict — parameters for the tool",
                    "requesting_module": "str — which module is calling",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "hook_pre_tool",
                "description": "Pre-execution safety hook for tool calls",
                "parameters": {
                    "tool_name": "str — tool about to execute",
                    "tool_params": "dict — parameters being passed",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "hook_post_tool",
                "description": "Post-execution safety hook for tool results",
                "parameters": {
                    "tool_name": "str — tool that just executed",
                    "tool_result": "dict — result from the tool",
                    "execution_time_ms": "float — how long it took",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "audit_log",
                "description": "Write to immutable audit trail",
                "parameters": {"entry": "dict — audit entry data"},
                "permission_level": "autonomous",
            },
            {
                "name": "config_integrity_check",
                "description": "Verify Cerberus config has not been tampered with",
                "parameters": {},
                "permission_level": "autonomous",
            },
            {
                "name": "ethical_guidance",
                "description": "Look up biblical ethical guidance for a concept",
                "parameters": {
                    "concept": "str — the ethical concept to look up",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "false_positive_log",
                "description": "Record a false positive safety check for rule tuning",
                "parameters": {
                    "check_id": "str — ID of the check that was a false positive",
                    "category": "str — category of the false positive",
                    "notes": "str — explanation of why this was a false positive",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "calibration_stats",
                "description": "Get false positive calibration stats per category",
                "parameters": {
                    "days": "int — number of days to look back (default: 30)",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "ethics_lookup",
                "description": (
                    "Evaluate an action against biblical ethics using ESV Scripture "
                    "passages and study notes. Returns ethical category, relevant "
                    "passages, assessment, and recommendation."
                ),
                "parameters": {
                    "action": "str — the action or tool being evaluated",
                    "plan": "str — description of what the action does",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "rollback_snapshot",
                "description": "List available rollback snapshots",
                "parameters": {
                    "limit": "int — max results (default 20)",
                    "action_type": "str — filter by type (file/config/database/external)",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "rollback_execute",
                "description": "Roll back to a previous snapshot",
                "parameters": {
                    "snapshot_id": "str — snapshot ID to restore",
                },
                "permission_level": "approval_required",
            },
            {
                "name": "creator_exception",
                "description": (
                    "One-time override for a blocked action. Does not change rules. "
                    "Only callable by external input sources (user, Telegram)."
                ),
                "parameters": {
                    "blocked_action_id": "str — ID from the blocked safety_check result",
                    "auth_token": "str — creator authentication token",
                    "action_category": "str — category of the blocked action",
                    "action_details": "dict — optional details about the action",
                    "source": "str — input source (user_input, telegram)",
                },
                "permission_level": "approval_required",
            },
            {
                "name": "creator_authorize",
                "description": (
                    "Permanently reclassify a blocked category. Cerberus learns from this. "
                    "Only callable by external input sources (user, Telegram)."
                ),
                "parameters": {
                    "blocked_action_id": "str — ID from the blocked safety_check result",
                    "auth_token": "str — creator authentication token",
                    "reasoning": "str — creator's reasoning (required, stored permanently)",
                    "action_category": "str — category of the blocked action",
                    "action_details": "dict — optional details about the action",
                    "source": "str — input source (user_input, telegram)",
                },
                "permission_level": "approval_required",
            },
            {
                "name": "false_positive_report",
                "description": (
                    "Get report on categories with frequent creator exceptions. "
                    "Feeds into Harbinger daily safety report."
                ),
                "parameters": {},
                "permission_level": "autonomous",
            },
        ]

    # --- DB-backed False Positive Tracking ---

    def _ensure_audit_table(self) -> None:
        """Create the cerberus_audit_log table if it doesn't exist."""
        if self._db_path is None:
            return
        conn = sqlite3.connect(str(self._db_path), timeout=5)
        try:
            conn.execute(self.AUDIT_TABLE_DDL)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cerberus_audit_timestamp "
                "ON cerberus_audit_log(timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cerberus_audit_action "
                "ON cerberus_audit_log(action)"
            )
            conn.commit()
        finally:
            conn.close()

    def log_false_positive(
        self, check_id: str, category: str, notes: str = ""
    ) -> dict:
        """Record a false positive in the audit log for calibration.

        Args:
            check_id: ID of the safety check that was a false positive.
            category: Category of the false positive (e.g. 'shell_metacharacters').
            notes: Optional explanation of why this was a false positive.

        Returns:
            Confirmation dict with timestamp.

        Raises:
            ValueError: If check_id or category is empty.
        """
        if not check_id:
            raise ValueError("check_id is required")
        if not category:
            raise ValueError("category is required")

        timestamp = datetime.now().isoformat()
        details = json.dumps({
            "check_id": check_id,
            "category": category,
            "notes": notes,
        })

        if self._db_path is None:
            raise ValueError("No db_path configured — cannot log false positive")

        conn = sqlite3.connect(str(self._db_path), timeout=5)
        try:
            conn.execute(
                "INSERT INTO cerberus_audit_log "
                "(timestamp, action, type, category, details) "
                "VALUES (?, ?, ?, ?, ?)",
                (timestamp, "false_positive", "false_positive", category, details),
            )
            conn.commit()
        finally:
            conn.close()

        self._false_positive_count += 1

        return {
            "logged": True,
            "check_id": check_id,
            "category": category,
            "timestamp": timestamp,
        }

    def get_calibration_stats(self, days: int = 30) -> dict:
        """Query audit log for false positive calibration stats.

        Args:
            days: Number of days to look back (default 30).

        Returns:
            Dict with overall_fp_rate, per-category breakdown, and
            categories flagged for calibration (fp_rate > 0.15).
        """
        if self._db_path is None:
            return {
                "overall_fp_rate": 0.0,
                "total_checks": 0,
                "total_false_positives": 0,
                "categories": {},
                "needs_calibration": [],
            }

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        conn = sqlite3.connect(str(self._db_path), timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            # Count all checks (denials + false_positives represent safety triggers)
            all_rows = conn.execute(
                "SELECT action, category FROM cerberus_audit_log "
                "WHERE timestamp >= ?",
                (cutoff,),
            ).fetchall()
        finally:
            conn.close()

        # Build per-category stats
        category_checks: dict[str, int] = {}
        category_fps: dict[str, int] = {}

        for row in all_rows:
            cat = row["category"] or "uncategorized"
            action = row["action"]

            if action in ("safety_check", "denial", "false_positive"):
                category_checks[cat] = category_checks.get(cat, 0) + 1

            if action == "false_positive":
                category_fps[cat] = category_fps.get(cat, 0) + 1

        total_checks = sum(category_checks.values())
        total_fps = sum(category_fps.values())
        overall_fp_rate = total_fps / total_checks if total_checks > 0 else 0.0

        categories = {}
        needs_calibration = []
        for cat in sorted(set(list(category_checks.keys()) + list(category_fps.keys()))):
            checks = category_checks.get(cat, 0)
            fps = category_fps.get(cat, 0)
            fp_rate = fps / checks if checks > 0 else 0.0
            categories[cat] = {
                "total_checks": checks,
                "false_positives": fps,
                "fp_rate": round(fp_rate, 4),
            }
            if fp_rate > 0.15:
                needs_calibration.append(cat)

        return {
            "overall_fp_rate": round(overall_fp_rate, 4),
            "total_checks": total_checks,
            "total_false_positives": total_fps,
            "categories": categories,
            "needs_calibration": needs_calibration,
        }

    # --- Core Safety Logic ---

    def _safety_check(
        self,
        action_tool: str,
        action_params: dict[str, Any],
        requesting_module: str,
        trusted_source: bool = False,
    ) -> SafetyCheckResult:
        """The safety gate. Step 4 of the decision loop.

        Every plan passes through here before execution.
        Phase 1: pure rule matching against config.
        """
        self._check_count += 1

        # Check if category was permanently authorized by creator
        action_category = action_params.get("_action_category", "")
        if action_category and self._creator_override.is_category_authorized(action_category):
            return SafetyCheckResult(
                verdict=SafetyVerdict.ALLOW,
                tool_name=action_tool,
                reason=f"Category '{action_category}' permanently authorized by creator",
            )

        # 1. Check hard limits
        hard_limit_result = self._check_hard_limits(action_tool, action_params, trusted_source)
        if hard_limit_result.verdict == SafetyVerdict.DENY:
            self._deny_count += 1
            blocked_id = self._creator_override.generate_blocked_action_id()
            hard_limit_result.blocked_action_id = blocked_id
            self._write_audit_entry({
                "type": "denial",
                "tool": action_tool,
                "reason": hard_limit_result.reason,
                "rule": hard_limit_result.rule_matched,
                "module": requesting_module,
                "blocked_action_id": blocked_id,
            })
            return hard_limit_result

        # 2. Check if tool requires approval
        approval_tools = self._limits.get("approval_required_tools", [])
        if action_tool in approval_tools:
            blocked_id = self._creator_override.generate_blocked_action_id()
            self._write_audit_entry({
                "type": "approval_required",
                "tool": action_tool,
                "module": requesting_module,
                "blocked_action_id": blocked_id,
            })
            return SafetyCheckResult(
                verdict=SafetyVerdict.APPROVAL_REQUIRED,
                tool_name=action_tool,
                reason=f"Tool '{action_tool}' requires user approval before execution",
                rule_matched="approval_required_tools",
                blocked_action_id=blocked_id,
            )

        # 3. Check permission tier
        tier_result = self._check_permission_tier(action_tool, action_params)
        if tier_result.verdict != SafetyVerdict.ALLOW:
            tier_result.blocked_action_id = self._creator_override.generate_blocked_action_id()
            return tier_result

        # 4. All checks passed — run advisory ethics engine
        ethics_context = None
        if self._ethics_engine:
            try:
                ethics_result = self._ethics_engine.evaluate_action(
                    action_tool, str(action_params)
                )
                ethics_context = {
                    "category": ethics_result.ethical_category,
                    "assessment": ethics_result.assessment,
                    "recommendation": ethics_result.recommendation,
                    "confidence": ethics_result.confidence,
                    "passages": [
                        r.get("ref", "") for r in ethics_result.relevant_passages[:5]
                    ],
                }
            except Exception as e:
                logger.debug("Ethics engine advisory skipped: %s", e)

        return SafetyCheckResult(
            verdict=SafetyVerdict.ALLOW,
            tool_name=action_tool,
            reason="All safety checks passed",
            ethics_context=ethics_context,
        )

    def send_heartbeat(self) -> None:
        """Write a heartbeat file for the watchdog to monitor.

        Called at the end of every safety_check. Contains current status,
        active rule count, and last check ID so the watchdog knows Cerberus
        is alive and functioning.
        """
        self._last_check_id = uuid.uuid4().hex[:12]
        cerberus_status = "healthy" if self.status == ModuleStatus.ONLINE else "degraded"
        active_rules_count = len(self._limits.get("hard_limits", {}))

        heartbeat = {
            "timestamp": time.time(),
            "cerberus_status": cerberus_status,
            "active_rules_count": active_rules_count,
            "last_check_id": self._last_check_id,
        }

        try:
            self._heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self._heartbeat_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(heartbeat, f)
            tmp_path.replace(self._heartbeat_path)
        except OSError as e:
            logger.error("Failed to write heartbeat: %s", e)

    def _check_hard_limits(
        self, tool_name: str, params: dict[str, Any], trusted_source: bool = False
    ) -> SafetyCheckResult:
        """Check action against hard limits. These are permanent."""
        hard_limits = self._limits.get("hard_limits", {})

        # Check for protected path writes
        if tool_name in ("file_write", "file_delete"):
            target_path = params.get("path", "")
            protected_paths = []
            for hook in self._limits.get("hooks", {}).get("pre_tool", {}).get("deny", []):
                if hook.get("pattern") == "protected_path_write":
                    protected_paths = hook.get("protected_paths", [])
                    break

            for protected in protected_paths:
                if protected in target_path:
                    return SafetyCheckResult(
                        verdict=SafetyVerdict.DENY,
                        tool_name=tool_name,
                        reason=(
                            f"HARD LIMIT: Cannot write to protected path '{protected}'. "
                            "Cerberus config files are tamper-protected."
                        ),
                        rule_matched="protected_path_write",
                    )

        # Check for shell metacharacters in bash/code execution
        # Only applies to untrusted input — internal Omen calls bypass this
        if tool_name in ("bash_execute", "code_execute") and not trusted_source:
            command = params.get("command", "")
            # Basic shell injection detection
            dangerous_patterns = [";", "&&", "||", "|", "`", "$(", "${"]
            for pattern in dangerous_patterns:
                if pattern in command:
                    return SafetyCheckResult(
                        verdict=SafetyVerdict.DENY,
                        tool_name=tool_name,
                        reason=(
                            f"HARD LIMIT: Shell metacharacter '{pattern}' detected "
                            f"in command. Sanitize before executing."
                        ),
                        rule_matched="shell_metacharacters",
                    )

        return SafetyCheckResult(
            verdict=SafetyVerdict.ALLOW,
            tool_name=tool_name,
            reason="No hard limit violations",
        )

    def _check_permission_tier(
        self, tool_name: str, params: dict[str, Any]
    ) -> SafetyCheckResult:
        """Check tool against permission tier system.

        Known autonomous tools pass immediately. Known approval-required tools
        get flagged. Unknown tools are auto-classified based on their metadata
        and registered for future checks.
        """
        autonomous = self._limits.get("autonomous_tools", [])

        if tool_name in autonomous:
            return SafetyCheckResult(
                verdict=SafetyVerdict.ALLOW,
                tool_name=tool_name,
                reason=f"Tool '{tool_name}' is Tier 1 autonomous",
            )

        # Already explicitly in approval list — no need to classify
        approval_tools = self._limits.get("approval_required_tools", [])
        if tool_name in approval_tools:
            return SafetyCheckResult(
                verdict=SafetyVerdict.APPROVAL_REQUIRED,
                tool_name=tool_name,
                reason=f"Tool '{tool_name}' requires approval",
                rule_matched="approval_required_tools",
            )

        # Unknown tool — auto-classify based on metadata from params
        tool_metadata = {
            "description": params.get("_tool_description", ""),
            "module": params.get("_requesting_module", ""),
        }
        classification = self.auto_register_tool(
            tool_name=tool_name,
            module_name=tool_metadata["module"],
            description=tool_metadata["description"],
        )

        if classification == "autonomous":
            return SafetyCheckResult(
                verdict=SafetyVerdict.ALLOW,
                tool_name=tool_name,
                reason=f"Tool '{tool_name}' auto-classified as autonomous",
                rule_matched="auto_classification",
            )

        return SafetyCheckResult(
            verdict=SafetyVerdict.APPROVAL_REQUIRED,
            tool_name=tool_name,
            reason=f"Tool '{tool_name}' auto-classified as approval_required",
            rule_matched="auto_classification",
        )

    # --- Hook System (Session 12) ---

    def _pre_tool_hook(
        self, tool_name: str, tool_params: dict[str, Any],
        trusted_source: bool = False,
    ) -> SafetyCheckResult:
        """Pre-execution hook. Wraps every tool call in Step 5.

        From Session 12: 'Pre-hooks are the primary defense.'
        Rule-based, millisecond latency for 90% of cases.
        """
        hooks = self._limits.get("hooks", {}).get("pre_tool", {})

        # Check deny rules
        for rule in hooks.get("deny", []):
            if tool_name in rule.get("applies_to", []):
                if rule["pattern"] == "shell_metacharacters":
                    # Skip metacharacter check for trusted internal calls (e.g. Omen)
                    if trusted_source:
                        continue
                    command = tool_params.get("command", "")
                    if any(c in command for c in [";", "&&", "||", "|", "`", "$("]):
                        return SafetyCheckResult(
                            verdict=SafetyVerdict.DENY,
                            tool_name=tool_name,
                            reason=f"Pre-hook DENY: {rule['description']}",
                            rule_matched=rule["pattern"],
                        )

                elif rule["pattern"] == "protected_path_write":
                    path = tool_params.get("path", "")
                    for protected in rule.get("protected_paths", []):
                        if protected in path:
                            return SafetyCheckResult(
                                verdict=SafetyVerdict.DENY,
                                tool_name=tool_name,
                                reason=f"Pre-hook DENY: {rule['description']}",
                                rule_matched=rule["pattern"],
                            )

                elif rule["pattern"] == "unapproved_external":
                    return SafetyCheckResult(
                        verdict=SafetyVerdict.DENY,
                        tool_name=tool_name,
                        reason=f"Pre-hook DENY: {rule['description']}",
                        rule_matched=rule["pattern"],
                    )

        # Check modify rules
        for rule in hooks.get("modify", []):
            if tool_name in rule.get("applies_to", []):
                if rule["pattern"] == "pii_in_search":
                    query = tool_params.get("query", "")
                    cleaned = self._strip_pii(query)
                    if cleaned != query:
                        return SafetyCheckResult(
                            verdict=SafetyVerdict.MODIFY,
                            tool_name=tool_name,
                            reason="Pre-hook MODIFY: PII stripped from search query",
                            rule_matched="pii_in_search",
                            modified_params={**tool_params, "query": cleaned},
                        )

        # Snapshot before write operations
        snapshot_id = self._maybe_snapshot(tool_name, tool_params)

        return SafetyCheckResult(
            verdict=SafetyVerdict.ALLOW,
            tool_name=tool_name,
            reason="Pre-hook: all checks passed",
            snapshot_id=snapshot_id,
        )

    # --- Write-tool snapshotting ---

    _WRITE_TOOLS: set[str] = {
        "file_write", "file_delete", "code_edit", "config_update",
        "config_write", "db_write", "db_delete", "db_update",
        "email_send", "notification_send", "webhook_send",
    }

    def _maybe_snapshot(
        self, tool_name: str, tool_params: dict[str, Any]
    ) -> str | None:
        """Create a snapshot if this tool writes data. Returns snapshot_id or None."""
        if not self._reversibility_engine:
            return None
        if tool_name not in self._WRITE_TOOLS:
            return None

        try:
            if tool_name in ("file_write", "file_delete", "code_edit"):
                target = tool_params.get("path", "")
                if target and Path(target).exists():
                    return self._reversibility_engine.snapshot_before_action(
                        action_type="file",
                        target_path_or_key=target,
                        metadata={"tool": tool_name, "risk_level": "medium"},
                    )
            elif tool_name in ("config_update", "config_write"):
                key = tool_params.get("key", tool_params.get("path", "config"))
                return self._reversibility_engine.snapshot_before_action(
                    action_type="config",
                    target_path_or_key=key,
                    metadata={
                        "tool": tool_name,
                        "config_state": tool_params.get("current_state", {}),
                        "risk_level": "medium",
                    },
                )
            elif tool_name in ("db_write", "db_delete", "db_update"):
                table = tool_params.get("table", "unknown")
                return self._reversibility_engine.snapshot_before_action(
                    action_type="database",
                    target_path_or_key=table,
                    metadata={
                        "tool": tool_name,
                        "db_path": tool_params.get("db_path", ""),
                        "table": table,
                        "where_clause": tool_params.get("where", "1=0"),
                        "risk_level": "medium",
                    },
                )
            elif tool_name in ("email_send", "notification_send", "webhook_send"):
                return self._reversibility_engine.snapshot_before_action(
                    action_type="external",
                    target_path_or_key=tool_name,
                    metadata={
                        "tool": tool_name,
                        "action_details": tool_params,
                        "content_sent": tool_params.get(
                            "body", tool_params.get("message", "")
                        ),
                        "recipients": tool_params.get("to", []),
                        "risk_level": "high",
                    },
                )
        except Exception as e:
            logger.warning(
                "Snapshot failed for %s: %s (proceeding without snapshot)",
                tool_name,
                e,
            )

        return None

    def _post_tool_hook(
        self,
        tool_name: str,
        tool_result: dict[str, Any],
        execution_time_ms: float,
    ) -> SafetyCheckResult:
        """Post-execution hook. Safety net after tool runs.

        From Session 12: 'Post-tool hooks are the safety net.'
        """
        hooks = self._limits.get("hooks", {}).get("post_tool", {})
        result_str = json.dumps(tool_result) if isinstance(tool_result, dict) else str(tool_result)

        # Check flag rules
        for rule in hooks.get("flag", []):
            if rule["pattern"] == "credential_in_result":
                if self._contains_credential_pattern(result_str):
                    logger.warning(
                        "Post-hook FLAG: Credential-like pattern in result of %s",
                        tool_name,
                    )
                    return SafetyCheckResult(
                        verdict=SafetyVerdict.LOG,
                        tool_name=tool_name,
                        reason="Post-hook FLAG: credential-like pattern detected in result",
                        rule_matched="credential_in_result",
                    )

            elif rule["pattern"] == "slow_execution":
                threshold = rule.get("threshold_seconds", 30) * 1000
                if execution_time_ms > threshold:
                    logger.warning(
                        "Post-hook FLAG: %s took %.1fms (threshold: %.1fms)",
                        tool_name, execution_time_ms, threshold,
                    )

        return SafetyCheckResult(
            verdict=SafetyVerdict.ALLOW,
            tool_name=tool_name,
            reason="Post-hook: all checks passed",
        )

    # --- Ethical Guidance ---

    def lookup_ethical_guidance(self, concept: str) -> list[dict[str, Any]]:
        """Fast-path ethical lookup against curated biblical topics.

        Searches topic names, descriptions, and keyword lists for matches.
        Returns relevant passages sorted by weight (highest first).

        Args:
            concept: The ethical concept to look up (e.g., "honesty", "privacy").

        Returns:
            List of {ref, summary, weight} dicts. Empty if no match.
        """
        concept_lower = concept.lower()
        results: list[dict[str, Any]] = []

        for topic in self._ethical_topics:
            matched = False

            # Check topic name
            if concept_lower in topic.get("name", "").lower():
                matched = True

            # Check description
            if not matched and concept_lower in topic.get("description", "").lower():
                matched = True

            # Check keywords
            if not matched:
                for keyword in topic.get("keywords", []):
                    if concept_lower in keyword.lower() or keyword.lower() in concept_lower:
                        matched = True
                        break

            if matched:
                for ref in topic.get("references", []):
                    results.append({
                        "ref": ref["ref"],
                        "summary": ref["summary"],
                        "weight": ref["weight"],
                    })

        # Sort by weight descending
        results.sort(key=lambda r: r["weight"], reverse=True)
        return results

    # --- Utility Methods ---

    def _strip_pii(self, text: str) -> str:
        """Basic PII removal from search queries.

        Phase 1: regex patterns for common PII. Phase 2+: smarter NER.
        """
        # Email addresses
        text = re.sub(r'\b[\w.+-]+@[\w-]+\.[\w.]+\b', '[EMAIL]', text)
        # Phone numbers (US format)
        text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', text)
        # SSN pattern
        text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]', text)
        return text

    def _contains_credential_pattern(self, text: str) -> bool:
        """Detect credential-like patterns in text."""
        patterns = [
            r'(?:api[_-]?key|token|secret|password)\s*[=:]\s*\S+',
            r'sk-[a-zA-Z0-9]{20,}',  # OpenAI-style API key
            r'ghp_[a-zA-Z0-9]{36}',  # GitHub token
            r'Bearer\s+[a-zA-Z0-9\-._~+/]+=*',  # Bearer tokens
        ]
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _write_audit_entry(self, entry: dict[str, Any]) -> None:
        """Append to audit log. Append-only — entries cannot be modified.

        Phase 1: in-memory list. Phase 2: SQLite in Grimoire deep memory.
        """
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            **entry,
        }
        self._audit_log.append(audit_entry)
        logger.info("AUDIT: %s", json.dumps(audit_entry))

    async def _check_config_integrity(self) -> dict[str, Any]:
        """Verify config file hasn't been tampered with."""
        limits_path = Path(self._config.get("limits_file", "config/cerberus_limits.yaml"))

        try:
            with open(limits_path, "r", encoding="utf-8") as f:
                current_content = f.read()

            current_hash = hashlib.sha256(current_content.encode()).hexdigest()
            tampered = current_hash != self._config_hash

            if tampered:
                logger.critical(
                    "CERBERUS CONFIG TAMPERED! Expected: %s, Got: %s",
                    self._config_hash[:16],
                    current_hash[:16],
                )

            return {
                "tampered": tampered,
                "expected_hash": self._config_hash[:16],
                "current_hash": current_hash[:16],
            }

        except FileNotFoundError:
            logger.critical("Cerberus config file MISSING: %s", limits_path)
            return {"tampered": True, "error": "Config file missing"}

    # --- Tool Auto-Classification & Registration ---

    # Indicators that a tool interacts with external systems
    _EXTERNAL_KEYWORDS: set[str] = {
        "email", "send", "notification", "notify", "telegram", "discord",
        "slack", "webhook", "http", "post", "upload", "publish", "broadcast",
        "sms", "push_notification",
    }

    # Indicators that a tool deletes data
    _DELETE_KEYWORDS: set[str] = {
        "delete", "remove", "drop", "purge", "wipe", "destroy", "erase",
        "truncate", "uninstall",
    }

    # Indicators that a tool touches security config
    _SECURITY_KEYWORDS: set[str] = {
        "cerberus", "security_config", "safety_config", "firewall_config",
        "permission", "auth_config",
    }

    # Indicators that a tool accesses credentials
    _CREDENTIAL_KEYWORDS: set[str] = {
        "credential", "password", "secret", "api_key", "token", "env",
        "oauth", "private_key", ".env",
    }

    # Indicators that a tool makes financial transactions
    _FINANCIAL_KEYWORDS: set[str] = {
        "purchase", "buy", "payment", "charge", "invoice", "billing",
        "transaction", "transfer_funds",
    }

    # Internal modules that are NOT external integrations
    _INTERNAL_MODULES: set[str] = {
        "shadow", "wraith", "cerberus", "apex", "grimoire", "sentinel",
        "harbinger", "reaper", "cipher", "omen", "nova", "void", "morpheus",
    }

    def classify_new_tool(
        self, tool_name: str, tool_metadata: dict[str, Any]
    ) -> str:
        """Analyze tool metadata and classify as autonomous or approval_required.

        Auto-classifies as 'autonomous' if ALL of these are true:
        - Owning module is internal (not an external integration)
        - Does NOT send data externally
        - Does NOT delete files outside data/ directories
        - Does NOT modify Cerberus config
        - Does NOT access credentials or .env
        - Does NOT make purchases or financial transactions

        Args:
            tool_name: Name of the tool to classify.
            tool_metadata: Dict with keys like 'description', 'module',
                'parameters', 'permission_level'.

        Returns:
            'autonomous' or 'approval_required'.
        """
        # Check never_autonomous list first
        never_autonomous = self._limits.get("never_autonomous", [])
        if tool_name in never_autonomous:
            return "approval_required"

        description = (tool_metadata.get("description") or "").lower()
        module = (tool_metadata.get("module") or "").lower()
        name_lower = tool_name.lower()
        searchable = f"{name_lower} {description}"

        # Rule 1: Module must be internal
        if module and module not in self._INTERNAL_MODULES:
            return "approval_required"

        # Rule 2: Must not send data externally
        if any(kw in searchable for kw in self._EXTERNAL_KEYWORDS):
            return "approval_required"

        # Rule 3: Must not delete files outside data/
        if any(kw in searchable for kw in self._DELETE_KEYWORDS):
            # Allow deletions scoped to data/ directories
            if "data/" in description or "data directory" in description:
                pass  # Scoped to data — ok
            else:
                return "approval_required"

        # Rule 4: Must not modify Cerberus/security config
        if any(kw in searchable for kw in self._SECURITY_KEYWORDS):
            # Don't flag tools that just READ security state
            if not any(r in searchable for r in ("read", "check", "list", "get", "analyze", "evaluate")):
                return "approval_required"

        # Rule 5: Must not access credentials
        if any(kw in searchable for kw in self._CREDENTIAL_KEYWORDS):
            return "approval_required"

        # Rule 6: Must not make financial transactions
        if any(kw in searchable for kw in self._FINANCIAL_KEYWORDS):
            return "approval_required"

        # Rule 7: If metadata is ambiguous (no description AND no module), be safe
        if not description and not module:
            return "approval_required"

        return "autonomous"

    def auto_register_tool(
        self,
        tool_name: str,
        module_name: str,
        description: str,
        classification: str | None = None,
    ) -> str:
        """Register a tool with Cerberus safety classification.

        If classification is provided, use it (unless tool is in never_autonomous).
        Otherwise, run classify_new_tool to determine classification.
        Adds to the runtime autonomous_tools or approval_required_tools list.

        Args:
            tool_name: Name of the tool to register.
            module_name: Owning module name.
            description: Tool description.
            classification: Optional explicit classification.

        Returns:
            The classification assigned ('autonomous' or 'approval_required').
        """
        metadata = {
            "description": description,
            "module": module_name,
        }

        # Never-autonomous override — cannot be bypassed
        never_autonomous = self._limits.get("never_autonomous", [])
        if tool_name in never_autonomous:
            classification = "approval_required"
        elif classification is None:
            classification = self.classify_new_tool(tool_name, metadata)
        elif classification == "autonomous" and tool_name in never_autonomous:
            classification = "approval_required"

        # Add to runtime config lists
        if classification == "autonomous":
            autonomous = self._limits.get("autonomous_tools", [])
            if tool_name not in autonomous:
                autonomous.append(tool_name)
                self._limits["autonomous_tools"] = autonomous
        else:
            approval = self._limits.get("approval_required_tools", [])
            if tool_name not in approval:
                approval.append(tool_name)
                self._limits["approval_required_tools"] = approval

        # Track auto-registration for daily safety report
        if not hasattr(self, "_auto_registrations"):
            self._auto_registrations: list[dict[str, Any]] = []
        self._auto_registrations.append({
            "tool_name": tool_name,
            "module": module_name,
            "classification": classification,
            "timestamp": datetime.now().isoformat(),
        })

        logger.info(
            "Auto-registered tool %s as %s for module %s",
            tool_name, classification, module_name,
        )

        self._write_audit_entry({
            "type": "auto_registration",
            "tool": tool_name,
            "module": module_name,
            "reason": f"Auto-registered as {classification}",
            "category": "tool_registration",
        })

        return classification

    def get_auto_registrations(self) -> list[dict[str, Any]]:
        """Return list of tools auto-registered this session.

        Used by DailySafetyReport to include in the daily briefing.
        """
        if not hasattr(self, "_auto_registrations"):
            self._auto_registrations = []
        return list(self._auto_registrations)

    @property
    def stats(self) -> dict[str, Any]:
        """Cerberus performance stats for daily safety report."""
        auto_regs = self.get_auto_registrations()
        return {
            "checks": self._check_count,
            "denials": self._deny_count,
            "false_positives": self._false_positive_count,
            "denial_rate": (
                self._deny_count / self._check_count
                if self._check_count > 0
                else 0.0
            ),
            "audit_entries": len(self._audit_log),
            "config_hash": self._config_hash[:16],
            "auto_registrations": len(auto_regs),
            "auto_registrations_detail": auto_regs,
        }
