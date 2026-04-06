"""
Growth Engine — Shadow's P2 Self-Improvement System
=====================================================
Analyzes performance data, sets learning goals, and tracks progress.
This is the standing Priority 2 mission: between user interactions,
Shadow actively works on getting smarter.

Components:
- Goal generation from performance data (escalations, failures, health, corrections)
- Performance metric recording and trend analysis
- Evening learning reports and morning growth summaries
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger("shadow.growth_engine")

# Metrics where lower values are better (inverted trend logic)
_LOWER_IS_BETTER = {"response_latency"}


class GrowthEngine:
    """Shadow's self-improvement system. Analyzes performance,
    sets learning goals, tracks progress."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.row_factory = sqlite3.Row
        self._create_tables()
        logger.info("GrowthEngine initialized: %s", self._db_path)

    def _create_tables(self) -> None:
        """Create growth tracking tables if they don't exist."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS growth_goals (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                date TEXT NOT NULL,
                goal TEXT NOT NULL,
                category TEXT NOT NULL,
                source TEXT NOT NULL,
                measurable_target TEXT,
                status TEXT DEFAULT 'active',
                progress_notes TEXT,
                completed_at TEXT,
                evidence TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_growth_goals_date
                ON growth_goals(date);

            CREATE INDEX IF NOT EXISTS idx_growth_goals_status
                ON growth_goals(status);

            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                context TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_perf_metrics_name_date
                ON performance_metrics(metric_name, date);
        """)
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            logger.info("GrowthEngine closed")

    # ================================================================
    # GOAL GENERATION
    # ================================================================

    def generate_daily_goals(
        self,
        escalation_log: list[dict] | None = None,
        failure_patterns: list[dict] | None = None,
        module_health: list[dict] | None = None,
        user_corrections: list[dict] | None = None,
    ) -> list[dict]:
        """Generate today's learning goals from performance data.

        Analyzes inputs to generate 3-5 concrete, measurable goals.
        If no data is available, generates safe defaults.
        Calling twice on the same day returns existing goals (no duplicates).
        """
        today = datetime.now().strftime("%Y-%m-%d")

        # Check for existing goals today — no duplicates
        existing = self._conn.execute(
            "SELECT * FROM growth_goals WHERE date = ?", (today,)
        ).fetchall()
        if existing:
            logger.info("Goals already exist for %s (%d goals)", today, len(existing))
            return [dict(row) for row in existing]

        goals: list[dict] = []
        now = datetime.now().isoformat()

        # Generate from escalation log
        if escalation_log:
            # Find most common escalation task type
            type_counts: dict[str, int] = {}
            for entry in escalation_log:
                task_type = entry.get("task_type", "unknown")
                type_counts[task_type] = type_counts.get(task_type, 0) + 1
            top_type = max(type_counts, key=type_counts.get)
            count = type_counts[top_type]
            goals.append(self._make_goal(
                goal=f"Reduce escalations for '{top_type}' tasks — appeared {count} times recently",
                category="escalation",
                source="apex_escalation_log",
                measurable_target=f"Fewer than {max(1, count - 1)} escalations for {top_type}",
                date=today,
                now=now,
            ))

        # Generate from failure patterns
        if failure_patterns:
            for pattern in failure_patterns[:2]:  # Cap at 2 failure goals
                desc = pattern.get("description", pattern.get("pattern", "unknown"))
                goals.append(self._make_goal(
                    goal=f"Address recurring failure: {desc}",
                    category="failure",
                    source="error_analysis",
                    measurable_target=f"Zero occurrences of '{desc}' pattern",
                    date=today,
                    now=now,
                ))

        # Generate from module health
        if module_health:
            for mod in module_health:
                status = mod.get("status", "unknown")
                if status not in ("online", "ONLINE"):
                    name = mod.get("name", "unknown")
                    goals.append(self._make_goal(
                        goal=f"Investigate {name} health — status: {status}",
                        category="health",
                        source="module_monitor",
                        measurable_target=f"{name} module back to online status",
                        date=today,
                        now=now,
                    ))

        # Generate from user corrections
        if user_corrections:
            for correction in user_corrections[:2]:  # Cap at 2 correction goals
                topic = correction.get("topic", correction.get("summary", "recent interaction"))
                goals.append(self._make_goal(
                    goal=f"Improve accuracy on '{topic}' based on user feedback",
                    category="correction",
                    source="user_feedback",
                    measurable_target=f"No repeated corrections on '{topic}'",
                    date=today,
                    now=now,
                ))

        # Default goals when no data available
        if not goals:
            defaults = [
                ("Review recent teaching signals for learning opportunities",
                 "Identify at least 1 actionable learning from teaching signals"),
                ("Run module health checks across all systems",
                 "All modules reporting online status"),
                ("Check for tool and capability updates",
                 "Document any new capabilities or tool changes"),
            ]
            for goal_text, target in defaults:
                goals.append(self._make_goal(
                    goal=goal_text,
                    category="default",
                    source="scheduled",
                    measurable_target=target,
                    date=today,
                    now=now,
                ))

        # Persist to DB
        for g in goals:
            self._conn.execute(
                """INSERT INTO growth_goals
                   (id, created_at, date, goal, category, source, measurable_target, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (g["id"], g["created_at"], g["date"], g["goal"],
                 g["category"], g["source"], g["measurable_target"], g["status"]),
            )
        self._conn.commit()

        logger.info("Generated %d growth goals for %s", len(goals), today)
        return goals

    def _make_goal(
        self, goal: str, category: str, source: str,
        measurable_target: str, date: str, now: str,
    ) -> dict:
        """Build a goal dict with a fresh UUID."""
        return {
            "id": str(uuid.uuid4()),
            "created_at": now,
            "date": date,
            "goal": goal,
            "category": category,
            "source": source,
            "measurable_target": measurable_target,
            "status": "active",
            "progress_notes": None,
            "completed_at": None,
            "evidence": None,
        }

    # ================================================================
    # PERFORMANCE METRICS
    # ================================================================

    def record_metric(
        self, metric_name: str, metric_value: float, context: str | None = None,
    ) -> None:
        """Store a performance metric data point."""
        now = datetime.now().isoformat()
        self._conn.execute(
            """INSERT INTO performance_metrics (date, metric_name, metric_value, context)
               VALUES (?, ?, ?, ?)""",
            (now, metric_name, metric_value, context),
        )
        self._conn.commit()

    def get_daily_metrics(
        self, date: str | None = None, days: int = 7,
    ) -> dict[str, Any]:
        """Return metrics for a date range with aggregation and trends.

        Args:
            date: End date (ISO format YYYY-MM-DD). Defaults to today.
            days: Number of days to include.

        Returns:
            Dict with date_range, metrics (count/avg/min/max/trend/alert per name), flags.
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        end_dt = datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)
        start_dt = end_dt - timedelta(days=days)
        end_str = end_dt.isoformat()
        start_str = start_dt.isoformat()

        # Current period metrics
        rows = self._conn.execute(
            """SELECT metric_name, metric_value, date
               FROM performance_metrics
               WHERE date >= ? AND date < ?
               ORDER BY date""",
            (start_str, end_str),
        ).fetchall()

        # Previous period (same length, for trend comparison)
        prev_start_dt = start_dt - timedelta(days=days)
        prev_start_str = prev_start_dt.isoformat()
        prev_rows = self._conn.execute(
            """SELECT metric_name, metric_value
               FROM performance_metrics
               WHERE date >= ? AND date < ?""",
            (prev_start_str, start_str),
        ).fetchall()

        # Aggregate current period
        metrics: dict[str, dict] = {}
        for row in rows:
            name = row["metric_name"]
            val = row["metric_value"]
            if name not in metrics:
                metrics[name] = {"values": [], "count": 0, "sum": 0.0}
            metrics[name]["values"].append(val)
            metrics[name]["count"] += 1
            metrics[name]["sum"] += val

        # Aggregate previous period
        prev_metrics: dict[str, dict] = {}
        for row in prev_rows:
            name = row["metric_name"]
            val = row["metric_value"]
            if name not in prev_metrics:
                prev_metrics[name] = {"values": [], "count": 0, "sum": 0.0}
            prev_metrics[name]["values"].append(val)
            prev_metrics[name]["count"] += 1
            prev_metrics[name]["sum"] += val

        # Build result with trends
        flags: list[str] = []
        result_metrics: dict[str, dict] = {}

        for name, data in metrics.items():
            values = data["values"]
            count = data["count"]
            avg = data["sum"] / count
            mn = min(values)
            mx = max(values)

            # Compute trend
            trend = "stable"
            alert = False
            if name in prev_metrics and prev_metrics[name]["count"] > 0:
                prev_avg = prev_metrics[name]["sum"] / prev_metrics[name]["count"]
                if prev_avg != 0:
                    change_pct = ((avg - prev_avg) / abs(prev_avg)) * 100
                else:
                    change_pct = 0.0

                if abs(change_pct) < 5:
                    trend = "stable"
                elif name in _LOWER_IS_BETTER:
                    trend = "improving" if change_pct < -5 else "declining"
                else:
                    trend = "improving" if change_pct > 5 else "declining"

                if trend == "declining":
                    alert = True
                    flags.append(f"{name} trending wrong direction ({change_pct:+.1f}%)")

            result_metrics[name] = {
                "count": count,
                "avg": round(avg, 4),
                "min": round(mn, 4),
                "max": round(mx, 4),
                "trend": trend,
                "alert": alert,
            }

        return {
            "date_range": {"start": start_dt.strftime("%Y-%m-%d"), "end": date},
            "metrics": result_metrics,
            "flags": flags,
        }

    # ================================================================
    # GOAL PROGRESS
    # ================================================================

    def update_goal_progress(
        self, goal_id: str, notes: str, status: str | None = None,
    ) -> None:
        """Add progress notes to a goal, optionally update status.

        Args:
            goal_id: UUID of the goal.
            notes: Progress notes to append.
            status: New status (active, completed, missed, deferred). Optional.

        Raises:
            KeyError: If goal_id doesn't exist.
            ValueError: If status is invalid.
        """
        valid_statuses = {"active", "completed", "missed", "deferred"}

        # Verify goal exists
        row = self._conn.execute(
            "SELECT * FROM growth_goals WHERE id = ?", (goal_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"Goal not found: {goal_id}")

        if status is not None and status not in valid_statuses:
            raise ValueError(f"Invalid status '{status}'. Must be one of: {valid_statuses}")

        # Build update
        now = datetime.now().isoformat()
        existing_notes = row["progress_notes"] or ""
        updated_notes = f"{existing_notes}\n[{now}] {notes}".strip()

        if status is not None:
            completed_at = now if status == "completed" else row["completed_at"]
            self._conn.execute(
                """UPDATE growth_goals
                   SET progress_notes = ?, status = ?, completed_at = ?
                   WHERE id = ?""",
                (updated_notes, status, completed_at, goal_id),
            )
        else:
            self._conn.execute(
                "UPDATE growth_goals SET progress_notes = ? WHERE id = ?",
                (updated_notes, goal_id),
            )
        self._conn.commit()

    # ================================================================
    # REPORTS
    # ================================================================

    def compile_evening_learning_report(self) -> dict[str, Any]:
        """Compile end-of-day learning report.

        Returns:
            Dict with: date, goals_hit, goals_missed, hit_rate,
            preliminary_tomorrow, generated_at.
        """
        today = datetime.now().strftime("%Y-%m-%d")

        rows = self._conn.execute(
            "SELECT * FROM growth_goals WHERE date = ?", (today,)
        ).fetchall()

        goals_hit = [dict(r) for r in rows if r["status"] == "completed"]
        goals_missed = [dict(r) for r in rows if r["status"] in ("active", "missed")]

        total = len(rows)
        hit_rate = len(goals_hit) / total if total > 0 else 0.0

        return {
            "date": today,
            "goals_hit": goals_hit,
            "goals_missed": goals_missed,
            "hit_rate": round(hit_rate, 4),
            "preliminary_tomorrow": [],
            "generated_at": datetime.now().isoformat(),
        }

    def get_growth_summary(self) -> dict[str, Any]:
        """Growth summary for morning briefing Section 9.

        Returns:
            Dict with: yesterday_completion, today_goals, metric_trends, flags.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        # Yesterday's completion rate
        yesterday_rows = self._conn.execute(
            "SELECT * FROM growth_goals WHERE date = ?", (yesterday,)
        ).fetchall()
        yesterday_total = len(yesterday_rows)
        yesterday_completed = sum(1 for r in yesterday_rows if r["status"] == "completed")
        yesterday_rate = yesterday_completed / yesterday_total if yesterday_total > 0 else 0.0

        # Today's goals
        today_rows = self._conn.execute(
            "SELECT * FROM growth_goals WHERE date = ?", (today,)
        ).fetchall()

        # Metric trends
        daily_metrics = self.get_daily_metrics(days=7)

        return {
            "yesterday_completion": {
                "total": yesterday_total,
                "completed": yesterday_completed,
                "rate": round(yesterday_rate, 4),
            },
            "today_goals": [dict(r) for r in today_rows],
            "metric_trends": daily_metrics.get("metrics", {}),
            "flags": daily_metrics.get("flags", []),
        }

    def analyze_trends(self, days: int = 14) -> list[dict[str, Any]]:
        """Analyze metric trends over time.

        Splits the window in half: current period vs previous period.
        Flags any metric trending wrong for 2+ consecutive periods.

        Args:
            days: Total window size (split in half for comparison).

        Returns:
            List of trend dicts with: metric, trend, alert, details.
        """
        half = days // 2
        today = datetime.now()
        current_end = (today + timedelta(days=1)).isoformat()
        current_start = (today - timedelta(days=half)).isoformat()
        prev_start = (today - timedelta(days=days)).isoformat()

        # Current period
        current_rows = self._conn.execute(
            """SELECT metric_name, metric_value
               FROM performance_metrics
               WHERE date >= ? AND date < ?""",
            (current_start, current_end),
        ).fetchall()

        # Previous period
        prev_rows = self._conn.execute(
            """SELECT metric_name, metric_value
               FROM performance_metrics
               WHERE date >= ? AND date < ?""",
            (prev_start, current_start),
        ).fetchall()

        # Aggregate
        def aggregate(rows):
            agg: dict[str, list[float]] = {}
            for r in rows:
                name = r["metric_name"]
                if name not in agg:
                    agg[name] = []
                agg[name].append(r["metric_value"])
            return {k: sum(v) / len(v) for k, v in agg.items()}

        current_avgs = aggregate(current_rows)
        prev_avgs = aggregate(prev_rows)

        # All metric names seen
        all_names = set(current_avgs.keys()) | set(prev_avgs.keys())

        results: list[dict] = []
        for name in sorted(all_names):
            curr = current_avgs.get(name)
            prev = prev_avgs.get(name)

            if curr is None or prev is None:
                results.append({
                    "metric": name,
                    "trend": "stable",
                    "alert": False,
                    "details": "Insufficient data for trend comparison",
                })
                continue

            if prev != 0:
                change_pct = ((curr - prev) / abs(prev)) * 100
            else:
                change_pct = 0.0

            if abs(change_pct) < 5:
                trend = "stable"
            elif name in _LOWER_IS_BETTER:
                trend = "improving" if change_pct < -5 else "declining"
            else:
                trend = "improving" if change_pct > 5 else "declining"

            alert = trend == "declining"

            details = (
                f"{name}: {prev:.4f} → {curr:.4f} ({change_pct:+.1f}%)"
            )

            results.append({
                "metric": name,
                "trend": trend,
                "alert": alert,
                "details": details,
            })

        return results
