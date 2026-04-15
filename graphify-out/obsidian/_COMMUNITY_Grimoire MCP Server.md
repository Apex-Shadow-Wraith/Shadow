---
type: community
cohesion: 0.03
members: 65
---

# Grimoire MCP Server

**Cohesion:** 0.03 - loosely connected
**Members:** 65 nodes

## Members
- [[.test_all_tools_have_input_schema()]] - code - tests\test_grimoire_mcp.py
- [[.test_collections_503_without_grimoire()]] - code - tests\test_grimoire_mcp.py
- [[.test_collections_empty()]] - code - tests\test_grimoire_mcp.py
- [[.test_collections_returns_categories()]] - code - tests\test_grimoire_mcp.py
- [[.test_manifest_exists_and_valid()]] - code - tests\test_grimoire_mcp.py
- [[.test_recall_503_without_grimoire()]] - code - tests\test_grimoire_mcp.py
- [[.test_recall_default_top_k()]] - code - tests\test_grimoire_mcp.py
- [[.test_recall_embedding_error()]] - code - tests\test_grimoire_mcp.py
- [[.test_recall_empty_db()]] - code - tests\test_grimoire_mcp.py
- [[.test_recall_returns_mcp_format()]] - code - tests\test_grimoire_mcp.py
- [[.test_recall_with_collection()]] - code - tests\test_grimoire_mcp.py
- [[.test_remember_503_without_grimoire()]] - code - tests\test_grimoire_mcp.py
- [[.test_remember_and_recall()]] - code - tests\test_grimoire_mcp.py
- [[.test_remember_error()]] - code - tests\test_grimoire_mcp.py
- [[.test_remember_stores_memory()]] - code - tests\test_grimoire_mcp.py
- [[.test_remember_with_metadata()]] - code - tests\test_grimoire_mcp.py
- [[.test_search_503_without_grimoire()]] - code - tests\test_grimoire_mcp.py
- [[.test_search_basic()]] - code - tests\test_grimoire_mcp.py
- [[.test_search_with_category_filter()]] - code - tests\test_grimoire_mcp.py
- [[.test_search_with_date_range()]] - code - tests\test_grimoire_mcp.py
- [[.test_search_with_min_trust()]] - code - tests\test_grimoire_mcp.py
- [[.test_search_with_module_filter()]] - code - tests\test_grimoire_mcp.py
- [[.test_stats_503_without_grimoire()]] - code - tests\test_grimoire_mcp.py
- [[.test_stats_error()]] - code - tests\test_grimoire_mcp.py
- [[.test_stats_returns_all_fields()]] - code - tests\test_grimoire_mcp.py
- [[Collections endpoint returns category counts.]] - rationale - tests\test_grimoire_mcp.py
- [[Collections returns 503 without Grimoire.]] - rationale - tests\test_grimoire_mcp.py
- [[Collections with no data returns empty dict.]] - rationale - tests\test_grimoire_mcp.py
- [[Create a mock Grimoire instance with sensible defaults.]] - rationale - tests\test_grimoire_mcp.py
- [[Endpoints return 503 when Grimoire is not initialized.]] - rationale - tests\test_grimoire_mcp.py
- [[Every tool in manifest has an input_schema.]] - rationale - tests\test_grimoire_mcp.py
- [[FastAPI test client with NO Grimoire (None).]] - rationale - tests\test_grimoire_mcp.py
- [[FastAPI test client with mocked Grimoire.]] - rationale - tests\test_grimoire_mcp.py
- [[MCP manifest JSON is valid and has all tools.]] - rationale - tests\test_grimoire_mcp.py
- [[Recall defaults to top_k=5.]] - rationale - tests\test_grimoire_mcp.py
- [[Recall passes collection as category filter.]] - rationale - tests\test_grimoire_mcp.py
- [[Recall returns error on embedding failure, not crash.]] - rationale - tests\test_grimoire_mcp.py
- [[Recall returns standard MCP tool result format.]] - rationale - tests\test_grimoire_mcp.py
- [[Recall with empty DB returns empty list.]] - rationale - tests\test_grimoire_mcp.py
- [[Remember passes metadata through.]] - rationale - tests\test_grimoire_mcp.py
- [[Remember returns 503 without Grimoire.]] - rationale - tests\test_grimoire_mcp.py
- [[Remember returns error on failure.]] - rationale - tests\test_grimoire_mcp.py
- [[Remember stores and returns memory ID.]] - rationale - tests\test_grimoire_mcp.py
- [[Remember stores, then recall retrieves it.]] - rationale - tests\test_grimoire_mcp.py
- [[Search filters by date range.]] - rationale - tests\test_grimoire_mcp.py
- [[Search filters results by source module.]] - rationale - tests\test_grimoire_mcp.py
- [[Search passes category filter to recall.]] - rationale - tests\test_grimoire_mcp.py
- [[Search passes min_trust to recall.]] - rationale - tests\test_grimoire_mcp.py
- [[Search returns 503 without Grimoire.]] - rationale - tests\test_grimoire_mcp.py
- [[Search returns MCP format.]] - rationale - tests\test_grimoire_mcp.py
- [[Stats returns 503 without Grimoire.]] - rationale - tests\test_grimoire_mcp.py
- [[Stats returns all required fields.]] - rationale - tests\test_grimoire_mcp.py
- [[Stats returns error on failure.]] - rationale - tests\test_grimoire_mcp.py
- [[TestGrimoireCollections]] - code - tests\test_grimoire_mcp.py
- [[TestGrimoireRecall]] - code - tests\test_grimoire_mcp.py
- [[TestGrimoireRemember]] - code - tests\test_grimoire_mcp.py
- [[TestGrimoireSearch]] - code - tests\test_grimoire_mcp.py
- [[TestGrimoireStats]] - code - tests\test_grimoire_mcp.py
- [[TestManifest]] - code - tests\test_grimoire_mcp.py
- [[TestServerWithoutGrimoire]] - code - tests\test_grimoire_mcp.py
- [[Tests for Grimoire MCP Server.  All tests mock the Grimoire class — no real Chro]] - rationale - tests\test_grimoire_mcp.py
- [[client()]] - code - tests\test_grimoire_mcp.py
- [[client_no_grimoire()]] - code - tests\test_grimoire_mcp.py
- [[mock_grimoire()_7]] - code - tests\test_grimoire_mcp.py
- [[test_grimoire_mcp.py]] - code - tests\test_grimoire_mcp.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Grimoire_MCP_Server
SORT file.name ASC
```

## Connections to other communities
- 2 edges to [[_COMMUNITY_Adversarial Sparring]]

## Top bridge nodes
- [[client()]] - degree 3, connects to 1 community
- [[client_no_grimoire()]] - degree 3, connects to 1 community