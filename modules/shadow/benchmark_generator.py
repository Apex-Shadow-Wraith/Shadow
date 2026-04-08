"""
Autonomous Benchmark Generator
================================
Shadow generates his own benchmarks as capabilities grow. Supplements
the fixed monthly benchmark (Item 8) with evolving challenges.

Three sources of benchmark generation:
- **Mastery**: Domain mastered at level N → generate level N+1 challenge
- **Discovery**: Morpheus made a discovery → benchmark the new capability
- **Gap**: Repeated failures in area X → targeted improvement tracking

Benchmarks retire automatically when Shadow consistently scores > 0.9,
ensuring the suite always tests at the frontier of current ability.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("shadow.benchmark_generator")


@dataclass
class GeneratedBenchmark:
    """A single auto-generated benchmark task."""

    benchmark_id: str
    domain: str
    difficulty: int                 # 1-10
    task_description: str
    evaluation_criteria: dict
    expected_output_hints: str      # not full answer, just what to check for
    generated_from: str             # "mastery", "discovery", "gap"
    created_at: float
    times_run: int
    avg_score: float
    status: str                     # "active", "retired", "deferred"


VALID_SOURCES = {"mastery", "discovery", "gap"}
VALID_STATUSES = {"active", "retired", "deferred"}

# Default prompts for each generation source
_MASTERY_PROMPT = (
    "Create a challenging {domain} task at difficulty level {level}. "
    "Include clear evaluation criteria. Return JSON with keys: "
    "task_description, evaluation_criteria (dict), expected_output_hints."
)
_DISCOVERY_PROMPT = (
    "Create a benchmark task that tests this capability: {description}. "
    "Return JSON with keys: task_description, evaluation_criteria (dict), "
    "expected_output_hints."
)
_WEAKNESS_PROMPT = (
    "Create a targeted benchmark to improve this weakness: {weakness}. "
    "Failure patterns observed: {patterns}. "
    "Return JSON with keys: task_description, evaluation_criteria (dict), "
    "expected_output_hints."
)


class BenchmarkGenerator:
    """Generates, runs, and manages evolving benchmarks for Shadow."""

    def __init__(
        self,
        generate_fn: Optional[Callable] = None,
        grimoire: Any = None,
        behavioral_benchmark: Any = None,
        db_path: str = "data/generated_benchmarks.db",
    ):
        self.generate_fn = generate_fn
        self.grimoire = grimoire
        self.behavioral_benchmark = behavioral_benchmark
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Create the benchmarks table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS benchmarks (
                    benchmark_id   TEXT PRIMARY KEY,
                    domain         TEXT NOT NULL,
                    difficulty     INTEGER NOT NULL,
                    task_description TEXT NOT NULL,
                    evaluation_criteria TEXT NOT NULL,
                    expected_output_hints TEXT NOT NULL,
                    generated_from TEXT NOT NULL,
                    created_at     REAL NOT NULL,
                    times_run      INTEGER NOT NULL DEFAULT 0,
                    avg_score      REAL NOT NULL DEFAULT 0.0,
                    status         TEXT NOT NULL DEFAULT 'active'
                )
            """)
            conn.commit()

    def _save_benchmark(self, bm: GeneratedBenchmark) -> None:
        """Insert or replace a benchmark in the database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO benchmarks
                    (benchmark_id, domain, difficulty, task_description,
                     evaluation_criteria, expected_output_hints, generated_from,
                     created_at, times_run, avg_score, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bm.benchmark_id,
                    bm.domain,
                    bm.difficulty,
                    bm.task_description,
                    json.dumps(bm.evaluation_criteria),
                    bm.expected_output_hints,
                    bm.generated_from,
                    bm.created_at,
                    bm.times_run,
                    bm.avg_score,
                    bm.status,
                ),
            )
            conn.commit()

    def _load_benchmark(self, row: tuple) -> GeneratedBenchmark:
        """Convert a database row to a GeneratedBenchmark."""
        return GeneratedBenchmark(
            benchmark_id=row[0],
            domain=row[1],
            difficulty=row[2],
            task_description=row[3],
            evaluation_criteria=json.loads(row[4]),
            expected_output_hints=row[5],
            generated_from=row[6],
            created_at=row[7],
            times_run=row[8],
            avg_score=row[9],
            status=row[10],
        )

    # ------------------------------------------------------------------
    # Generation helpers
    # ------------------------------------------------------------------

    def _call_generate(self, prompt: str) -> dict:
        """Call generate_fn and parse the JSON response.

        Returns a dict with task_description, evaluation_criteria,
        expected_output_hints. Falls back to sensible defaults on failure.
        """
        if self.generate_fn is None:
            logger.warning("No generate_fn provided — returning placeholder benchmark")
            return {
                "task_description": prompt,
                "evaluation_criteria": {"completeness": "Task completed as described"},
                "expected_output_hints": "Verify task output matches criteria",
            }

        raw = self.generate_fn(prompt)
        if isinstance(raw, dict):
            return raw
        # Try to parse string as JSON
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("generate_fn returned non-JSON; wrapping as description")
            return {
                "task_description": str(raw),
                "evaluation_criteria": {"completeness": "Task completed as described"},
                "expected_output_hints": "Verify task output matches criteria",
            }

    def _make_benchmark(
        self, domain: str, difficulty: int, source: str, parsed: dict
    ) -> GeneratedBenchmark:
        """Build a GeneratedBenchmark from parsed generation output."""
        bm = GeneratedBenchmark(
            benchmark_id=str(uuid.uuid4()),
            domain=domain,
            difficulty=max(1, min(10, difficulty)),
            task_description=parsed.get("task_description", ""),
            evaluation_criteria=parsed.get("evaluation_criteria", {}),
            expected_output_hints=parsed.get("expected_output_hints", ""),
            generated_from=source,
            created_at=time.time(),
            times_run=0,
            avg_score=0.0,
            status="active",
        )
        self._save_benchmark(bm)
        logger.info(
            "Generated benchmark %s [%s] domain=%s difficulty=%d",
            bm.benchmark_id, source, domain, difficulty,
        )
        return bm

    # ------------------------------------------------------------------
    # Public generation methods
    # ------------------------------------------------------------------

    def generate_from_mastery(
        self, domain: str, current_level: int
    ) -> GeneratedBenchmark:
        """Generate a harder benchmark after mastering a domain level.

        Args:
            domain: The domain that was mastered (e.g. "code_review").
            current_level: The level just mastered (1-9). Next challenge
                will target current_level + 1.

        Returns:
            A new active GeneratedBenchmark at the next difficulty level.
        """
        next_level = min(current_level + 1, 10)
        prompt = _MASTERY_PROMPT.format(domain=domain, level=next_level)
        parsed = self._call_generate(prompt)
        return self._make_benchmark(domain, next_level, "mastery", parsed)

    def generate_from_discovery(self, discovery: dict) -> GeneratedBenchmark:
        """Generate a benchmark to track a new capability from Morpheus.

        Args:
            discovery: Dict with at least 'description' and optionally
                'domain' and 'difficulty'.

        Returns:
            A new active GeneratedBenchmark for the discovered capability.
        """
        description = discovery.get("description", "unknown capability")
        domain = discovery.get("domain", "general")
        difficulty = discovery.get("difficulty", 5)
        prompt = _DISCOVERY_PROMPT.format(description=description)
        parsed = self._call_generate(prompt)
        return self._make_benchmark(domain, difficulty, "discovery", parsed)

    def generate_from_weakness(
        self, failure_patterns: list[dict]
    ) -> GeneratedBenchmark:
        """Generate a targeted benchmark from observed failure patterns.

        Args:
            failure_patterns: List of dicts describing failures, each with
                at least 'description'. Optionally 'domain' and 'count'.

        Returns:
            A new active GeneratedBenchmark targeting the weakness, or a
            placeholder if failure_patterns is empty.
        """
        if not failure_patterns:
            logger.warning("Empty failure_patterns — generating generic benchmark")
            return self._make_benchmark(
                "general", 5, "gap",
                {
                    "task_description": "General improvement benchmark",
                    "evaluation_criteria": {"improvement": "Measurable progress"},
                    "expected_output_hints": "Show progress in weak areas",
                },
            )

        # Summarize the weakness from the most common patterns
        descriptions = [fp.get("description", "unknown") for fp in failure_patterns]
        weakness = "; ".join(descriptions[:5])  # cap at 5 for prompt length
        domain = failure_patterns[0].get("domain", "general")
        # Difficulty based on how many failures — more failures = harder problem
        difficulty = min(max(len(failure_patterns), 3), 10)

        prompt = _WEAKNESS_PROMPT.format(weakness=weakness, patterns=descriptions[:3])
        parsed = self._call_generate(prompt)
        return self._make_benchmark(domain, difficulty, "gap", parsed)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run_benchmark(
        self, benchmark: GeneratedBenchmark, executor_fn: Callable
    ) -> dict:
        """Execute a benchmark and evaluate the result.

        Args:
            benchmark: The benchmark to run.
            executor_fn: Callable that takes a task_description (str) and
                returns a dict with at least 'output' and optionally 'score'.

        Returns:
            Dict with score, passed, evaluation_notes, duration.
        """
        start = time.time()

        try:
            result = executor_fn(benchmark.task_description)
        except Exception as e:
            logger.error("Benchmark %s execution failed: %s", benchmark.benchmark_id, e)
            duration = time.time() - start
            return {
                "score": 0.0,
                "passed": False,
                "evaluation_notes": f"Execution error: {e}",
                "duration": duration,
            }

        duration = time.time() - start

        # Extract score from executor result
        if isinstance(result, dict):
            score = float(result.get("score", 0.0))
            notes = result.get("notes", "")
        else:
            score = 0.0
            notes = str(result)

        score = max(0.0, min(1.0, score))
        passed = score >= 0.7

        # Update benchmark stats
        total_score = benchmark.avg_score * benchmark.times_run + score
        benchmark.times_run += 1
        benchmark.avg_score = total_score / benchmark.times_run
        self._save_benchmark(benchmark)

        logger.info(
            "Benchmark %s run #%d: score=%.2f passed=%s",
            benchmark.benchmark_id, benchmark.times_run, score, passed,
        )

        return {
            "score": score,
            "passed": passed,
            "evaluation_notes": notes,
            "duration": duration,
        }

    # ------------------------------------------------------------------
    # Management
    # ------------------------------------------------------------------

    def retire_benchmark(self, benchmark_id: str) -> bool:
        """Mark a benchmark as retired (too easy, no longer informative).

        Args:
            benchmark_id: The ID of the benchmark to retire.

        Returns:
            True if the benchmark was found and retired, False otherwise.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE benchmarks SET status = 'retired' WHERE benchmark_id = ? AND status = 'active'",
                (benchmark_id,),
            )
            conn.commit()
            if cursor.rowcount > 0:
                logger.info("Retired benchmark %s", benchmark_id)
                return True
            logger.warning("Benchmark %s not found or not active", benchmark_id)
            return False

    def get_active_benchmarks(
        self, domain: Optional[str] = None
    ) -> list[GeneratedBenchmark]:
        """Return all active benchmarks, optionally filtered by domain.

        Args:
            domain: If provided, only return benchmarks for this domain.

        Returns:
            List of active GeneratedBenchmark objects.
        """
        with sqlite3.connect(self.db_path) as conn:
            if domain:
                rows = conn.execute(
                    "SELECT * FROM benchmarks WHERE status = 'active' AND domain = ? ORDER BY created_at DESC",
                    (domain,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM benchmarks WHERE status = 'active' ORDER BY created_at DESC"
                ).fetchall()
        return [self._load_benchmark(row) for row in rows]

    def get_benchmark_by_id(self, benchmark_id: str) -> Optional[GeneratedBenchmark]:
        """Retrieve a single benchmark by ID."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM benchmarks WHERE benchmark_id = ?",
                (benchmark_id,),
            ).fetchone()
        if row:
            return self._load_benchmark(row)
        return None

    def get_generator_stats(self) -> dict:
        """Return summary statistics for all generated benchmarks.

        Returns:
            Dict with total_generated, active, retired, deferred,
            and by_source breakdown.
        """
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM benchmarks").fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM benchmarks WHERE status = 'active'"
            ).fetchone()[0]
            retired = conn.execute(
                "SELECT COUNT(*) FROM benchmarks WHERE status = 'retired'"
            ).fetchone()[0]
            deferred = conn.execute(
                "SELECT COUNT(*) FROM benchmarks WHERE status = 'deferred'"
            ).fetchone()[0]

            by_source = {}
            for source in VALID_SOURCES:
                count = conn.execute(
                    "SELECT COUNT(*) FROM benchmarks WHERE generated_from = ?",
                    (source,),
                ).fetchone()[0]
                by_source[source] = count

        return {
            "total_generated": total,
            "active": active,
            "retired": retired,
            "deferred": deferred,
            "by_source": by_source,
        }
