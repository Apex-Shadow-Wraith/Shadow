---
source_file: "modules\shadow\ollama_supervisor.py"
type: "code"
community: "Introspection Dashboard"
location: "L23"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Introspection_Dashboard
---

# OllamaSupervisor

## Connections
- [[.__init__()_75]] - `method` [EXTRACTED]
- [[._monitor_loop()]] - `method` [EXTRACTED]
- [[._on_failure()]] - `method` [EXTRACTED]
- [[.get_status()_1]] - `method` [EXTRACTED]
- [[.health_check()]] - `method` [EXTRACTED]
- [[.restart_ollama()]] - `method` [EXTRACTED]
- [[.start()_3]] - `method` [EXTRACTED]
- [[.stop()_3]] - `method` [EXTRACTED]
- [[After max_retries restarts, verify supervisor stops trying and logs critical.]] - `uses` [INFERRED]
- [[Configure logging. Every interaction is logged from day one.]] - `uses` [INFERRED]
- [[Create a supervisor with a mocked Harbinger.]] - `uses` [INFERRED]
- [[Create a supervisor with short intervals for testing.]] - `uses` [INFERRED]
- [[Create, wire, and initialize everything in the right order.      Dependency chai]] - `uses` [INFERRED]
- [[Detect if user is asking about a previous task's results.      Returns the task]] - `uses` [INFERRED]
- [[Handle slash commands. Returns True if handled, False otherwise.]] - `uses` [INFERRED]
- [[Import a module class, returning None on failure.]] - `uses` [INFERRED]
- [[Load master configuration.]] - `uses` [INFERRED]
- [[Main entry point. Load config, start Shadow, run the loop.]] - `uses` [INFERRED]
- [[Mock 3 consecutive failures, verify alert created.]] - `uses` [INFERRED]
- [[Mock connection error, verify returns False.]] - `uses` [INFERRED]
- [[Mock health check failing, verify restart attempted.]] - `uses` [INFERRED]
- [[Mock successful HTTP response, verify returns True.]] - `uses` [INFERRED]
- [[Monitors Ollama process health and restarts on failure.      Runs a background h]] - `rationale_for` [EXTRACTED]
- [[Return the closest known command for cmd_body, or None.      cmd_body is the]] - `uses` [INFERRED]
- [[Search Grimoire for a persisted async task result by task ID prefix.      Return]] - `uses` [INFERRED]
- [[Shadow — Main Entry Point =========================== Run this to start Shadow]] - `uses` [INFERRED]
- [[Starting twice should not create duplicate loops.]] - `uses` [INFERRED]
- [[Strip GIN log noise and other leading garbage from user input.      Ollama's GIN]] - `uses` [INFERRED]
- [[TestGetStatus]] - `uses` [INFERRED]
- [[TestHarbingerAlert]] - `uses` [INFERRED]
- [[TestHealthCheck]] - `uses` [INFERRED]
- [[TestRestart]] - `uses` [INFERRED]
- [[TestStartStop]] - `uses` [INFERRED]
- [[Tests for Harbinger alerting.]] - `uses` [INFERRED]
- [[Tests for get_status method.]] - `uses` [INFERRED]
- [[Tests for health_check method.]] - `uses` [INFERRED]
- [[Tests for restart behavior.]] - `uses` [INFERRED]
- [[Tests for startstop lifecycle._1]] - `uses` [INFERRED]
- [[Tests for the Ollama Supervisor module.]] - `uses` [INFERRED]
- [[Verify status dict has all required fields.]] - `uses` [INFERRED]
- [[Verify status updates after start.]] - `uses` [INFERRED]
- [[Verify supervisor starts and stops cleanly.]] - `uses` [INFERRED]
- [[main()]] - `calls` [INFERRED]
- [[ollama_supervisor.py]] - `contains` [EXTRACTED]
- [[supervisor()]] - `calls` [INFERRED]
- [[supervisor_with_harbinger()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Introspection_Dashboard