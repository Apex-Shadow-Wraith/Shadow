"""
Prompt Evolver — Dynamic System Prompt Evolution
==================================================
Module system prompts evolve based on performance data. Drop mastered
instructions, add new patterns from Grimoire, track all versions.

HOW IT WORKS:
    1. Each module registers its current system prompt
    2. As tasks run, outcomes are recorded with which instructions were referenced
    3. Weekly analysis identifies effective, unused, and harmful instructions
    4. evolve_prompt() generates an optimized prompt version
    5. Rollback is always available as a safety net

DESIGN PRINCIPLES:
    - Evolution is WEEKLY, not per-task (prevents churn)
    - All prompt versions preserved — never delete history
    - Rollback always available
    - Grimoire integration pulls in frequently-needed patterns

Author: Patrick (with Claude Opus 4.6)
Project: Shadow
Module: Shadow / Prompt Evolver (Item 11)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("shadow.prompt_evolver")

# Thresholds for analysis
CONFIDENCE_HIGH_THRESHOLD = 0.7      # Instructions above this are "effective"
CONFIDENCE_LOW_THRESHOLD = 0.4       # Instructions below this are "harmful"
UNUSED_THRESHOLD = 0                 # Zero references = unused
MIN_TASKS_FOR_EVOLUTION = 100        # Minimum tasks before auto-evolution
PERFORMANCE_DECLINE_THRESHOLD = 0.05 # Trigger evolution if performance drops this much


@dataclass
class PromptVersion:
    """A versioned snapshot of a module's system prompt."""
    version_id: str
    module: str
    prompt_text: str
    version_number: int
    parent_version: str
    changes: list[str]
    performance_score: float
    task_count: int
    created_at: float
    status: str  # "active", "testing", "retired", "rolled_back"


class PromptEvolver:
    """Evolves module system prompts based on performance data.

    Tracks which instructions correlate with good outcomes,
    removes unused or harmful ones, and incorporates patterns
    from Grimoire that Shadow keeps needing from memory.
    """

    def __init__(self, grimoire=None, db_path: str = "data/prompt_versions.db") -> None:
        """Initialize prompt evolver with SQLite storage.

        Args:
            grimoire: Optional Grimoire instance for retrieving patterns.
            db_path: Path to SQLite database for version history.
        """
        self._grimoire = grimoire
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.row_factory = sqlite3.Row
        self._create_tables()
        logger.info("PromptEvolver initialized: %s", self._db_path)

    def _create_tables(self) -> None:
        """Create tables for prompt versions and instruction tracking."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS prompt_versions (
                version_id TEXT PRIMARY KEY,
                module TEXT NOT NULL,
                prompt_text TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                parent_version TEXT,
                changes TEXT NOT NULL DEFAULT '[]',
                performance_score REAL NOT NULL DEFAULT 0.0,
                task_count INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'active'
            );

            CREATE INDEX IF NOT EXISTS idx_prompt_versions_module
                ON prompt_versions(module);
            CREATE INDEX IF NOT EXISTS idx_prompt_versions_status
                ON prompt_versions(module, status);

            CREATE TABLE IF NOT EXISTS task_outcomes (
                id TEXT PRIMARY KEY,
                module TEXT NOT NULL,
                task_type TEXT NOT NULL,
                confidence REAL NOT NULL,
                instructions_referenced TEXT NOT NULL DEFAULT '[]',
                version_id TEXT,
                recorded_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_task_outcomes_module
                ON task_outcomes(module);

            CREATE TABLE IF NOT EXISTS instruction_stats (
                module TEXT NOT NULL,
                instruction TEXT NOT NULL,
                times_referenced INTEGER NOT NULL DEFAULT 0,
                total_confidence REAL NOT NULL DEFAULT 0.0,
                avg_confidence REAL NOT NULL DEFAULT 0.0,
                PRIMARY KEY (module, instruction)
            );
        """)
        self._conn.commit()

    def close(self) -> None:
        """Close database connection."""
        self._conn.close()

    # =========================================================================
    # REGISTRATION
    # =========================================================================

    def register_prompt(self, module: str, prompt_text: str) -> str:
        """Register a system prompt for a module.

        Creates version 1 if first registration, otherwise increments version.

        Args:
            module: Module codename (e.g., "wraith", "cerberus").
            prompt_text: The full system prompt text.

        Returns:
            version_id for the registered prompt.
        """
        # Find the latest version for this module
        row = self._conn.execute(
            "SELECT version_id, version_number FROM prompt_versions "
            "WHERE module = ? ORDER BY version_number DESC LIMIT 1",
            (module,)
        ).fetchone()

        if row:
            version_number = row["version_number"] + 1
            parent_version = row["version_id"]
        else:
            version_number = 1
            parent_version = ""

        version_id = str(uuid.uuid4())
        now = datetime.now().timestamp()

        # If this is a new version, retire the old active one
        if parent_version:
            self._conn.execute(
                "UPDATE prompt_versions SET status = 'retired' "
                "WHERE module = ? AND status = 'active'",
                (module,)
            )

        self._conn.execute(
            "INSERT INTO prompt_versions "
            "(version_id, module, prompt_text, version_number, parent_version, "
            "changes, performance_score, task_count, created_at, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (version_id, module, prompt_text, version_number, parent_version,
             json.dumps(["initial registration"] if version_number == 1
                        else ["manual registration"]),
             0.0, 0, now, "active")
        )
        self._conn.commit()

        logger.info("Registered prompt for %s: version %d (id=%s)",
                     module, version_number, version_id)
        return version_id

    # =========================================================================
    # TASK TRACKING
    # =========================================================================

    def record_task_outcome(
        self,
        module: str,
        task_type: str,
        confidence: float,
        instructions_referenced: list[str] | None = None
    ) -> bool:
        """Record a task outcome and which instructions correlated.

        Args:
            module: Module codename.
            task_type: Type of task (e.g., "routing", "ethics_check").
            confidence: Confidence score for the task outcome (0.0–1.0).
            instructions_referenced: Which prompt instructions the model
                appeared to use (keyword matching between prompt and response).

        Returns:
            True if recorded successfully.
        """
        if instructions_referenced is None:
            instructions_referenced = []

        # Get active version for this module
        active = self._conn.execute(
            "SELECT version_id FROM prompt_versions "
            "WHERE module = ? AND status = 'active' LIMIT 1",
            (module,)
        ).fetchone()

        if not active:
            logger.warning("No active prompt version for module %s", module)
            return False

        version_id = active["version_id"]
        outcome_id = str(uuid.uuid4())
        now = datetime.now().timestamp()

        self._conn.execute(
            "INSERT INTO task_outcomes "
            "(id, module, task_type, confidence, instructions_referenced, "
            "version_id, recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (outcome_id, module, task_type, confidence,
             json.dumps(instructions_referenced), version_id, now)
        )

        # Update instruction stats
        for instruction in instructions_referenced:
            existing = self._conn.execute(
                "SELECT times_referenced, total_confidence FROM instruction_stats "
                "WHERE module = ? AND instruction = ?",
                (module, instruction)
            ).fetchone()

            if existing:
                new_count = existing["times_referenced"] + 1
                new_total = existing["total_confidence"] + confidence
                new_avg = new_total / new_count
                self._conn.execute(
                    "UPDATE instruction_stats SET times_referenced = ?, "
                    "total_confidence = ?, avg_confidence = ? "
                    "WHERE module = ? AND instruction = ?",
                    (new_count, new_total, new_avg, module, instruction)
                )
            else:
                self._conn.execute(
                    "INSERT INTO instruction_stats "
                    "(module, instruction, times_referenced, total_confidence, "
                    "avg_confidence) VALUES (?, ?, ?, ?, ?)",
                    (module, instruction, 1, confidence, confidence)
                )

        # Update version performance score
        self._conn.execute(
            "UPDATE prompt_versions SET task_count = task_count + 1, "
            "performance_score = ("
            "  (performance_score * task_count + ?) / (task_count + 1)"
            ") WHERE version_id = ?",
            (confidence, version_id)
        )
        # Fix: the task_count was already incremented above, so recalculate
        # Actually the SQL updates task_count first, then uses the NEW value
        # Let's just recalculate from scratch
        stats = self._conn.execute(
            "SELECT COUNT(*) as cnt, AVG(confidence) as avg_conf "
            "FROM task_outcomes WHERE version_id = ?",
            (version_id,)
        ).fetchone()
        self._conn.execute(
            "UPDATE prompt_versions SET task_count = ?, performance_score = ? "
            "WHERE version_id = ?",
            (stats["cnt"], stats["avg_conf"] or 0.0, version_id)
        )

        self._conn.commit()
        return True

    # =========================================================================
    # ANALYSIS
    # =========================================================================

    def _get_prompt_instructions(self, module: str) -> list[str]:
        """Extract instruction sections from the active prompt.

        Splits prompt on double-newlines to get logical sections.
        """
        active = self._conn.execute(
            "SELECT prompt_text FROM prompt_versions "
            "WHERE module = ? AND status = 'active' LIMIT 1",
            (module,)
        ).fetchone()

        if not active:
            return []

        # Split prompt into instruction blocks (separated by double newlines)
        sections = [s.strip() for s in active["prompt_text"].split("\n\n") if s.strip()]
        return sections

    def _get_grimoire_patterns(self, module: str) -> list[str]:
        """Retrieve frequently-used patterns from Grimoire for this module.

        Returns patterns that are accessed often but not in the current prompt.
        """
        if not self._grimoire:
            return []

        try:
            # Try to search Grimoire for patterns related to this module
            if hasattr(self._grimoire, "search"):
                results = self._grimoire.search(
                    query=f"{module} patterns instructions",
                    limit=10
                )
                if results:
                    return [r.get("content", r.get("text", ""))
                            for r in results if isinstance(r, dict)]
            return []
        except Exception as e:
            logger.warning("Failed to query Grimoire for patterns: %s", e)
            return []

    def analyze_prompt(self, module: str) -> dict:
        """Analyze current prompt performance.

        Args:
            module: Module codename.

        Returns:
            Dict with effective_instructions, unused_instructions,
            harmful_instructions, missing_patterns, and recommendations.
        """
        active = self._conn.execute(
            "SELECT version_id, prompt_text FROM prompt_versions "
            "WHERE module = ? AND status = 'active' LIMIT 1",
            (module,)
        ).fetchone()

        if not active:
            return {
                "error": f"No active prompt for module {module}",
                "effective_instructions": [],
                "unused_instructions": [],
                "harmful_instructions": [],
                "missing_patterns": [],
                "recommendations": []
            }

        instructions = self._get_prompt_instructions(module)
        stats = self._conn.execute(
            "SELECT instruction, times_referenced, avg_confidence "
            "FROM instruction_stats WHERE module = ?",
            (module,)
        ).fetchall()

        # Build a lookup of instruction → stats
        stats_map = {row["instruction"]: dict(row) for row in stats}

        effective = []
        unused = []
        harmful = []

        for instruction in instructions:
            if instruction in stats_map:
                s = stats_map[instruction]
                if s["avg_confidence"] >= CONFIDENCE_HIGH_THRESHOLD:
                    effective.append(instruction)
                elif s["avg_confidence"] < CONFIDENCE_LOW_THRESHOLD:
                    harmful.append(instruction)
                else:
                    effective.append(instruction)  # Keep neutral instructions
            else:
                unused.append(instruction)

        # Get Grimoire patterns not already in the prompt
        grimoire_patterns = self._get_grimoire_patterns(module)
        prompt_text = active["prompt_text"]
        missing_patterns = [p for p in grimoire_patterns if p not in prompt_text]

        recommendations = []
        if unused:
            recommendations.append(
                f"Remove {len(unused)} unused instruction(s) to save tokens"
            )
        if harmful:
            recommendations.append(
                f"Remove {len(harmful)} harmful instruction(s) that correlate "
                f"with low confidence"
            )
        if missing_patterns:
            recommendations.append(
                f"Add {len(missing_patterns)} pattern(s) from Grimoire that "
                f"Shadow frequently references"
            )

        return {
            "effective_instructions": effective,
            "unused_instructions": unused,
            "harmful_instructions": harmful,
            "missing_patterns": missing_patterns,
            "recommendations": recommendations
        }

    # =========================================================================
    # EVOLUTION
    # =========================================================================

    def evolve_prompt(self, module: str) -> PromptVersion | None:
        """Generate an optimized prompt based on analysis.

        1. Keep effective instructions
        2. Remove unused instructions (wasted tokens)
        3. Remove harmful instructions
        4. Add missing patterns from Grimoire

        Args:
            module: Module codename.

        Returns:
            New PromptVersion with status "testing", or None if no changes.
        """
        analysis = self.analyze_prompt(module)

        if "error" in analysis:
            logger.warning("Cannot evolve prompt for %s: %s",
                           module, analysis["error"])
            return None

        # Check if there are any changes to make
        has_removals = (analysis["unused_instructions"] or
                        analysis["harmful_instructions"])
        has_additions = bool(analysis["missing_patterns"])

        if not has_removals and not has_additions:
            logger.info("No changes needed for %s prompt", module)
            return None

        # Build the new prompt from effective instructions + new patterns
        new_sections = list(analysis["effective_instructions"])

        # Add missing patterns from Grimoire
        for pattern in analysis["missing_patterns"]:
            new_sections.append(pattern)

        new_prompt = "\n\n".join(new_sections)

        # Track what changed
        changes = []
        if analysis["unused_instructions"]:
            changes.append(
                f"Removed {len(analysis['unused_instructions'])} unused instruction(s)"
            )
        if analysis["harmful_instructions"]:
            changes.append(
                f"Removed {len(analysis['harmful_instructions'])} harmful instruction(s)"
            )
        if analysis["missing_patterns"]:
            changes.append(
                f"Added {len(analysis['missing_patterns'])} pattern(s) from Grimoire"
            )

        # Get current version info
        current = self._conn.execute(
            "SELECT version_id, version_number FROM prompt_versions "
            "WHERE module = ? AND status = 'active' LIMIT 1",
            (module,)
        ).fetchone()

        version_id = str(uuid.uuid4())
        version_number = current["version_number"] + 1
        parent_version = current["version_id"]
        now = datetime.now().timestamp()

        self._conn.execute(
            "INSERT INTO prompt_versions "
            "(version_id, module, prompt_text, version_number, parent_version, "
            "changes, performance_score, task_count, created_at, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (version_id, module, new_prompt, version_number, parent_version,
             json.dumps(changes), 0.0, 0, now, "testing")
        )
        self._conn.commit()

        version = PromptVersion(
            version_id=version_id,
            module=module,
            prompt_text=new_prompt,
            version_number=version_number,
            parent_version=parent_version,
            changes=changes,
            performance_score=0.0,
            task_count=0,
            created_at=now,
            status="testing"
        )

        logger.info("Evolved prompt for %s: v%d → v%d (%s)",
                     module, version_number - 1, version_number,
                     "; ".join(changes))
        return version

    # =========================================================================
    # VERSION MANAGEMENT
    # =========================================================================

    def activate_version(self, version_id: str) -> bool:
        """Set a prompt version as active for its module.

        Previous active version is retired.

        Args:
            version_id: The version to activate.

        Returns:
            True if activated successfully.
        """
        row = self._conn.execute(
            "SELECT module FROM prompt_versions WHERE version_id = ?",
            (version_id,)
        ).fetchone()

        if not row:
            logger.warning("Version %s not found", version_id)
            return False

        module = row["module"]

        # Retire current active version
        self._conn.execute(
            "UPDATE prompt_versions SET status = 'retired' "
            "WHERE module = ? AND status = 'active'",
            (module,)
        )

        # Activate the specified version
        self._conn.execute(
            "UPDATE prompt_versions SET status = 'active' "
            "WHERE version_id = ?",
            (version_id,)
        )
        self._conn.commit()

        logger.info("Activated version %s for module %s", version_id, module)
        return True

    def rollback(self, module: str) -> PromptVersion | None:
        """Revert to previous version if current is performing worse.

        Sets current → "rolled_back", previous → "active".

        Args:
            module: Module codename.

        Returns:
            Restored PromptVersion, or None if no previous version exists.
        """
        # Get the two most recent versions
        rows = self._conn.execute(
            "SELECT * FROM prompt_versions "
            "WHERE module = ? ORDER BY version_number DESC LIMIT 2",
            (module,)
        ).fetchall()

        if len(rows) < 2:
            logger.warning("No previous version to rollback to for %s", module)
            return None

        current = rows[0]
        previous = rows[1]

        # Roll back current
        self._conn.execute(
            "UPDATE prompt_versions SET status = 'rolled_back' "
            "WHERE version_id = ?",
            (current["version_id"],)
        )

        # Reactivate previous
        self._conn.execute(
            "UPDATE prompt_versions SET status = 'active' "
            "WHERE version_id = ?",
            (previous["version_id"],)
        )
        self._conn.commit()

        restored = PromptVersion(
            version_id=previous["version_id"],
            module=previous["module"],
            prompt_text=previous["prompt_text"],
            version_number=previous["version_number"],
            parent_version=previous["parent_version"],
            changes=json.loads(previous["changes"]),
            performance_score=previous["performance_score"],
            task_count=previous["task_count"],
            created_at=previous["created_at"],
            status="active"
        )

        logger.info("Rolled back %s from v%d to v%d",
                     module, current["version_number"],
                     previous["version_number"])
        return restored

    def compare_versions(self, version_a: str, version_b: str) -> dict:
        """Compare two prompt versions.

        Args:
            version_a: First version ID.
            version_b: Second version ID.

        Returns:
            Dict with scores, which is better, difference, and changes between.
        """
        row_a = self._conn.execute(
            "SELECT * FROM prompt_versions WHERE version_id = ?",
            (version_a,)
        ).fetchone()
        row_b = self._conn.execute(
            "SELECT * FROM prompt_versions WHERE version_id = ?",
            (version_b,)
        ).fetchone()

        if not row_a or not row_b:
            return {"error": "One or both versions not found"}

        score_a = row_a["performance_score"]
        score_b = row_b["performance_score"]
        difference = abs(score_a - score_b)

        if score_a > score_b:
            better = version_a
        elif score_b > score_a:
            better = version_b
        else:
            better = "tied"

        # Compute changes between the two versions
        changes_a = set(row_a["prompt_text"].split("\n\n"))
        changes_b = set(row_b["prompt_text"].split("\n\n"))
        added = changes_b - changes_a
        removed = changes_a - changes_b

        changes_between = []
        if added:
            changes_between.append(f"Added {len(added)} section(s)")
        if removed:
            changes_between.append(f"Removed {len(removed)} section(s)")

        return {
            "version_a_score": score_a,
            "version_b_score": score_b,
            "better": better,
            "difference": difference,
            "changes_between": changes_between
        }

    def get_version_history(self, module: str, limit: int = 10) -> list[PromptVersion]:
        """Return prompt version history for a module.

        Args:
            module: Module codename.
            limit: Max versions to return.

        Returns:
            List of PromptVersion, newest first.
        """
        rows = self._conn.execute(
            "SELECT * FROM prompt_versions "
            "WHERE module = ? ORDER BY version_number DESC LIMIT ?",
            (module, limit)
        ).fetchall()

        return [
            PromptVersion(
                version_id=row["version_id"],
                module=row["module"],
                prompt_text=row["prompt_text"],
                version_number=row["version_number"],
                parent_version=row["parent_version"],
                changes=json.loads(row["changes"]),
                performance_score=row["performance_score"],
                task_count=row["task_count"],
                created_at=row["created_at"],
                status=row["status"]
            )
            for row in rows
        ]

    # =========================================================================
    # SCHEDULING
    # =========================================================================

    def should_evolve(self, module: str) -> bool:
        """Check if a module's prompt should evolve.

        Returns True if:
        - 100+ tasks since last evolution
        - Performance trending down
        - Or manually triggered

        Args:
            module: Module codename.

        Returns:
            True if evolution is recommended.
        """
        active = self._conn.execute(
            "SELECT version_id, task_count, performance_score FROM prompt_versions "
            "WHERE module = ? AND status = 'active' LIMIT 1",
            (module,)
        ).fetchone()

        if not active:
            return False

        # Check task count threshold
        if active["task_count"] >= MIN_TASKS_FOR_EVOLUTION:
            return True

        # Check for performance decline vs previous version
        previous = self._conn.execute(
            "SELECT performance_score, task_count FROM prompt_versions "
            "WHERE module = ? AND version_number < ("
            "  SELECT version_number FROM prompt_versions WHERE version_id = ?"
            ") ORDER BY version_number DESC LIMIT 1",
            (module, active["version_id"])
        ).fetchone()

        if previous and previous["task_count"] > 0 and active["task_count"] > 0:
            decline = previous["performance_score"] - active["performance_score"]
            if decline >= PERFORMANCE_DECLINE_THRESHOLD:
                return True

        return False

    # =========================================================================
    # STATS (for Growth Engine)
    # =========================================================================

    def get_evolution_stats(self) -> dict:
        """Get overall evolution statistics.

        Returns:
            Dict with total_evolutions, avg_improvement_per_evolution,
            rollback_rate, most_evolved_module, most_stable_module.
        """
        # Total evolutions (versions > 1 that aren't initial registrations)
        total = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM prompt_versions "
            "WHERE version_number > 1"
        ).fetchone()["cnt"]

        # Rollback rate
        rollbacks = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM prompt_versions "
            "WHERE status = 'rolled_back'"
        ).fetchone()["cnt"]

        rollback_rate = rollbacks / total if total > 0 else 0.0

        # Average improvement per evolution
        # Compare each version's score to its parent's score
        improvements = self._conn.execute(
            "SELECT pv.performance_score - parent.performance_score as improvement "
            "FROM prompt_versions pv "
            "JOIN prompt_versions parent ON pv.parent_version = parent.version_id "
            "WHERE pv.version_number > 1 AND pv.task_count > 0 "
            "AND parent.task_count > 0"
        ).fetchall()

        if improvements:
            avg_improvement = sum(r["improvement"] for r in improvements) / len(improvements)
        else:
            avg_improvement = 0.0

        # Most evolved module (most versions)
        most_evolved = self._conn.execute(
            "SELECT module, COUNT(*) as cnt FROM prompt_versions "
            "GROUP BY module ORDER BY cnt DESC LIMIT 1"
        ).fetchone()

        # Most stable module (fewest versions, at least 1)
        most_stable = self._conn.execute(
            "SELECT module, COUNT(*) as cnt FROM prompt_versions "
            "GROUP BY module ORDER BY cnt ASC LIMIT 1"
        ).fetchone()

        return {
            "total_evolutions": total,
            "avg_improvement_per_evolution": round(avg_improvement, 4),
            "rollback_rate": round(rollback_rate, 4),
            "most_evolved_module": most_evolved["module"] if most_evolved else None,
            "most_stable_module": most_stable["module"] if most_stable else None
        }
