---
type: community
cohesion: 0.04
members: 76
---

# Embedding Evaluator

**Cohesion:** 0.04 - loosely connected
**Members:** 76 nodes

## Members
- [[._cross_category_query()]] - code - modules\grimoire\embedding_evaluator.py
- [[._extract_generic_query()]] - code - modules\grimoire\embedding_evaluator.py
- [[._fetch_all_active_memories()]] - code - modules\grimoire\embedding_evaluator.py
- [[._generate_negative_query()]] - code - modules\grimoire\embedding_evaluator.py
- [[._generate_positive_query()]] - code - modules\grimoire\embedding_evaluator.py
- [[._load_latest_benchmark()]] - code - modules\omen\model_evaluator.py
- [[._pick_negative_document()]] - code - modules\grimoire\embedding_evaluator.py
- [[.build_eval_set()]] - code - modules\grimoire\embedding_evaluator.py
- [[.compare_models()]] - code - modules\grimoire\embedding_evaluator.py
- [[.export_training_pairs()]] - code - modules\grimoire\embedding_evaluator.py
- [[.format_report()]] - code - modules\grimoire\embedding_evaluator.py
- [[.run_eval()]] - code - modules\grimoire\embedding_evaluator.py
- [[.store_benchmark()_1]] - code - modules\omen\model_evaluator.py
- [[.test_auto_builds_eval_set_when_none()]] - code - tests\test_embedding_evaluator.py
- [[.test_bible_memory_generates_verse_query()]] - code - tests\test_embedding_evaluator.py
- [[.test_class_name_extraction()]] - code - tests\test_embedding_evaluator.py
- [[.test_code_memory_generates_code_query()]] - code - tests\test_embedding_evaluator.py
- [[.test_creates_jsonl_file()]] - code - tests\test_embedding_evaluator.py
- [[.test_creates_parent_directories()]] - code - tests\test_embedding_evaluator.py
- [[.test_each_pair_has_required_keys()]] - code - tests\test_embedding_evaluator.py
- [[.test_empty_eval_set_returns_zero_metrics()]] - code - tests\test_embedding_evaluator.py
- [[.test_empty_grimoire_exports_zero()]] - code - tests\test_embedding_evaluator.py
- [[.test_empty_grimoire_returns_empty()]] - code - tests\test_embedding_evaluator.py
- [[.test_format_comparison_contains_both_models()]] - code - tests\test_embedding_evaluator.py
- [[.test_format_report_contains_metrics()]] - code - tests\test_embedding_evaluator.py
- [[.test_generates_positive_and_negative_pairs()]] - code - tests\test_embedding_evaluator.py
- [[.test_generic_fallback_for_unknown_category()]] - code - tests\test_embedding_evaluator.py
- [[.test_hardware_spec_extraction()]] - code - tests\test_embedding_evaluator.py
- [[.test_jsonl_format_valid()]] - code - tests\test_embedding_evaluator.py
- [[.test_metrics_between_0_and_1()]] - code - tests\test_embedding_evaluator.py
- [[.test_negative_queries_differ_from_category()]] - code - tests\test_embedding_evaluator.py
- [[.test_perfect_recall_when_all_found()]] - code - tests\test_embedding_evaluator.py
- [[.test_positive_and_negative_differ()]] - code - tests\test_embedding_evaluator.py
- [[.test_positive_queries_have_content()]] - code - tests\test_embedding_evaluator.py
- [[.test_returns_all_required_metrics()]] - code - tests\test_embedding_evaluator.py
- [[.test_returns_count_of_pairs()]] - code - tests\test_embedding_evaluator.py
- [[.test_returns_failures_list()]] - code - tests\test_embedding_evaluator.py
- [[.test_returns_list()]] - code - tests\test_embedding_evaluator.py
- [[.test_returns_timestamp()]] - code - tests\test_embedding_evaluator.py
- [[.test_returns_total_count()]] - code - tests\test_embedding_evaluator.py
- [[.test_stored_content_is_valid_json()]] - code - tests\test_embedding_evaluator.py
- [[.test_stores_to_grimoire()_1]] - code - tests\test_embedding_evaluator.py
- [[.test_uses_correct_category()]] - code - tests\test_embedding_evaluator.py
- [[.test_uses_correct_tags()]] - code - tests\test_embedding_evaluator.py
- [[.test_zero_metrics_when_nothing_found()]] - code - tests\test_embedding_evaluator.py
- [[Create a mock Grimoire with controllable recall() and remember().]] - rationale - tests\test_embedding_evaluator.py
- [[Create evaluation pairs from existing Grimoire data.          For each active me]] - rationale - modules\grimoire\embedding_evaluator.py
- [[Export query-document pairs as fine-tuning data.          Format one JSON objec]] - rationale - modules\grimoire\embedding_evaluator.py
- [[Fallback extract first meaningful phrase as a query.]] - rationale - modules\grimoire\embedding_evaluator.py
- [[Fetch all active memories from SQLite directly.]] - rationale - modules\grimoire\embedding_evaluator.py
- [[Format eval results as a human-readable report.          Args             resul]] - rationale - modules\grimoire\embedding_evaluator.py
- [[Generate a query from a different category (should NOT retrieve this memory).]] - rationale - modules\grimoire\embedding_evaluator.py
- [[Generate a query that should retrieve this memory.          Uses category-specif]] - rationale - modules\grimoire\embedding_evaluator.py
- [[Generate a query typical of a given category (for negatives).]] - rationale - modules\grimoire\embedding_evaluator.py
- [[Grimoire mock with 4 diverse memories.]] - rationale - tests\test_embedding_evaluator.py
- [[Load the most recent benchmark for a model.]] - rationale - modules\omen\model_evaluator.py
- [[Negative queries should come from a different category.]] - rationale - tests\test_embedding_evaluator.py
- [[Pick a document from a different category as a negative example.]] - rationale - modules\grimoire\embedding_evaluator.py
- [[Pre-built eval set for reuse.]] - rationale - tests\test_embedding_evaluator.py
- [[Run retrieval evaluation against Grimoire.          For each positive query, che]] - rationale - modules\grimoire\embedding_evaluator.py
- [[Run the same eval set against two embedding models.          Temporarily swaps t]] - rationale - modules\grimoire\embedding_evaluator.py
- [[Store benchmark results in Grimoire and JSON file.          Args             re]] - rationale - modules\omen\model_evaluator.py
- [[TestBuildEvalSet]] - code - tests\test_embedding_evaluator.py
- [[TestExportTrainingPairs]] - code - tests\test_embedding_evaluator.py
- [[TestFormatReport]] - code - tests\test_embedding_evaluator.py
- [[TestQueryExtraction]] - code - tests\test_embedding_evaluator.py
- [[TestRunEval]] - code - tests\test_embedding_evaluator.py
- [[TestStoreBenchmark]] - code - tests\test_embedding_evaluator.py
- [[Tests for Embedding Evaluator — Retrieval Quality Metrics ======================]] - rationale - tests\test_embedding_evaluator.py
- [[When recall() always returns the expected doc at rank 1.]] - rationale - tests\test_embedding_evaluator.py
- [[When recall() never returns the expected doc.]] - rationale - tests\test_embedding_evaluator.py
- [[_make_mock_grimoire()]] - code - tests\test_embedding_evaluator.py
- [[eval_set()]] - code - tests\test_embedding_evaluator.py
- [[mock_grimoire()_5]] - code - tests\test_embedding_evaluator.py
- [[run_eval(None) should call build_eval_set() internally.]] - rationale - tests\test_embedding_evaluator.py
- [[test_embedding_evaluator.py]] - code - tests\test_embedding_evaluator.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Embedding_Evaluator
SORT file.name ASC
```

## Connections to other communities
- 38 edges to [[_COMMUNITY_Async Task Queue]]
- 10 edges to [[_COMMUNITY_Code Analyzer (Omen)]]
- 3 edges to [[_COMMUNITY_Module Lifecycle]]
- 3 edges to [[_COMMUNITY_Cross-Reference & Security]]
- 1 edge to [[_COMMUNITY_Data Pipeline & Embeddings]]

## Top bridge nodes
- [[.store_benchmark()_1]] - degree 15, connects to 4 communities
- [[.export_training_pairs()]] - degree 13, connects to 3 communities
- [[.build_eval_set()]] - degree 20, connects to 2 communities
- [[.run_eval()]] - degree 20, connects to 2 communities
- [[test_embedding_evaluator.py]] - degree 12, connects to 2 communities