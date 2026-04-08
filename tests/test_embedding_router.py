"""
Tests for Embedding Router — Domain-Specific Embedding Routing
===============================================================
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from modules.grimoire.embedding_router import EmbeddingRouter, DEFAULT_ROUTING


# ── Classification Tests ───────────────────────────────────────────

class TestClassifyQuery:
    def setup_method(self):
        self.router = EmbeddingRouter()

    def test_code_keyword_def(self):
        assert self.router.classify_query("def fibonacci(n):") == "code"

    def test_code_keyword_sql(self):
        assert self.router.classify_query("Fix the SQL query") == "code"

    def test_code_keyword_import(self):
        assert self.router.classify_query("import os module") == "code"

    def test_code_keyword_bug(self):
        assert self.router.classify_query("There's a bug in the API") == "code"

    def test_business_keyword_schedule(self):
        assert self.router.classify_query("Schedule landscaping job for Tuesday") == "business"

    def test_business_keyword_invoice(self):
        assert self.router.classify_query("Send invoice to customer") == "business"

    def test_natural_language_default(self):
        assert self.router.classify_query("Explain photosynthesis") == "natural_language"

    def test_mixed_content_code_dominant(self):
        """When code keywords outnumber business keywords, classify as code."""
        result = self.router.classify_query("Fix the database SQL error for client")
        # 3 code keywords (database, sql, error) vs 1 business (client)
        assert result == "code"

    def test_empty_query(self):
        assert self.router.classify_query("") == "natural_language"

    def test_very_short_query(self):
        result = self.router.classify_query("hi")
        assert result == "natural_language"

    def test_whitespace_only_query(self):
        assert self.router.classify_query("   ") == "natural_language"


# ── Routing Tests ──────────────────────────────────────────────────

class TestRouteQuery:
    def setup_method(self):
        self.router = EmbeddingRouter()

    def test_route_code_query(self):
        result = self.router.route_query("def my_function():")
        assert result["domain"] == "code"
        assert result["embedding_model"] == "nomic-embed-text"
        assert result["collection_name"] == "grimoire_knowledge_code"
        assert result["query"] == "def my_function():"

    def test_route_business_query(self):
        result = self.router.route_query("Send invoice to customer")
        assert result["domain"] == "business"
        assert result["collection_name"] == "grimoire_knowledge_biz"

    def test_route_natural_language_query(self):
        result = self.router.route_query("What is the meaning of life?")
        assert result["domain"] == "natural_language"
        assert result["collection_name"] == "grimoire_knowledge_nl"

    def test_route_unknown_domain_fallback(self):
        """get_embedding_model falls back to default for unknown domains."""
        model = self.router.get_embedding_model("nonexistent_domain")
        assert model == "nomic-embed-text"


# ── Storage Routing Tests ─────────────────────────────────────────

class TestRouteForStorage:
    def setup_method(self):
        self.router = EmbeddingRouter()

    def test_uses_metadata_domain_tags(self):
        result = self.router.route_for_storage(
            "some content",
            metadata={"domain_tags": "code"},
        )
        assert result["domain"] == "code"
        assert result["collection_name"] == "grimoire_knowledge_code"

    def test_uses_metadata_domain_tags_list(self):
        result = self.router.route_for_storage(
            "some content",
            metadata={"domain_tags": ["business", "code"]},
        )
        assert result["domain"] == "business"

    def test_classifies_from_content_when_no_metadata(self):
        result = self.router.route_for_storage("def fibonacci(n):")
        assert result["domain"] == "code"

    def test_classifies_from_content_when_no_domain_tags(self):
        result = self.router.route_for_storage(
            "Schedule landscaping job",
            metadata={"source": "wraith"},
        )
        assert result["domain"] == "business"


# ── Collection Tests ───────────────────────────────────────────────

class TestCollections:
    def setup_method(self):
        self.router = EmbeddingRouter()

    def test_collection_name_code(self):
        assert self.router.get_collection_name("grimoire_knowledge", "code") == "grimoire_knowledge_code"

    def test_collection_name_default(self):
        assert self.router.get_collection_name("grimoire_knowledge", "default") == "grimoire_knowledge"

    def test_collection_name_unknown_domain(self):
        """Unknown domain falls back to default (no suffix)."""
        assert self.router.get_collection_name("grimoire_knowledge", "unknown") == "grimoire_knowledge"

    def test_get_all_collections(self):
        collections = self.router.get_all_collections_for_search("grimoire_knowledge")
        assert "grimoire_knowledge_code" in collections
        assert "grimoire_knowledge_nl" in collections
        assert "grimoire_knowledge_biz" in collections
        assert "grimoire_knowledge" in collections
        assert len(collections) == 4


# ── Configuration Tests ────────────────────────────────────────────

class TestConfiguration:
    def test_update_routing_config(self):
        router = EmbeddingRouter()
        result = router.update_routing_config("code", "code-bert-v2", "_code_v2")
        assert result is True
        assert router.get_embedding_model("code") == "code-bert-v2"
        assert router.get_collection_name("base", "code") == "base_code_v2"

    def test_default_config_has_all_domains(self):
        assert "code" in DEFAULT_ROUTING
        assert "natural_language" in DEFAULT_ROUTING
        assert "business" in DEFAULT_ROUTING
        assert "default" in DEFAULT_ROUTING

    def test_custom_config(self):
        config = {"code": {"model": "custom-model", "collection_suffix": "_custom"}}
        router = EmbeddingRouter(config=config)
        assert router.get_embedding_model("code") == "custom-model"


# ── Stats Tests ────────────────────────────────────────────────────

class TestRoutingStats:
    def test_stats_track_per_domain(self):
        router = EmbeddingRouter()
        router.route_query("def foo():")
        router.route_query("import os")
        router.route_query("What is the weather?")
        stats = router.get_routing_stats()
        assert stats["queries_per_domain"]["code"] == 2
        assert stats["queries_per_domain"]["natural_language"] == 1
        assert stats["total_queries"] == 3

    def test_stats_empty_initially(self):
        router = EmbeddingRouter()
        stats = router.get_routing_stats()
        assert stats["total_queries"] == 0
        assert stats["queries_per_domain"] == {}


# ── Grimoire Integration Tests ─────────────────────────────────────

class TestGrimoireIntegration:
    def test_search_routed_calls_router(self):
        """GrimoireModule.search_routed should use the embedding router."""
        from modules.grimoire.grimoire_module import GrimoireModule

        module = GrimoireModule(config={})
        # Mock the router and grimoire
        mock_router = MagicMock()
        mock_router.route_query.return_value = {
            "domain": "code",
            "embedding_model": "nomic-embed-text",
            "collection_name": "grimoire_knowledge_code",
            "query": "def foo():",
        }
        module._embedding_router = mock_router
        mock_grimoire = MagicMock()
        mock_grimoire.recall.return_value = [{"content": "result"}]
        module._grimoire = mock_grimoire

        results = module.search_routed("def foo():")
        mock_router.route_query.assert_called_once_with("def foo():", "grimoire_knowledge")

    def test_search_routed_falls_back_to_base(self):
        """When domain-specific collection returns nothing, fall back to base."""
        from modules.grimoire.grimoire_module import GrimoireModule

        module = GrimoireModule(config={})
        mock_router = MagicMock()
        mock_router.route_query.return_value = {
            "domain": "code",
            "embedding_model": "nomic-embed-text",
            "collection_name": "grimoire_knowledge_code",
            "query": "def foo():",
        }
        module._embedding_router = mock_router
        mock_grimoire = MagicMock()
        # First call (domain-specific) returns empty, second (base) returns results
        mock_grimoire.recall.side_effect = [[], [{"content": "fallback"}]]
        module._grimoire = mock_grimoire

        results = module.search_routed("def foo():")
        assert len(mock_grimoire.recall.call_args_list) == 2

    def test_store_routed_routes_to_correct_collection(self):
        """GrimoireModule.store_routed should route storage through the router."""
        from modules.grimoire.grimoire_module import GrimoireModule

        module = GrimoireModule(config={})
        mock_router = MagicMock()
        mock_router.route_for_storage.return_value = {
            "domain": "business",
            "embedding_model": "nomic-embed-text",
            "collection_name": "grimoire_knowledge_biz",
        }
        module._embedding_router = mock_router
        mock_grimoire = MagicMock()
        mock_grimoire.remember.return_value = "mem_123"
        module._grimoire = mock_grimoire

        result = module.store_routed("Schedule landscaping job", metadata={"source": "wraith"})
        mock_router.route_for_storage.assert_called_once()

    def test_existing_search_unchanged(self):
        """The existing search_staged method should still work without router."""
        from modules.grimoire.grimoire_module import GrimoireModule

        module = GrimoireModule(config={})
        mock_grimoire = MagicMock()
        mock_grimoire.recall.return_value = [{"content": "result"}]
        module._grimoire = mock_grimoire
        module.staged_retrieval = None

        results = module.search_staged("test query")
        mock_grimoire.recall.assert_called_once()

    def test_search_routed_without_router(self):
        """search_routed without a router falls back to regular recall."""
        from modules.grimoire.grimoire_module import GrimoireModule

        module = GrimoireModule(config={})
        module._embedding_router = None
        mock_grimoire = MagicMock()
        mock_grimoire.recall.return_value = [{"content": "result"}]
        module._grimoire = mock_grimoire

        results = module.search_routed("test")
        mock_grimoire.recall.assert_called_once_with(query="test", n_results=5)
