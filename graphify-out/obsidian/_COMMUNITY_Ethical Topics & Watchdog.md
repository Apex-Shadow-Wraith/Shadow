---
type: community
cohesion: 0.03
members: 110
---

# Ethical Topics & Watchdog

**Cohesion:** 0.03 - loosely connected
**Members:** 110 nodes

## Members
- [[.__init__()_11]] - code - modules\cerberus\watchdog.py
- [[._heartbeat_loop()]] - code - modules\cerberus\watchdog.py
- [[._send_telegram_alert()]] - code - modules\cerberus\watchdog.py
- [[._write_heartbeat()]] - code - modules\cerberus\watchdog.py
- [[.increment_checks()]] - code - modules\cerberus\watchdog.py
- [[.lookup_ethical_guidance()]] - code - modules\cerberus\cerberus.py
- [[.on_cerberus_down()]] - code - modules\cerberus\watchdog.py
- [[.start()]] - code - modules\cerberus\watchdog.py
- [[.stop()]] - code - modules\cerberus\watchdog.py
- [[.test_clear_lock_removes_lockfile()]] - code - tests\test_watchdog.py
- [[.test_clear_lock_safe_when_no_lockfile()]] - code - tests\test_watchdog.py
- [[.test_corrupted_heartbeat_returns_false()]] - code - tests\test_watchdog.py
- [[.test_fresh_heartbeat_returns_healthy()]] - code - tests\test_watchdog.py
- [[.test_heartbeat_exactly_at_boundary()]] - code - tests\test_watchdog.py
- [[.test_heartbeat_just_past_boundary()]] - code - tests\test_watchdog.py
- [[.test_heartbeat_reflects_check_id()]] - code - tests\test_watchdog.py
- [[.test_is_locked_returns_false_when_no_lockfile()]] - code - tests\test_watchdog.py
- [[.test_is_locked_returns_true_when_lockfile_exists()]] - code - tests\test_watchdog.py
- [[.test_missing_heartbeat_file_returns_false()]] - code - tests\test_watchdog.py
- [[.test_on_cerberus_down_creates_lockfile()]] - code - tests\test_watchdog.py
- [[.test_on_cerberus_down_lockfile_has_metadata()]] - code - tests\test_watchdog.py
- [[.test_on_cerberus_down_sends_telegram()]] - code - tests\test_watchdog.py
- [[.test_on_cerberus_down_writes_emergency_log()]] - code - tests\test_watchdog.py
- [[.test_send_heartbeat_writes_file()]] - code - tests\test_watchdog.py
- [[.test_stale_heartbeat_detected_as_down()]] - code - tests\test_watchdog.py
- [[A corrupted heartbeat file should be treated as failure.]] - rationale - tests\test_watchdog.py
- [[A heartbeat at 91s should be detected as stale.]] - rationale - tests\test_watchdog.py
- [[A heartbeat at exactly 89s should still be considered fresh.]] - rationale - tests\test_watchdog.py
- [[A heartbeat older than 90s should be detected as down.]] - rationale - tests\test_watchdog.py
- [[A heartbeat written just now should be detected as healthy.]] - rationale - tests\test_watchdog.py
- [[Atomic write of heartbeat JSON.]] - rationale - modules\cerberus\watchdog.py
- [[Attempt to kill the Shadow main process.]] - rationale - scripts\watchdog_cerberus.py
- [[Cerberus External Watchdog — Standalone Monitoring Script ======================]] - rationale - scripts\watchdog_cerberus.py
- [[Cerberus Watchdog — Heartbeat Monitoring and Emergency Lockdown ================]] - rationale - modules\cerberus\watchdog.py
- [[Check if Cerberus heartbeat is fresh.      Returns True if Cerberus is alive, Fa]] - rationale - scripts\watchdog_cerberus.py
- [[Create a Cerberus instance with a temporary SQLite database.]] - rationale - tests\test_false_positive.py
- [[Create a CerberusWatchdog with test paths.]] - rationale - tests\test_watchdog.py
- [[Create a HeartbeatWriter with fast interval for testing.]] - rationale - tests\test_watchdog.py
- [[Create temp limits and ethics files, return initialized Cerberus.]] - rationale - tests\test_ethical_topics.py
- [[Each heartbeat should have a unique check ID.]] - rationale - tests\test_watchdog.py
- [[Emergency response when Cerberus is detected as down.          Creates a lockfil]] - rationale - modules\cerberus\watchdog.py
- [[Full emergency response when Cerberus is down.]] - rationale - scripts\watchdog_cerberus.py
- [[HeartbeatWriter]] - code - modules\cerberus\watchdog.py
- [[Helper to write a heartbeat file for testing.]] - rationale - tests\test_watchdog.py
- [[Increment the checks counter. Called by Cerberus after each safety check.]] - rationale - modules\cerberus\watchdog.py
- [[Load environment variables from .env file._1]] - rationale - scripts\watchdog_cerberus.py
- [[Load environment variables from .env file.]] - rationale - modules\cerberus\watchdog.py
- [[Lockfile should contain structured data about the failure.]] - rationale - tests\test_watchdog.py
- [[Main heartbeat loop. Runs in background thread.]] - rationale - modules\cerberus\watchdog.py
- [[Main watchdog loop. Runs forever.]] - rationale - scripts\watchdog_cerberus.py
- [[No heartbeat file at all means Cerberus never started.]] - rationale - tests\test_watchdog.py
- [[Provide isolated paths for watchdog testing.]] - rationale - tests\test_watchdog.py
- [[Send emergency alert via Telegram bot.]] - rationale - scripts\watchdog_cerberus.py
- [[Send emergency alert via Telegram bot. Best-effort.]] - rationale - modules\cerberus\watchdog.py
- [[Start the heartbeat background thread.]] - rationale - modules\cerberus\watchdog.py
- [[Stop the heartbeat thread and write a final 'stopped' heartbeat.]] - rationale - modules\cerberus\watchdog.py
- [[Test heartbeat checking.]] - rationale - tests\test_watchdog.py
- [[Test lockfile creation, detection, and clearing.]] - rationale - tests\test_watchdog.py
- [[Test orchestrator integration (lockfile blocks requests).]] - rationale - tests\test_watchdog.py
- [[Test that Cerberus.send_heartbeat() writes correct data.]] - rationale - tests\test_watchdog.py
- [[TestCerberusHeartbeatIntegration]] - code - tests\test_watchdog.py
- [[TestCerberusWatchdogHeartbeat]] - code - tests\test_watchdog.py
- [[TestCerberusWatchdogLockfile]] - code - tests\test_watchdog.py
- [[TestCerberusWatchdogOrchestrator]] - code - tests\test_watchdog.py
- [[TestEthicalGuidanceLookup]] - code - tests\test_ethical_topics.py
- [[TestEthicalTopicsLoading]] - code - tests\test_ethical_topics.py
- [[Tests for Cerberus Watchdog System ===================================== Tests b]] - rationale - tests\test_watchdog.py
- [[Tests for Ethical Topics Integration in Cerberus ===============================]] - rationale - tests\test_ethical_topics.py
- [[The orchestrator should refuse all input when locked.]] - rationale - tests\test_watchdog.py
- [[Writes periodic heartbeat files for external monitoring.      The heartbeat is a]] - rationale - modules\cerberus\watchdog.py
- [[_load_env()]] - code - modules\cerberus\watchdog.py
- [[_write_heartbeat()]] - code - tests\test_watchdog.py
- [[cerberus()_3]] - code - tests\test_ethical_topics.py
- [[cerberus_with_db()]] - code - tests\test_false_positive.py
- [[check_heartbeat()]] - code - scripts\watchdog_cerberus.py
- [[checks_performed()]] - code - modules\cerberus\watchdog.py
- [[clear_lock must remove the lockfile.]] - rationale - tests\test_watchdog.py
- [[clear_lock should not crash if there's nothing to clear.]] - rationale - tests\test_watchdog.py
- [[clear_lock()]] - code - modules\cerberus\watchdog.py
- [[emergency_response()]] - code - scripts\watchdog_cerberus.py
- [[ethics_setup()]] - code - tests\test_ethical_topics.py
- [[heartbeat()]] - code - tests\test_watchdog.py
- [[is_locked should return False when there's no lockfile.]] - rationale - tests\test_watchdog.py
- [[is_locked should return True when the lockfile exists.]] - rationale - tests\test_watchdog.py
- [[is_locked()]] - code - modules\cerberus\watchdog.py
- [[is_running()]] - code - modules\cerberus\watchdog.py
- [[kill_shadow_process()]] - code - scripts\watchdog_cerberus.py
- [[load_env()]] - code - scripts\watchdog_cerberus.py
- [[main()_6]] - code - scripts\watchdog_cerberus.py
- [[on_cerberus_down must create the lockfile.]] - rationale - tests\test_watchdog.py
- [[on_cerberus_down must write to the emergency shutdown log.]] - rationale - tests\test_watchdog.py
- [[on_cerberus_down should attempt to send a Telegram alert.]] - rationale - tests\test_watchdog.py
- [[send_heartbeat should create a heartbeat file with correct fields.]] - rationale - tests\test_watchdog.py
- [[send_telegram_alert()]] - code - scripts\watchdog_cerberus.py
- [[test_case_insensitive()]] - code - tests\test_ethical_topics.py
- [[test_description_match()]] - code - tests\test_ethical_topics.py
- [[test_ethical_topics.py]] - code - tests\test_ethical_topics.py
- [[test_exact_name_match()]] - code - tests\test_ethical_topics.py
- [[test_graceful_without_file()]] - code - tests\test_ethical_topics.py
- [[test_keyword_match()]] - code - tests\test_ethical_topics.py
- [[test_loads_topics()]] - code - tests\test_ethical_topics.py
- [[test_no_match_returns_empty()]] - code - tests\test_ethical_topics.py
- [[test_orchestrator_rejects_when_locked()]] - code - tests\test_watchdog.py
- [[test_sorted_by_weight()]] - code - tests\test_ethical_topics.py
- [[test_via_execute()]] - code - tests\test_ethical_topics.py
- [[test_watchdog.py]] - code - tests\test_watchdog.py
- [[watchdog()]] - code - tests\test_watchdog.py
- [[watchdog.py]] - code - modules\cerberus\watchdog.py
- [[watchdog_cerberus.py]] - code - scripts\watchdog_cerberus.py
- [[watchdog_paths()]] - code - tests\test_watchdog.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Ethical_Topics_&_Watchdog
SORT file.name ASC
```

## Connections to other communities
- 46 edges to [[_COMMUNITY_Base Module & Apex API]]
- 35 edges to [[_COMMUNITY_Async Task Queue]]
- 7 edges to [[_COMMUNITY_Module Lifecycle]]
- 4 edges to [[_COMMUNITY_Introspection Dashboard]]
- 4 edges to [[_COMMUNITY_Data Pipeline & Embeddings]]
- 3 edges to [[_COMMUNITY_Ethics Engine (Cerberus)]]
- 2 edges to [[_COMMUNITY_Module Registry & Tools]]
- 1 edge to [[_COMMUNITY_Code Analyzer (Omen)]]

## Top bridge nodes
- [[cerberus()_3]] - degree 15, connects to 5 communities
- [[HeartbeatWriter]] - degree 42, connects to 3 communities
- [[TestCerberusWatchdogLockfile]] - degree 13, connects to 2 communities
- [[TestCerberusWatchdogHeartbeat]] - degree 11, connects to 2 communities
- [[TestCerberusHeartbeatIntegration]] - degree 8, connects to 2 communities