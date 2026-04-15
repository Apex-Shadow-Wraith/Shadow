---
source_file: "modules\shadow\standing_tasks.py"
type: "code"
community: "Module Registry & Tools"
location: "L43"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Module_Registry_&_Tools
---

# StandingTaskScheduler

## Connections
- [[.__init__()_88]] - `method` [EXTRACTED]
- [[._marshal()]] - `method` [EXTRACTED]
- [[._run_grimoire_stats()]] - `method` [EXTRACTED]
- [[._run_self_analysis()]] - `method` [EXTRACTED]
- [[._run_standing_research()]] - `method` [EXTRACTED]
- [[.get_schedule_info()]] - `method` [EXTRACTED]
- [[.run_task()]] - `method` [EXTRACTED]
- [[.start()_5]] - `method` [EXTRACTED]
- [[.stop()_4]] - `method` [EXTRACTED]
- [[.test_creates_without_errors()]] - `calls` [INFERRED]
- [[.test_custom_research_topics()]] - `calls` [INFERRED]
- [[.test_failed_task_does_not_crash_scheduler()]] - `calls` [INFERRED]
- [[.test_missing_module_reports_failure()]] - `calls` [INFERRED]
- [[.test_no_marshaling_needed()]] - `calls` [INFERRED]
- [[.test_works_without_event_loop()]] - `calls` [INFERRED]
- [[A task failure updates status but doesn't propagate exceptions.]] - `uses` [INFERRED]
- [[After a task runs, schedule info shows the execution time.]] - `uses` [INFERRED]
- [[All defined task names are accepted by run_task.]] - `uses` [INFERRED]
- [[All tasks start with 'never run' status.]] - `uses` [INFERRED]
- [[Configure logging. Every interaction is logged from day one.]] - `uses` [INFERRED]
- [[Create, wire, and initialize everything in the right order.      Dependency chai]] - `uses` [INFERRED]
- [[Custom research topics override defaults.]] - `uses` [INFERRED]
- [[Default research topics match the module constant.]] - `uses` [INFERRED]
- [[Detect if user is asking about a previous task's results.      Returns the task]] - `uses` [INFERRED]
- [[Grimoire stats collects data and stores a health summary.]] - `uses` [INFERRED]
- [[Handle slash commands. Returns True if handled, False otherwise.]] - `uses` [INFERRED]
- [[Helper create a loop, set it on the scheduler, run a task synchronously.]] - `uses` [INFERRED]
- [[Import a module class, returning None on failure.]] - `uses` [INFERRED]
- [[Load master configuration.]] - `uses` [INFERRED]
- [[Main entry point. Load config, start Shadow, run the loop.]] - `uses` [INFERRED]
- [[Manages recurring background tasks via APScheduler.]] - `rationale_for` [EXTRACTED]
- [[Minimal module mock that tracks execute calls.]] - `uses` [INFERRED]
- [[MockModule_2]] - `uses` [INFERRED]
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[Provide a running event loop for marshaling.]] - `uses` [INFERRED]
- [[Registry with mock omen, reaper, and grimoire modules.]] - `uses` [INFERRED]
- [[Return the closest known command for cmd_body, or None.      cmd_body is the]] - `uses` [INFERRED]
- [[Scheduler initializes cleanly with a registry.]] - `uses` [INFERRED]
- [[Scheduler starts and stops without errors.]] - `uses` [INFERRED]
- [[Search Grimoire for a persisted async task result by task ID prefix.      Return]] - `uses` [INFERRED]
- [[Self-analysis calls Omen and stores result in Grimoire.]] - `uses` [INFERRED]
- [[Shadow — Main Entry Point =========================== Run this to start Shadow]] - `uses` [INFERRED]
- [[Standing research calls Reaper and stores result in Grimoire.]] - `uses` [INFERRED]
- [[StandingTaskScheduler with mocked registry, not started.]] - `uses` [INFERRED]
- [[Stopping a never-started scheduler doesn't raise.]] - `uses` [INFERRED]
- [[Strip GIN log noise and other leading garbage from user input.      Ollama's GIN]] - `uses` [INFERRED]
- [[Tasks fail gracefully when a required module is missing.]] - `uses` [INFERRED]
- [[TestFailureHandling_1]] - `uses` [INFERRED]
- [[TestGetScheduleInfo]] - `uses` [INFERRED]
- [[TestGrimoireStats_1]] - `uses` [INFERRED]
- [[TestGrimoireStatsNoEventLoop]] - `uses` [INFERRED]
- [[TestRunTask]] - `uses` [INFERRED]
- [[TestSchedulerInit]] - `uses` [INFERRED]
- [[TestSchedulerLifecycle]] - `uses` [INFERRED]
- [[TestSelfAnalysis]] - `uses` [INFERRED]
- [[TestStandingResearch]] - `uses` [INFERRED]
- [[Tests for StandingTaskScheduler — APScheduler-based recurring background tasks.]] - `uses` [INFERRED]
- [[Topics rotate through the list on successive runs.]] - `uses` [INFERRED]
- [[Verify grimoire_stats runs without an event loop (pure sync path).]] - `uses` [INFERRED]
- [[get_schedule_info returns a formatted string with all tasks.]] - `uses` [INFERRED]
- [[grimoire_stats never calls _marshal (no async dependency).]] - `uses` [INFERRED]
- [[grimoire_stats succeeds even when no event loop is set.]] - `uses` [INFERRED]
- [[main()]] - `calls` [INFERRED]
- [[run_task with invalid name returns error message, doesn't crash.]] - `uses` [INFERRED]
- [[scheduler()]] - `calls` [INFERRED]
- [[standing_tasks.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Module_Registry_&_Tools