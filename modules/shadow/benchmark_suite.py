"""
Monthly Benchmark Suite — Objective Capability Measurement
============================================================
Measures Shadow's capabilities across task categories and tracks
improvement over time. This is the objective measure of whether
LoRA fine-tuning and Grimoire learning are actually making Shadow
smarter.

60 deterministic tasks across 10 categories, scored by rule-based
rubrics (no LLM judge needed). Includes 5 multi-turn conversation
continuity tasks that test context retention across follow-ups.
Results are saved as JSON for historical comparison and trend analysis.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("shadow.benchmark_suite")

# Root paths
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_BENCHMARKS_DIR = _PROJECT_ROOT / "benchmarks"
_TASKS_FILE = _BENCHMARKS_DIR / "benchmark_tasks.json"


class BenchmarkSuite:
    """Automated benchmark system for measuring Shadow's capabilities.

    Loads a fixed set of 60 benchmark tasks, runs them through the
    orchestrator, scores responses with rule-based rubrics, and
    tracks improvement over time.
    """

    def __init__(self, orchestrator: Any, config: dict | None = None):
        """Initialise the benchmark suite.

        Args:
            orchestrator: Shadow orchestrator instance for running tasks.
            config: Optional configuration dict with model_name, etc.
        """
        self.orchestrator = orchestrator
        self.config = config or {}
        self._benchmarks_dir = _BENCHMARKS_DIR
        self._tasks_file = _TASKS_FILE

    # ------------------------------------------------------------------
    # Loading tasks
    # ------------------------------------------------------------------

    def load_benchmark_set(self) -> list[dict]:
        """Load the deterministic benchmark tasks from JSON.

        Returns:
            List of 60 task dicts, each with id, input,
            expected_output_keywords, category, difficulty, rubric.

        Raises:
            FileNotFoundError: If benchmark_tasks.json is missing.
        """
        if not self._tasks_file.exists():
            raise FileNotFoundError(
                f"Benchmark tasks file not found: {self._tasks_file}"
            )
        with open(self._tasks_file, "r", encoding="utf-8") as f:
            tasks = json.load(f)

        # Validate required fields
        base_fields = {
            "id", "expected_output_keywords",
            "category", "difficulty", "rubric",
        }
        for task in tasks:
            missing = base_fields - set(task.keys())
            if missing:
                raise ValueError(
                    f"Task {task.get('id', '?')} missing fields: {missing}"
                )
            # Must have either 'input' (single-turn) or 'turns' (multi-turn)
            has_input = "input" in task
            has_turns = "turns" in task
            if not has_input and not has_turns:
                raise ValueError(
                    f"Task {task['id']} must have either 'input' or 'turns'"
                )
            if has_turns:
                turns = task["turns"]
                if not isinstance(turns, list) or len(turns) < 2:
                    raise ValueError(
                        f"Task {task['id']} 'turns' must be a list with at least 2 entries"
                    )
                for i, turn in enumerate(turns):
                    if "input" not in turn:
                        raise ValueError(
                            f"Task {task['id']} turn {i} missing 'input'"
                        )
        return tasks

    # ------------------------------------------------------------------
    # Running benchmarks
    # ------------------------------------------------------------------

    async def run_benchmark(self, tasks: list[dict] | None = None) -> dict:
        """Run all benchmark tasks through the orchestrator and score them.

        Args:
            tasks: Optional task list override. Loads from file if None.

        Returns:
            Dict with overall_score, category_scores, per_task_results,
            timestamp, model_info, and run duration.
        """
        if tasks is None:
            tasks = self.load_benchmark_set()

        run_start = time.time()
        per_task_results = []
        category_scores: dict[str, list[float]] = {}

        for task in tasks:
            task_start = time.time()

            if "turns" in task:
                # Multi-turn conversation continuity task
                result = await self._run_multi_turn_task(task)
            else:
                # Single-turn task
                try:
                    response = await self.orchestrator.process_input(
                        task["input"], source="benchmark"
                    )
                except Exception as e:
                    logger.error("Benchmark task %s failed: %s", task["id"], e)
                    response = f"[ERROR] {e}"

                # Capture routing decision for routing-type rubrics
                routed_module = None
                last_route = getattr(self.orchestrator, "_last_route", None)
                if last_route is not None:
                    routed_module = getattr(last_route, "target_module", None)

                score = self.score_response(response, task, routed_module=routed_module)
                result = {
                    "task_id": task["id"],
                    "category": task["category"],
                    "difficulty": task["difficulty"],
                    "input": task["input"],
                    "response": response,
                    "routed_module": routed_module,
                    "score": score,
                }

            task_duration = time.time() - task_start
            result["duration_seconds"] = round(task_duration, 3)
            per_task_results.append(result)

            category_scores.setdefault(task["category"], []).append(result["score"])

        # Aggregate scores
        all_scores = [r["score"] for r in per_task_results]
        overall_score = (
            sum(all_scores) / len(all_scores) if all_scores else 0.0
        )
        cat_averages = {
            cat: round(sum(scores) / len(scores), 4)
            for cat, scores in category_scores.items()
        }

        run_duration = time.time() - run_start
        model_info = self.config.get("model_name", "unknown")

        return {
            "overall_score": round(overall_score, 4),
            "category_scores": cat_averages,
            "per_task_results": per_task_results,
            "timestamp": datetime.now().isoformat(),
            "model_info": model_info,
            "total_tasks": len(tasks),
            "run_duration_seconds": round(run_duration, 3),
        }

    # ------------------------------------------------------------------
    # Multi-turn execution
    # ------------------------------------------------------------------

    async def _run_multi_turn_task(self, task: dict) -> dict:
        """Run a multi-turn conversation continuity task.

        Executes each turn sequentially, prepending prior turns as
        context for turn 2+. Scores only turns that have an evaluation
        rubric and returns the averaged score.

        Args:
            task: A task dict with a 'turns' list instead of 'input'.

        Returns:
            Result dict with task_id, category, difficulty, turns
            detail, and averaged score.
        """
        turns = task["turns"]
        history: list[dict[str, str]] = []  # {"user": ..., "shadow": ...}
        turn_results = []
        eval_scores = []

        for i, turn in enumerate(turns):
            user_input = turn["input"]

            # Build contextualised input for turn 2+
            if history:
                context_lines = ["[Previous conversation]"]
                for entry in history:
                    context_lines.append(f"User: {entry['user']}")
                    context_lines.append(f"Shadow: {entry['shadow']}")
                context_lines.append("[Current question]")
                context_lines.append(user_input)
                full_input = "\n".join(context_lines)
            else:
                full_input = user_input

            try:
                response = await self.orchestrator.process_input(
                    full_input, source="benchmark"
                )
            except Exception as e:
                logger.error(
                    "Benchmark task %s turn %d failed: %s",
                    task["id"], i, e,
                )
                response = f"[ERROR] {e}"

            history.append({"user": user_input, "shadow": response})

            # Score turns that have evaluation criteria
            turn_score = None
            if "evaluation" in turn:
                eval_task = {
                    "id": f"{task['id']}_turn{i}",
                    "rubric": turn["evaluation"],
                }
                turn_score = self.score_response(response, eval_task)
                eval_scores.append(turn_score)

            turn_results.append({
                "turn": i,
                "input": user_input,
                "response": response,
                "score": turn_score,
            })

        # Average across evaluated turns
        avg_score = (
            sum(eval_scores) / len(eval_scores) if eval_scores else 0.0
        )

        return {
            "task_id": task["id"],
            "category": task["category"],
            "difficulty": task["difficulty"],
            "input": " → ".join(t["input"] for t in turns),
            "response": turn_results[-1]["response"] if turn_results else "",
            "turns": turn_results,
            "score": round(avg_score, 4),
        }

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def score_response(
        self,
        response: str,
        task: dict,
        routed_module: str | None = None,
    ) -> float:
        """Score a single response 0.0–1.0 based on rule-based rubric.

        Scoring strategy depends on rubric type:
        - exact_answer: 1.0 if answer present, 0.0 otherwise
        - keyword: weighted keyword/phrase matching
        - code: keyword match + code structure checks
        - personality: keyword match + banned-phrase penalty
        - routing: checks the routed module against banned/allowed lists

        Args:
            response: The text response from the orchestrator.
            task: The benchmark task dict including rubric.
            routed_module: The module the router selected (for routing rubrics).

        Returns:
            Float score between 0.0 and 1.0.
        """
        rubric = task.get("rubric", {})
        rubric_type = rubric.get("type", "keyword")
        response_lower = response.lower()

        if rubric_type == "exact_answer":
            return self._score_exact(response, rubric)
        elif rubric_type == "code":
            return self._score_code(response, response_lower, rubric)
        elif rubric_type == "personality":
            return self._score_personality(response, response_lower, rubric)
        elif rubric_type == "routing":
            return self._score_routing(routed_module, rubric)
        else:
            # Default: keyword matching
            return self._score_keyword(response_lower, rubric)

    def _score_exact(self, response: str, rubric: dict) -> float:
        """Score exact-answer tasks. Answer must appear in response."""
        answer = rubric.get("answer", "")
        if not answer:
            return 0.0
        # Check if the answer appears in the response (case-insensitive)
        if answer.lower() in response.lower():
            return 1.0
        return 0.0

    def _score_keyword(self, response_lower: str, rubric: dict) -> float:
        """Score keyword-matching tasks.

        Components:
        - required_keywords: all must be present (weighted 0.6)
        - required_any: at least one must be present (weighted 0.2)
        - banned_phrases: deduct if present (weighted 0.2)
        """
        score = 0.0
        weights_used = 0.0

        # Required keywords (all must match)
        required = rubric.get("required_keywords", [])
        if required:
            matched = sum(
                1 for kw in required if kw.lower() in response_lower
            )
            score += 0.6 * (matched / len(required))
            weights_used += 0.6

        # Required any (at least one must match)
        required_any = rubric.get("required_any", [])
        if required_any:
            any_matched = any(
                kw.lower() in response_lower for kw in required_any
            )
            score += 0.2 * (1.0 if any_matched else 0.0)
            weights_used += 0.2

        # Banned phrases (penalty)
        banned = rubric.get("banned_phrases", [])
        if banned:
            has_banned = any(
                bp.lower() in response_lower for bp in banned
            )
            score += 0.2 * (0.0 if has_banned else 1.0)
            weights_used += 0.2

        # If no scoring criteria were defined, return 0
        if weights_used == 0.0:
            return 0.0

        # Normalise to 0–1 based on weights actually used
        return round(min(1.0, score / weights_used), 4)

    def _score_code(
        self, response: str, response_lower: str, rubric: dict,
    ) -> float:
        """Score code generation tasks.

        Components:
        - Keyword match (0.5 weight)
        - Code structure: contains def/class/import (0.3 weight)
        - Banned phrases absent (0.2 weight)
        """
        # Keyword component
        required = rubric.get("required_keywords", [])
        if required:
            kw_score = sum(
                1 for kw in required if kw.lower() in response_lower
            ) / len(required)
        else:
            kw_score = 0.0

        # Code structure component
        code_indicators = ["def ", "class ", "import ", "from "]
        has_code = any(ind in response for ind in code_indicators)
        code_score = 1.0 if has_code else 0.0

        # Banned phrases component
        banned = rubric.get("banned_phrases", [])
        if banned:
            has_banned = any(bp.lower() in response_lower for bp in banned)
            ban_score = 0.0 if has_banned else 1.0
        else:
            ban_score = 1.0

        return round(0.5 * kw_score + 0.3 * code_score + 0.2 * ban_score, 4)

    def _score_personality(
        self, response: str, response_lower: str, rubric: dict,
    ) -> float:
        """Score personality consistency tasks.

        Components:
        - Required keywords present (0.3 weight)
        - Required any present (0.2 weight)
        - Desired keywords present (0.1 weight — bonus)
        - Banned phrases absent (0.4 weight — heavy penalty)
        """
        score = 0.0

        # Required keywords
        required = rubric.get("required_keywords", [])
        if required:
            matched = sum(
                1 for kw in required if kw.lower() in response_lower
            )
            score += 0.3 * (matched / len(required))
        else:
            score += 0.3  # No requirement = full marks

        # Required any
        required_any = rubric.get("required_any", [])
        if required_any:
            any_matched = any(
                kw.lower() in response_lower for kw in required_any
            )
            score += 0.2 * (1.0 if any_matched else 0.0)
        else:
            score += 0.2

        # Desired keywords (bonus, not penalty for missing)
        desired = rubric.get("desired_keywords", [])
        if desired:
            desired_matched = sum(
                1 for kw in desired if kw.lower() in response_lower
            )
            score += 0.1 * (desired_matched / len(desired))
        else:
            score += 0.1

        # Banned phrases (heavy penalty)
        banned = rubric.get("banned_phrases", [])
        if banned:
            has_banned = any(bp.lower() in response_lower for bp in banned)
            score += 0.4 * (0.0 if has_banned else 1.0)
        else:
            score += 0.4

        return round(min(1.0, score), 4)

    def _score_routing(
        self, routed_module: str | None, rubric: dict,
    ) -> float:
        """Score adversarial routing tasks.

        Checks whether the router avoided misleading stem words and
        selected an appropriate module.

        Components:
        - banned_modules: must NOT route here (0.0 if hit, contributes 0.7)
        - allowed_modules: should route here (bonus 0.3 if matched)

        If only banned_modules is specified and the route avoids them,
        the task scores 1.0.

        Args:
            routed_module: The module the router selected, or None.
            rubric: Dict with banned_modules and optional allowed_modules.

        Returns:
            Float score between 0.0 and 1.0.
        """
        if routed_module is None:
            return 0.0

        module_lower = routed_module.lower()
        banned = [m.lower() for m in rubric.get("banned_modules", [])]
        allowed = [m.lower() for m in rubric.get("allowed_modules", [])]

        # Primary check: did the router avoid the banned module?
        if module_lower in banned:
            return 0.0

        # Router avoided the trap — base score earned
        if not allowed:
            # No allowed list specified; avoiding banned is full marks
            return 1.0

        # Bonus: did it land on one of the expected-correct modules?
        if module_lower in allowed:
            return 1.0

        # Avoided banned but landed somewhere unexpected — partial credit
        return 0.7

    # ------------------------------------------------------------------
    # Comparison and history
    # ------------------------------------------------------------------

    def compare_runs(self, run_a: dict, run_b: dict) -> dict:
        """Compare two benchmark runs, showing improvement/regression.

        Args:
            run_a: Earlier benchmark run results.
            run_b: Later benchmark run results.

        Returns:
            Dict with overall_delta, category_deltas, improved/regressed
            task lists, and summary.
        """
        overall_delta = run_b["overall_score"] - run_a["overall_score"]

        # Category deltas
        all_categories = set(
            list(run_a.get("category_scores", {}).keys())
            + list(run_b.get("category_scores", {}).keys())
        )
        category_deltas = {}
        for cat in sorted(all_categories):
            score_a = run_a.get("category_scores", {}).get(cat, 0.0)
            score_b = run_b.get("category_scores", {}).get(cat, 0.0)
            category_deltas[cat] = round(score_b - score_a, 4)

        # Per-task comparison
        tasks_a = {
            r["task_id"]: r["score"]
            for r in run_a.get("per_task_results", [])
        }
        tasks_b = {
            r["task_id"]: r["score"]
            for r in run_b.get("per_task_results", [])
        }
        all_task_ids = set(list(tasks_a.keys()) + list(tasks_b.keys()))

        improved = []
        regressed = []
        unchanged = []
        for tid in sorted(all_task_ids):
            sa = tasks_a.get(tid, 0.0)
            sb = tasks_b.get(tid, 0.0)
            delta = round(sb - sa, 4)
            if delta > 0.01:
                improved.append({"task_id": tid, "delta": delta, "from": sa, "to": sb})
            elif delta < -0.01:
                regressed.append({"task_id": tid, "delta": delta, "from": sa, "to": sb})
            else:
                unchanged.append(tid)

        # Summary
        direction = "improved" if overall_delta > 0.01 else (
            "regressed" if overall_delta < -0.01 else "unchanged"
        )
        summary = (
            f"Overall: {direction} by {abs(overall_delta):.2%} "
            f"({run_a['overall_score']:.2%} → {run_b['overall_score']:.2%}). "
            f"{len(improved)} tasks improved, {len(regressed)} regressed, "
            f"{len(unchanged)} unchanged."
        )

        return {
            "overall_delta": round(overall_delta, 4),
            "category_deltas": category_deltas,
            "improved": improved,
            "regressed": regressed,
            "unchanged": unchanged,
            "summary": summary,
            "run_a_timestamp": run_a.get("timestamp", "unknown"),
            "run_b_timestamp": run_b.get("timestamp", "unknown"),
        }

    def save_results(self, results: dict) -> str:
        """Save benchmark results to a dated JSON file.

        Args:
            results: The benchmark run results dict.

        Returns:
            String path to the saved file.
        """
        self._benchmarks_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        filepath = self._benchmarks_dir / f"benchmark_{date_str}.json"

        # If a file already exists for today, append a counter
        if filepath.exists():
            counter = 2
            while True:
                filepath = self._benchmarks_dir / f"benchmark_{date_str}_{counter}.json"
                if not filepath.exists():
                    break
                counter += 1

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        logger.info("Benchmark results saved to %s", filepath)
        return str(filepath)

    def load_history(self) -> list[dict]:
        """Load all past benchmark results for trend analysis.

        Returns:
            List of results dicts, sorted by timestamp ascending.
        """
        self._benchmarks_dir.mkdir(parents=True, exist_ok=True)
        history = []
        for fp in sorted(self._benchmarks_dir.glob("benchmark_*.json")):
            # Skip the tasks file
            if fp.name == "benchmark_tasks.json":
                continue
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Must have overall_score to be a valid result
                if "overall_score" in data:
                    data["_filepath"] = str(fp)
                    history.append(data)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Skipping corrupt benchmark file %s: %s", fp, e)

        # Sort by timestamp
        history.sort(key=lambda r: r.get("timestamp", ""))
        return history

    def trend_report(self) -> str:
        """Generate a text report showing score trends over time.

        Returns:
            Formatted string with per-category trends and overall score
            history. Returns a no-data message if no history exists.
        """
        history = self.load_history()
        if not history:
            return "No benchmark history found. Run /benchmark run first."

        lines = ["**Benchmark Trend Report**", ""]

        # Overall score timeline
        lines.append("**Overall Scores:**")
        for run in history:
            ts = run.get("timestamp", "unknown")[:10]
            model = run.get("model_info", "unknown")
            score = run["overall_score"]
            lines.append(f"  {ts}  {score:.2%}  ({model})")

        lines.append("")

        # Category trends (first vs. latest)
        if len(history) >= 2:
            first = history[0]
            latest = history[-1]
            lines.append(
                f"**Category Trends** (first run → latest run):"
            )
            all_cats = sorted(set(
                list(first.get("category_scores", {}).keys())
                + list(latest.get("category_scores", {}).keys())
            ))
            for cat in all_cats:
                s_first = first.get("category_scores", {}).get(cat, 0.0)
                s_latest = latest.get("category_scores", {}).get(cat, 0.0)
                delta = s_latest - s_first
                arrow = "↑" if delta > 0.01 else ("↓" if delta < -0.01 else "→")
                lines.append(
                    f"  {cat}: {s_first:.2%} → {s_latest:.2%} {arrow}"
                )
        elif len(history) == 1:
            lines.append("**Category Scores:**")
            for cat, score in sorted(
                history[0].get("category_scores", {}).items()
            ):
                lines.append(f"  {cat}: {score:.2%}")

        return "\n".join(lines)
