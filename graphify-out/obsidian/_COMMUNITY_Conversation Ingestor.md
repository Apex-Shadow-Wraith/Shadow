---
type: community
cohesion: 0.03
members: 127
---

# Conversation Ingestor

**Cohesion:** 0.03 - loosely connected
**Members:** 127 nodes

## Members
- [[._categorize()]] - code - modules\grimoire\conversation_ingestor.py
- [[._extract_file_changes()]] - code - modules\grimoire\conversation_ingestor.py
- [[._is_noise()]] - code - modules\grimoire\conversation_ingestor.py
- [[._normalize_entry()]] - code - modules\grimoire\conversation_ingestor.py
- [[._parse_by_format()]] - code - modules\grimoire\conversation_ingestor.py
- [[._save_manifest()]] - code - modules\grimoire\conversation_ingestor.py
- [[.extract_knowledge()]] - code - modules\grimoire\conversation_ingestor.py
- [[.ingest()]] - code - modules\grimoire\conversation_ingestor.py
- [[.parse_chatgpt_export()]] - code - modules\grimoire\conversation_ingestor.py
- [[.parse_claude_export()]] - code - modules\grimoire\conversation_ingestor.py
- [[.parse_transcript()]] - code - modules\grimoire\conversation_ingestor.py
- [[.scan_transcripts()]] - code - modules\grimoire\conversation_ingestor.py
- [[.test_auto_detect_ingest()]] - code - tests\test_conversation_ingestor.py
- [[.test_basic_parse()_2]] - code - tests\test_conversation_ingestor.py
- [[.test_basic_parse()_1]] - code - tests\test_conversation_ingestor.py
- [[.test_basic_parse()]] - code - tests\test_conversation_ingestor.py
- [[.test_categorizes_architecture()]] - code - tests\test_conversation_ingestor.py
- [[.test_categorizes_bug_fix()]] - code - tests\test_conversation_ingestor.py
- [[.test_categorizes_configuration()]] - code - tests\test_conversation_ingestor.py
- [[.test_categorizes_implementation()]] - code - tests\test_conversation_ingestor.py
- [[.test_categorizes_testing()]] - code - tests\test_conversation_ingestor.py
- [[.test_chatgpt_ingest_tags()]] - code - tests\test_conversation_ingestor.py
- [[.test_chatgpt_knowledge_extraction()]] - code - tests\test_conversation_ingestor.py
- [[.test_claude_ai_ingest_tags()]] - code - tests\test_conversation_ingestor.py
- [[.test_claude_ai_knowledge_extraction()]] - code - tests\test_conversation_ingestor.py
- [[.test_content_blocks_format()]] - code - tests\test_conversation_ingestor.py
- [[.test_detects_chatgpt()]] - code - tests\test_conversation_ingestor.py
- [[.test_detects_claude_ai()]] - code - tests\test_conversation_ingestor.py
- [[.test_detects_claude_code_jsonl()]] - code - tests\test_conversation_ingestor.py
- [[.test_empty_conversations()]] - code - tests\test_conversation_ingestor.py
- [[.test_empty_directory()]] - code - tests\test_conversation_ingestor.py
- [[.test_empty_messages()]] - code - tests\test_conversation_ingestor.py
- [[.test_end_to_end()]] - code - tests\test_conversation_ingestor.py
- [[.test_errors_collected_not_raised()]] - code - tests\test_conversation_ingestor.py
- [[.test_file_changes_detected()]] - code - tests\test_conversation_ingestor.py
- [[.test_filters_path_listings()]] - code - tests\test_conversation_ingestor.py
- [[.test_filters_short_content()]] - code - tests\test_conversation_ingestor.py
- [[.test_filters_tool_output_noise()]] - code - tests\test_conversation_ingestor.py
- [[.test_finds_jsonl_files()]] - code - tests\test_conversation_ingestor.py
- [[.test_grimoire_remember_called_correctly()]] - code - tests\test_conversation_ingestor.py
- [[.test_invalid_json_defaults_to_claude_code()]] - code - tests\test_conversation_ingestor.py
- [[.test_keeps_substantial_tool_output()]] - code - tests\test_conversation_ingestor.py
- [[.test_malformed_json()_1]] - code - tests\test_conversation_ingestor.py
- [[.test_malformed_json()]] - code - tests\test_conversation_ingestor.py
- [[.test_manifest_persisted_to_disk()]] - code - tests\test_conversation_ingestor.py
- [[.test_messages_sorted_by_time()]] - code - tests\test_conversation_ingestor.py
- [[.test_metadata_populated()]] - code - tests\test_conversation_ingestor.py
- [[.test_missing_file()_2]] - code - tests\test_conversation_ingestor.py
- [[.test_missing_file()_1]] - code - tests\test_conversation_ingestor.py
- [[.test_missing_file()]] - code - tests\test_conversation_ingestor.py
- [[.test_multiple_conversations()]] - code - tests\test_conversation_ingestor.py
- [[.test_multiple_files()]] - code - tests\test_conversation_ingestor.py
- [[.test_new_files_processed_after_manifest_load()]] - code - tests\test_conversation_ingestor.py
- [[.test_no_files_returns_zeros()]] - code - tests\test_conversation_ingestor.py
- [[.test_nodes_without_message_skipped()]] - code - tests\test_conversation_ingestor.py
- [[.test_nonexistent_defaults_to_claude_code()]] - code - tests\test_conversation_ingestor.py
- [[.test_nonexistent_directory()]] - code - tests\test_conversation_ingestor.py
- [[.test_processed_files_tracked()]] - code - tests\test_conversation_ingestor.py
- [[.test_sanitization_applied_to_exports()]] - code - tests\test_conversation_ingestor.py
- [[.test_sanitizes_secrets()]] - code - tests\test_conversation_ingestor.py
- [[.test_scan_chatgpt()]] - code - tests\test_conversation_ingestor.py
- [[.test_scan_claude_ai()]] - code - tests\test_conversation_ingestor.py
- [[.test_scan_claude_code()]] - code - tests\test_conversation_ingestor.py
- [[.test_scans_subdirectories()]] - code - tests\test_conversation_ingestor.py
- [[.test_skips_already_processed()]] - code - tests\test_conversation_ingestor.py
- [[.test_skips_invalid_json_lines()]] - code - tests\test_conversation_ingestor.py
- [[.test_skips_system_role()]] - code - tests\test_conversation_ingestor.py
- [[.test_source_metadata()_1]] - code - tests\test_conversation_ingestor.py
- [[.test_source_metadata()]] - code - tests\test_conversation_ingestor.py
- [[.test_stats_accumulate()]] - code - tests\test_conversation_ingestor.py
- [[.test_stats_after_ingestion()]] - code - tests\test_conversation_ingestor.py
- [[.test_timestamp_preserved()]] - code - tests\test_conversation_ingestor.py
- [[.test_timestamps_converted()]] - code - tests\test_conversation_ingestor.py
- [[.test_timestamps_preserved()]] - code - tests\test_conversation_ingestor.py
- [[.test_tool_calls_extracted()]] - code - tests\test_conversation_ingestor.py
- [[.test_unexpected_format()]] - code - tests\test_conversation_ingestor.py
- [[.test_unknown_json_structure()]] - code - tests\test_conversation_ingestor.py
- [[Categorize an exchange using keyword heuristics.]] - rationale - modules\grimoire\conversation_ingestor.py
- [[Claude Code may store content as a list of blocks.]] - rationale - tests\test_conversation_ingestor.py
- [[Conversation Ingestor — mines Claude Code transcripts into Grimoire.  Scans ~.c]] - rationale - modules\grimoire\conversation_ingestor.py
- [[Convert a raw JSONL entry into a normalized exchange dict.]] - rationale - modules\grimoire\conversation_ingestor.py
- [[Create temp transcript dir and manifest path.]] - rationale - tests\test_conversation_ingestor.py
- [[Dispatch to the correct parser based on format.]] - rationale - modules\grimoire\conversation_ingestor.py
- [[Extract Grimoire-worthy knowledge entries from exchanges.          Filters noise]] - rationale - modules\grimoire\conversation_ingestor.py
- [[Find all unprocessed transcriptexport files.          Args             directo]] - rationale - modules\grimoire\conversation_ingestor.py
- [[Mapping nodes without a message key should be skipped.]] - rationale - tests\test_conversation_ingestor.py
- [[Messages should come out in chronological order.]] - rationale - tests\test_conversation_ingestor.py
- [[Mock Grimoire that tracks remember() calls.]] - rationale - tests\test_conversation_ingestor.py
- [[Non-dict top-level should return empty.]] - rationale - tests\test_conversation_ingestor.py
- [[Parse a ChatGPT conversation export (conversations.json).          ChatGPT expor]] - rationale - modules\grimoire\conversation_ingestor.py
- [[Parse a Claude Code JSONL transcript into structured exchanges.          Each li]] - rationale - modules\grimoire\conversation_ingestor.py
- [[Parse a Claude.ai conversation export (JSON format).          Claude.ai exports]] - rationale - modules\grimoire\conversation_ingestor.py
- [[Persist the manifest to disk (append-only semantics).]] - rationale - modules\grimoire\conversation_ingestor.py
- [[Pull file paths from tool calls that modify files.]] - rationale - modules\grimoire\conversation_ingestor.py
- [[Return True if the exchange is pure noise (tool output, listings).]] - rationale - modules\grimoire\conversation_ingestor.py
- [[Return a sample ChatGPT conversations.json list.]] - rationale - tests\test_conversation_ingestor.py
- [[Return a sample Claude.ai export dict.]] - rationale - tests\test_conversation_ingestor.py
- [[Run the full pipeline scan → parse → extract → store in Grimoire.          Args]] - rationale - modules\grimoire\conversation_ingestor.py
- [[System messages should be included (role in allowed set).]] - rationale - tests\test_conversation_ingestor.py
- [[TestAutoDetection]] - code - tests\test_conversation_ingestor.py
- [[TestExportKnowledgeExtraction]] - code - tests\test_conversation_ingestor.py
- [[TestExtractKnowledge]] - code - tests\test_conversation_ingestor.py
- [[TestIngestPipeline]] - code - tests\test_conversation_ingestor.py
- [[TestManifestTracking]] - code - tests\test_conversation_ingestor.py
- [[TestParseChatGPTExport]] - code - tests\test_conversation_ingestor.py
- [[TestParseClaudeExport]] - code - tests\test_conversation_ingestor.py
- [[TestParseTranscript]] - code - tests\test_conversation_ingestor.py
- [[TestScanTranscripts]] - code - tests\test_conversation_ingestor.py
- [[TestScanWithSource]] - code - tests\test_conversation_ingestor.py
- [[TestSourceTagging]] - code - tests\test_conversation_ingestor.py
- [[TestStats]] - code - tests\test_conversation_ingestor.py
- [[Tests for the Conversation Ingestor — Claude Code transcript mining.]] - rationale - tests\test_conversation_ingestor.py
- [[When source is not specified, detect_format is used for .json files.]] - rationale - tests\test_conversation_ingestor.py
- [[Write a list of dicts as JSONL to the given path, return str path.]] - rationale - tests\test_conversation_ingestor.py
- [[Write data as JSON to the given path, return str path.]] - rationale - tests\test_conversation_ingestor.py
- [[_looks_like_path()]] - code - modules\grimoire\conversation_ingestor.py
- [[_sample_chatgpt_export()]] - code - tests\test_conversation_ingestor.py
- [[_sample_claude_ai_export()]] - code - tests\test_conversation_ingestor.py
- [[_sanitize()]] - code - modules\grimoire\conversation_ingestor.py
- [[_source_tag()]] - code - modules\grimoire\conversation_ingestor.py
- [[_write_json()]] - code - tests\test_conversation_ingestor.py
- [[_write_jsonl()]] - code - tests\test_conversation_ingestor.py
- [[conversation_ingestor.py]] - code - modules\grimoire\conversation_ingestor.py
- [[detect_format()]] - code - modules\grimoire\conversation_ingestor.py
- [[mock_grimoire()_3]] - code - tests\test_conversation_ingestor.py
- [[test_conversation_ingestor.py]] - code - tests\test_conversation_ingestor.py
- [[tmp_dirs()]] - code - tests\test_conversation_ingestor.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Conversation_Ingestor
SORT file.name ASC
```

## Connections to other communities
- 43 edges to [[_COMMUNITY_Async Task Queue]]
- 5 edges to [[_COMMUNITY_Module Lifecycle]]
- 3 edges to [[_COMMUNITY_Apex API Providers]]
- 1 edge to [[_COMMUNITY_Cross-Reference & Security]]
- 1 edge to [[_COMMUNITY_Code Analyzer (Omen)]]

## Top bridge nodes
- [[.ingest()]] - degree 24, connects to 3 communities
- [[.parse_chatgpt_export()]] - degree 15, connects to 2 communities
- [[.parse_claude_export()]] - degree 13, connects to 2 communities
- [[.parse_transcript()]] - degree 12, connects to 2 communities
- [[.scan_transcripts()]] - degree 12, connects to 2 communities