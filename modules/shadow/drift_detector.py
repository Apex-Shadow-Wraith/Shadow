"""
Drift Detector — Module Specialization Drift Detection
========================================================
Audits each module's actual behavior against its designed role.
Detects when modules handle tasks outside their specialty.

HOW IT WORKS:
    1. Every routing decision is logged via log_routing()
    2. detect_violations() checks in real-time if routing makes sense
    3. analyze_drift() examines logs over a time window for patterns
    4. generate_correction_report() produces plain-English recommendations

DESIGN PRINCIPLES:
    - Observation only — NEVER blocks routing decisions
    - Can inform prompt adjustments (Item 11) but doesn't auto-modify
    - All data in SQLite for historical analysis
    - Drift score: 0.0 = perfect specialization, 1.0 = total drift

Author: Patrick (with Claude Opus 4.6)
Project: Shadow
Module: Shadow / Drift Detector (Item 54)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger("shadow.drift_detector")

# Baseline role definitions for all 13 modules
MODULE_ROLES = {
    "shadow": {"role": "orchestrator", "should_handle": ["routing", "coordination", "meta"]},
    "wraith": {"role": "fast_daily", "should_handle": ["reminders", "quick_lookup", "simple_tasks"]},
    "grimoire": {"role": "memory", "should_handle": ["storage", "retrieval", "knowledge"]},
    "reaper": {"role": "research", "should_handle": ["web_search", "scraping", "data_gathering"]},
    "cerberus": {
        "role": "ethics_safety_security",
        # Absorbed Sentinel's security surface in Phase A; "should_handle"
        # union covers both ethics/safety and the inherited firewall /
        # threats / monitoring vocabulary.
        "should_handle": [
            "ethics", "safety", "permissions",
            "firewall", "threats", "monitoring",
        ],
    },
    "apex": {"role": "cloud_fallback", "should_handle": ["escalation", "teaching"]},
    "harbinger": {"role": "briefings", "should_handle": ["alerts", "summaries", "notifications"]},
    # Omen absorbed Cipher's math/logic surface in Phase A.
    "omen": {
        "role": "code_and_math",
        "should_handle": [
            "code", "programming", "debugging", "compilation",
            "math", "calculation", "logic", "proof",
        ],
    },
    "nova": {"role": "content", "should_handle": ["writing", "creative", "content_creation"]},
    "morpheus": {"role": "creative_discovery", "should_handle": ["exploration", "dreaming", "research"]},
}

# A module handling more than this many distinct task types is becoming a generalist
GENERALIST_THRESHOLD = 5


class DriftDetector:
    """Detects when modules drift from their designed specialization."""

    def __init__(self, db_path: str = "data/drift_detection.db", config: dict = None):
        """Initialize drift detector with SQLite storage.

        Args:
            db_path: Path to SQLite database for routing logs.
            config: Optional configuration overrides.
        """
        self.db_path = Path(db_path)
        self.config = config or {}
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        logger.info("DriftDetector initialized — db=%s", self.db_path)

    def _init_db(self) -> None:
        """Create tables for routing logs and drift analysis."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS routing_logs (
                    log_id TEXT PRIMARY KEY,
                    task_type TEXT NOT NULL,
                    routed_to TEXT NOT NULL,
                    task_description TEXT DEFAULT '',
                    is_violation INTEGER DEFAULT 0,
                    violation_reason TEXT DEFAULT '',
                    logged_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_routing_logged_at
                ON routing_logs(logged_at)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_routing_routed_to
                ON routing_logs(routed_to)
            """)
            conn.commit()

    def log_routing(self, task_type: str, routed_to: str, task_description: str = "") -> str:
        """Record a routing decision.

        Args:
            task_type: Category of task (e.g., 'math', 'code', 'ethics').
            routed_to: Module name that received the task.
            task_description: Optional description of the task.

        Returns:
            The log_id for this entry.
        """
        log_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        # Check for violation at log time
        violation = self.detect_violations(task_type, routed_to)
        is_violation = 1 if violation else 0
        violation_reason = violation.get("reason", "") if violation else ""

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """INSERT INTO routing_logs
                   (log_id, task_type, routed_to, task_description,
                    is_violation, violation_reason, logged_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (log_id, task_type, routed_to, task_description,
                 is_violation, violation_reason, now),
            )
            conn.commit()

        if is_violation:
            logger.warning(
                "Routing drift: task_type=%s routed_to=%s — %s",
                task_type, routed_to, violation_reason,
            )
        else:
            logger.debug("Routing logged: task_type=%s → %s", task_type, routed_to)

        return log_id

    def detect_violations(self, task_type: str, routed_to: str) -> dict | None:
        """Real-time check: does this routing make sense?

        Args:
            task_type: Category of task being routed.
            routed_to: Module receiving the task.

        Returns:
            Violation details dict if routing is suspect, None if correct.
        """
        # Unknown module — can't flag what we don't know
        if routed_to not in MODULE_ROLES:
            return None

        role_info = MODULE_ROLES[routed_to]
        if task_type not in role_info["should_handle"]:
            # Find which module should handle this
            correct_modules = [
                mod for mod, info in MODULE_ROLES.items()
                if task_type in info["should_handle"]
            ]
            return {
                "task_type": task_type,
                "routed_to": routed_to,
                "designed_role": role_info["role"],
                "expected_tasks": role_info["should_handle"],
                "suggested_modules": correct_modules,
                "reason": (
                    f"'{task_type}' is not in {routed_to}'s designed role "
                    f"({role_info['role']}). "
                    + (f"Consider: {', '.join(correct_modules)}" if correct_modules
                       else "No module has this as a primary task type")
                ),
            }

        return None

    def analyze_drift(self, days: int = 7) -> dict:
        """Analyze routing logs for boundary violations and drift patterns.

        Args:
            days: Number of days to look back.

        Returns:
            Dict with violations, generalists, underused modules, examples,
            and drift_score (0.0 = perfect, 1.0 = total drift).
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM routing_logs WHERE logged_at >= ? ORDER BY logged_at",
                (cutoff,),
            ).fetchall()

        if not rows:
            return {
                "violations": [],
                "generalists": [],
                "underused": [],
                "examples": [],
                "drift_score": 0.0,
            }

        total = len(rows)
        violations = []
        module_task_types: dict[str, set[str]] = {}
        module_counts: Counter = Counter()

        for row in rows:
            module = row["routed_to"]
            task_type = row["task_type"]
            module_counts[module] += 1
            module_task_types.setdefault(module, set()).add(task_type)

            if row["is_violation"]:
                violations.append({
                    "log_id": row["log_id"],
                    "task_type": task_type,
                    "routed_to": module,
                    "reason": row["violation_reason"],
                    "logged_at": row["logged_at"],
                })

        # Generalist detection
        generalists = [
            {"module": mod, "task_type_count": len(types), "task_types": sorted(types)}
            for mod, types in module_task_types.items()
            if len(types) >= GENERALIST_THRESHOLD
        ]

        # Underused modules — known modules that received no tasks or very few
        avg_count = total / max(len(module_counts), 1)
        underused_threshold = avg_count * 0.1  # Less than 10% of average
        all_modules = set(MODULE_ROLES.keys())
        active_modules = set(module_counts.keys())
        underused = [
            {"module": mod, "task_count": module_counts.get(mod, 0)}
            for mod in all_modules
            if module_counts.get(mod, 0) <= underused_threshold
        ]

        # Pick up to 5 example violations
        examples = violations[:5]

        # Drift score: ratio of violations to total routings
        drift_score = len(violations) / total if total > 0 else 0.0
        drift_score = min(drift_score, 1.0)

        return {
            "violations": violations,
            "generalists": generalists,
            "underused": underused,
            "examples": examples,
            "drift_score": round(drift_score, 4),
        }

    def get_module_profile(self, module: str, days: int = 7) -> dict:
        """Profile a module's actual behavior vs its designed role.

        Args:
            module: Module codename.
            days: Number of days to look back.

        Returns:
            Dict with module info, actual task types, on-role percentage,
            and off-role tasks.
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        role_info = MODULE_ROLES.get(module, {"role": "unknown", "should_handle": []})

        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT task_type FROM routing_logs WHERE routed_to = ? AND logged_at >= ?",
                (module, cutoff),
            ).fetchall()

        if not rows:
            return {
                "module": module,
                "designed_role": role_info["role"],
                "actual_task_types": [],
                "on_role_pct": 1.0,
                "off_role_tasks": [],
            }

        task_types = [r[0] for r in rows]
        total = len(task_types)
        on_role = sum(1 for t in task_types if t in role_info["should_handle"])
        off_role = [t for t in set(task_types) if t not in role_info["should_handle"]]

        return {
            "module": module,
            "designed_role": role_info["role"],
            "actual_task_types": sorted(set(task_types)),
            "on_role_pct": round(on_role / total, 4) if total > 0 else 1.0,
            "off_role_tasks": sorted(off_role),
        }

    def generate_correction_report(self) -> str:
        """Generate a plain-English report of drift patterns.

        Returns:
            Human-readable report for Patrick / Harbinger briefing.
        """
        analysis = self.analyze_drift(days=7)
        lines = ["=== Module Specialization Drift Report ===", ""]

        # Overall score
        score = analysis["drift_score"]
        if score == 0.0:
            lines.append("Drift Score: 0.0 — Perfect specialization. All routings on-role.")
        elif score < 0.1:
            lines.append(f"Drift Score: {score} — Minimal drift. A few off-role routings.")
        elif score < 0.3:
            lines.append(f"Drift Score: {score} — Moderate drift. Router prompts may need tuning.")
        else:
            lines.append(f"Drift Score: {score} — Significant drift. Review routing logic.")
        lines.append("")

        # Violations summary
        violations = analysis["violations"]
        if violations:
            lines.append(f"Boundary Violations: {len(violations)}")
            # Group violations by module
            by_module: dict[str, list[str]] = {}
            for v in violations:
                by_module.setdefault(v["routed_to"], []).append(v["task_type"])
            for mod, tasks in sorted(by_module.items()):
                task_counts = Counter(tasks)
                details = ", ".join(f"{t} ({c}x)" for t, c in task_counts.most_common())
                role = MODULE_ROLES.get(mod, {}).get("role", "unknown")
                lines.append(f"  - {mod.capitalize()} ({role}) handling: {details}")
                # Suggest correct module
                for task_type in task_counts:
                    correct = [
                        m for m, info in MODULE_ROLES.items()
                        if task_type in info["should_handle"]
                    ]
                    if correct:
                        lines.append(
                            f"    → '{task_type}' should route to: "
                            f"{', '.join(c.capitalize() for c in correct)}"
                        )
            lines.append("")

        # Generalists
        if analysis["generalists"]:
            lines.append("Generalist Warning:")
            for g in analysis["generalists"]:
                lines.append(
                    f"  - {g['module'].capitalize()} handling {g['task_type_count']} "
                    f"task types: {', '.join(g['task_types'])}"
                )
            lines.append("")

        # Underused
        if analysis["underused"]:
            lines.append("Underused Modules:")
            for u in analysis["underused"]:
                role = MODULE_ROLES.get(u["module"], {}).get("role", "unknown")
                lines.append(
                    f"  - {u['module'].capitalize()} ({role}): "
                    f"{u['task_count']} tasks"
                )
            lines.append("")

        if not violations and not analysis["generalists"]:
            lines.append("No issues detected. All modules operating within specialization.")

        lines.append("=== End Report ===")
        return "\n".join(lines)

    def get_drift_stats(self) -> dict:
        """Get summary stats for Growth Engine integration.

        Returns:
            Dict with overall_drift_score, violations_this_week, and trend.
        """
        current = self.analyze_drift(days=7)
        previous = self.analyze_drift(days=14)

        current_score = current["drift_score"]
        # Previous period: subtract current violations from 14-day window
        prev_total_violations = len(previous["violations"])
        curr_violations = len(current["violations"])
        prev_only_violations = prev_total_violations - curr_violations

        # Determine trend
        if curr_violations < prev_only_violations:
            trend = "improving"
        elif curr_violations > prev_only_violations:
            trend = "degrading"
        else:
            trend = "stable"

        return {
            "overall_drift_score": current_score,
            "violations_this_week": curr_violations,
            "trend": trend,
        }
