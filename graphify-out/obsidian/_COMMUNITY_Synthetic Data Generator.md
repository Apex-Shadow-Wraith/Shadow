---
type: community
cohesion: 0.05
members: 82
---

# Synthetic Data Generator

**Cohesion:** 0.05 - loosely connected
**Members:** 82 nodes

## Members
- [[._build_anti_sycophancy_prompt()]] - code - modules\apex\synthetic_data_generator.py
- [[._build_generation_prompt()]] - code - modules\apex\synthetic_data_generator.py
- [[._build_personality_prompt()]] - code - modules\apex\synthetic_data_generator.py
- [[._call_claude()_1]] - code - modules\apex\synthetic_data_generator.py
- [[._format_entry()]] - code - modules\apex\synthetic_data_generator.py
- [[._get_api_key()]] - code - modules\apex\synthetic_data_generator.py
- [[._handle_synthetic_command()]] - code - modules\shadow\orchestrator.py
- [[._parse_response()]] - code - modules\apex\synthetic_data_generator.py
- [[.generate_anti_sycophancy()]] - code - modules\apex\synthetic_data_generator.py
- [[.generate_batch()]] - code - modules\apex\synthetic_data_generator.py
- [[.generate_personality_examples()]] - code - modules\apex\synthetic_data_generator.py
- [[.save_batch()]] - code - modules\apex\synthetic_data_generator.py
- [[.test_all_categories_accepted()]] - code - tests\test_synthetic_data_generator.py
- [[.test_all_difficulties_accepted()]] - code - tests\test_synthetic_data_generator.py
- [[.test_anti_sycophancy_prompt_includes_pushback()]] - code - tests\test_synthetic_data_generator.py
- [[.test_falls_back_to_env()]] - code - tests\test_synthetic_data_generator.py
- [[.test_generation_prompt_includes_category()]] - code - tests\test_synthetic_data_generator.py
- [[.test_generation_prompt_includes_difficulty()]] - code - tests\test_synthetic_data_generator.py
- [[.test_generation_prompt_includes_shadow_identity()]] - code - tests\test_synthetic_data_generator.py
- [[.test_invalid_category_raises()]] - code - tests\test_synthetic_data_generator.py
- [[.test_invalid_difficulty_raises()]] - code - tests\test_synthetic_data_generator.py
- [[.test_mixed_difficulty_prompt()]] - code - tests\test_synthetic_data_generator.py
- [[.test_parse_filters_invalid_entries()]] - code - tests\test_synthetic_data_generator.py
- [[.test_parse_invalid_json()]] - code - tests\test_synthetic_data_generator.py
- [[.test_parse_non_array()]] - code - tests\test_synthetic_data_generator.py
- [[.test_parse_valid_json()]] - code - tests\test_synthetic_data_generator.py
- [[.test_parse_with_markdown_fences()]] - code - tests\test_synthetic_data_generator.py
- [[.test_personality_prompt_includes_master()]] - code - tests\test_synthetic_data_generator.py
- [[.test_raises_without_key()]] - code - tests\test_synthetic_data_generator.py
- [[.test_save_empty_batch()]] - code - tests\test_synthetic_data_generator.py
- [[.test_uses_init_key()]] - code - tests\test_synthetic_data_generator.py
- [[Build a fake Claude API response containing the given examples.]] - rationale - tests\test_synthetic_data_generator.py
- [[Build a list of raw example dicts (as Claude would return).]] - rationale - tests\test_synthetic_data_generator.py
- [[Build prompt for generating anti-sycophancy examples.          Args]] - rationale - modules\apex\synthetic_data_generator.py
- [[Build prompt for generating personality examples.          Args             cou]] - rationale - modules\apex\synthetic_data_generator.py
- [[Build raw anti-sycophancy examples with pushback language.]] - rationale - tests\test_synthetic_data_generator.py
- [[Build raw personality examples that use 'Master' and avoid hedging.]] - rationale - tests\test_synthetic_data_generator.py
- [[Build the prompt sent to Claude for generating examples.          Args]] - rationale - modules\apex\synthetic_data_generator.py
- [[Call Claude API with the given prompt.          Args             prompt The ge]] - rationale - modules\apex\synthetic_data_generator.py
- [[Every defined category should be accepted without ValueError.]] - rationale - tests\test_synthetic_data_generator.py
- [[Format a single example into the JSONL training schema.          Args]] - rationale - modules\apex\synthetic_data_generator.py
- [[Generate examples demonstrating Shadow's voice.          Direct, no hedging, use]] - rationale - modules\apex\synthetic_data_generator.py
- [[Generate examples where Shadow pushes back, disagrees, or says 'I don't know'.]] - rationale - modules\apex\synthetic_data_generator.py
- [[Generate synthetic training examples via Claude API.          Args]] - rationale - modules\apex\synthetic_data_generator.py
- [[Parse Claude's JSON response into example dicts.          Handles markdown fence]] - rationale - modules\apex\synthetic_data_generator.py
- [[Resolve API key from init param or environment.          Returns             Th]] - rationale - modules\apex\synthetic_data_generator.py
- [[Save a batch of examples to a JSONL file.          Args             examples L]] - rationale - modules\apex\synthetic_data_generator.py
- [[TestAntiSycophancy]] - code - tests\test_synthetic_data_generator.py
- [[TestApiKey]] - code - tests\test_synthetic_data_generator.py
- [[TestCategoryValidation]] - code - tests\test_synthetic_data_generator.py
- [[TestGenerateBatch]] - code - tests\test_synthetic_data_generator.py
- [[TestParsing]] - code - tests\test_synthetic_data_generator.py
- [[TestPersonalityExamples]] - code - tests\test_synthetic_data_generator.py
- [[TestPromptBuilding]] - code - tests\test_synthetic_data_generator.py
- [[TestSaveBatch]] - code - tests\test_synthetic_data_generator.py
- [[Tests for Synthetic Training Data Generator ====================================]] - rationale - tests\test_synthetic_data_generator.py
- [[_make_anti_sycophancy_examples()]] - code - tests\test_synthetic_data_generator.py
- [[_make_examples()]] - code - tests\test_synthetic_data_generator.py
- [[_make_personality_examples()]] - code - tests\test_synthetic_data_generator.py
- [[_mock_claude_response()]] - code - tests\test_synthetic_data_generator.py
- [[test_appends_not_overwrites()]] - code - tests\test_synthetic_data_generator.py
- [[test_contains_master()]] - code - tests\test_synthetic_data_generator.py
- [[test_contains_pushback_language()]] - code - tests\test_synthetic_data_generator.py
- [[test_conversations_are_chatml_format()]] - code - tests\test_synthetic_data_generator.py
- [[test_correct_filepath_format()]] - code - tests\test_synthetic_data_generator.py
- [[test_count_respected()]] - code - tests\test_synthetic_data_generator.py
- [[test_creates_file()]] - code - tests\test_synthetic_data_generator.py
- [[test_empty_api_response()]] - code - tests\test_synthetic_data_generator.py
- [[test_malformed_json_response()]] - code - tests\test_synthetic_data_generator.py
- [[test_markdown_fenced_response()]] - code - tests\test_synthetic_data_generator.py
- [[test_metadata_fields()]] - code - tests\test_synthetic_data_generator.py
- [[test_metadata_source()]] - code - tests\test_synthetic_data_generator.py
- [[test_no_hedging_phrases()]] - code - tests\test_synthetic_data_generator.py
- [[test_rate_limit_max_5_calls()]] - code - tests\test_synthetic_data_generator.py
- [[test_rate_limited()]] - code - tests\test_synthetic_data_generator.py
- [[test_returns_entries()]] - code - tests\test_synthetic_data_generator.py
- [[test_returns_valid_entries()]] - code - tests\test_synthetic_data_generator.py
- [[test_stats_after_save()]] - code - tests\test_synthetic_data_generator.py
- [[test_stats_multiple_categories()]] - code - tests\test_synthetic_data_generator.py
- [[test_synthetic_data_generator.py]] - code - tests\test_synthetic_data_generator.py
- [[test_system_prompt_included()]] - code - tests\test_synthetic_data_generator.py
- [[test_valid_jsonl_output()]] - code - tests\test_synthetic_data_generator.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Synthetic_Data_Generator
SORT file.name ASC
```

## Connections to other communities
- 32 edges to [[_COMMUNITY_Async Task Queue]]
- 4 edges to [[_COMMUNITY_Module Lifecycle]]
- 4 edges to [[_COMMUNITY_Apex API Providers]]
- 3 edges to [[_COMMUNITY_Code Analyzer (Omen)]]
- 1 edge to [[_COMMUNITY_Base Module & Apex API]]
- 1 edge to [[_COMMUNITY_Security Analyzer Rationale]]

## Top bridge nodes
- [[test_synthetic_data_generator.py]] - degree 37, connects to 3 communities
- [[.save_batch()]] - degree 12, connects to 3 communities
- [[._handle_synthetic_command()]] - degree 9, connects to 3 communities
- [[.generate_batch()]] - degree 25, connects to 2 communities
- [[.generate_anti_sycophancy()]] - degree 13, connects to 2 communities