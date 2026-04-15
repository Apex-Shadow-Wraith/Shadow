---
type: community
cohesion: 0.04
members: 126
---

# Prompt Evolution

**Cohesion:** 0.04 - loosely connected
**Members:** 126 nodes

## Members
- [[.__init__()_82]] - code - modules\shadow\prompt_evolver.py
- [[._create_tables()_8]] - code - modules\shadow\prompt_evolver.py
- [[._get_grimoire_patterns()]] - code - modules\shadow\prompt_evolver.py
- [[._get_prompt_instructions()]] - code - modules\shadow\prompt_evolver.py
- [[.activate_version()]] - code - modules\shadow\prompt_evolver.py
- [[.analyze_prompt()]] - code - modules\shadow\prompt_evolver.py
- [[.close()_14]] - code - modules\shadow\prompt_evolver.py
- [[.compare_versions()]] - code - modules\shadow\prompt_evolver.py
- [[.evolve_prompt()]] - code - modules\shadow\prompt_evolver.py
- [[.get_evolution_stats()]] - code - modules\shadow\prompt_evolver.py
- [[.get_version_history()]] - code - modules\shadow\prompt_evolver.py
- [[.record_task_outcome()]] - code - modules\shadow\prompt_evolver.py
- [[.register_prompt()]] - code - modules\shadow\prompt_evolver.py
- [[.should_evolve()]] - code - modules\shadow\prompt_evolver.py
- [[.test_activate_nonexistent_version()]] - code - tests\test_prompt_evolver.py
- [[.test_activate_version_sets_correct_statuses()]] - code - tests\test_prompt_evolver.py
- [[.test_analyze_identifies_effective_instructions()]] - code - tests\test_prompt_evolver.py
- [[.test_analyze_identifies_harmful_instructions()]] - code - tests\test_prompt_evolver.py
- [[.test_analyze_identifies_missing_patterns()]] - code - tests\test_prompt_evolver.py
- [[.test_analyze_identifies_unused_instructions()]] - code - tests\test_prompt_evolver.py
- [[.test_analyze_no_active_prompt()]] - code - tests\test_prompt_evolver.py
- [[.test_compare_nonexistent_version()]] - code - tests\test_prompt_evolver.py
- [[.test_compare_versions()]] - code - tests\test_prompt_evolver.py
- [[.test_empty_task_history()]] - code - tests\test_prompt_evolver.py
- [[.test_evolution_stats_empty()]] - code - tests\test_prompt_evolver.py
- [[.test_evolution_stats_with_data()]] - code - tests\test_prompt_evolver.py
- [[.test_evolve_adds_missing_patterns()]] - code - tests\test_prompt_evolver.py
- [[.test_evolve_creates_testing_version()]] - code - tests\test_prompt_evolver.py
- [[.test_evolve_no_active_prompt()]] - code - tests\test_prompt_evolver.py
- [[.test_evolve_removes_unused_instructions()]] - code - tests\test_prompt_evolver.py
- [[.test_evolve_returns_none_when_no_changes()]] - code - tests\test_prompt_evolver.py
- [[.test_get_version_history_ordered()]] - code - tests\test_prompt_evolver.py
- [[.test_module_no_registered_prompt()]] - code - tests\test_prompt_evolver.py
- [[.test_record_task_no_active_prompt()]] - code - tests\test_prompt_evolver.py
- [[.test_record_task_outcome_stores_data()]] - code - tests\test_prompt_evolver.py
- [[.test_referenced_instructions_tracked()]] - code - tests\test_prompt_evolver.py
- [[.test_register_prompt_creates_version_1()]] - code - tests\test_prompt_evolver.py
- [[.test_register_prompt_different_modules()]] - code - tests\test_prompt_evolver.py
- [[.test_register_prompt_same_module_creates_version_2()]] - code - tests\test_prompt_evolver.py
- [[.test_rollback_no_previous_version()]] - code - tests\test_prompt_evolver.py
- [[.test_rollback_restores_previous_version()]] - code - tests\test_prompt_evolver.py
- [[.test_rollback_with_no_previous()]] - code - tests\test_prompt_evolver.py
- [[.test_should_evolve_enough_tasks()]] - code - tests\test_prompt_evolver.py
- [[.test_should_evolve_just_evolved()]] - code - tests\test_prompt_evolver.py
- [[.test_should_evolve_no_active_prompt()]] - code - tests\test_prompt_evolver.py
- [[.test_should_evolve_performance_declining()]] - code - tests\test_prompt_evolver.py
- [[.test_sqlite_db_created_on_init()_1]] - code - tests\test_prompt_evolver.py
- [[.test_unreferenced_instructions_not_tracked()]] - code - tests\test_prompt_evolver.py
- [[A versioned snapshot of a module's system prompt.]] - rationale - modules\shadow\prompt_evolver.py
- [[Activating a nonexistent version returns False.]] - rationale - tests\test_prompt_evolver.py
- [[Activating a version retires the current one.]] - rationale - tests\test_prompt_evolver.py
- [[Analysis of module with no prompt returns error.]] - rationale - tests\test_prompt_evolver.py
- [[Analyze current prompt performance.          Args             module Module co]] - rationale - modules\shadow\prompt_evolver.py
- [[Check if a module's prompt should evolve.          Returns True if         - 10]] - rationale - modules\shadow\prompt_evolver.py
- [[Close database connection._1]] - rationale - modules\shadow\prompt_evolver.py
- [[Compare returns correct scores and better version.]] - rationale - tests\test_prompt_evolver.py
- [[Compare two prompt versions.          Args             version_a First version]] - rationale - modules\shadow\prompt_evolver.py
- [[Comparing with nonexistent version returns error.]] - rationale - tests\test_prompt_evolver.py
- [[Create a PromptEvolver with mocked Grimoire.]] - rationale - tests\test_prompt_evolver.py
- [[Create a PromptEvolver with temp database.]] - rationale - tests\test_prompt_evolver.py
- [[Create a mock Grimoire that returns patterns.]] - rationale - tests\test_prompt_evolver.py
- [[Create a temporary database path.]] - rationale - tests\test_prompt_evolver.py
- [[Create tables for prompt versions and instruction tracking.]] - rationale - modules\shadow\prompt_evolver.py
- [[Edge case and error handling tests._1]] - rationale - tests\test_prompt_evolver.py
- [[Evolution adds patterns from Grimoire.]] - rationale - tests\test_prompt_evolver.py
- [[Evolution removes instructions that were never referenced.]] - rationale - tests\test_prompt_evolver.py
- [[Evolution stats with no data returns zeros.]] - rationale - tests\test_prompt_evolver.py
- [[Evolution stats with real data returns correct values.]] - rationale - tests\test_prompt_evolver.py
- [[Evolution with no active prompt returns None.]] - rationale - tests\test_prompt_evolver.py
- [[Evolved prompt has 'testing' status.]] - rationale - tests\test_prompt_evolver.py
- [[Evolves module system prompts based on performance data.      Tracks which instr]] - rationale - modules\shadow\prompt_evolver.py
- [[Extract instruction sections from the active prompt.          Splits prompt on d]] - rationale - modules\shadow\prompt_evolver.py
- [[First registration creates version 1.]] - rationale - tests\test_prompt_evolver.py
- [[Generate an optimized prompt based on analysis.          1. Keep effective instr]] - rationale - modules\shadow\prompt_evolver.py
- [[Get overall evolution statistics.          Returns             Dict with total_]] - rationale - modules\shadow\prompt_evolver.py
- [[Initialize prompt evolver with SQLite storage.          Args             grimoi]] - rationale - modules\shadow\prompt_evolver.py
- [[Instructions never referenced are identified as unused.]] - rationale - tests\test_prompt_evolver.py
- [[Instructions not referenced don't appear in stats.]] - rationale - tests\test_prompt_evolver.py
- [[Instructions with high confidence are identified as effective.]] - rationale - tests\test_prompt_evolver.py
- [[Instructions with low confidence are identified as harmful.]] - rationale - tests\test_prompt_evolver.py
- [[Missing Grimoire patterns are identified.]] - rationale - tests\test_prompt_evolver.py
- [[Module with no registered prompt handles gracefully.]] - rationale - tests\test_prompt_evolver.py
- [[No evolution with empty task history.]] - rationale - tests\test_prompt_evolver.py
- [[Prompt Evolver — Dynamic System Prompt Evolution ===============================]] - rationale - modules\shadow\prompt_evolver.py
- [[PromptEvolver]] - code - modules\shadow\prompt_evolver.py
- [[PromptVersion]] - code - modules\shadow\prompt_evolver.py
- [[Record a task outcome and which instructions correlated.          Args]] - rationale - modules\shadow\prompt_evolver.py
- [[Recording without an active prompt returns False.]] - rationale - tests\test_prompt_evolver.py
- [[Referenced instructions accumulate stats correctly.]] - rationale - tests\test_prompt_evolver.py
- [[Register a system prompt for a module.          Creates version 1 if first regis]] - rationale - modules\shadow\prompt_evolver.py
- [[Registration for different modules is independent.]] - rationale - tests\test_prompt_evolver.py
- [[Retrieve frequently-used patterns from Grimoire for this module.          Return]] - rationale - modules\shadow\prompt_evolver.py
- [[Return prompt version history for a module.          Args             module M]] - rationale - modules\shadow\prompt_evolver.py
- [[Rollback restores the previous version.]] - rationale - tests\test_prompt_evolver.py
- [[Rollback with no previous version returns None.]] - rationale - tests\test_prompt_evolver.py
- [[Rollback with only one version returns None.]] - rationale - tests\test_prompt_evolver.py
- [[SQLite database is created on initialization.]] - rationale - tests\test_prompt_evolver.py
- [[Second registration for same module creates version 2.]] - rationale - tests\test_prompt_evolver.py
- [[Set a prompt version as active for its module.          Previous active version]] - rationale - modules\shadow\prompt_evolver.py
- [[Task outcome is stored correctly.]] - rationale - tests\test_prompt_evolver.py
- [[TestAnalysis]] - code - tests\test_prompt_evolver.py
- [[TestEdgeCases_16]] - code - tests\test_prompt_evolver.py
- [[TestEvolution]] - code - tests\test_prompt_evolver.py
- [[TestRegistration_1]] - code - tests\test_prompt_evolver.py
- [[TestScheduling]] - code - tests\test_prompt_evolver.py
- [[TestTaskTracking]] - code - tests\test_prompt_evolver.py
- [[TestVersionManagement]] - code - tests\test_prompt_evolver.py
- [[Tests for Prompt Evolver — Dynamic System Prompt Evolution =====================]] - rationale - tests\test_prompt_evolver.py
- [[Tests for evolution scheduling.]] - rationale - tests\test_prompt_evolver.py
- [[Tests for prompt analysis.]] - rationale - tests\test_prompt_evolver.py
- [[Tests for prompt evolution.]] - rationale - tests\test_prompt_evolver.py
- [[Tests for prompt registration.]] - rationale - tests\test_prompt_evolver.py
- [[Tests for task outcome recording.]] - rationale - tests\test_prompt_evolver.py
- [[Tests for version activation, rollback, comparison.]] - rationale - tests\test_prompt_evolver.py
- [[Version history is returned newest first.]] - rationale - tests\test_prompt_evolver.py
- [[evolve_prompt returns None when no changes are needed.]] - rationale - tests\test_prompt_evolver.py
- [[evolver()]] - code - tests\test_prompt_evolver.py
- [[evolver_with_grimoire()]] - code - tests\test_prompt_evolver.py
- [[mock_grimoire()_11]] - code - tests\test_prompt_evolver.py
- [[prompt_evolver.py]] - code - modules\shadow\prompt_evolver.py
- [[should_evolve returns False when few tasks since last evolution.]] - rationale - tests\test_prompt_evolver.py
- [[should_evolve returns False when no active prompt.]] - rationale - tests\test_prompt_evolver.py
- [[should_evolve returns True when 100+ tasks recorded.]] - rationale - tests\test_prompt_evolver.py
- [[should_evolve returns True when performance is declining.]] - rationale - tests\test_prompt_evolver.py
- [[test_prompt_evolver.py]] - code - tests\test_prompt_evolver.py
- [[tmp_db()_4]] - code - tests\test_prompt_evolver.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Prompt_Evolution
SORT file.name ASC
```

## Connections to other communities
- 13 edges to [[_COMMUNITY_Data Pipeline & Embeddings]]
- 12 edges to [[_COMMUNITY_Module Lifecycle]]
- 1 edge to [[_COMMUNITY_Adversarial Sparring]]

## Top bridge nodes
- [[.register_prompt()]] - degree 29, connects to 2 communities
- [[.evolve_prompt()]] - degree 13, connects to 2 communities
- [[.activate_version()]] - degree 7, connects to 2 communities
- [[.__init__()_82]] - degree 5, connects to 2 communities
- [[PromptEvolver]] - degree 73, connects to 1 community