"""
LoRA Performance Tracker — Per-Adapter Performance Metrics
============================================================
Track per-adapter performance metrics for domain-specific LoRA stacking.
Know which adapters help, which hurt, and when to retrain.

Tracking is passive — doesn't control adapter loading, only records
and analyzes performance data for informed decisions.

Feeds into: Harbinger (briefing metrics), Shadow (adapter recommendations).
"""

from __future__ import annotations

import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("shadow.lora_tracker")


@dataclass
class LoRARecord:
    """Single performance observation for an adapter on a task."""
    record_id: str
    adapter_name: str
    task_type: str
    module: str
    confidence_with: float
    confidence_without: float | None
    improvement: float | None
    task_succeeded: bool
    timestamp: float


@dataclass
class AdapterProfile:
    """Aggregated performance profile for one adapter."""
    adapter_name: str
    total_tasks: int
    avg_improvement: float
    tasks_helped: int
    tasks_hurt: int
    tasks_neutral: int
    help_rate: float
    hurt_rate: float
    best_task_types: list[str]
    worst_task_types: list[str]
    last_used: float
    needs_retrain: bool


class LoRAPerformanceTracker:
    """Track and analyze LoRA adapter performance across tasks."""

    def __init__(self, db_path: str = "data/lora_performance.db"):
        try:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._init_db()
        except Exception:
            logger.exception("Failed to initialize LoRA tracker database")
            raise

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS lora_records (
                record_id TEXT PRIMARY KEY,
                adapter_name TEXT NOT NULL,
                task_type TEXT NOT NULL,
                module TEXT NOT NULL,
                confidence_with REAL NOT NULL,
                confidence_without REAL,
                improvement REAL,
                task_succeeded INTEGER NOT NULL,
                timestamp REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_adapter_name
            ON lora_records(adapter_name)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_type
            ON lora_records(task_type)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON lora_records(timestamp)
        """)
        self._conn.commit()

    def record(
        self,
        adapter_name: str,
        task_type: str,
        module: str,
        confidence_with: float,
        confidence_without: float | None = None,
        task_succeeded: bool = True,
    ) -> str:
        """Store a performance record for an adapter on a task.

        Args:
            adapter_name: Name of the LoRA adapter.
            task_type: Type of task performed.
            module: Shadow module that handled the task.
            confidence_with: Confidence score with adapter loaded.
            confidence_without: Baseline confidence without adapter.
            task_succeeded: Whether the task completed successfully.

        Returns:
            The record_id of the stored record.
        """
        try:
            record_id = uuid.uuid4().hex[:12]
            improvement = None
            if confidence_without is not None:
                improvement = confidence_with - confidence_without
            ts = time.time()

            self._conn.execute(
                """INSERT INTO lora_records
                   (record_id, adapter_name, task_type, module,
                    confidence_with, confidence_without, improvement,
                    task_succeeded, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (record_id, adapter_name, task_type, module,
                 confidence_with, confidence_without, improvement,
                 int(task_succeeded), ts),
            )
            self._conn.commit()
            logger.info("Recorded LoRA performance: %s on %s (improvement=%s)",
                        adapter_name, task_type, improvement)
            return record_id
        except Exception:
            logger.exception("Failed to record LoRA performance")
            raise

    def get_adapter_profile(self, adapter_name: str, days: int = 30) -> AdapterProfile:
        """Aggregate performance for one adapter over a time period.

        Args:
            adapter_name: Name of the adapter to profile.
            days: Number of days to look back.

        Returns:
            AdapterProfile with aggregated metrics.
        """
        try:
            cutoff = time.time() - (days * 86400)
            rows = self._conn.execute(
                """SELECT * FROM lora_records
                   WHERE adapter_name = ? AND timestamp >= ?
                   ORDER BY timestamp DESC""",
                (adapter_name, cutoff),
            ).fetchall()

            if not rows:
                return AdapterProfile(
                    adapter_name=adapter_name,
                    total_tasks=0,
                    avg_improvement=0.0,
                    tasks_helped=0,
                    tasks_hurt=0,
                    tasks_neutral=0,
                    help_rate=0.0,
                    hurt_rate=0.0,
                    best_task_types=[],
                    worst_task_types=[],
                    last_used=0.0,
                    needs_retrain=False,
                )

            total = len(rows)
            improvements = [r["improvement"] for r in rows if r["improvement"] is not None]
            avg_imp = sum(improvements) / len(improvements) if improvements else 0.0

            helped = sum(1 for v in improvements if v > 0.05)
            hurt = sum(1 for v in improvements if v < -0.05)
            neutral = total - helped - hurt

            # Best/worst task types by average improvement
            task_type_improvements: dict[str, list[float]] = {}
            for r in rows:
                if r["improvement"] is not None:
                    task_type_improvements.setdefault(r["task_type"], []).append(r["improvement"])

            task_type_avgs = {
                tt: sum(vals) / len(vals)
                for tt, vals in task_type_improvements.items()
            }
            sorted_types = sorted(task_type_avgs.items(), key=lambda x: x[1], reverse=True)
            best = [tt for tt, avg in sorted_types if avg > 0.05][:5]
            worst = [tt for tt, avg in sorted_types if avg < -0.05][:5]

            last_used = max(r["timestamp"] for r in rows)

            # Detect need for retraining
            needs_retrain = self._check_needs_retrain(adapter_name, total, hurt, improvements)

            return AdapterProfile(
                adapter_name=adapter_name,
                total_tasks=total,
                avg_improvement=round(avg_imp, 4),
                tasks_helped=helped,
                tasks_hurt=hurt,
                tasks_neutral=neutral,
                help_rate=round(helped / total, 4) if total else 0.0,
                hurt_rate=round(hurt / total, 4) if total else 0.0,
                best_task_types=best,
                worst_task_types=worst,
                last_used=last_used,
                needs_retrain=needs_retrain,
            )
        except Exception:
            logger.exception("Failed to get adapter profile for %s", adapter_name)
            raise

    def _check_needs_retrain(
        self, adapter_name: str, total: int, hurt: int, improvements: list[float]
    ) -> bool:
        """Determine if an adapter needs retraining.

        True if hurt_rate > 0.2 or performance declining over last 7 days.
        """
        if total > 0 and hurt / total > 0.2:
            return True

        # Check for declining performance over last 7 days
        cutoff_7d = time.time() - (7 * 86400)
        recent = self._conn.execute(
            """SELECT improvement, timestamp FROM lora_records
               WHERE adapter_name = ? AND timestamp >= ? AND improvement IS NOT NULL
               ORDER BY timestamp ASC""",
            (adapter_name, cutoff_7d),
        ).fetchall()

        if len(recent) >= 4:
            mid = len(recent) // 2
            first_half_avg = sum(r["improvement"] for r in recent[:mid]) / mid
            second_half_avg = sum(r["improvement"] for r in recent[mid:]) / (len(recent) - mid)
            if second_half_avg < first_half_avg - 0.02:
                return True

        return False

    def get_all_profiles(self, days: int = 30) -> list[AdapterProfile]:
        """Get profiles for all adapters, sorted by avg_improvement descending.

        Args:
            days: Number of days to look back.

        Returns:
            List of AdapterProfile sorted by avg_improvement descending.
        """
        try:
            cutoff = time.time() - (days * 86400)
            rows = self._conn.execute(
                """SELECT DISTINCT adapter_name FROM lora_records
                   WHERE timestamp >= ?""",
                (cutoff,),
            ).fetchall()

            profiles = [self.get_adapter_profile(r["adapter_name"], days) for r in rows]
            profiles.sort(key=lambda p: p.avg_improvement, reverse=True)
            return profiles
        except Exception:
            logger.exception("Failed to get all adapter profiles")
            raise

    def recommend_adapter(self, task_type: str, module: str | None = None) -> dict:
        """Recommend the best adapter for a given task type.

        Args:
            task_type: Type of task to get a recommendation for.
            module: Optional module filter.

        Returns:
            Dict with recommended_adapter, expected_improvement, confidence, alternatives.
        """
        try:
            query = """SELECT adapter_name, improvement, task_type FROM lora_records
                       WHERE task_type = ? AND improvement IS NOT NULL"""
            params: list = [task_type]
            if module:
                query += " AND module = ?"
                params.append(module)

            rows = self._conn.execute(query, params).fetchall()

            if not rows:
                return {
                    "recommended_adapter": None,
                    "expected_improvement": 0.0,
                    "confidence": 0.0,
                    "alternatives": [],
                }

            # Group by adapter
            adapter_stats: dict[str, list[float]] = {}
            for r in rows:
                adapter_stats.setdefault(r["adapter_name"], []).append(r["improvement"])

            # Rank by average improvement
            ranked = []
            for name, imps in adapter_stats.items():
                avg = sum(imps) / len(imps)
                count = len(imps)
                # Confidence scales with sample size, capped at 1.0
                confidence = min(1.0, count / 20.0)
                ranked.append({
                    "adapter": name,
                    "avg_improvement": round(avg, 4),
                    "confidence": round(confidence, 4),
                    "sample_size": count,
                })

            ranked.sort(key=lambda x: x["avg_improvement"], reverse=True)

            # If best adapter has no positive improvement, recommend none
            if ranked[0]["avg_improvement"] <= 0:
                return {
                    "recommended_adapter": None,
                    "expected_improvement": 0.0,
                    "confidence": 0.0,
                    "alternatives": [],
                }

            best = ranked[0]
            alternatives = [
                {"adapter": r["adapter"], "expected_improvement": r["avg_improvement"]}
                for r in ranked[1:]
                if r["avg_improvement"] > 0
            ]

            return {
                "recommended_adapter": best["adapter"],
                "expected_improvement": best["avg_improvement"],
                "confidence": best["confidence"],
                "alternatives": alternatives,
            }
        except Exception:
            logger.exception("Failed to recommend adapter for task_type=%s", task_type)
            raise

    def detect_overlap(self, adapter_a: str, adapter_b: str) -> dict:
        """Detect overlap between two adapters' effective task types.

        Args:
            adapter_a: First adapter name.
            adapter_b: Second adapter name.

        Returns:
            Dict with overlap_rate, shared_task_types, recommendation.
        """
        try:
            types_a = set(
                r["task_type"] for r in self._conn.execute(
                    """SELECT DISTINCT task_type FROM lora_records
                       WHERE adapter_name = ? AND improvement IS NOT NULL AND improvement > 0.05""",
                    (adapter_a,),
                ).fetchall()
            )
            types_b = set(
                r["task_type"] for r in self._conn.execute(
                    """SELECT DISTINCT task_type FROM lora_records
                       WHERE adapter_name = ? AND improvement IS NOT NULL AND improvement > 0.05""",
                    (adapter_b,),
                ).fetchall()
            )

            if not types_a and not types_b:
                return {
                    "overlap_rate": 0.0,
                    "shared_task_types": [],
                    "recommendation": "Insufficient data for both adapters",
                }

            union = types_a | types_b
            intersection = types_a & types_b
            overlap_rate = len(intersection) / len(union) if union else 0.0

            if overlap_rate > 0.8:
                recommendation = "Consider merging adapters"
            elif overlap_rate < 0.2:
                recommendation = "Adapters are well-specialized"
            else:
                recommendation = "Moderate overlap — review shared task types"

            return {
                "overlap_rate": round(overlap_rate, 4),
                "shared_task_types": sorted(intersection),
                "recommendation": recommendation,
            }
        except Exception:
            logger.exception("Failed to detect overlap between %s and %s", adapter_a, adapter_b)
            raise

    def get_retrain_candidates(self) -> list[str]:
        """Get adapters that need retraining.

        Returns:
            List of adapter names where needs_retrain is True.
        """
        try:
            profiles = self.get_all_profiles()
            return [p.adapter_name for p in profiles if p.needs_retrain]
        except Exception:
            logger.exception("Failed to get retrain candidates")
            raise

    def get_performance_trend(self, adapter_name: str, days: int = 30) -> list[dict]:
        """Get daily performance trend for an adapter.

        Args:
            adapter_name: Name of the adapter.
            days: Number of days to look back.

        Returns:
            List of dicts with date, avg_improvement, task_count per day.
        """
        try:
            cutoff = time.time() - (days * 86400)
            rows = self._conn.execute(
                """SELECT improvement, timestamp FROM lora_records
                   WHERE adapter_name = ? AND timestamp >= ? AND improvement IS NOT NULL
                   ORDER BY timestamp ASC""",
                (adapter_name, cutoff),
            ).fetchall()

            # Group by date
            daily: dict[str, list[float]] = {}
            for r in rows:
                date_str = datetime.fromtimestamp(r["timestamp"], tz=timezone.utc).strftime("%Y-%m-%d")
                daily.setdefault(date_str, []).append(r["improvement"])

            return [
                {
                    "date": date,
                    "avg_improvement": round(sum(vals) / len(vals), 4),
                    "task_count": len(vals),
                }
                for date, vals in sorted(daily.items())
            ]
        except Exception:
            logger.exception("Failed to get performance trend for %s", adapter_name)
            raise

    def get_tracker_summary(self) -> str:
        """Generate a plain-English summary for Harbinger briefing.

        Returns:
            Human-readable summary of adapter performance.
        """
        try:
            profiles = self.get_all_profiles()

            if not profiles:
                return "No LoRA adapters tracked yet."

            parts = [f"{len(profiles)} LoRA adapter{'s' if len(profiles) != 1 else ''} tracked."]

            # Best performer
            best = max(profiles, key=lambda p: p.avg_improvement)
            if best.avg_improvement > 0:
                parts.append(
                    f"{best.adapter_name} adapter performing well "
                    f"(+{best.avg_improvement:.2f} avg improvement)."
                )

            # Worst performer
            worst = min(profiles, key=lambda p: p.avg_improvement)
            if worst.adapter_name != best.adapter_name and worst.avg_improvement < 0:
                parts.append(
                    f"{worst.adapter_name} adapter underperforming "
                    f"({worst.avg_improvement:.2f} avg improvement)."
                )

            # Retrain candidates
            retrain = [p for p in profiles if p.needs_retrain]
            if retrain:
                names = ", ".join(p.adapter_name for p in retrain)
                parts.append(f"{names} {'needs' if len(retrain) == 1 else 'need'} retraining "
                             f"(declining performance).")

            # High help-rate adapters
            high_help = [p for p in profiles if p.help_rate >= 0.8 and p.total_tasks >= 5]
            for p in high_help:
                parts.append(
                    f"{p.adapter_name} adapter helping on {p.help_rate:.0%} of tasks."
                )

            return " ".join(parts)
        except Exception:
            logger.exception("Failed to generate tracker summary")
            return "Error generating LoRA tracker summary."
