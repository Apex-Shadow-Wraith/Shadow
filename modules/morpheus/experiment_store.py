"""
ExperimentStore — Failed Experiment Knowledge Base with Retry Triggers
======================================================================
Preserves failed experiments with conditions that would warrant re-testing.
When conditions change, experiments automatically re-enter the queue.

Part of Morpheus (Creative Discovery Pipeline).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger("shadow.morpheus.experiment_store")

VALID_STATUSES = {"failed", "succeeded", "queued_for_retry", "deprioritized"}


@dataclass
class Experiment:
    """A tracked experiment with retry trigger support."""

    id: str
    hypothesis: str
    approach: str
    domain_tags: list[str]
    result: str
    success: bool
    failure_reason: str
    conditions: dict
    retry_triggers: list[str]
    attempt_count: int
    attempt_history: list[dict]
    created_at: float
    last_attempted: float
    status: str
    deprioritized: bool


class ExperimentStore:
    """SQLite-backed store for experiments with retry trigger logic.

    Args:
        grimoire: Optional Grimoire module for cross-referencing knowledge base.
        db_path: Path to SQLite database file.
    """

    def __init__(self, grimoire=None, db_path: str = "data/experiments.db") -> None:
        self._grimoire = grimoire
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        """Create the experiments table if it doesn't exist."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS failed_experiments (
                id TEXT PRIMARY KEY,
                hypothesis TEXT NOT NULL,
                approach TEXT NOT NULL,
                domain_tags TEXT NOT NULL,
                result TEXT NOT NULL,
                success INTEGER NOT NULL DEFAULT 0,
                failure_reason TEXT NOT NULL DEFAULT '',
                conditions TEXT NOT NULL DEFAULT '{}',
                retry_triggers TEXT NOT NULL DEFAULT '[]',
                attempt_count INTEGER NOT NULL DEFAULT 1,
                attempt_history TEXT NOT NULL DEFAULT '[]',
                created_at REAL NOT NULL,
                last_attempted REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'failed',
                deprioritized INTEGER NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_exp_status
            ON failed_experiments(status)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_exp_deprioritized
            ON failed_experiments(deprioritized)
        """)
        self._conn.commit()

    def store_experiment(self, experiment: Experiment) -> str:
        """Store an experiment in SQLite.

        If the experiment succeeded, also store findings in Grimoire.

        Args:
            experiment: The Experiment to persist.

        Returns:
            The experiment ID.
        """
        self._conn.execute(
            """INSERT OR REPLACE INTO failed_experiments
               (id, hypothesis, approach, domain_tags, result, success,
                failure_reason, conditions, retry_triggers, attempt_count,
                attempt_history, created_at, last_attempted, status, deprioritized)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                experiment.id,
                experiment.hypothesis,
                experiment.approach,
                json.dumps(experiment.domain_tags),
                experiment.result,
                1 if experiment.success else 0,
                experiment.failure_reason,
                json.dumps(experiment.conditions),
                json.dumps(experiment.retry_triggers),
                experiment.attempt_count,
                json.dumps(experiment.attempt_history),
                experiment.created_at,
                experiment.last_attempted,
                experiment.status,
                1 if experiment.deprioritized else 0,
            ),
        )
        self._conn.commit()

        if experiment.success:
            self._store_in_grimoire(experiment)

        return experiment.id

    def store_failure(
        self,
        hypothesis: str,
        approach: str,
        domain_tags: list[str],
        failure_reason: str,
        conditions: dict,
        retry_triggers: list[str],
    ) -> str:
        """Convenience method to store a failed experiment.

        Args:
            hypothesis: What was being tested.
            approach: How it was tested.
            domain_tags: Domain categories (e.g. ["cuda", "optimization"]).
            failure_reason: Why it failed.
            conditions: Conditions at time of experiment.
            retry_triggers: Conditions that warrant re-testing.

        Returns:
            The experiment ID.
        """
        now = time.time()
        exp_id = str(uuid.uuid4())
        experiment = Experiment(
            id=exp_id,
            hypothesis=hypothesis,
            approach=approach,
            domain_tags=domain_tags,
            result="",
            success=False,
            failure_reason=failure_reason,
            conditions=conditions,
            retry_triggers=retry_triggers,
            attempt_count=1,
            attempt_history=[{
                "attempt": 1,
                "date": now,
                "conditions": conditions,
                "result": failure_reason,
            }],
            created_at=now,
            last_attempted=now,
            status="failed",
            deprioritized=False,
        )
        return self.store_experiment(experiment)

    def check_retry_triggers(self, current_conditions: dict) -> list[Experiment]:
        """Scan failed experiments and return those whose retry triggers are met.

        Deprioritized experiments are excluded.

        Trigger types:
            - "new_grimoire_knowledge:{domain}" — matches when domain is in
              current_conditions["new_knowledge_domains"]
            - "model_changed" — matches when current_conditions contains "model"
              different from experiment's conditions
            - "embedding_model_changed" — matches when current_conditions contains
              "embedding_model" different from experiment's conditions
            - "tool_added:{tool_name}" — matches when current_conditions contains
              "available_tools" list including tool_name
            - "knowledge_depth:{domain}:{min_count}" — matches when
              current_conditions["knowledge_counts"][domain] >= min_count

        Args:
            current_conditions: Dict describing current system state.

        Returns:
            List of experiments whose triggers are now met.
        """
        rows = self._conn.execute(
            "SELECT * FROM failed_experiments WHERE status='failed' AND deprioritized=0"
        ).fetchall()

        triggered = []
        for row in rows:
            experiment = self._row_to_experiment(row)
            if self._any_trigger_met(experiment, current_conditions):
                triggered.append(experiment)

        return triggered

    def queue_for_retry(self, experiment_id: str) -> bool:
        """Queue an experiment for retry.

        Increments attempt_count and adds to attempt_history.
        If attempt_count >= 3 and all attempts failed under different conditions,
        the experiment is deprioritized instead.

        Args:
            experiment_id: UUID of the experiment.

        Returns:
            True if successfully queued (or deprioritized), False if not found.
        """
        row = self._conn.execute(
            "SELECT * FROM failed_experiments WHERE id=?", (experiment_id,)
        ).fetchone()
        if row is None:
            return False

        experiment = self._row_to_experiment(row)
        experiment.attempt_count += 1
        now = time.time()
        experiment.last_attempted = now
        experiment.attempt_history.append({
            "attempt": experiment.attempt_count,
            "date": now,
            "conditions": {},
            "result": "queued_for_retry",
        })

        # Check deprioritization: 3+ attempts with different conditions
        if experiment.attempt_count >= 3 and self._all_different_conditions(experiment):
            experiment.deprioritized = True
            experiment.status = "deprioritized"
        else:
            experiment.status = "queued_for_retry"

        self._update_experiment(experiment)
        return True

    def record_retry_result(
        self, experiment_id: str, success: bool, result: str, conditions: dict
    ) -> bool:
        """Record the result of a retried experiment.

        Args:
            experiment_id: UUID of the experiment.
            success: Whether the retry succeeded.
            result: Description of what happened.
            conditions: Conditions during the retry.

        Returns:
            True if updated successfully, False if not found.
        """
        row = self._conn.execute(
            "SELECT * FROM failed_experiments WHERE id=?", (experiment_id,)
        ).fetchone()
        if row is None:
            return False

        experiment = self._row_to_experiment(row)
        now = time.time()
        experiment.last_attempted = now
        experiment.result = result

        # Update the last attempt_history entry with actual results
        if experiment.attempt_history:
            experiment.attempt_history[-1]["conditions"] = conditions
            experiment.attempt_history[-1]["result"] = result

        if success:
            experiment.success = True
            experiment.status = "succeeded"
            experiment.failure_reason = ""
            self._update_experiment(experiment)
            self._store_in_grimoire(experiment)
        else:
            experiment.failure_reason = result
            # Check deprioritization
            if experiment.attempt_count >= 3 and self._all_different_conditions(experiment):
                experiment.deprioritized = True
                experiment.status = "deprioritized"
            else:
                experiment.status = "failed"
            self._update_experiment(experiment)

        return True

    def get_pending_retries(self) -> list[Experiment]:
        """Return experiments queued for retry, ordered by priority.

        Fewer attempts = higher priority. Deprioritized experiments come last.

        Returns:
            List of experiments with status "queued_for_retry".
        """
        rows = self._conn.execute(
            """SELECT * FROM failed_experiments
               WHERE status='queued_for_retry'
               ORDER BY deprioritized ASC, attempt_count ASC"""
        ).fetchall()
        return [self._row_to_experiment(row) for row in rows]

    def get_experiment_stats(self) -> dict:
        """Return aggregate statistics for reporting.

        Returns:
            Dict with total_experiments, succeeded, failed, deprioritized,
            queued_for_retry, and retry_success_rate.
        """
        counts: dict[str, int] = {}
        for row in self._conn.execute(
            "SELECT status, COUNT(*) as cnt FROM failed_experiments GROUP BY status"
        ).fetchall():
            counts[row["status"]] = row["cnt"]

        total = sum(counts.values())
        succeeded = counts.get("succeeded", 0)
        failed = counts.get("failed", 0)
        deprioritized = counts.get("deprioritized", 0)
        queued = counts.get("queued_for_retry", 0)

        # retry_success_rate: succeeded / (succeeded + failed + deprioritized) among
        # experiments that have been attempted more than once
        multi_attempt_rows = self._conn.execute(
            "SELECT success FROM failed_experiments WHERE attempt_count > 1"
        ).fetchall()
        multi_total = len(multi_attempt_rows)
        multi_succeeded = sum(1 for r in multi_attempt_rows if r["success"])
        retry_success_rate = (multi_succeeded / multi_total) if multi_total > 0 else 0.0

        return {
            "total_experiments": total,
            "succeeded": succeeded,
            "failed": failed,
            "deprioritized": deprioritized,
            "queued_for_retry": queued,
            "retry_success_rate": retry_success_rate,
        }

    def get_experiments_by_domain(
        self, domain: str, include_deprioritized: bool = False
    ) -> list[Experiment]:
        """Filter experiments by domain tag.

        Args:
            domain: Domain tag to filter by.
            include_deprioritized: Whether to include deprioritized experiments.

        Returns:
            List of matching experiments.
        """
        if include_deprioritized:
            rows = self._conn.execute(
                "SELECT * FROM failed_experiments"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM failed_experiments WHERE deprioritized=0"
            ).fetchall()

        results = []
        for row in rows:
            exp = self._row_to_experiment(row)
            if domain in exp.domain_tags:
                results.append(exp)
        return results

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    # --- Internal helpers ---

    def _any_trigger_met(self, experiment: Experiment, current: dict) -> bool:
        """Check if any of the experiment's retry triggers are met."""
        for trigger in experiment.retry_triggers:
            if self._trigger_met(trigger, experiment, current):
                return True
        return False

    def _trigger_met(self, trigger: str, experiment: Experiment, current: dict) -> bool:
        """Evaluate a single trigger against current conditions."""
        if trigger.startswith("new_grimoire_knowledge:"):
            domain = trigger.split(":", 1)[1]
            new_domains = current.get("new_knowledge_domains", [])
            return domain in new_domains

        if trigger == "model_changed":
            current_model = current.get("model")
            exp_model = experiment.conditions.get("model")
            return current_model is not None and current_model != exp_model

        if trigger == "embedding_model_changed":
            current_emb = current.get("embedding_model")
            exp_emb = experiment.conditions.get("embedding_model")
            return current_emb is not None and current_emb != exp_emb

        if trigger.startswith("tool_added:"):
            tool_name = trigger.split(":", 1)[1]
            available = current.get("available_tools", [])
            return tool_name in available

        if trigger.startswith("knowledge_depth:"):
            parts = trigger.split(":")
            if len(parts) == 3:
                domain = parts[1]
                try:
                    min_count = int(parts[2])
                except ValueError:
                    return False
                counts = current.get("knowledge_counts", {})
                return counts.get(domain, 0) >= min_count

        return False

    def _all_different_conditions(self, experiment: Experiment) -> bool:
        """Check if all attempts in history had different conditions.

        Returns False if any two attempts share the same conditions,
        indicating the experiment hasn't been tried under genuinely
        different circumstances.
        """
        history = experiment.attempt_history
        # Only consider entries that have real conditions (not empty dicts from queue_for_retry)
        condition_sets = []
        for entry in history:
            conds = entry.get("conditions", {})
            if conds:  # Skip empty conditions
                cond_key = json.dumps(conds, sort_keys=True)
                condition_sets.append(cond_key)

        if len(condition_sets) < 2:
            return False

        # All conditions must be unique
        return len(condition_sets) == len(set(condition_sets))

    def _update_experiment(self, experiment: Experiment) -> None:
        """Update an experiment in the database."""
        self._conn.execute(
            """UPDATE failed_experiments
               SET hypothesis=?, approach=?, domain_tags=?, result=?, success=?,
                   failure_reason=?, conditions=?, retry_triggers=?,
                   attempt_count=?, attempt_history=?, created_at=?,
                   last_attempted=?, status=?, deprioritized=?
               WHERE id=?""",
            (
                experiment.hypothesis,
                experiment.approach,
                json.dumps(experiment.domain_tags),
                experiment.result,
                1 if experiment.success else 0,
                experiment.failure_reason,
                json.dumps(experiment.conditions),
                json.dumps(experiment.retry_triggers),
                experiment.attempt_count,
                json.dumps(experiment.attempt_history),
                experiment.created_at,
                experiment.last_attempted,
                experiment.status,
                1 if experiment.deprioritized else 0,
                experiment.id,
            ),
        )
        self._conn.commit()

    def _row_to_experiment(self, row: sqlite3.Row) -> Experiment:
        """Convert a database row to an Experiment dataclass."""
        return Experiment(
            id=row["id"],
            hypothesis=row["hypothesis"],
            approach=row["approach"],
            domain_tags=json.loads(row["domain_tags"]),
            result=row["result"],
            success=bool(row["success"]),
            failure_reason=row["failure_reason"],
            conditions=json.loads(row["conditions"]),
            retry_triggers=json.loads(row["retry_triggers"]),
            attempt_count=row["attempt_count"],
            attempt_history=json.loads(row["attempt_history"]),
            created_at=row["created_at"],
            last_attempted=row["last_attempted"],
            status=row["status"],
            deprioritized=bool(row["deprioritized"]),
        )

    def _store_in_grimoire(self, experiment: Experiment) -> None:
        """Store experiment findings in Grimoire knowledge base."""
        if self._grimoire is None:
            return
        try:
            self._grimoire.store(
                content=json.dumps({
                    "hypothesis": experiment.hypothesis,
                    "approach": experiment.approach,
                    "result": experiment.result,
                    "domain_tags": experiment.domain_tags,
                }),
                category="experiment_result",
                source=f"morpheus_experiment:{experiment.id}",
            )
        except Exception as e:
            logger.warning("Failed to store experiment in Grimoire: %s", e)
