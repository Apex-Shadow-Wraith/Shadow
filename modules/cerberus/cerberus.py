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

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from modules.base import BaseModule, ModuleStatus, ToolResult

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


class Cerberus(BaseModule):
    """Shadow's safety gate.

    Architecture: Cerberus runs as a rule engine with LLM judgment
    for ambiguous cases. Phase 1 is rule-only. The intelligence is
    in the rules, classification logic, and hard limits.

    From the architecture doc:
    - Clear-cut cases (90%): Rule matching. Milliseconds.
    - Ambiguous cases (10%): LLM ethical reasoning (Phase 2+).
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
                )
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
        ]

    # --- Core Safety Logic ---

    def _safety_check(
        self,
        action_tool: str,
        action_params: dict[str, Any],
        requesting_module: str,
    ) -> SafetyCheckResult:
        """The safety gate. Step 4 of the decision loop.

        Every plan passes through here before execution.
        Phase 1: pure rule matching against config.
        """
        self._check_count += 1

        # 1. Check hard limits
        hard_limit_result = self._check_hard_limits(action_tool, action_params)
        if hard_limit_result.verdict == SafetyVerdict.DENY:
            self._deny_count += 1
            self._write_audit_entry({
                "type": "denial",
                "tool": action_tool,
                "reason": hard_limit_result.reason,
                "rule": hard_limit_result.rule_matched,
                "module": requesting_module,
            })
            return hard_limit_result

        # 2. Check if tool requires approval
        approval_tools = self._limits.get("approval_required_tools", [])
        if action_tool in approval_tools:
            self._write_audit_entry({
                "type": "approval_required",
                "tool": action_tool,
                "module": requesting_module,
            })
            return SafetyCheckResult(
                verdict=SafetyVerdict.APPROVAL_REQUIRED,
                tool_name=action_tool,
                reason=f"Tool '{action_tool}' requires user approval before execution",
                rule_matched="approval_required_tools",
            )

        # 3. Check permission tier
        tier_result = self._check_permission_tier(action_tool, action_params)
        if tier_result.verdict != SafetyVerdict.ALLOW:
            return tier_result

        # 4. All checks passed
        return SafetyCheckResult(
            verdict=SafetyVerdict.ALLOW,
            tool_name=action_tool,
            reason="All safety checks passed",
        )

    def _check_hard_limits(
        self, tool_name: str, params: dict[str, Any]
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
        if tool_name in ("bash_execute", "code_execute"):
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
        """Check tool against permission tier system."""
        # Phase 1: Simple — autonomous tools proceed, everything else needs approval
        autonomous = self._limits.get("autonomous_tools", [])

        if tool_name in autonomous:
            return SafetyCheckResult(
                verdict=SafetyVerdict.ALLOW,
                tool_name=tool_name,
                reason=f"Tool '{tool_name}' is Tier 1 autonomous",
            )

        # Not in autonomous list and not in approval list = unknown tool
        # Phase 1: default to approval required for unknown tools
        return SafetyCheckResult(
            verdict=SafetyVerdict.APPROVAL_REQUIRED,
            tool_name=tool_name,
            reason=f"Tool '{tool_name}' not in autonomous list — approval required",
            rule_matched="default_approval",
        )

    # --- Hook System (Session 12) ---

    def _pre_tool_hook(
        self, tool_name: str, tool_params: dict[str, Any]
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

        return SafetyCheckResult(
            verdict=SafetyVerdict.ALLOW,
            tool_name=tool_name,
            reason="Pre-hook: all checks passed",
        )

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

    @property
    def stats(self) -> dict[str, Any]:
        """Cerberus performance stats for daily safety report."""
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
        }
