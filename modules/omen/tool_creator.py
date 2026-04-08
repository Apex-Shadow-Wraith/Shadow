"""
Autonomous Tool Creation Pipeline
====================================
Omen identifies repeated code patterns and creates new tools automatically.
New tools wait in staging for Patrick's approval via Telegram.

CRITICAL: New tool installs require user approval. Omen proposes,
Cerberus validates, but the tool waits in staging until Patrick approves.
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("shadow.omen.tool_creator")

# Dangerous operations that should never appear in generated tools
DANGEROUS_OPERATIONS = {
    "os.remove",
    "os.unlink",
    "shutil.rmtree",
    "subprocess.call",
    "subprocess.Popen",
    "eval(",
    "exec(",
    "__import__",
    "os.system",
    "open(.*, 'w')",
}

DANGEROUS_MODULES = {
    "ctypes",
    "socket",
    "http.server",
    "ftplib",
    "smtplib",
    "telnetlib",
}


@dataclass
class ToolCandidate:
    """A tool proposed by the autonomous creation pipeline."""

    candidate_id: str
    name: str
    description: str
    code: str
    tests: str
    docstring: str
    detected_pattern: str
    occurrence_count: int
    risk_classification: str
    sandbox_test_passed: bool
    status: str  # "proposed", "testing", "staged", "approved", "rejected"
    created_at: float
    approved_at: Optional[float] = None
    rejection_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolCandidate:
        """Deserialize from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class ToolCreator:
    """Autonomous tool creation pipeline with approval staging.

    Detects repeated code patterns, generates reusable tools,
    validates through Cerberus and sandbox, then stages for
    Patrick's manual approval.
    """

    def __init__(
        self,
        generate_fn: Callable | None = None,
        grimoire: Any = None,
        cerberus: Any = None,
        sandbox: Any = None,
        notifier: Any = None,
        staging_dir: str = "data/staged_tools",
    ) -> None:
        self._generate_fn = generate_fn
        self._grimoire = grimoire
        self._cerberus = cerberus
        self._sandbox = sandbox
        self._notifier = notifier
        self._staging_dir = Path(staging_dir)
        self._candidates: dict[str, ToolCandidate] = {}

        # Stats tracking
        self._stats = {
            "patterns_detected": 0,
            "tools_proposed": 0,
            "tools_approved": 0,
            "tools_rejected": 0,
        }

    def _ensure_staging_dir(self) -> None:
        """Create staging directory if it doesn't exist."""
        try:
            self._staging_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error("Failed to create staging directory: %s", e)

    def _normalize_code(self, code: str) -> str:
        """Normalize code for pattern comparison.

        Strip variable names and whitespace differences to compare
        structural similarity.
        """
        try:
            tree = ast.parse(code)
            # Walk the AST and collect node types as structural signature
            node_types = []
            for node in ast.walk(tree):
                node_types.append(type(node).__name__)
            return "|".join(sorted(node_types))
        except SyntaxError:
            # Fallback: normalize whitespace and strip comments
            lines = []
            for line in code.strip().splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    lines.append(stripped)
            return "\n".join(lines)

    def _compute_signature(self, code: str) -> str:
        """Compute a structural signature hash for code."""
        normalized = self._normalize_code(code)
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _check_code_safety(self, code: str) -> tuple[bool, list[str]]:
        """Check generated code for dangerous operations.

        Returns (is_safe, list_of_violations).
        """
        violations = []

        for dangerous in DANGEROUS_OPERATIONS:
            if dangerous.rstrip("(") in code:
                violations.append(f"Dangerous operation detected: {dangerous}")

        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in DANGEROUS_MODULES:
                            violations.append(
                                f"Dangerous module import: {alias.name}"
                            )
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module in DANGEROUS_MODULES:
                        violations.append(
                            f"Dangerous module import: {node.module}"
                        )
        except SyntaxError:
            violations.append("Code has syntax errors — cannot verify safety")

        return (len(violations) == 0, violations)

    def detect_pattern(
        self, recent_executions: list[dict], min_occurrences: int = 3
    ) -> list[dict]:
        """Analyze recent code executions for repeated patterns.

        Args:
            recent_executions: List of dicts with at least a 'code' key.
            min_occurrences: Minimum times a pattern must appear.

        Returns:
            List of detected patterns with occurrence counts.
        """
        if not recent_executions:
            return []

        try:
            # Group executions by structural signature
            signature_groups: dict[str, list[dict]] = {}
            for execution in recent_executions:
                code = execution.get("code", "")
                if not code or not code.strip():
                    continue

                sig = self._compute_signature(code)
                if sig not in signature_groups:
                    signature_groups[sig] = []
                signature_groups[sig].append(execution)

            # Filter groups that meet the minimum occurrence threshold
            patterns = []
            for sig, group in signature_groups.items():
                if len(group) >= min_occurrences:
                    self._stats["patterns_detected"] += 1
                    patterns.append(
                        {
                            "pattern": sig,
                            "occurrences": len(group),
                            "example_code": group[0].get("code", ""),
                        }
                    )

            return patterns

        except Exception as e:
            logger.error("Pattern detection failed: %s", e)
            return []

    def propose_tool(self, pattern: dict) -> ToolCandidate:
        """Generate a reusable tool function from a repeated pattern.

        Args:
            pattern: Dict with 'pattern', 'occurrences', 'example_code'.

        Returns:
            ToolCandidate with status 'proposed'.
        """
        try:
            candidate_id = str(uuid.uuid4())[:8]
            example_code = pattern.get("example_code", "")
            occurrences = pattern.get("occurrences", 0)

            # Use generate_fn if available to create tool code
            if self._generate_fn:
                generated = self._generate_fn(example_code)
                tool_name = generated.get("name", f"auto_tool_{candidate_id}")
                tool_code = generated.get("code", example_code)
                tool_tests = generated.get("tests", "")
                tool_docstring = generated.get(
                    "docstring", f"Auto-generated tool from detected pattern"
                )
                tool_description = generated.get(
                    "description",
                    f"Tool created from pattern detected {occurrences} times",
                )
            else:
                # Fallback: wrap example code in a function
                tool_name = f"auto_tool_{candidate_id}"
                tool_code = (
                    f"def {tool_name}(*args, **kwargs):\n"
                    f'    """Auto-generated tool from detected pattern."""\n'
                    f"    # Based on pattern:\n"
                    f"    # {example_code[:200]}\n"
                    f"    pass\n"
                )
                tool_tests = (
                    f"def test_{tool_name}():\n"
                    f"    result = {tool_name}()\n"
                    f"    assert result is None\n"
                )
                tool_docstring = "Auto-generated tool from detected pattern"
                tool_description = (
                    f"Tool created from pattern detected {occurrences} times"
                )

            candidate = ToolCandidate(
                candidate_id=candidate_id,
                name=tool_name,
                description=tool_description,
                code=tool_code,
                tests=tool_tests,
                docstring=tool_docstring,
                detected_pattern=pattern.get("pattern", ""),
                occurrence_count=occurrences,
                risk_classification="unclassified",
                sandbox_test_passed=False,
                status="proposed",
                created_at=time.time(),
            )

            self._candidates[candidate_id] = candidate
            self._stats["tools_proposed"] += 1
            logger.info("Tool proposed: %s (%s)", tool_name, candidate_id)
            return candidate

        except Exception as e:
            logger.error("Tool proposal failed: %s", e)
            raise

    def validate_tool(self, candidate: ToolCandidate) -> ToolCandidate:
        """Validate a proposed tool through Cerberus and sandbox.

        Pipeline:
        1. Cerberus classification (risk level)
        2. Code safety check (dangerous operations)
        3. Sandbox testing (run generated tests)

        Args:
            candidate: ToolCandidate to validate.

        Returns:
            Updated ToolCandidate.
        """
        try:
            candidate.status = "testing"

            # Step 1: Cerberus risk classification
            if self._cerberus:
                try:
                    classification = self._cerberus.classify_risk(candidate.code)
                    candidate.risk_classification = classification
                except Exception as e:
                    logger.warning("Cerberus classification failed: %s", e)
                    candidate.risk_classification = "unclassified"
            else:
                candidate.risk_classification = "unclassified"
                logger.info("No Cerberus available — skipping risk classification")

            # Step 2: Code safety check
            is_safe, violations = self._check_code_safety(candidate.code)
            if not is_safe:
                logger.warning(
                    "Safety violations in %s: %s", candidate.name, violations
                )
                candidate.risk_classification = "approval_required"

            # Step 3: Sandbox testing
            if self._sandbox:
                try:
                    test_result = self._sandbox.run_tests(candidate.tests)
                    candidate.sandbox_test_passed = test_result.get(
                        "passed", False
                    )
                except Exception as e:
                    logger.warning("Sandbox testing failed: %s", e)
                    candidate.sandbox_test_passed = False
            else:
                logger.info(
                    "No sandbox available — skipping test execution, staging with warning"
                )
                candidate.sandbox_test_passed = False

            # Determine final status
            if self._sandbox and not candidate.sandbox_test_passed:
                candidate.status = "proposed"
                logger.info(
                    "Tool %s failed sandbox tests — staying proposed",
                    candidate.name,
                )
            else:
                candidate.status = "staged"

            # Update stored candidate
            self._candidates[candidate.candidate_id] = candidate
            return candidate

        except Exception as e:
            logger.error("Tool validation failed: %s", e)
            candidate.status = "proposed"
            return candidate

    def stage_tool(self, candidate: ToolCandidate) -> str:
        """Write tool to staging directory and notify Patrick.

        Args:
            candidate: Validated ToolCandidate to stage.

        Returns:
            candidate_id for tracking.
        """
        try:
            self._ensure_staging_dir()

            # Write tool code to staging file
            tool_file = self._staging_dir / f"{candidate.name}.py"
            tool_file.write_text(
                f'"""\n{candidate.docstring}\n\n'
                f"Auto-generated by Omen Tool Creator\n"
                f"Pattern detected {candidate.occurrence_count} times\n"
                f"Risk classification: {candidate.risk_classification}\n"
                f'Candidate ID: {candidate.candidate_id}\n"""\n\n'
                f"{candidate.code}\n",
                encoding="utf-8",
            )

            # Write metadata alongside
            meta_file = self._staging_dir / f"{candidate.name}.meta.json"
            meta_file.write_text(
                json.dumps(candidate.to_dict(), indent=2, default=str),
                encoding="utf-8",
            )

            candidate.status = "staged"
            self._candidates[candidate.candidate_id] = candidate

            # Send Telegram notification if notifier available
            if self._notifier:
                try:
                    message = (
                        f"\U0001f527 New tool proposed: {candidate.name}\n"
                        f"Description: {candidate.description}\n"
                        f"Pattern detected {candidate.occurrence_count} times\n"
                        f"Risk: {candidate.risk_classification}\n"
                        f"Sandbox tests: {'passed' if candidate.sandbox_test_passed else 'not run'}\n"
                        f"Approve? Reply 'approve {candidate.candidate_id}'"
                    )
                    self._notifier.send(message)
                except Exception as e:
                    logger.warning("Notification failed: %s", e)
            else:
                logger.info(
                    "No notifier available — tool staged for manual review"
                )

            logger.info(
                "Tool staged: %s (%s)", candidate.name, candidate.candidate_id
            )
            return candidate.candidate_id

        except Exception as e:
            logger.error("Tool staging failed: %s", e)
            raise

    def approve_tool(self, candidate_id: str) -> bool:
        """Approve a staged tool and move to production.

        Args:
            candidate_id: ID of the tool to approve.

        Returns:
            True if approved successfully.
        """
        try:
            candidate = self._candidates.get(candidate_id)
            if not candidate:
                logger.error("Candidate not found: %s", candidate_id)
                return False

            if candidate.status not in ("staged", "proposed"):
                logger.error(
                    "Cannot approve tool in status: %s", candidate.status
                )
                return False

            candidate.status = "approved"
            candidate.approved_at = time.time()

            # Register with Cerberus if available
            if self._cerberus:
                try:
                    self._cerberus.register_tool(
                        candidate.name, candidate.risk_classification
                    )
                except Exception as e:
                    logger.warning("Cerberus registration failed: %s", e)

            # Store in Grimoire if available
            if self._grimoire:
                try:
                    self._grimoire.store(
                        category="created_tool",
                        key=candidate.name,
                        value=candidate.to_dict(),
                    )
                except Exception as e:
                    logger.warning("Grimoire storage failed: %s", e)

            self._candidates[candidate_id] = candidate
            self._stats["tools_approved"] += 1
            logger.info(
                "Tool approved: %s (%s)", candidate.name, candidate_id
            )
            return True

        except Exception as e:
            logger.error("Tool approval failed: %s", e)
            return False

    def reject_tool(self, candidate_id: str, reason: str = "") -> bool:
        """Reject a staged tool with optional reason.

        Tool is kept in staging for reference but marked rejected.

        Args:
            candidate_id: ID of the tool to reject.
            reason: Why the tool was rejected.

        Returns:
            True if rejected successfully.
        """
        try:
            candidate = self._candidates.get(candidate_id)
            if not candidate:
                logger.error("Candidate not found: %s", candidate_id)
                return False

            candidate.status = "rejected"
            candidate.rejection_reason = reason
            self._candidates[candidate_id] = candidate
            self._stats["tools_rejected"] += 1

            logger.info(
                "Tool rejected: %s (%s) — %s",
                candidate.name,
                candidate_id,
                reason or "no reason given",
            )
            return True

        except Exception as e:
            logger.error("Tool rejection failed: %s", e)
            return False

    def get_staged_tools(self) -> list[ToolCandidate]:
        """Return all tools waiting for approval.

        Returns:
            List of ToolCandidates with status 'staged'.
        """
        return [
            c
            for c in self._candidates.values()
            if c.status == "staged"
        ]

    def get_creation_stats(self) -> dict[str, Any]:
        """Return pipeline statistics for Growth Engine / daily briefing.

        Returns:
            Dict with patterns_detected, tools_proposed, tools_approved,
            tools_rejected, and approval_rate.
        """
        total_decided = (
            self._stats["tools_approved"] + self._stats["tools_rejected"]
        )
        approval_rate = (
            self._stats["tools_approved"] / total_decided
            if total_decided > 0
            else 0.0
        )

        return {
            "patterns_detected": self._stats["patterns_detected"],
            "tools_proposed": self._stats["tools_proposed"],
            "tools_approved": self._stats["tools_approved"],
            "tools_rejected": self._stats["tools_rejected"],
            "approval_rate": round(approval_rate, 2),
        }
