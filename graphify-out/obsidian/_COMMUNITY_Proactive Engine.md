---
type: community
cohesion: 0.04
members: 114
---

# Proactive Engine

**Cohesion:** 0.04 - loosely connected
**Members:** 114 nodes

## Members
- [[.__init__()_79]] - code - modules\shadow\proactive_engine.py
- [[.__init__()_80]] - code - modules\shadow\proactive_engine.py
- [[._auto_disable_spam()]] - code - modules\shadow\proactive_engine.py
- [[._build_default_triggers()]] - code - modules\shadow\proactive_engine.py
- [[._check_rate_limit()]] - code - modules\shadow\proactive_engine.py
- [[._check_schedule()]] - code - modules\shadow\proactive_engine.py
- [[._on_event_fired()]] - code - modules\shadow\proactive_engine.py
- [[.check_triggers()]] - code - modules\shadow\proactive_engine.py
- [[.disable_trigger()]] - code - modules\shadow\proactive_engine.py
- [[.emit_sync()]] - code - modules\shadow\proactive_engine.py
- [[.enable_trigger()]] - code - modules\shadow\proactive_engine.py
- [[.get_active_triggers()]] - code - modules\shadow\proactive_engine.py
- [[.idle_work_cycle()]] - code - modules\shadow\proactive_engine.py
- [[.load_triggers()]] - code - modules\shadow\proactive_engine.py
- [[.register_default_triggers()]] - code - modules\shadow\proactive_engine.py
- [[.register_trigger()]] - code - modules\shadow\proactive_engine.py
- [[.save_triggers()]] - code - modules\shadow\proactive_engine.py
- [[.stop_all_background()]] - code - modules\shadow\proactive_engine.py
- [[.subscribe()_1]] - code - modules\shadow\proactive_engine.py
- [[.test_auto_disable_spam_trigger()]] - code - tests\test_proactive_engine.py
- [[.test_bad_callback_doesnt_break_others()]] - code - tests\test_proactive_engine.py
- [[.test_condition_exception_is_caught()]] - code - tests\test_proactive_engine.py
- [[.test_condition_skipped_in_persistence()]] - code - tests\test_proactive_engine.py
- [[.test_default_triggers_have_valid_types()]] - code - tests\test_proactive_engine.py
- [[.test_disabled_trigger_does_not_fire()]] - code - tests\test_proactive_engine.py
- [[.test_does_not_fire_when_condition_false()]] - code - tests\test_proactive_engine.py
- [[.test_does_not_fire_when_not_due()]] - code - tests\test_proactive_engine.py
- [[.test_enable_disable_toggle()]] - code - tests\test_proactive_engine.py
- [[.test_event_trigger_subscribes_to_event_bus()]] - code - tests\test_proactive_engine.py
- [[.test_event_triggers_have_event_names()]] - code - tests\test_proactive_engine.py
- [[.test_event_without_subscribers_produces_no_tasks()]] - code - tests\test_proactive_engine.py
- [[.test_filter_by_module()_1]] - code - tests\test_proactive_engine.py
- [[.test_fire_history_persisted()]] - code - tests\test_proactive_engine.py
- [[.test_fires_immediately_if_never_fired()]] - code - tests\test_proactive_engine.py
- [[.test_fires_when_condition_true()]] - code - tests\test_proactive_engine.py
- [[.test_fires_when_interval_elapsed()]] - code - tests\test_proactive_engine.py
- [[.test_full_event_flow()]] - code - tests\test_proactive_engine.py
- [[.test_global_rate_limit()]] - code - tests\test_proactive_engine.py
- [[.test_max_frequency_prevents_rapid_fire()]] - code - tests\test_proactive_engine.py
- [[.test_no_subscribers()]] - code - tests\test_proactive_engine.py
- [[.test_parse_cron_time()]] - code - tests\test_proactive_engine.py
- [[.test_parse_cron_time_invalid()]] - code - tests\test_proactive_engine.py
- [[.test_parse_interval_hours()]] - code - tests\test_proactive_engine.py
- [[.test_parse_interval_invalid()]] - code - tests\test_proactive_engine.py
- [[.test_parse_interval_minutes()]] - code - tests\test_proactive_engine.py
- [[.test_parse_interval_seconds()]] - code - tests\test_proactive_engine.py
- [[.test_parse_interval_singular()]] - code - tests\test_proactive_engine.py
- [[.test_register_default_triggers()]] - code - tests\test_proactive_engine.py
- [[.test_register_default_triggers_idempotent()]] - code - tests\test_proactive_engine.py
- [[.test_register_returns_id()]] - code - tests\test_proactive_engine.py
- [[.test_report_structure()]] - code - tests\test_proactive_engine.py
- [[.test_resume_all_background()]] - code - tests\test_proactive_engine.py
- [[.test_returns_first_waterfall_task()]] - code - tests\test_proactive_engine.py
- [[.test_returns_none_when_stopped()]] - code - tests\test_proactive_engine.py
- [[.test_save_and_load()]] - code - tests\test_proactive_engine.py
- [[.test_schedule_triggers_have_valid_schedules()]] - code - tests\test_proactive_engine.py
- [[.test_stop_all_background()]] - code - tests\test_proactive_engine.py
- [[.test_subscribe_and_emit()]] - code - tests\test_proactive_engine.py
- [[.test_task_dict_has_required_fields()]] - code - tests\test_proactive_engine.py
- [[.test_unregister_nonexistent_is_noop()]] - code - tests\test_proactive_engine.py
- [[.test_unregister_removes_trigger()]] - code - tests\test_proactive_engine.py
- [[.test_unsubscribe()]] - code - tests\test_proactive_engine.py
- [[.unregister_trigger()]] - code - modules\shadow\proactive_engine.py
- [[.unsubscribe()_1]] - code - modules\shadow\proactive_engine.py
- [[A condition that causes a module to initiate work autonomously.]] - rationale - modules\shadow\proactive_engine.py
- [[Build the full set of default triggers for all 13 modules.]] - rationale - modules\shadow\proactive_engine.py
- [[Called by EventSystem when a subscribed event emits.]] - rationale - modules\shadow\proactive_engine.py
- [[Check all triggers and return task dicts for those that fire.          Called by]] - rationale - modules\shadow\proactive_engine.py
- [[Disable a trigger if it fires  spam_threshold times per hour.          Returns]] - rationale - modules\shadow\proactive_engine.py
- [[Disable a trigger without removing it.]] - rationale - modules\shadow\proactive_engine.py
- [[Event fires → trigger activates → task dict produced.]] - rationale - tests\test_proactive_engine.py
- [[List all enabled triggers, optionally filtered by module.]] - rationale - modules\shadow\proactive_engine.py
- [[Load triggers and fire history from JSON.]] - rationale - modules\shadow\proactive_engine.py
- [[Match the real EventSystem's subscribe signature.]] - rationale - modules\shadow\proactive_engine.py
- [[Match the real EventSystem's unsubscribe signature.]] - rationale - modules\shadow\proactive_engine.py
- [[Minimal pubsub used when ``modules.shadow.events.EventSystem`` is     not wired]] - rationale - modules\shadow\proactive_engine.py
- [[Parse 'cron HHMM' → (hour, minute), or None.]] - rationale - modules\shadow\proactive_engine.py
- [[Parse 'every N hoursminutesseconds' → total seconds, or None.]] - rationale - modules\shadow\proactive_engine.py
- [[Persist triggers and fire history to JSON.]] - rationale - modules\shadow\proactive_engine.py
- [[Proactive Initiative System — Shadow's Autonomous Work Engine ==================]] - rationale - modules\shadow\proactive_engine.py
- [[ProactiveTrigger]] - code - modules\shadow\proactive_engine.py
- [[Re-enable a disabled trigger.]] - rationale - modules\shadow\proactive_engine.py
- [[Register a trigger.  Subscribes event triggers to the EventSystem.]] - rationale - modules\shadow\proactive_engine.py
- [[Register the standard set of triggers for all modules.          Idempotent trig]] - rationale - modules\shadow\proactive_engine.py
- [[Remove a trigger and unsubscribe from events if applicable.]] - rationale - modules\shadow\proactive_engine.py
- [[Return True if a schedule trigger is due to fire.]] - rationale - modules\shadow\proactive_engine.py
- [[Return True if under the global rate limit (fires per hour).]] - rationale - modules\shadow\proactive_engine.py
- [[Return the highest-priority idle task, or None if nothing to do.          Called]] - rationale - modules\shadow\proactive_engine.py
- [[Stop all proactive work.  Creator command 'stop all background work'.]] - rationale - modules\shadow\proactive_engine.py
- [[Synchronous emit for the proactive engine's internal use.]] - rationale - modules\shadow\proactive_engine.py
- [[TestBackgroundControl]] - code - tests\test_proactive_engine.py
- [[TestConditionTriggers]] - code - tests\test_proactive_engine.py
- [[TestDefaultTriggers]] - code - tests\test_proactive_engine.py
- [[TestDisabledTriggers]] - code - tests\test_proactive_engine.py
- [[TestEventIntegration]] - code - tests\test_proactive_engine.py
- [[TestGetActiveTriggers]] - code - tests\test_proactive_engine.py
- [[TestIdleWorkCycle]] - code - tests\test_proactive_engine.py
- [[TestInitiativeReport]] - code - tests\test_proactive_engine.py
- [[TestLightEventBus]] - code - tests\test_proactive_engine.py
- [[TestMaxFrequency]] - code - tests\test_proactive_engine.py
- [[TestPersistence_3]] - code - tests\test_proactive_engine.py
- [[TestRateLimiting]] - code - tests\test_proactive_engine.py
- [[TestScheduleParsing]] - code - tests\test_proactive_engine.py
- [[TestScheduleTriggers]] - code - tests\test_proactive_engine.py
- [[TestTaskDictShape]] - code - tests\test_proactive_engine.py
- [[TestTriggerRegistration]] - code - tests\test_proactive_engine.py
- [[Tests for ProactiveEngine — trigger-based initiative system.]] - rationale - tests\test_proactive_engine.py
- [[_LightEventBus]] - code - modules\shadow\proactive_engine.py
- [[_parse_cron_time()]] - code - modules\shadow\proactive_engine.py
- [[_parse_interval_seconds()]] - code - modules\shadow\proactive_engine.py
- [[engine()_1]] - code - tests\test_proactive_engine.py
- [[event_bus()]] - code - tests\test_proactive_engine.py
- [[proactive_engine.py]] - code - modules\shadow\proactive_engine.py
- [[test_proactive_engine.py]] - code - tests\test_proactive_engine.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Proactive_Engine
SORT file.name ASC
```

## Connections to other communities
- 53 edges to [[_COMMUNITY_Async Task Queue]]
- 6 edges to [[_COMMUNITY_Module Lifecycle]]
- 2 edges to [[_COMMUNITY_Adversarial Sparring]]

## Top bridge nodes
- [[.register_trigger()]] - degree 30, connects to 2 communities
- [[.check_triggers()]] - degree 27, connects to 2 communities
- [[.register_default_triggers()]] - degree 11, connects to 2 communities
- [[.load_triggers()]] - degree 7, connects to 2 communities
- [[.stop_all_background()]] - degree 7, connects to 2 communities