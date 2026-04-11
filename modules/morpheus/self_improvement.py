"""
Self-Improvement Engine — Morpheus × Omen RSI Bridge
=====================================================
Morpheus proposes code improvements to Shadow's own modules.

Pipeline: Analyze → Hypothesize → Implement → Test → Report

SAFETY INVARIANTS:
1. NEVER modifies production files directly
2. ALL changes tested in isolated sandbox copy
3. Full test suite must pass with ZERO regressions
4. Creator approval required before any merge
5. Full diff stored in Grimoire for audit trail
6. Cerberus can veto any proposal

Phase 1: Pure AST/regex static analysis. No LLM calls.
Actual code generation and sandbox testing deferred to Phase 2.
"""

from __future__ import annotations

import ast
import hashlib
import logging
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger("shadow.morpheus.self_improvement")

# Valid change types for proposals
VALID_CHANGE_TYPES = {
    "optimize",
    "refactor",
    "add_feature",
    "fix_pattern",
    "add_test",
}

# Valid proposal statuses
VALID_STATUSES = {
    "proposed",
    "testing",
    "passed",
    "failed",
    "approved",
    "rejected",
}

# Regex for TODO/FIXME/HACK comments
_TODO_PATTERN = re.compile(
    r"#\s*(TODO|FIXME|HACK)\b[:\s]*(.*)", re.IGNORECASE
)


class SelfImprovementEngine:
    """Morpheus proposes code improvements to Shadow's own modules.

    Pipeline: Analyze → Hypothesize → Implement → Test → Report

    SAFETY INVARIANTS:
    1. NEVER modifies production files directly
    2. ALL changes tested in isolated sandbox copy
    3. Full test suite must pass with ZERO regressions
    4. Creator approval required before any merge
    5. Full diff stored in Grimoire for audit trail
    6. Cerberus can veto any proposal
    """

    def __init__(self, db_path: Path | str) -> None:
        """Initialize the self-improvement engine.

        Args:
            db_path: Path to SQLite database. The improvement_proposals
                     table is created alongside Morpheus's existing tables.
        """
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        """Create the improvement_proposals table."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS improvement_proposals (
                id TEXT PRIMARY KEY,
                target_module TEXT NOT NULL,
                target_file TEXT NOT NULL,
                hypothesis TEXT NOT NULL,
                change_type TEXT NOT NULL,
                proposed_diff TEXT NOT NULL,
                test_result TEXT,
                tests_before INTEGER,
                tests_after INTEGER,
                tests_passing_before INTEGER,
                tests_passing_after INTEGER,
                performance_before TEXT,
                performance_after TEXT,
                status TEXT DEFAULT 'proposed',
                rejection_reason TEXT,
                template_id TEXT,
                created_at REAL,
                tested_at REAL,
                resolved_at REAL
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_proposals_status
            ON improvement_proposals(status)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_proposals_module
            ON improvement_proposals(target_module)
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Analysis — pure AST/regex, NO LLM calls, read-only
    # ------------------------------------------------------------------

    def analyze_module(self, module_name: str, source_path: str) -> dict:
        """Static analysis of a module file.

        Returns line count, function count, detected issues (TODO/FIXME/HACK,
        bare excepts, long functions, missing docstrings, duplicate blocks).

        This method is strictly read-only — it never modifies the source file.

        Args:
            module_name: Shadow module codename (for labeling).
            source_path: Path to the .py file to analyze.

        Returns:
            Dict with analysis results keyed by issue category.
        """
        path = Path(source_path)
        if not path.exists():
            return {
                "module": module_name,
                "file": str(source_path),
                "error": f"File not found: {source_path}",
            }

        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()

        result: dict[str, Any] = {
            "module": module_name,
            "file": str(source_path),
            "line_count": len(lines),
            "function_count": 0,
            "todo_comments": [],
            "bare_excepts": [],
            "long_functions": [],
            "missing_docstrings": [],
            "duplicate_blocks": [],
        }

        # --- Regex-based checks (work even if AST parse fails) ---
        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()

            # TODO / FIXME / HACK
            match = _TODO_PATTERN.search(stripped)
            if match:
                result["todo_comments"].append({
                    "line": lineno,
                    "type": match.group(1).upper(),
                    "text": match.group(2).strip(),
                })

            # Bare except
            if stripped == "except:" or stripped.startswith("except:"):
                result["bare_excepts"].append({
                    "line": lineno,
                    "text": stripped,
                })
            elif (
                stripped.startswith("except Exception:")
                or stripped == "except Exception:"
            ):
                result["bare_excepts"].append({
                    "line": lineno,
                    "text": stripped,
                })

        # --- AST-based checks ---
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            result["parse_error"] = str(e)
            return result

        functions = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(node)
            elif isinstance(node, ast.ClassDef):
                # Check class docstring
                if not (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                ):
                    result["missing_docstrings"].append({
                        "name": node.name,
                        "line": node.lineno,
                        "type": "class",
                    })

        result["function_count"] = len(functions)

        for func in functions:
            # Function length
            end_line = getattr(func, "end_lineno", None)
            if end_line is None:
                # Fallback: estimate from body
                end_line = func.lineno + len(func.body)
            length = end_line - func.lineno + 1
            if length > 50:
                result["long_functions"].append({
                    "name": func.name,
                    "start_line": func.lineno,
                    "end_line": end_line,
                    "length": length,
                })

            # Missing docstrings
            has_docstring = (
                func.body
                and isinstance(func.body[0], ast.Expr)
                and isinstance(func.body[0].value, ast.Constant)
            )
            if not has_docstring:
                result["missing_docstrings"].append({
                    "name": func.name,
                    "line": func.lineno,
                    "type": "function",
                })

        # --- Duplicate block detection (simple hash-based) ---
        block_size = 3
        if len(lines) >= block_size:
            block_hashes: dict[str, list[int]] = {}
            for i in range(len(lines) - block_size + 1):
                block = "\n".join(
                    line.strip() for line in lines[i : i + block_size]
                )
                # Skip empty/whitespace-only blocks
                if not block.strip():
                    continue
                h = hashlib.md5(block.encode()).hexdigest()
                if h not in block_hashes:
                    block_hashes[h] = []
                block_hashes[h].append(i + 1)  # 1-indexed

            for h, positions in block_hashes.items():
                if len(positions) >= 2:
                    result["duplicate_blocks"].append({
                        "lines": positions,
                        "block_size": block_size,
                    })

        return result

    # ------------------------------------------------------------------
    # Proposal generation — rule-based, NO LLM calls
    # ------------------------------------------------------------------

    def generate_proposals(
        self,
        module_name: str,
        source_path: str,
        max_proposals: int = 3,
    ) -> list[dict]:
        """Generate improvement proposals based on static analysis.

        Rule-based in Phase 1 — maps detected issues to typed proposals.
        Consults rejection patterns to suppress frequently-rejected types.

        Args:
            module_name: Shadow module codename.
            source_path: Path to the .py file.
            max_proposals: Maximum proposals to generate.

        Returns:
            List of proposal dicts persisted to the database.
        """
        analysis = self.analyze_module(module_name, source_path)
        if "error" in analysis or "parse_error" in analysis:
            return []

        # Get rejection patterns to suppress
        rejection_patterns = self.get_rejection_patterns()
        suppressed = {
            (p["change_type"], p["target_module"]) for p in rejection_patterns
        }

        proposals: list[dict] = []

        # Long functions → refactor
        if ("refactor", module_name) not in suppressed:
            for func in analysis.get("long_functions", []):
                if len(proposals) >= max_proposals:
                    break
                proposals.append(self._make_proposal(
                    module_name=module_name,
                    source_path=source_path,
                    hypothesis=(
                        f"Extracting lines {func['start_line']}-{func['end_line']} "
                        f"of {func['name']}() into helper functions improves "
                        f"readability and testability"
                    ),
                    change_type="refactor",
                ))

        # Bare excepts → fix_pattern
        if ("fix_pattern", module_name) not in suppressed:
            for exc in analysis.get("bare_excepts", []):
                if len(proposals) >= max_proposals:
                    break
                proposals.append(self._make_proposal(
                    module_name=module_name,
                    source_path=source_path,
                    hypothesis=(
                        f"Replacing bare except at line {exc['line']} with "
                        f"specific exception types improves error handling "
                        f"and debugging"
                    ),
                    change_type="fix_pattern",
                ))

        # Missing docstrings → refactor
        if ("refactor", module_name) not in suppressed:
            for item in analysis.get("missing_docstrings", []):
                if len(proposals) >= max_proposals:
                    break
                proposals.append(self._make_proposal(
                    module_name=module_name,
                    source_path=source_path,
                    hypothesis=(
                        f"Adding docstring to {item['type']} {item['name']} "
                        f"at line {item['line']} improves maintainability"
                    ),
                    change_type="refactor",
                ))

        # TODO/FIXME/HACK → add_feature
        if ("add_feature", module_name) not in suppressed:
            for todo in analysis.get("todo_comments", []):
                if len(proposals) >= max_proposals:
                    break
                proposals.append(self._make_proposal(
                    module_name=module_name,
                    source_path=source_path,
                    hypothesis=(
                        f"Implementing {todo['type']} at line {todo['line']}: "
                        f"{todo['text'] or 'unspecified task'}"
                    ),
                    change_type="add_feature",
                ))

        # Duplicate blocks → refactor
        if ("refactor", module_name) not in suppressed:
            for dup in analysis.get("duplicate_blocks", []):
                if len(proposals) >= max_proposals:
                    break
                proposals.append(self._make_proposal(
                    module_name=module_name,
                    source_path=source_path,
                    hypothesis=(
                        f"Extracting duplicate code block (found at lines "
                        f"{', '.join(str(l) for l in dup['lines'])}) into a "
                        f"shared helper reduces duplication"
                    ),
                    change_type="refactor",
                ))

        # Persist all proposals
        for proposal in proposals:
            self._persist_proposal(proposal)

        return proposals

    def _make_proposal(
        self,
        module_name: str,
        source_path: str,
        hypothesis: str,
        change_type: str,
    ) -> dict:
        """Create a proposal dict (not yet persisted)."""
        return {
            "id": str(uuid.uuid4()),
            "target_module": module_name,
            "target_file": str(source_path),
            "hypothesis": hypothesis,
            "change_type": change_type,
            "proposed_diff": "",  # Phase 2: LLM generates actual diff
            "test_result": None,
            "tests_before": None,
            "tests_after": None,
            "tests_passing_before": None,
            "tests_passing_after": None,
            "performance_before": None,
            "performance_after": None,
            "status": "proposed",
            "rejection_reason": None,
            "template_id": None,
            "created_at": time.time(),
            "tested_at": None,
            "resolved_at": None,
        }

    def _persist_proposal(self, proposal: dict) -> None:
        """Insert a proposal into the database."""
        self._conn.execute(
            """
            INSERT INTO improvement_proposals (
                id, target_module, target_file, hypothesis, change_type,
                proposed_diff, test_result, tests_before, tests_after,
                tests_passing_before, tests_passing_after,
                performance_before, performance_after,
                status, rejection_reason, template_id,
                created_at, tested_at, resolved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                proposal["id"],
                proposal["target_module"],
                proposal["target_file"],
                proposal["hypothesis"],
                proposal["change_type"],
                proposal["proposed_diff"],
                proposal["test_result"],
                proposal["tests_before"],
                proposal["tests_after"],
                proposal["tests_passing_before"],
                proposal["tests_passing_after"],
                proposal["performance_before"],
                proposal["performance_after"],
                proposal["status"],
                proposal["rejection_reason"],
                proposal["template_id"],
                proposal["created_at"],
                proposal["tested_at"],
                proposal["resolved_at"],
            ),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Testing — Phase 1 stub
    # ------------------------------------------------------------------

    def test_proposal(self, proposal_id: str, sandbox_path: str) -> dict:
        """Test a proposal in an isolated sandbox.

        Phase 1 STUB: Returns pending status. In Phase 2, this will:
        1. Copy target file to sandbox
        2. Apply proposed diff
        3. Run full test suite
        4. Compare before/after results
        5. Return pass/fail with full details

        Args:
            proposal_id: UUID of the proposal to test.
            sandbox_path: Path to isolated sandbox directory.

        Returns:
            Dict with test status and message.
        """
        row = self._conn.execute(
            "SELECT * FROM improvement_proposals WHERE id = ?",
            (proposal_id,),
        ).fetchone()

        if not row:
            return {"status": "error", "message": f"Proposal not found: {proposal_id}"}

        # Update status to testing
        self._conn.execute(
            "UPDATE improvement_proposals SET status = 'testing', tested_at = ? WHERE id = ?",
            (time.time(), proposal_id),
        )
        self._conn.commit()

        return {
            "status": "pending",
            "message": "LLM code generation required for diff — Phase 2",
            "proposal_id": proposal_id,
        }

    # ------------------------------------------------------------------
    # Proposal management
    # ------------------------------------------------------------------

    def get_proposals(
        self,
        status: str | None = None,
        module: str | None = None,
    ) -> list[dict]:
        """List proposals with optional filters.

        Args:
            status: Filter by proposal status.
            module: Filter by target module name.

        Returns:
            List of proposal dicts ordered by created_at descending.
        """
        query = "SELECT * FROM improvement_proposals WHERE 1=1"
        params: list[Any] = []

        if status is not None:
            query += " AND status = ?"
            params.append(status)
        if module is not None:
            query += " AND target_module = ?"
            params.append(module)

        query += " ORDER BY created_at DESC"

        rows = self._conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def approve_proposal(self, proposal_id: str) -> dict:
        """Mark a proposal as approved (creator-only action).

        In Phase 2, this triggers actual file modification + git commit.

        Args:
            proposal_id: UUID of the proposal to approve.

        Returns:
            Dict with result status.
        """
        row = self._conn.execute(
            "SELECT * FROM improvement_proposals WHERE id = ?",
            (proposal_id,),
        ).fetchone()

        if not row:
            return {"success": False, "error": f"Proposal not found: {proposal_id}"}

        current_status = row["status"]
        if current_status == "rejected":
            return {
                "success": False,
                "error": "Cannot approve a rejected proposal",
            }
        if current_status == "approved":
            return {
                "success": False,
                "error": "Proposal is already approved",
            }

        self._conn.execute(
            "UPDATE improvement_proposals SET status = 'approved', resolved_at = ? WHERE id = ?",
            (time.time(), proposal_id),
        )
        self._conn.commit()

        return {"success": True, "proposal_id": proposal_id, "status": "approved"}

    def reject_proposal(self, proposal_id: str, reason: str) -> dict:
        """Mark a proposal as rejected with reason.

        The reason is stored for future learning — Morpheus should
        avoid similar proposals in the future.

        Args:
            proposal_id: UUID of the proposal to reject.
            reason: Why the proposal was rejected.

        Returns:
            Dict with result status.
        """
        row = self._conn.execute(
            "SELECT * FROM improvement_proposals WHERE id = ?",
            (proposal_id,),
        ).fetchone()

        if not row:
            return {"success": False, "error": f"Proposal not found: {proposal_id}"}

        current_status = row["status"]
        if current_status == "approved":
            return {
                "success": False,
                "error": "Cannot reject an approved proposal",
            }
        if current_status == "rejected":
            return {
                "success": False,
                "error": "Proposal is already rejected",
            }

        self._conn.execute(
            """UPDATE improvement_proposals
               SET status = 'rejected', rejection_reason = ?, resolved_at = ?
               WHERE id = ?""",
            (reason, time.time(), proposal_id),
        )
        self._conn.commit()

        return {"success": True, "proposal_id": proposal_id, "status": "rejected"}

    # ------------------------------------------------------------------
    # Statistics and learning
    # ------------------------------------------------------------------

    def get_improvement_stats(self) -> dict:
        """Summary statistics for the improvement pipeline.

        Returns:
            Dict with total proposals, counts by status, counts by
            change_type, approval rate, and most-improved modules.
        """
        rows = self._conn.execute(
            "SELECT * FROM improvement_proposals"
        ).fetchall()

        if not rows:
            return {
                "total": 0,
                "by_status": {},
                "by_change_type": {},
                "approval_rate": 0.0,
                "most_improved_modules": [],
            }

        by_status: dict[str, int] = {}
        by_change_type: dict[str, int] = {}
        by_module: dict[str, int] = {}
        approved_count = 0
        resolved_count = 0

        for row in rows:
            status = row["status"]
            by_status[status] = by_status.get(status, 0) + 1

            ctype = row["change_type"]
            by_change_type[ctype] = by_change_type.get(ctype, 0) + 1

            if status == "approved":
                approved_count += 1
                module = row["target_module"]
                by_module[module] = by_module.get(module, 0) + 1

            if status in ("approved", "rejected"):
                resolved_count += 1

        approval_rate = (
            approved_count / resolved_count if resolved_count > 0 else 0.0
        )

        most_improved = sorted(
            by_module.items(), key=lambda x: x[1], reverse=True
        )

        return {
            "total": len(rows),
            "by_status": by_status,
            "by_change_type": by_change_type,
            "approval_rate": approval_rate,
            "most_improved_modules": [
                {"module": m, "approved_count": c} for m, c in most_improved
            ],
        }

    def get_rejection_patterns(self) -> list[dict]:
        """Analyze rejected proposals to find patterns to avoid.

        Groups rejected proposals by (change_type, target_module) and
        returns patterns where the same combination was rejected 2+ times.
        This feeds back into generate_proposals to suppress proposal
        types that get consistently rejected.

        Returns:
            List of pattern dicts with change_type, target_module, and count.
        """
        rows = self._conn.execute(
            """SELECT change_type, target_module, COUNT(*) as cnt
               FROM improvement_proposals
               WHERE status = 'rejected'
               GROUP BY change_type, target_module
               HAVING cnt >= 2
               ORDER BY cnt DESC"""
        ).fetchall()

        return [
            {
                "change_type": row["change_type"],
                "target_module": row["target_module"],
                "count": row["cnt"],
            }
            for row in rows
        ]

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
