---
type: community
cohesion: 0.04
members: 111
---

# Cross-Module Dreaming

**Cohesion:** 0.04 - loosely connected
**Members:** 111 nodes

## Members
- [[.__init__()_27]] - code - modules\morpheus\cross_module_dreaming.py
- [[._generate_hypotheses()]] - code - modules\morpheus\cross_module_dreaming.py
- [[._normalize_hypothesis()]] - code - modules\morpheus\cross_module_dreaming.py
- [[._parse_hypotheses()]] - code - modules\morpheus\cross_module_dreaming.py
- [[.dream()]] - code - modules\morpheus\cross_module_dreaming.py
- [[.evaluate_dream()]] - code - modules\morpheus\cross_module_dreaming.py
- [[.get_dream_history()]] - code - modules\morpheus\cross_module_dreaming.py
- [[.get_dreaming_stats()]] - code - modules\morpheus\cross_module_dreaming.py
- [[.get_module_descriptions()]] - code - modules\morpheus\cross_module_dreaming.py
- [[.get_unexplored_combinations()]] - code - modules\morpheus\cross_module_dreaming.py
- [[.store_dream()]] - code - modules\morpheus\cross_module_dreaming.py
- [[.test_all_pairs_are_unique_tuples()]] - code - tests\test_cross_module_dreaming.py
- [[.test_creative_hypothesis_worth_investigating()]] - code - tests\test_cross_module_dreaming.py
- [[.test_descriptions_are_nonempty_strings()]] - code - tests\test_cross_module_dreaming.py
- [[.test_dream_generates_hypotheses()]] - code - tests\test_cross_module_dreaming.py
- [[.test_dream_no_generate_fn_returns_empty()]] - code - tests\test_cross_module_dreaming.py
- [[.test_dream_respects_max_combinations()]] - code - tests\test_cross_module_dreaming.py
- [[.test_dream_same_pair_not_dreamed_twice()]] - code - tests\test_cross_module_dreaming.py
- [[.test_dream_with_max_combinations_3()]] - code - tests\test_cross_module_dreaming.py
- [[.test_empty_history_returns_empty()]] - code - tests\test_cross_module_dreaming.py
- [[.test_empty_hypothesis_not_worth_it()]] - code - tests\test_cross_module_dreaming.py
- [[.test_empty_module_registry_graceful()]] - code - tests\test_cross_module_dreaming.py
- [[.test_generate_fn_failure_partial_results()]] - code - tests\test_cross_module_dreaming.py
- [[.test_generate_fn_returns_empty()]] - code - tests\test_cross_module_dreaming.py
- [[.test_generate_fn_returns_garbage()]] - code - tests\test_cross_module_dreaming.py
- [[.test_initial_stats()_1]] - code - tests\test_cross_module_dreaming.py
- [[.test_respects_limit()]] - code - tests\test_cross_module_dreaming.py
- [[.test_restated_capability_not_worth_it()]] - code - tests\test_cross_module_dreaming.py
- [[.test_returns_all_13_modules()]] - code - tests\test_cross_module_dreaming.py
- [[.test_returns_past_dreams()]] - code - tests\test_cross_module_dreaming.py
- [[.test_returns_untried_pairs()]] - code - tests\test_cross_module_dreaming.py
- [[.test_returns_valid_counts()]] - code - tests\test_cross_module_dreaming.py
- [[.test_shrinks_as_combinations_explored()]] - code - tests\test_cross_module_dreaming.py
- [[.test_single_module_registry_no_pairs()]] - code - tests\test_cross_module_dreaming.py
- [[.test_store_dream_no_store_returns_empty()]] - code - tests\test_cross_module_dreaming.py
- [[.test_store_dream_saves_to_experiment_store()]] - code - tests\test_cross_module_dreaming.py
- [[.test_testable_dream_gets_priority_boost()]] - code - tests\test_cross_module_dreaming.py
- [[.test_trivial_combination_not_worth_it()]] - code - tests\test_cross_module_dreaming.py
- [[.test_uses_custom_registry()]] - code - tests\test_cross_module_dreaming.py
- [[A creative, non-trivial hypothesis should be worth investigating.]] - rationale - tests\test_cross_module_dreaming.py
- [[A hypothesis that just restates a module's description isn't novel.]] - rationale - tests\test_cross_module_dreaming.py
- [[All descriptions should be non-empty strings.]] - rationale - tests\test_cross_module_dreaming.py
- [[All returned pairs should be unique sorted tuples.]] - rationale - tests\test_cross_module_dreaming.py
- [[Create a JSON string from a list of hypothesis dicts.]] - rationale - tests\test_cross_module_dreaming.py
- [[Create a mock generate_fn returning the given response.]] - rationale - tests\test_cross_module_dreaming.py
- [[CrossModuleDreamer]] - code - modules\morpheus\cross_module_dreaming.py
- [[CrossModuleDreamer with a working generate_fn.]] - rationale - tests\test_cross_module_dreaming.py
- [[CrossModuleDreamer with experiment_store.]] - rationale - tests\test_cross_module_dreaming.py
- [[CrossModuleDreamer without generate_fn.]] - rationale - tests\test_cross_module_dreaming.py
- [[CrossModuleDreamer — Cross-Module Capability Discovery =========================]] - rationale - modules\morpheus\cross_module_dreaming.py
- [[Edge case and error handling tests.]] - rationale - tests\test_cross_module_dreaming.py
- [[Empty hypothesis should not be worth investigating.]] - rationale - tests\test_cross_module_dreaming.py
- [[Empty module registry should return empty results.]] - rationale - tests\test_cross_module_dreaming.py
- [[Empty response from generate_fn should produce empty results for that pair.]] - rationale - tests\test_cross_module_dreaming.py
- [[Ensure hypothesis dict has all required keys with correct types.]] - rationale - modules\morpheus\cross_module_dreaming.py
- [[Explored pairs should be excluded from unexplored list.]] - rationale - tests\test_cross_module_dreaming.py
- [[Generate hypotheses for random module pair combinations.          Picks up to ma]] - rationale - modules\morpheus\cross_module_dreaming.py
- [[Generates speculative hypotheses about combining module capabilities.      Picks]] - rationale - modules\morpheus\cross_module_dreaming.py
- [[If generate_fn raises, that pair produces no hypotheses but doesn't crash.]] - rationale - tests\test_cross_module_dreaming.py
- [[Initial stats should show zero explored, 78 unexplored.]] - rationale - tests\test_cross_module_dreaming.py
- [[Mock ExperimentStore that records calls.]] - rationale - tests\test_cross_module_dreaming.py
- [[Non-JSON response should be handled gracefully.]] - rationale - tests\test_cross_module_dreaming.py
- [[Parse LLM response into structured hypothesis dicts.          Attempts JSON pars]] - rationale - modules\morpheus\cross_module_dreaming.py
- [[Quick assessment of whether a dream is worth investigating.          Checks that]] - rationale - modules\morpheus\cross_module_dreaming.py
- [[Return descriptions for all 13 modules.          Uses module_registry if provide]] - rationale - modules\morpheus\cross_module_dreaming.py
- [[Return dreaming statistics for Growth Engine.          Returns             Dict]] - rationale - modules\morpheus\cross_module_dreaming.py
- [[Return module pairs that haven't been explored yet.          13 modules = 78 pos]] - rationale - modules\morpheus\cross_module_dreaming.py
- [[Return past dreams from this session.          Args             limit Maximum]] - rationale - modules\morpheus\cross_module_dreaming.py
- [[Same module pair should not be explored twice in a session.]] - rationale - tests\test_cross_module_dreaming.py
- [[Should not return more dreams than limit.]] - rationale - tests\test_cross_module_dreaming.py
- [[Should return all 78 pairs initially (13 choose 2).]] - rationale - tests\test_cross_module_dreaming.py
- [[Should return descriptions for all 13 Shadow modules.]] - rationale - tests\test_cross_module_dreaming.py
- [[Should return dreams from previous dream() calls.]] - rationale - tests\test_cross_module_dreaming.py
- [[Should return empty list when no dreams have been generated.]] - rationale - tests\test_cross_module_dreaming.py
- [[Should use module_registry when provided.]] - rationale - tests\test_cross_module_dreaming.py
- [[Single module registry can't make pairs.]] - rationale - tests\test_cross_module_dreaming.py
- [[Stats should have correct keys and non-negative values.]] - rationale - tests\test_cross_module_dreaming.py
- [[Store a dream in experiment_store as a new experiment.          Args]] - rationale - modules\morpheus\cross_module_dreaming.py
- [[TestDream]] - code - tests\test_cross_module_dreaming.py
- [[TestEdgeCases_6]] - code - tests\test_cross_module_dreaming.py
- [[TestEvaluateDream]] - code - tests\test_cross_module_dreaming.py
- [[TestGetDreamHistory]] - code - tests\test_cross_module_dreaming.py
- [[TestGetDreamingStats]] - code - tests\test_cross_module_dreaming.py
- [[TestGetModuleDescriptions]] - code - tests\test_cross_module_dreaming.py
- [[TestGetUnexploredCombinations]] - code - tests\test_cross_module_dreaming.py
- [[TestStoreDream]] - code - tests\test_cross_module_dreaming.py
- [[Testable dreams should get better (lower) priority.]] - rationale - tests\test_cross_module_dreaming.py
- [[Tests for CrossModuleDreamer — Cross-Module Capability Discovery.]] - rationale - tests\test_cross_module_dreaming.py
- [[Tests for evaluate_dream().]] - rationale - tests\test_cross_module_dreaming.py
- [[Tests for get_dream_history().]] - rationale - tests\test_cross_module_dreaming.py
- [[Tests for get_dreaming_stats().]] - rationale - tests\test_cross_module_dreaming.py
- [[Tests for get_module_descriptions().]] - rationale - tests\test_cross_module_dreaming.py
- [[Tests for get_unexplored_combinations().]] - rationale - tests\test_cross_module_dreaming.py
- [[Tests for store_dream().]] - rationale - tests\test_cross_module_dreaming.py
- [[Tests for the dream() method.]] - rationale - tests\test_cross_module_dreaming.py
- [[Trivial data piping should not be worth investigating.]] - rationale - tests\test_cross_module_dreaming.py
- [[Use generate_fn to produce hypotheses for a module pair.          Falls back to]] - rationale - modules\morpheus\cross_module_dreaming.py
- [[cross_module_dreaming.py]] - code - modules\morpheus\cross_module_dreaming.py
- [[dream() should not exceed max_combinations pairs.]] - rationale - tests\test_cross_module_dreaming.py
- [[dream() should return hypothesis dicts for random module pairs.]] - rationale - tests\test_cross_module_dreaming.py
- [[dream() with max_combinations=3 explores up to 3 pairs.]] - rationale - tests\test_cross_module_dreaming.py
- [[dream() without generate_fn should return empty results.]] - rationale - tests\test_cross_module_dreaming.py
- [[dreamer_no_generate()]] - code - tests\test_cross_module_dreaming.py
- [[dreamer_with_generate()]] - code - tests\test_cross_module_dreaming.py
- [[dreamer_with_store()]] - code - tests\test_cross_module_dreaming.py
- [[make_generate_fn()]] - code - tests\test_cross_module_dreaming.py
- [[make_json_response()]] - code - tests\test_cross_module_dreaming.py
- [[mock_experiment_store()]] - code - tests\test_cross_module_dreaming.py
- [[store_dream() should call experiment_store.store_failure().]] - rationale - tests\test_cross_module_dreaming.py
- [[store_dream() without experiment_store returns empty string.]] - rationale - tests\test_cross_module_dreaming.py
- [[test_cross_module_dreaming.py]] - code - tests\test_cross_module_dreaming.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Cross-Module_Dreaming
SORT file.name ASC
```

## Connections to other communities
- 1 edge to [[_COMMUNITY_Experiment Store]]

## Top bridge nodes
- [[.store_dream()]] - degree 5, connects to 1 community