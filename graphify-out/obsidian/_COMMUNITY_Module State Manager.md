---
type: community
cohesion: 0.03
members: 116
---

# Module State Manager

**Cohesion:** 0.03 - loosely connected
**Members:** 116 nodes

## Members
- [[.decrement_queue()]] - code - modules\shadow\module_state.py
- [[.find_capable_module()]] - code - modules\shadow\module_state.py
- [[.get_all_states()]] - code - modules\shadow\module_state.py
- [[.get_available_modules()]] - code - modules\shadow\module_state.py
- [[.get_busy_modules()]] - code - modules\shadow\module_state.py
- [[.get_state()]] - code - modules\shadow\module_state.py
- [[.get_system_overview()]] - code - modules\shadow\module_state.py
- [[.increment_queue()]] - code - modules\shadow\module_state.py
- [[.reset_daily_counters()]] - code - modules\shadow\module_state.py
- [[.should_defer()]] - code - modules\shadow\module_state.py
- [[.test_avg_task_duration_calculated()]] - code - tests\test_module_state.py
- [[.test_busy_fallback_shortest_queue()]] - code - tests\test_module_state.py
- [[.test_busy_to_error_increments_failed()]] - code - tests\test_module_state.py
- [[.test_busy_to_idle_increments_completed()]] - code - tests\test_module_state.py
- [[.test_concurrent_queue_operations()]] - code - tests\test_module_state.py
- [[.test_concurrent_updates_no_corruption()]] - code - tests\test_module_state.py
- [[.test_decrement_floor_zero()]] - code - tests\test_module_state.py
- [[.test_decrement_queue()]] - code - tests\test_module_state.py
- [[.test_default_state()]] - code - tests\test_module_state.py
- [[.test_defer_on_high_errors()]] - code - tests\test_module_state.py
- [[.test_defer_on_high_queue()]] - code - tests\test_module_state.py
- [[.test_error_tracks_error_count()]] - code - tests\test_module_state.py
- [[.test_finds_correct_module()]] - code - tests\test_module_state.py
- [[.test_from_dict_roundtrip()]] - code - tests\test_module_state.py
- [[.test_get_all_states()]] - code - tests\test_module_state.py
- [[.test_get_available_modules()]] - code - tests\test_module_state.py
- [[.test_get_busy_modules()]] - code - tests\test_module_state.py
- [[.test_get_state_raises_for_unknown()]] - code - tests\test_module_state.py
- [[.test_increment_queue()]] - code - tests\test_module_state.py
- [[.test_invalid_status_ignored()]] - code - tests\test_module_state.py
- [[.test_last_active_updates()]] - code - tests\test_module_state.py
- [[.test_no_defer_normal_state()]] - code - tests\test_module_state.py
- [[.test_no_defer_unknown_module()]] - code - tests\test_module_state.py
- [[.test_overview_counts()]] - code - tests\test_module_state.py
- [[.test_overview_empty_manager()]] - code - tests\test_module_state.py
- [[.test_overview_structure()]] - code - tests\test_module_state.py
- [[.test_prefers_idle_over_busy()]] - code - tests\test_module_state.py
- [[.test_reset_clears_counters()]] - code - tests\test_module_state.py
- [[.test_returns_none_for_unknown_capability()]] - code - tests\test_module_state.py
- [[.test_to_dict()]] - code - tests\test_module_state.py
- [[.test_unregistered_module_auto_creates()]] - code - tests\test_module_state.py
- [[.test_update_to_busy()]] - code - tests\test_module_state.py
- [[.test_update_to_idle_clears_task()]] - code - tests\test_module_state.py
- [[.to_dict()_2]] - code - modules\shadow\module_state.py
- [[.update_state()]] - code - modules\shadow\module_state.py
- [[Average task duration should be calculated from completions.]] - rationale - tests\test_module_state.py
- [[Check if a module is overloaded and tasks should be deferred.          Returns T]] - rationale - modules\shadow\module_state.py
- [[Completing a task (busy→idle) should increment completed counter.]] - rationale - tests\test_module_state.py
- [[Concurrent queue operations should maintain consistency.]] - rationale - tests\test_module_state.py
- [[Concurrent state updates should not corrupt data.]] - rationale - tests\test_module_state.py
- [[Create a fresh ModuleStateManager with temp snapshot path.]] - rationale - tests\test_module_state.py
- [[Current state of a single Shadow module.]] - rationale - modules\shadow\module_state.py
- [[Decrement a module's queue depth (message processed).]] - rationale - modules\shadow\module_state.py
- [[Decrement should decrease queue depth.]] - rationale - tests\test_module_state.py
- [[Default state should be offline with zero counters.]] - rationale - tests\test_module_state.py
- [[Error state should track error_count_last_hour.]] - rationale - tests\test_module_state.py
- [[Failing a task (busy→error) should increment failed counter.]] - rationale - tests\test_module_state.py
- [[Find which module can handle a given capability (tool name).          If multipl]] - rationale - modules\shadow\module_state.py
- [[High-level dashboard for Harbinger briefings.          Returns             Dict]] - rationale - modules\shadow\module_state.py
- [[Increment a module's queue depth (message waiting).]] - rationale - modules\shadow\module_state.py
- [[Increment should increase queue depth.]] - rationale - tests\test_module_state.py
- [[Invalid status strings should be silently ignored.]] - rationale - tests\test_module_state.py
- [[Manager with several modules registered.]] - rationale - tests\test_module_state.py
- [[ModuleState]] - code - modules\shadow\module_state.py
- [[Overview counts should reflect actual states.]] - rationale - tests\test_module_state.py
- [[Overview should contain all required fields.]] - rationale - tests\test_module_state.py
- [[Overview should work with no modules registered.]] - rationale - tests\test_module_state.py
- [[Queue depth should never go negative.]] - rationale - tests\test_module_state.py
- [[Reset should zero out daily task counters.]] - rationale - tests\test_module_state.py
- [[Reset tasks_completed_today and tasks_failed_today at midnight.]] - rationale - modules\shadow\module_state.py
- [[Return current state of a specific module.          Returns a copy to prevent ex]] - rationale - modules\shadow\module_state.py
- [[Return module names currently working.]] - rationale - modules\shadow\module_state.py
- [[Return module names with status 'idle' — ready for work.]] - rationale - modules\shadow\module_state.py
- [[Return states of all registered modules.]] - rationale - modules\shadow\module_state.py
- [[Serialization should include all public fields.]] - rationale - tests\test_module_state.py
- [[Serialize to dict for snapshot persistence.]] - rationale - modules\shadow\module_state.py
- [[Setting busy should record task info.]] - rationale - tests\test_module_state.py
- [[Setting idle should clear task info.]] - rationale - tests\test_module_state.py
- [[Should defer when error_count_last_hour  5.]] - rationale - tests\test_module_state.py
- [[Should defer when queue_depth  10.]] - rationale - tests\test_module_state.py
- [[Should find the module that owns a capability.]] - rationale - tests\test_module_state.py
- [[Should not defer for unregistered module.]] - rationale - tests\test_module_state.py
- [[Should not defer under normal conditions.]] - rationale - tests\test_module_state.py
- [[Should raise KeyError for unregistered module.]] - rationale - tests\test_module_state.py
- [[Should return None for capabilities no module has.]] - rationale - tests\test_module_state.py
- [[Should return only busy modules.]] - rationale - tests\test_module_state.py
- [[Should return only idle modules.]] - rationale - tests\test_module_state.py
- [[Should return states for all registered modules.]] - rationale - tests\test_module_state.py
- [[TestCapabilityRouting]] - code - tests\test_module_state.py
- [[TestDailyReset]] - code - tests\test_module_state.py
- [[TestModuleState]] - code - tests\test_module_state.py
- [[TestQueryMethods]] - code - tests\test_module_state.py
- [[TestQueueManagement]] - code - tests\test_module_state.py
- [[TestShouldDefer]] - code - tests\test_module_state.py
- [[TestStateUpdates]] - code - tests\test_module_state.py
- [[TestSystemOverview]] - code - tests\test_module_state.py
- [[TestThreadSafety]] - code - tests\test_module_state.py
- [[Tests for ModuleState dataclass.]] - rationale - tests\test_module_state.py
- [[Tests for ModuleStateManager — Module State Awareness ==========================]] - rationale - tests\test_module_state.py
- [[Tests for concurrent access.]] - rationale - tests\test_module_state.py
- [[Tests for daily counter reset.]] - rationale - tests\test_module_state.py
- [[Tests for find_capable_module.]] - rationale - tests\test_module_state.py
- [[Tests for overload detection.]] - rationale - tests\test_module_state.py
- [[Tests for queue depth tracking.]] - rationale - tests\test_module_state.py
- [[Tests for state query methods.]] - rationale - tests\test_module_state.py
- [[Tests for state transitions.]] - rationale - tests\test_module_state.py
- [[Tests for the dashboard method.]] - rationale - tests\test_module_state.py
- [[Update a module's state. Called by modules on startfinishfail.          Args]] - rationale - modules\shadow\module_state.py
- [[Updating an unregistered module should auto-create its state.]] - rationale - tests\test_module_state.py
- [[When all capable modules busy, pick shortest queue.]] - rationale - tests\test_module_state.py
- [[When multiple modules can do it, prefer idle.]] - rationale - tests\test_module_state.py
- [[from_dict should restore all fields from to_dict output.]] - rationale - tests\test_module_state.py
- [[last_active should update on every state change.]] - rationale - tests\test_module_state.py
- [[manager()_1]] - code - tests\test_module_state.py
- [[populated_manager()]] - code - tests\test_module_state.py
- [[test_module_state.py]] - code - tests\test_module_state.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Module_State_Manager
SORT file.name ASC
```

## Connections to other communities
- 85 edges to [[_COMMUNITY_Async Task Queue]]
- 3 edges to [[_COMMUNITY_Base Module & Apex API]]
- 2 edges to [[_COMMUNITY_Introspection Dashboard]]
- 1 edge to [[_COMMUNITY_Module Lifecycle]]

## Top bridge nodes
- [[.get_state()]] - degree 22, connects to 2 communities
- [[.find_capable_module()]] - degree 7, connects to 2 communities
- [[.reset_daily_counters()]] - degree 4, connects to 2 communities
- [[ModuleState]] - degree 70, connects to 1 community
- [[.update_state()]] - degree 22, connects to 1 community