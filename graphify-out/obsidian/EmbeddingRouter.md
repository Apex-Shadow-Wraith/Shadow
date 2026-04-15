---
source_file: "modules\grimoire\embedding_router.py"
type: "code"
community: "Embedding Router"
location: "L40"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Embedding_Router
---

# EmbeddingRouter

## Connections
- [[.__init__()_17]] - `method` [EXTRACTED]
- [[.__init__()_20]] - `calls` [INFERRED]
- [[.classify_query()]] - `method` [EXTRACTED]
- [[.get_all_collections_for_search()]] - `method` [EXTRACTED]
- [[.get_collection_name()]] - `method` [EXTRACTED]
- [[.get_embedding_model()]] - `method` [EXTRACTED]
- [[.get_routing_stats()]] - `method` [EXTRACTED]
- [[.route_for_storage()]] - `method` [EXTRACTED]
- [[.route_query()]] - `method` [EXTRACTED]
- [[.setup_method()]] - `calls` [INFERRED]
- [[.setup_method()_1]] - `calls` [INFERRED]
- [[.setup_method()_2]] - `calls` [INFERRED]
- [[.setup_method()_3]] - `calls` [INFERRED]
- [[.test_custom_config()_1]] - `calls` [INFERRED]
- [[.test_stats_empty_initially()]] - `calls` [INFERRED]
- [[.test_stats_track_per_domain()]] - `calls` [INFERRED]
- [[.test_update_routing_config()]] - `calls` [INFERRED]
- [[.update_routing_config()]] - `method` [EXTRACTED]
- [[BaseModule adapter for Grimoire (memory system).      Architecture 'Always ru]] - `uses` [INFERRED]
- [[Grimoire Module Adapter ======================== Wraps the existing Grimoire i]] - `uses` [INFERRED]
- [[Grimoire shutdown. Close connections.]] - `uses` [INFERRED]
- [[Grimoire's MCP tools.]] - `uses` [INFERRED]
- [[GrimoireModule]] - `uses` [INFERRED]
- [[GrimoireModule.search_routed should use the embedding router.]] - `uses` [INFERRED]
- [[GrimoireModule.store_routed should route storage through the router.]] - `uses` [INFERRED]
- [[Initialize the existing Grimoire system.]] - `uses` [INFERRED]
- [[Route Grimoire queries to domain-specific embedding models and collections.]] - `rationale_for` [EXTRACTED]
- [[Route tool calls to the existing Grimoire methods.]] - `uses` [INFERRED]
- [[Search using domain-specific embedding routing.          Routes the query to t]] - `uses` [INFERRED]
- [[Store content using domain-specific embedding routing.          Routes storage]] - `uses` [INFERRED]
- [[TestClassifyQuery]] - `uses` [INFERRED]
- [[TestCollections]] - `uses` [INFERRED]
- [[TestConfiguration]] - `uses` [INFERRED]
- [[TestGrimoireIntegration_1]] - `uses` [INFERRED]
- [[TestRouteForStorage]] - `uses` [INFERRED]
- [[TestRouteQuery]] - `uses` [INFERRED]
- [[TestRoutingStats]] - `uses` [INFERRED]
- [[Tests for Embedding Router — Domain-Specific Embedding Routing =================]] - `uses` [INFERRED]
- [[The existing search_staged method should still work without router.]] - `uses` [INFERRED]
- [[Two-stage search summaries first, then full content for top hits.          Fa]] - `uses` [INFERRED]
- [[Unknown domain falls back to default (no suffix).]] - `uses` [INFERRED]
- [[When code keywords outnumber business keywords, classify as code.]] - `uses` [INFERRED]
- [[When domain-specific collection returns nothing, fall back to base.]] - `uses` [INFERRED]
- [[embedding_router.py]] - `contains` [EXTRACTED]
- [[get_embedding_model falls back to default for unknown domains.]] - `uses` [INFERRED]
- [[search_routed without a router falls back to regular recall.]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/Embedding_Router