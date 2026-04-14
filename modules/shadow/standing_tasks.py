"""
Standing Tasks — APScheduler-based recurring background tasks.
================================================================
Provides time-based scheduling for Shadow's autonomous operations:
  - Self-analysis (every 6 hours)
  - Standing research (every 12 hours)
  - Grimoire stats (daily at 5:00 AM)

Uses BackgroundScheduler so the CLI input loop is never blocked.
All module calls are marshaled back to the main asyncio event loop
to respect SQLite's check_same_thread constraint.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler

from modules.base import ModuleRegistry

logger = logging.getLogger("shadow.standing_tasks")

# Default topics for standing research — rotate through these.
DEFAULT_RESEARCH_TOPICS: list[str] = [
    "ollama updates",
    "llama.cpp updates",
    "RTX 5090 pricing",
]

# Task definitions: name → (description, interval description)
TASK_DEFS: dict[str, tuple[str, str]] = {
    "self_analysis": ("Omen codebase self-analysis", "every 6h"),
    "standing_research": ("Reaper web research on standing topics", "every 12h"),
    "grimoire_stats": ("Grimoire database health snapshot", "daily 5:00 AM"),
}


class StandingTaskScheduler:
    """Manages recurring background tasks via APScheduler."""

    def __init__(
        self,
        registry: ModuleRegistry,
        task_logger: logging.Logger | None = None,
        research_topics: list[str] | None = None,
    ) -> None:
        self._registry = registry
        self._logger = task_logger or logger
        self._scheduler = BackgroundScheduler(daemon=True)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._research_topics = research_topics or list(DEFAULT_RESEARCH_TOPICS)
        self._topic_index: int = 0

        # Tracking state
        self._last_run: dict[str, datetime | None] = {k: None for k in TASK_DEFS}
        self._last_status: dict[str, str] = {k: "never run" for k in TASK_DEFS}

    # ── Lifecycle ───────────────────────────────────────────────

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        """Start the scheduler. Must be called from an async context."""
        self._loop = loop

        self._scheduler.add_job(
            self._run_self_analysis,
            "interval",
            hours=6,
            id="self_analysis",
            name="Self-Analysis",
            misfire_grace_time=300,
        )
        self._scheduler.add_job(
            self._run_standing_research,
            "interval",
            hours=12,
            id="standing_research",
            name="Standing Research",
            misfire_grace_time=300,
        )
        self._scheduler.add_job(
            self._run_grimoire_stats,
            "cron",
            hour=5,
            minute=0,
            id="grimoire_stats",
            name="Grimoire Stats",
            misfire_grace_time=300,
        )

        self._scheduler.start()
        print(
            "Standing tasks active: self_analysis (6h), "
            "research (12h), grimoire_stats (daily 5AM)"
        )
        self._logger.info("StandingTaskScheduler started with %d jobs", len(TASK_DEFS))

    def stop(self) -> None:
        """Shut down the scheduler gracefully."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            self._logger.info("StandingTaskScheduler stopped")

    # ── Manual trigger ──────────────────────────────────────────

    def run_task(self, task_name: str) -> str:
        """Manually trigger a standing task by name. Returns status message."""
        runners = {
            "self_analysis": self._run_self_analysis,
            "standing_research": self._run_standing_research,
            "grimoire_stats": self._run_grimoire_stats,
        }
        runner = runners.get(task_name)
        if runner is None:
            valid = ", ".join(runners.keys())
            return f"Unknown task: '{task_name}'. Valid tasks: {valid}"

        runner()
        status = self._last_status.get(task_name, "unknown")
        return f"Task '{task_name}' executed. Status: {status}"

    # ── Schedule info ───────────────────────────────────────────

    def get_schedule_info(self) -> str:
        """Return a formatted summary of all standing tasks."""
        lines = ["\n--- Standing Tasks ---"]
        for name, (desc, interval) in TASK_DEFS.items():
            last = self._last_run.get(name)
            last_str = last.strftime("%Y-%m-%d %H:%M:%S") if last else "never"
            status = self._last_status.get(name, "unknown")
            lines.append(f"  {name:<20s} {interval:<14s} last: {last_str}  [{status}]")
            lines.append(f"    {desc}")

        # Next fire times from APScheduler
        jobs = self._scheduler.get_jobs() if self._scheduler.running else []
        if jobs:
            lines.append("\n  Next scheduled runs:")
            for job in jobs:
                next_run = job.next_run_time
                next_str = next_run.strftime("%Y-%m-%d %H:%M:%S") if next_run else "paused"
                lines.append(f"    {job.id:<20s} → {next_str}")

        lines.append("")
        return "\n".join(lines)

    # ── Task implementations ────────────────────────────────────
    # Each runs in APScheduler's thread pool. All module/Grimoire
    # calls are dispatched to the main event loop to avoid SQLite
    # check_same_thread errors.

    def _marshal(self, coro: Any, timeout: float = 300) -> Any:
        """Run a coroutine on the main event loop from a background thread."""
        if self._loop is None or self._loop.is_closed():
            raise RuntimeError("Event loop not available for standing task")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def _run_self_analysis(self) -> None:
        """Execute Omen's code_analyze_self and store results in Grimoire."""
        task_name = "self_analysis"
        self._logger.info("Standing task starting: %s", task_name)
        try:
            async def _do() -> dict:
                omen = self._registry.get_module("omen")
                if omen is None:
                    raise RuntimeError("Omen module not available")
                result = await omen.execute("code_analyze_self", {})
                if not result.success:
                    raise RuntimeError(f"code_analyze_self failed: {result.error}")

                grimoire_mod = self._registry.get_module("grimoire")
                if grimoire_mod is not None:
                    grim = getattr(grimoire_mod, "_grimoire", None)
                    if grim is not None:
                        grim.remember(
                            content=json.dumps(result.content, default=str),
                            source="standing_task",
                            source_module="omen",
                            category="self_analysis",
                            trust_level=0.9,
                            tags=["standing_task", "self_analysis", "automated"],
                            metadata={
                                "task": task_name,
                                "timestamp": datetime.now().isoformat(),
                            },
                            check_duplicates=False,
                        )
                return result.content

            self._marshal(_do())
            self._last_run[task_name] = datetime.now()
            self._last_status[task_name] = "success"
            self._logger.info("Standing task completed: %s", task_name)
        except Exception as e:
            self._last_run[task_name] = datetime.now()
            self._last_status[task_name] = f"failed: {e}"
            self._logger.error(
                "Standing task failed: %s — %s", task_name, e, exc_info=True
            )

    def _run_standing_research(self) -> None:
        """Pick the next research topic, search via Reaper, store in Grimoire."""
        task_name = "standing_research"
        topic = self._research_topics[self._topic_index % len(self._research_topics)]
        self._topic_index += 1
        self._logger.info("Standing task starting: %s (topic: %s)", task_name, topic)
        try:
            async def _do() -> list:
                reaper = self._registry.get_module("reaper")
                if reaper is None:
                    raise RuntimeError("Reaper module not available")
                result = await reaper.execute(
                    "web_search", {"query": topic, "max_results": 5}
                )
                if not result.success:
                    raise RuntimeError(f"web_search failed: {result.error}")

                grimoire_mod = self._registry.get_module("grimoire")
                if grimoire_mod is not None:
                    grim = getattr(grimoire_mod, "_grimoire", None)
                    if grim is not None:
                        summary = json.dumps(result.content, default=str)
                        grim.remember(
                            content=f"Standing research: {topic}\n\n{summary}",
                            source="standing_task",
                            source_module="reaper",
                            category="standing_research",
                            trust_level=0.3,
                            tags=["standing_task", "research", topic.replace(" ", "_")],
                            metadata={
                                "task": task_name,
                                "topic": topic,
                                "timestamp": datetime.now().isoformat(),
                            },
                            check_duplicates=False,
                        )
                return result.content

            self._marshal(_do())
            self._last_run[task_name] = datetime.now()
            self._last_status[task_name] = f"success (topic: {topic})"
            self._logger.info("Standing task completed: %s", task_name)
        except Exception as e:
            self._last_run[task_name] = datetime.now()
            self._last_status[task_name] = f"failed: {e}"
            self._logger.error(
                "Standing task failed: %s — %s", task_name, e, exc_info=True
            )

    def _run_grimoire_stats(self) -> None:
        """Collect Grimoire database stats and store a health summary."""
        task_name = "grimoire_stats"
        self._logger.info("Standing task starting: %s", task_name)
        try:
            async def _do() -> dict:
                grimoire_mod = self._registry.get_module("grimoire")
                if grimoire_mod is None:
                    raise RuntimeError("Grimoire module not available")
                grim = getattr(grimoire_mod, "_grimoire", None)
                if grim is None:
                    raise RuntimeError("Grimoire internal instance not available")

                stats = grim.stats()

                summary = (
                    f"Grimoire Health Report — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                    f"  Active memories: {stats.get('active_memories', 0)}\n"
                    f"  Inactive memories: {stats.get('inactive_memories', 0)}\n"
                    f"  Total stored: {stats.get('total_stored', 0)}\n"
                    f"  Vector count: {stats.get('vector_count', 0)}\n"
                    f"  Unique tags: {stats.get('unique_tags', 0)}\n"
                    f"  Corrections: {stats.get('corrections', 0)}\n"
                    f"  By category: {json.dumps(stats.get('by_category', {}))}\n"
                    f"  By source: {json.dumps(stats.get('by_source', {}))}"
                )

                grim.remember(
                    content=summary,
                    source="standing_task",
                    source_module="grimoire",
                    category="system_health",
                    trust_level=0.9,
                    tags=["standing_task", "grimoire_stats", "system_health"],
                    metadata={
                        "task": task_name,
                        "timestamp": datetime.now().isoformat(),
                        "raw_stats": stats,
                    },
                    check_duplicates=False,
                )
                return stats

            self._marshal(_do())
            self._last_run[task_name] = datetime.now()
            self._last_status[task_name] = "success"
            self._logger.info("Standing task completed: %s", task_name)
        except Exception as e:
            self._last_run[task_name] = datetime.now()
            self._last_status[task_name] = f"failed: {e}"
            self._logger.error(
                "Standing task failed: %s — %s", task_name, e, exc_info=True
            )
