---
type: community
cohesion: 0.04
members: 66
---

# Grimoire Reader

**Cohesion:** 0.04 - loosely connected
**Members:** 66 nodes

## Members
- [[._ensure_initialized()]] - code - modules\grimoire\grimoire_reader.py
- [[._get_embedding()_2]] - code - modules\grimoire\grimoire_reader.py
- [[.check_knowledge_exists()]] - code - modules\grimoire\grimoire_reader.py
- [[.get_module_knowledge()]] - code - modules\grimoire\grimoire_reader.py
- [[.get_recent()]] - code - modules\grimoire\grimoire_reader.py
- [[.search()]] - code - modules\grimoire\grimoire_reader.py
- [[.search_by_category()]] - code - modules\grimoire\grimoire_reader.py
- [[.search_related()]] - code - modules\grimoire\grimoire_reader.py
- [[.test_custom_threshold()]] - code - tests\test_grimoire_reader.py
- [[.test_empty_category()]] - code - tests\test_grimoire_reader.py
- [[.test_excludes_old_memories()]] - code - tests\test_grimoire_reader.py
- [[.test_filters_by_category()]] - code - tests\test_grimoire_reader.py
- [[.test_filters_by_module_name()]] - code - tests\test_grimoire_reader.py
- [[.test_finds_related_memories()]] - code - tests\test_grimoire_reader.py
- [[.test_multiple_results()]] - code - tests\test_grimoire_reader.py
- [[.test_ordered_newest_first()_1]] - code - tests\test_grimoire_reader.py
- [[.test_ordered_newest_first()]] - code - tests\test_grimoire_reader.py
- [[.test_respects_limit()_2]] - code - tests\test_grimoire_reader.py
- [[.test_respects_limit()_1]] - code - tests\test_grimoire_reader.py
- [[.test_returns_empty_for_missing_memory()]] - code - tests\test_grimoire_reader.py
- [[.test_returns_empty_for_unknown_module()]] - code - tests\test_grimoire_reader.py
- [[.test_returns_false_for_new_knowledge()]] - code - tests\test_grimoire_reader.py
- [[.test_returns_false_when_no_results()]] - code - tests\test_grimoire_reader.py
- [[.test_returns_recent_memories()]] - code - tests\test_grimoire_reader.py
- [[.test_returns_true_for_existing_knowledge()]] - code - tests\test_grimoire_reader.py
- [[Create a mock ChromaDB collection.]] - rationale - tests\test_grimoire_reader.py
- [[Create a test SQLite database with sample memories.]] - rationale - tests\test_grimoire_reader.py
- [[Find memories related to a specific memory entry.          Uses the existing mem]] - rationale - modules\grimoire\grimoire_reader.py
- [[Generate embedding vector via Ollama API.          Mirrors Grimoire's embedding]] - rationale - modules\grimoire\grimoire_reader.py
- [[Lazy initialization — connect on first use, not on construction.]] - rationale - modules\grimoire\grimoire_reader.py
- [[Modules with multiple entries should return all of them.]] - rationale - tests\test_grimoire_reader.py
- [[Quick check does Grimoire already have knowledge about this topic          Use]] - rationale - modules\grimoire\grimoire_reader.py
- [[Results should be ordered by created_at DESC.]] - rationale - tests\test_grimoire_reader.py
- [[Results should be ordered by created_at DESC._1]] - rationale - tests\test_grimoire_reader.py
- [[Return all entries in a category, newest first.          Uses SQLite directly —]] - rationale - modules\grimoire\grimoire_reader.py
- [[Return all knowledge stored by a specific module.          Answers What has Om]] - rationale - modules\grimoire\grimoire_reader.py
- [[Return most recently stored memories within a time window.          Args]] - rationale - modules\grimoire\grimoire_reader.py
- [[Semantic search across Grimoire's knowledge base.          Uses ChromaDB embeddi]] - rationale - modules\grimoire\grimoire_reader.py
- [[Should find memories related to a given memory.]] - rationale - tests\test_grimoire_reader.py
- [[Should not return memories older than the time window.]] - rationale - tests\test_grimoire_reader.py
- [[Should respect custom threshold.]] - rationale - tests\test_grimoire_reader.py
- [[Should respect the limit parameter.]] - rationale - tests\test_grimoire_reader.py
- [[Should respect the limit parameter._1]] - rationale - tests\test_grimoire_reader.py
- [[Should return False when ChromaDB has no results.]] - rationale - tests\test_grimoire_reader.py
- [[Should return False when nothing similar exists.]] - rationale - tests\test_grimoire_reader.py
- [[Should return True when similar knowledge exists above threshold.]] - rationale - tests\test_grimoire_reader.py
- [[Should return empty list for a module with no stored knowledge.]] - rationale - tests\test_grimoire_reader.py
- [[Should return empty list for nonexistent category.]] - rationale - tests\test_grimoire_reader.py
- [[Should return empty list if source memory not found in vectors.]] - rationale - tests\test_grimoire_reader.py
- [[Should return memories created within the time window.]] - rationale - tests\test_grimoire_reader.py
- [[Should return only knowledge stored by the specified module.]] - rationale - tests\test_grimoire_reader.py
- [[Should return only memories in the specified category.]] - rationale - tests\test_grimoire_reader.py
- [[TestCheckKnowledgeExists]] - code - tests\test_grimoire_reader.py
- [[TestGetModuleKnowledge]] - code - tests\test_grimoire_reader.py
- [[TestGetRecent]] - code - tests\test_grimoire_reader.py
- [[TestSearchByCategory]] - code - tests\test_grimoire_reader.py
- [[TestSearchRelated]] - code - tests\test_grimoire_reader.py
- [[Tests for GrimoireReader — Read-Only Grimoire Access ===========================]] - rationale - tests\test_grimoire_reader.py
- [[Tests for category browsing.]] - rationale - tests\test_grimoire_reader.py
- [[Tests for deduplication check.]] - rationale - tests\test_grimoire_reader.py
- [[Tests for finding related memories.]] - rationale - tests\test_grimoire_reader.py
- [[Tests for module-specific knowledge retrieval.]] - rationale - tests\test_grimoire_reader.py
- [[Tests for time-windowed retrieval.]] - rationale - tests\test_grimoire_reader.py
- [[memory_db()]] - code - tests\test_grimoire_reader.py
- [[mock_collection()]] - code - tests\test_grimoire_reader.py
- [[test_grimoire_reader.py]] - code - tests\test_grimoire_reader.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Grimoire_Reader
SORT file.name ASC
```

## Connections to other communities
- 39 edges to [[_COMMUNITY_Async Task Queue]]
- 6 edges to [[_COMMUNITY_Data Pipeline & Embeddings]]
- 3 edges to [[_COMMUNITY_Base Module & Apex API]]
- 2 edges to [[_COMMUNITY_Module Lifecycle]]
- 1 edge to [[_COMMUNITY_Introspection Dashboard]]
- 1 edge to [[_COMMUNITY_Adversarial Sparring]]

## Top bridge nodes
- [[test_grimoire_reader.py]] - degree 11, connects to 3 communities
- [[.get_module_knowledge()]] - degree 9, connects to 3 communities
- [[.search_by_category()]] - degree 9, connects to 3 communities
- [[.get_recent()]] - degree 8, connects to 3 communities
- [[.check_knowledge_exists()]] - degree 9, connects to 2 communities