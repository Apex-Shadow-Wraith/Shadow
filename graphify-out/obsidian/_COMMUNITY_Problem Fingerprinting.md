---
type: community
cohesion: 0.04
members: 106
---

# Problem Fingerprinting

**Cohesion:** 0.04 - loosely connected
**Members:** 106 nodes

## Members
- [[.__init__()_81]] - code - modules\shadow\problem_fingerprint.py
- [[._compute_hash()]] - code - modules\shadow\problem_fingerprint.py
- [[._detect_complexity()]] - code - modules\shadow\problem_fingerprint.py
- [[._detect_constraints()]] - code - modules\shadow\problem_fingerprint.py
- [[._detect_domain()]] - code - modules\shadow\problem_fingerprint.py
- [[._detect_io_type()]] - code - modules\shadow\problem_fingerprint.py
- [[._rank_results()]] - code - modules\shadow\problem_fingerprint.py
- [[.find_similar_solutions()]] - code - modules\shadow\problem_fingerprint.py
- [[.fingerprint()]] - code - modules\shadow\problem_fingerprint.py
- [[.get_cross_domain_matches()]] - code - modules\shadow\problem_fingerprint.py
- [[.get_fingerprint_stats()]] - code - modules\shadow\problem_fingerprint.py
- [[.store_with_fingerprint()]] - code - modules\shadow\problem_fingerprint.py
- [[.test_aggregation_detected()]] - code - tests\test_problem_fingerprint.py
- [[.test_classification_detected()]] - code - tests\test_problem_fingerprint.py
- [[.test_code_input_detected()]] - code - tests\test_problem_fingerprint.py
- [[.test_comparison_detected()]] - code - tests\test_problem_fingerprint.py
- [[.test_constraint_detection()]] - code - tests\test_problem_fingerprint.py
- [[.test_constraint_satisfaction_detected()]] - code - tests\test_problem_fingerprint.py
- [[.test_cross_domain_match()]] - code - tests\test_problem_fingerprint.py
- [[.test_data_input_detected()]] - code - tests\test_problem_fingerprint.py
- [[.test_decision_output_detected()]] - code - tests\test_problem_fingerprint.py
- [[.test_decomposition_detected()]] - code - tests\test_problem_fingerprint.py
- [[.test_diagnosis_detected()]] - code - tests\test_problem_fingerprint.py
- [[.test_different_shape_different_hash()]] - code - tests\test_problem_fingerprint.py
- [[.test_domain_detection()]] - code - tests\test_problem_fingerprint.py
- [[.test_empty_task()_1]] - code - tests\test_problem_fingerprint.py
- [[.test_filters_to_different_domain()]] - code - tests\test_problem_fingerprint.py
- [[.test_generation_detected()]] - code - tests\test_problem_fingerprint.py
- [[.test_get_fingerprint_stats_with_data()]] - code - tests\test_problem_fingerprint.py
- [[.test_get_fingerprint_stats_without_grimoire()]] - code - tests\test_problem_fingerprint.py
- [[.test_graceful_grimoire_unavailable_for_stats()]] - code - tests\test_problem_fingerprint.py
- [[.test_handles_grimoire_error()]] - code - tests\test_problem_fingerprint.py
- [[.test_handles_store_error()]] - code - tests\test_problem_fingerprint.py
- [[.test_hash_is_deterministic()]] - code - tests\test_problem_fingerprint.py
- [[.test_hash_is_nonempty_string()]] - code - tests\test_problem_fingerprint.py
- [[.test_includes_adaptation_hint()]] - code - tests\test_problem_fingerprint.py
- [[.test_iterative_detected()]] - code - tests\test_problem_fingerprint.py
- [[.test_mapping_detected()]] - code - tests\test_problem_fingerprint.py
- [[.test_multi_shape_task()]] - code - tests\test_problem_fingerprint.py
- [[.test_multi_step_detected()]] - code - tests\test_problem_fingerprint.py
- [[.test_no_matching_keywords_defaults_to_generation()]] - code - tests\test_problem_fingerprint.py
- [[.test_none_task_handled()]] - code - tests\test_problem_fingerprint.py
- [[.test_optimization_detected()]] - code - tests\test_problem_fingerprint.py
- [[.test_parallel_detected()]] - code - tests\test_problem_fingerprint.py
- [[.test_recursive_detected()]] - code - tests\test_problem_fingerprint.py
- [[.test_repair_detected()]] - code - tests\test_problem_fingerprint.py
- [[.test_respects_n_results()]] - code - tests\test_problem_fingerprint.py
- [[.test_returns_empty_without_grimoire()]] - code - tests\test_problem_fingerprint.py
- [[.test_returns_empty_without_grimoire()_1]] - code - tests\test_problem_fingerprint.py
- [[.test_same_shape_same_hash()]] - code - tests\test_problem_fingerprint.py
- [[.test_scheduling_detected()]] - code - tests\test_problem_fingerprint.py
- [[.test_search_detected()]] - code - tests\test_problem_fingerprint.py
- [[.test_secondary_shapes_are_list()]] - code - tests\test_problem_fingerprint.py
- [[.test_stores_with_correct_metadata()]] - code - tests\test_problem_fingerprint.py
- [[.test_text_output_detected()]] - code - tests\test_problem_fingerprint.py
- [[.test_transformation_detected()]] - code - tests\test_problem_fingerprint.py
- [[.test_uses_override_grimoire()]] - code - tests\test_problem_fingerprint.py
- [[.test_verification_detected()]] - code - tests\test_problem_fingerprint.py
- [[.test_very_short_task()]] - code - tests\test_problem_fingerprint.py
- [[.test_whitespace_only_task()]] - code - tests\test_problem_fingerprint.py
- [[Classify a task by structural shape using rule-based keyword analysis.]] - rationale - modules\shadow\problem_fingerprint.py
- [[Classify problems by structural shape for cross-domain solution transfer.]] - rationale - modules\shadow\problem_fingerprint.py
- [[Compute deterministic hash from structural properties (not domain).]] - rationale - modules\shadow\problem_fingerprint.py
- [[Detect complexity indicators from task keywords.]] - rationale - modules\shadow\problem_fingerprint.py
- [[Detect constraint types from task keywords.]] - rationale - modules\shadow\problem_fingerprint.py
- [[Detect inputoutput type from task keywords.]] - rationale - modules\shadow\problem_fingerprint.py
- [[Detect the problem domain from task content.]] - rationale - modules\shadow\problem_fingerprint.py
- [[Fingerprint a task and find solutions from different domains.          Combined]] - rationale - modules\shadow\problem_fingerprint.py
- [[Fingerprinter with mock Grimoire.]] - rationale - tests\test_problem_fingerprint.py
- [[Fingerprinter with no Grimoire.]] - rationale - tests\test_problem_fingerprint.py
- [[Get distribution of problem shapes and cross-domain match stats.          Return]] - rationale - modules\shadow\problem_fingerprint.py
- [[Initialize with optional Grimoire for solution storageretrieval.]] - rationale - modules\shadow\problem_fingerprint.py
- [[Mock Grimoire for testing storageretrieval.]] - rationale - tests\test_problem_fingerprint.py
- [[Optimization in CUDA should match optimization in database.]] - rationale - tests\test_problem_fingerprint.py
- [[Problem Fingerprinting — classify problems by structural shape for cross-domain]] - rationale - modules\shadow\problem_fingerprint.py
- [[ProblemFingerprint]] - code - modules\shadow\problem_fingerprint.py
- [[ProblemFingerprinter]] - code - modules\shadow\problem_fingerprint.py
- [[Rank results by shape match strength, recency, and trust.]] - rationale - modules\shadow\problem_fingerprint.py
- [[Same primary shape + same indicatorsconstraints → same hash.]] - rationale - tests\test_problem_fingerprint.py
- [[Search Grimoire for solutions with matching fingerprint or similar shape.]] - rationale - modules\shadow\problem_fingerprint.py
- [[Store a solution in Grimoire with fingerprint metadata.          Args]] - rationale - modules\shadow\problem_fingerprint.py
- [[Structural fingerprint of a problem, independent of domain.]] - rationale - modules\shadow\problem_fingerprint.py
- [[Test complexity indicator detection.]] - rationale - tests\test_problem_fingerprint.py
- [[Test edge cases and graceful degradation.]] - rationale - tests\test_problem_fingerprint.py
- [[Test fingerprint hash properties.]] - rationale - tests\test_problem_fingerprint.py
- [[Test inputoutput type detection.]] - rationale - tests\test_problem_fingerprint.py
- [[Test searching for solutions with matching fingerprints.]] - rationale - tests\test_problem_fingerprint.py
- [[Test storing solutions with fingerprint metadata.]] - rationale - tests\test_problem_fingerprint.py
- [[Test that multi-faceted tasks get primary + secondary shapes.]] - rationale - tests\test_problem_fingerprint.py
- [[Test that tasks are classified to the correct primary shape.]] - rationale - tests\test_problem_fingerprint.py
- [[Test the convenience method for cross-domain solution discovery.]] - rationale - tests\test_problem_fingerprint.py
- [[TestComplexityIndicators]] - code - tests\test_problem_fingerprint.py
- [[TestCrossDomainMatches]] - code - tests\test_problem_fingerprint.py
- [[TestEdgeCases_15]] - code - tests\test_problem_fingerprint.py
- [[TestFindSimilarSolutions]] - code - tests\test_problem_fingerprint.py
- [[TestFingerprintHash]] - code - tests\test_problem_fingerprint.py
- [[TestIOTypeDetection]] - code - tests\test_problem_fingerprint.py
- [[TestPrimaryShapeDetection]] - code - tests\test_problem_fingerprint.py
- [[TestSecondaryShapes]] - code - tests\test_problem_fingerprint.py
- [[TestStoreWithFingerprint]] - code - tests\test_problem_fingerprint.py
- [[Tests for Problem Fingerprinting — cross-domain solution transfer via structural]] - rationale - tests\test_problem_fingerprint.py
- [[fingerprinter()]] - code - tests\test_problem_fingerprint.py
- [[fingerprinter_with_grimoire()]] - code - tests\test_problem_fingerprint.py
- [[mock_grimoire()_10]] - code - tests\test_problem_fingerprint.py
- [[problem_fingerprint.py]] - code - modules\shadow\problem_fingerprint.py
- [[test_problem_fingerprint.py]] - code - tests\test_problem_fingerprint.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Problem_Fingerprinting
SORT file.name ASC
```

## Connections to other communities
- 3 edges to [[_COMMUNITY_Cross-Reference & Security]]

## Top bridge nodes
- [[.find_similar_solutions()]] - degree 9, connects to 1 community
- [[.store_with_fingerprint()]] - degree 7, connects to 1 community
- [[.get_fingerprint_stats()]] - degree 6, connects to 1 community