---
source_file: "modules\grimoire\query_optimizer.py"
type: "code"
community: "Module Lifecycle"
location: "L38"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Module_Lifecycle
---

# GrimoireQueryOptimizer

## Connections
- [[.__init__()_22]] - `method` [EXTRACTED]
- [[._init_db()_2]] - `method` [EXTRACTED]
- [[.analyze_relevance()]] - `method` [EXTRACTED]
- [[.apply_optimizations()]] - `method` [EXTRACTED]
- [[.find_co_retrieved_documents()]] - `method` [EXTRACTED]
- [[.find_never_used_results()]] - `method` [EXTRACTED]
- [[.generate_optimization_plan()]] - `method` [EXTRACTED]
- [[.get_optimal_n_results()]] - `method` [EXTRACTED]
- [[.get_query_stats()]] - `method` [EXTRACTED]
- [[.get_similarity_threshold_recommendation()]] - `method` [EXTRACTED]
- [[.log_query()]] - `method` [EXTRACTED]
- [[.test_confidence_scales_with_sample_size()]] - `calls` [INFERRED]
- [[.test_sqlite_db_created_on_init()_2]] - `calls` [INFERRED]
- [[5 returned, 2 used → 40% usage, 60% waste.]] - `uses` [INFERRED]
- [[All logged fields should be retrievable from SQLite.]] - `uses` [INFERRED]
- [[Apply optimizations to a mock grimoire object.]] - `uses` [INFERRED]
- [[Auto-tune Grimoire retrieval based on query pattern analysis.]] - `rationale_for` [EXTRACTED]
- [[Average across multiple queries.]] - `uses` [INFERRED]
- [[Collection-specific optimal n.]] - `uses` [INFERRED]
- [[Database file should exist after initialization.]] - `uses` [INFERRED]
- [[Doc returned 10 times via response_referenced but with 0 actual use is tricky.]] - `uses` [INFERRED]
- [[Doc returned 10 times, used 8+ times → not in results.]] - `uses` [INFERRED]
- [[Docs A+B returned together 5 times → in results.]] - `uses` [INFERRED]
- [[Docs that only co-occur once → not in results with min=3.]] - `uses` [INFERRED]
- [[Empty query log → valid plan with 0 confidence.]] - `uses` [INFERRED]
- [[Even with 0 usage, minimum recommendation is 1.]] - `uses` [INFERRED]
- [[If avg 3 results used, recommend ~5 (with buffer).]] - `uses` [INFERRED]
- [[Many results returned but few used → higher threshold.]] - `uses` [INFERRED]
- [[More queries → higher confidence.]] - `uses` [INFERRED]
- [[Most results used → moderatelower threshold.]] - `uses` [INFERRED]
- [[Multiple log_query calls should create multiple rows.]] - `uses` [INFERRED]
- [[No data → default 0.5.]] - `uses` [INFERRED]
- [[No data → default of 5.]] - `uses` [INFERRED]
- [[No queries → all zeros.]] - `uses` [INFERRED]
- [[No queries → no co-retrieved docs.]] - `uses` [INFERRED]
- [[No queries → no never-used docs.]] - `uses` [INFERRED]
- [[Optimizer works fine without a grimoire reference.]] - `uses` [INFERRED]
- [[Plan recommendations list should have at least one entry.]] - `uses` [INFERRED]
- [[Plan should contain all required keys.]] - `uses` [INFERRED]
- [[Provide a fresh GrimoireQueryOptimizer with a temp database.]] - `uses` [INFERRED]
- [[Provide a temporary database path._1]] - `uses` [INFERRED]
- [[Single query → valid but low confidence.]] - `uses` [INFERRED]
- [[Stats should reflect logged queries.]] - `uses` [INFERRED]
- [[Test co-retrieval detection.]] - `uses` [INFERRED]
- [[Test detection of documents returned but never used.]] - `uses` [INFERRED]
- [[Test edge cases and robustness.]] - `uses` [INFERRED]
- [[Test optimal n_results recommendation.]] - `uses` [INFERRED]
- [[Test optimization plan application.]] - `uses` [INFERRED]
- [[Test optimization plan generation.]] - `uses` [INFERRED]
- [[Test query logging stores all fields correctly.]] - `uses` [INFERRED]
- [[Test relevance analysis calculations.]] - `uses` [INFERRED]
- [[Test similarity threshold recommendations.]] - `uses` [INFERRED]
- [[TestAnalyzeRelevance]] - `uses` [INFERRED]
- [[TestApplyOptimizations]] - `uses` [INFERRED]
- [[TestCoRetrievedDocuments]] - `uses` [INFERRED]
- [[TestEdgeCases_17]] - `uses` [INFERRED]
- [[TestNeverUsedResults]] - `uses` [INFERRED]
- [[TestOptimalNResults]] - `uses` [INFERRED]
- [[TestOptimizationPlan]] - `uses` [INFERRED]
- [[TestQueryLogging]] - `uses` [INFERRED]
- [[TestSimilarityThreshold]] - `uses` [INFERRED]
- [[Tests for Grimoire Query Optimizer ==================================== Validate]] - `uses` [INFERRED]
- [[Token savings should be non-negative.]] - `uses` [INFERRED]
- [[Without approval flag → all changes skipped.]] - `uses` [INFERRED]
- [[log_query should return a non-empty string ID.]] - `uses` [INFERRED]
- [[optimizer()]] - `calls` [INFERRED]
- [[query_optimizer.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Module_Lifecycle