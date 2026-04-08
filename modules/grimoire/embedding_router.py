"""
Embedding Router — Domain-Specific Embedding Routing for Grimoire
==================================================================
Routes Grimoire queries to different embedding models optimized for
different content types. Code queries use a code-optimized model,
natural language uses a general model.

Initially all domains use the same model (nomic-embed-text). The
architecture supports swapping in domain-specific models later
(e.g., code-optimized embeddings) without changing any calling code.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("shadow.grimoire.embedding_router")

DEFAULT_ROUTING = {
    "code": {"model": "nomic-embed-text", "collection_suffix": "_code"},
    "natural_language": {"model": "nomic-embed-text", "collection_suffix": "_nl"},
    "business": {"model": "nomic-embed-text", "collection_suffix": "_biz"},
    "default": {"model": "nomic-embed-text", "collection_suffix": ""},
}

# Keywords for domain classification
_CODE_KEYWORDS = {
    "function", "class", "def", "import", "error", "bug",
    "compile", "syntax", "variable", "api", "database", "sql",
}

_BUSINESS_KEYWORDS = {
    "invoice", "client", "schedule", "job", "estimate",
    "landscaping", "payment", "customer",
}


class EmbeddingRouter:
    """Route Grimoire queries to domain-specific embedding models and collections."""

    def __init__(
        self,
        config: dict | None = None,
        ollama_base_url: str = "http://localhost:11434",
    ) -> None:
        self._routing = dict(config) if config else dict(DEFAULT_ROUTING)
        self._ollama_base_url = ollama_base_url
        self._stats: dict[str, int] = {}

    def classify_query(self, query: str) -> str:
        """Determine which domain a query belongs to using rule-based classification."""
        if not query or not query.strip():
            return "natural_language"

        lower = query.lower()
        words = set(re.findall(r'[a-z]+', lower))

        code_hits = len(words & _CODE_KEYWORDS)
        biz_hits = len(words & _BUSINESS_KEYWORDS)

        if code_hits > 0 and code_hits >= biz_hits:
            return "code"
        if biz_hits > 0:
            return "business"
        return "natural_language"

    def get_embedding_model(self, domain: str) -> str:
        """Return the embedding model name for a domain, falling back to default."""
        if domain in self._routing:
            return self._routing[domain]["model"]
        return self._routing["default"]["model"]

    def get_collection_name(self, base_collection: str, domain: str) -> str:
        """Return domain-specific collection name with suffix applied."""
        if domain in self._routing:
            suffix = self._routing[domain]["collection_suffix"]
        else:
            suffix = self._routing["default"]["collection_suffix"]
        return f"{base_collection}{suffix}"

    def route_query(
        self,
        query: str,
        base_collection: str = "grimoire_knowledge",
    ) -> dict[str, Any]:
        """Classify, get model, get collection — all in one call."""
        domain = self.classify_query(query)
        self._stats[domain] = self._stats.get(domain, 0) + 1

        return {
            "domain": domain,
            "embedding_model": self.get_embedding_model(domain),
            "collection_name": self.get_collection_name(base_collection, domain),
            "query": query,
        }

    def route_for_storage(
        self,
        content: str,
        metadata: dict | None = None,
        base_collection: str = "grimoire_knowledge",
    ) -> dict[str, Any]:
        """Determine which collection to store content in."""
        # Use metadata domain_tags if available
        if metadata and "domain_tags" in metadata:
            domain = metadata["domain_tags"]
            if isinstance(domain, list):
                domain = domain[0] if domain else "natural_language"
        else:
            domain = self.classify_query(content)

        return {
            "domain": domain,
            "embedding_model": self.get_embedding_model(domain),
            "collection_name": self.get_collection_name(base_collection, domain),
        }

    def get_all_collections_for_search(
        self,
        base_collection: str = "grimoire_knowledge",
    ) -> list[str]:
        """Return all domain-specific collection names for broad searches."""
        collections = []
        for domain in self._routing:
            name = self.get_collection_name(base_collection, domain)
            if name not in collections:
                collections.append(name)
        return collections

    def update_routing_config(
        self,
        domain: str,
        model: str,
        collection_suffix: str,
    ) -> bool:
        """Update routing for a domain (e.g., swap in a code-optimized model)."""
        self._routing[domain] = {
            "model": model,
            "collection_suffix": collection_suffix,
        }
        return True

    def get_routing_stats(self) -> dict[str, Any]:
        """Return queries routed per domain and model usage distribution."""
        model_usage: dict[str, int] = {}
        for domain, count in self._stats.items():
            model = self.get_embedding_model(domain)
            model_usage[model] = model_usage.get(model, 0) + count

        return {
            "queries_per_domain": dict(self._stats),
            "model_usage": model_usage,
            "total_queries": sum(self._stats.values()),
        }
