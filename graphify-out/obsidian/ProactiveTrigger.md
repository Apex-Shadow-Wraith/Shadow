---
source_file: "modules\shadow\proactive_engine.py"
type: "code"
community: "Proactive Engine"
location: "L86"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Proactive_Engine
---

# ProactiveTrigger

## Connections
- [[._build_default_triggers()]] - `calls` [EXTRACTED]
- [[.load_triggers()]] - `calls` [EXTRACTED]
- [[.test_auto_disable_spam_trigger()]] - `calls` [INFERRED]
- [[.test_condition_exception_is_caught()]] - `calls` [INFERRED]
- [[.test_condition_skipped_in_persistence()]] - `calls` [INFERRED]
- [[.test_disabled_trigger_does_not_fire()]] - `calls` [INFERRED]
- [[.test_does_not_fire_when_condition_false()]] - `calls` [INFERRED]
- [[.test_does_not_fire_when_not_due()]] - `calls` [INFERRED]
- [[.test_enable_disable_toggle()]] - `calls` [INFERRED]
- [[.test_event_trigger_subscribes_to_event_bus()]] - `calls` [INFERRED]
- [[.test_filter_by_module()_1]] - `calls` [INFERRED]
- [[.test_fire_history_persisted()]] - `calls` [INFERRED]
- [[.test_fires_immediately_if_never_fired()]] - `calls` [INFERRED]
- [[.test_fires_when_condition_true()]] - `calls` [INFERRED]
- [[.test_fires_when_interval_elapsed()]] - `calls` [INFERRED]
- [[.test_full_event_flow()]] - `calls` [INFERRED]
- [[.test_global_rate_limit()]] - `calls` [INFERRED]
- [[.test_max_frequency_prevents_rapid_fire()]] - `calls` [INFERRED]
- [[.test_register_returns_id()]] - `calls` [INFERRED]
- [[.test_report_structure()]] - `calls` [INFERRED]
- [[.test_resume_all_background()]] - `calls` [INFERRED]
- [[.test_save_and_load()]] - `calls` [INFERRED]
- [[.test_stop_all_background()]] - `calls` [INFERRED]
- [[.test_task_dict_has_required_fields()]] - `calls` [INFERRED]
- [[.test_unregister_removes_trigger()]] - `calls` [INFERRED]
- [[A condition that causes a module to initiate work autonomously.]] - `rationale_for` [EXTRACTED]
- [[Event fires → trigger activates → task dict produced.]] - `uses` [INFERRED]
- [[TestBackgroundControl]] - `uses` [INFERRED]
- [[TestConditionTriggers]] - `uses` [INFERRED]
- [[TestDefaultTriggers]] - `uses` [INFERRED]
- [[TestDisabledTriggers]] - `uses` [INFERRED]
- [[TestEventIntegration]] - `uses` [INFERRED]
- [[TestGetActiveTriggers]] - `uses` [INFERRED]
- [[TestIdleWorkCycle]] - `uses` [INFERRED]
- [[TestInitiativeReport]] - `uses` [INFERRED]
- [[TestLightEventBus]] - `uses` [INFERRED]
- [[TestMaxFrequency]] - `uses` [INFERRED]
- [[TestPersistence_3]] - `uses` [INFERRED]
- [[TestRateLimiting]] - `uses` [INFERRED]
- [[TestScheduleParsing]] - `uses` [INFERRED]
- [[TestScheduleTriggers]] - `uses` [INFERRED]
- [[TestTaskDictShape]] - `uses` [INFERRED]
- [[TestTriggerRegistration]] - `uses` [INFERRED]
- [[Tests for ProactiveEngine — trigger-based initiative system.]] - `uses` [INFERRED]
- [[proactive_engine.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Proactive_Engine