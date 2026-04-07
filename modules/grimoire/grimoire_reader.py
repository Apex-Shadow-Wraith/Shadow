"""
GrimoireReader — Read-Only Grimoire Access for All Modules
============================================================
Lightweight interface that gives any module independent access to
Grimoire's knowledge base without going through the orchestrator.

Read-only by design: modules can search and retrieve, but storage
still goes through Grimoire proper to maintain consistency and
deduplication logic.

Each module gets its own GrimoireReader instance with the module name
tracked for audit logging (which module searched for what).

Usage:
    reader = GrimoireReader("sentinel")
    results = reader.search("firewall configuration patterns")
    exists = reader.check_knowledge_exists("port scanning detection")
    reader.close()
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import requests

logger = logging.getLogger("grimoire.reader")


class GrimoireReader:
    """Read-only interface to Grimoire's dual-storage memory system.

    Connects to the same SQLite database and ChromaDB collection that
    Grimoire uses, but only performs SELECT queries and vector searches.
    No INSERT, UPDATE, or DELETE operations.
    """

    def __init__(
        self,
        module_name: str,
        memory_db_path: str = "data/memory/shadow_memory.db",
        vector_db_path: str = "data/vectors",
        ollama_url: str = "http://localhost:11434",
        embed_model: str = "nomic-embed-text",
    ) -> None:
        """Initialize a read-only Grimoire connection for a specific module.

        Args:
            module_name: Which module owns this reader (for audit logging).
            memory_db_path: Path to Grimoire's SQLite database.
            vector_db_path: Path to ChromaDB persistent storage.
            ollama_url: Ollama API endpoint for embeddings.
            embed_model: Embedding model name.
        """
        self.module_name = module_name
        self.db_path = Path(memory_db_path)
        self.vector_path = Path(vector_db_path)
        self.ollama_url = ollama_url
        self.embed_model = embed_model

        self._conn: sqlite3.Connection | None = None
        self._collection = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization — connect on first use, not on construction."""
        if self._initialized:
            return

        try:
            # SQLite read-only connection
            if self.db_path.exists():
                self._conn = sqlite3.connect(
                    f"file:{self.db_path}?mode=ro",
                    uri=True,
                    check_same_thread=False,
                )
                self._conn.row_factory = sqlite3.Row
            else:
                logger.warning(
                    "[GrimoireReader:%s] Database not found: %s",
                    self.module_name,
                    self.db_path,
                )

            # ChromaDB — shared persistent client (read operations only)
            if self.vector_path.exists():
                import chromadb

                self._chroma_client = chromadb.PersistentClient(
                    path=str(self.vector_path)
                )
                self._collection = self._chroma_client.get_or_create_collection(
                    name="shadow_memories",
                    metadata={"hnsw:space": "cosine"},
                )
            else:
                logger.warning(
                    "[GrimoireReader:%s] Vector path not found: %s",
                    self.module_name,
                    self.vector_path,
                )
        except Exception as e:
            logger.error(
                "[GrimoireReader:%s] Initialization failed: %s",
                self.module_name,
                e,
            )

        self._initialized = True

    def _get_embedding(self, text: str) -> list[float]:
        """Generate embedding vector via Ollama API.

        Mirrors Grimoire's embedding logic for consistency.
        Truncates long text to ~2000 chars before embedding.

        Args:
            text: Text to embed.

        Returns:
            768-dimensional float vector.

        Raises:
            RuntimeError: If embedding fails after retries.
        """
        truncated = text[:2000] if len(text) > 2000 else text

        for attempt in range(3):
            try:
                response = requests.post(
                    f"{self.ollama_url}/api/embeddings",
                    json={"model": self.embed_model, "prompt": truncated},
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()
                embedding = data.get("embedding", [])
                if embedding:
                    return embedding
            except Exception as e:
                if attempt == 2:
                    raise RuntimeError(
                        f"Embedding failed after 3 attempts: {e}"
                    ) from e
                logger.warning(
                    "[GrimoireReader:%s] Embedding attempt %d failed: %s",
                    self.module_name,
                    attempt + 1,
                    e,
                )

        raise RuntimeError("Embedding returned empty result")

    def search(
        self,
        query: str,
        limit: int = 5,
        category: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Semantic search across Grimoire's knowledge base.

        Uses ChromaDB embeddings to find memories by meaning, then
        enriches results with full metadata from SQLite.

        Args:
            query: Natural language search query.
            limit: Maximum results to return.
            category: Optional category filter.

        Returns:
            List of dicts with: content, metadata, relevance_score, source, timestamp.
        """
        self._ensure_initialized()

        if not self._collection or not self._conn:
            logger.warning(
                "[GrimoireReader:%s] Search unavailable — not connected",
                self.module_name,
            )
            return []

        try:
            query_embedding = self._get_embedding(query)
        except RuntimeError as e:
            logger.error("[GrimoireReader:%s] %s", self.module_name, e)
            return []

        # Build ChromaDB filter
        where_filter = None
        if category:
            where_filter = {"category": category}

        try:
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                where=where_filter,
            )
        except Exception as e:
            logger.error(
                "[GrimoireReader:%s] ChromaDB query failed: %s",
                self.module_name,
                e,
            )
            return []

        # Enrich with SQLite data
        memories = []
        if results and results["ids"] and results["ids"][0]:
            cursor = self._conn.cursor()
            for i, memory_id in enumerate(results["ids"][0]):
                cursor.execute(
                    "SELECT * FROM memories WHERE id = ? AND is_active = 1",
                    (memory_id,),
                )
                row = cursor.fetchone()
                if row:
                    distance = results["distances"][0][i]
                    relevance = max(0.0, 1.0 - distance)

                    memories.append({
                        "content": row["content"],
                        "metadata": json.loads(row["metadata_json"] or "{}"),
                        "relevance_score": round(relevance, 4),
                        "source": row["source"],
                        "timestamp": row["created_at"],
                        "id": row["id"],
                        "category": row["category"],
                        "source_module": row["source_module"],
                        "trust_level": row["trust_level"],
                        "confidence": row["confidence"],
                        "access_count": row["access_count"],
                    })

        logger.debug(
            "[GrimoireReader:%s] search(%r) → %d results",
            self.module_name,
            query[:50],
            len(memories),
        )
        return memories

    def search_by_category(
        self,
        category: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Return all entries in a category, newest first.

        Uses SQLite directly — no embedding needed for category browsing.

        Args:
            category: Category to browse (e.g., "code_pattern", "security_knowledge").
            limit: Maximum results.

        Returns:
            List of memory dicts.
        """
        self._ensure_initialized()

        if not self._conn:
            return []

        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT id, content, category, source, source_module, trust_level,
                   confidence, created_at, access_count, metadata_json
            FROM memories
            WHERE category = ? AND is_active = 1
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (category, limit),
        )
        rows = cursor.fetchall()

        return [
            {
                "content": row["content"],
                "metadata": json.loads(row["metadata_json"] or "{}"),
                "relevance_score": 1.0,  # Exact category match
                "source": row["source"],
                "timestamp": row["created_at"],
                "id": row["id"],
                "category": row["category"],
                "source_module": row["source_module"],
                "trust_level": row["trust_level"],
                "confidence": row["confidence"],
                "access_count": row["access_count"],
            }
            for row in rows
        ]

    def search_related(
        self,
        memory_id: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Find memories related to a specific memory entry.

        Uses the existing memory's embedding to find nearest neighbors
        in ChromaDB, excluding the source memory itself.

        Args:
            memory_id: UUID of the memory to find relatives for.
            limit: Maximum related memories to return.

        Returns:
            List of related memory dicts.
        """
        self._ensure_initialized()

        if not self._collection or not self._conn:
            return []

        try:
            # Fetch the embedding of the source memory
            result = self._collection.get(
                ids=[memory_id],
                include=["embeddings"],
            )
            if not result or not result["embeddings"] or not result["embeddings"][0]:
                logger.warning(
                    "[GrimoireReader:%s] Memory %s not found in vectors",
                    self.module_name,
                    memory_id,
                )
                return []

            source_embedding = result["embeddings"][0]

            # Search for neighbors (request limit+1 to exclude self)
            neighbors = self._collection.query(
                query_embeddings=[source_embedding],
                n_results=limit + 1,
            )
        except Exception as e:
            logger.error(
                "[GrimoireReader:%s] Related search failed: %s",
                self.module_name,
                e,
            )
            return []

        # Enrich with SQLite, excluding the source memory
        memories = []
        if neighbors and neighbors["ids"] and neighbors["ids"][0]:
            cursor = self._conn.cursor()
            for i, neighbor_id in enumerate(neighbors["ids"][0]):
                if neighbor_id == memory_id:
                    continue
                if len(memories) >= limit:
                    break

                cursor.execute(
                    "SELECT * FROM memories WHERE id = ? AND is_active = 1",
                    (neighbor_id,),
                )
                row = cursor.fetchone()
                if row:
                    distance = neighbors["distances"][0][i]
                    relevance = max(0.0, 1.0 - distance)

                    memories.append({
                        "content": row["content"],
                        "metadata": json.loads(row["metadata_json"] or "{}"),
                        "relevance_score": round(relevance, 4),
                        "source": row["source"],
                        "timestamp": row["created_at"],
                        "id": row["id"],
                        "category": row["category"],
                        "source_module": row["source_module"],
                        "trust_level": row["trust_level"],
                        "confidence": row["confidence"],
                        "access_count": row["access_count"],
                    })

        return memories

    def get_module_knowledge(
        self,
        module_name: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return all knowledge stored by a specific module.

        Answers: "What has Omen learned?" or "What does Sentinel know?"

        Args:
            module_name: Module whose knowledge to retrieve.
            limit: Maximum results.

        Returns:
            List of memory dicts from that module.
        """
        self._ensure_initialized()

        if not self._conn:
            return []

        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT id, content, category, source, source_module, trust_level,
                   confidence, created_at, access_count, metadata_json
            FROM memories
            WHERE source_module = ? AND is_active = 1
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (module_name, limit),
        )
        rows = cursor.fetchall()

        return [
            {
                "content": row["content"],
                "metadata": json.loads(row["metadata_json"] or "{}"),
                "relevance_score": 1.0,
                "source": row["source"],
                "timestamp": row["created_at"],
                "id": row["id"],
                "category": row["category"],
                "source_module": row["source_module"],
                "trust_level": row["trust_level"],
                "confidence": row["confidence"],
                "access_count": row["access_count"],
            }
            for row in rows
        ]

    def check_knowledge_exists(
        self,
        query: str,
        threshold: float = 0.85,
    ) -> bool:
        """Quick check: does Grimoire already have knowledge about this topic?

        Used for deduplication before storing new knowledge.

        Args:
            query: Topic to check for.
            threshold: Similarity threshold (0.0-1.0). Default 0.85 means
                      "very similar content already exists."

        Returns:
            True if any existing memory exceeds the similarity threshold.
        """
        self._ensure_initialized()

        if not self._collection:
            return False

        try:
            query_embedding = self._get_embedding(query)
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=1,
            )

            if results and results["distances"] and results["distances"][0]:
                distance = results["distances"][0][0]
                relevance = 1.0 - distance
                return relevance >= threshold

        except Exception as e:
            logger.error(
                "[GrimoireReader:%s] Knowledge check failed: %s",
                self.module_name,
                e,
            )

        return False

    def get_recent(
        self,
        limit: int = 10,
        hours: int = 24,
    ) -> list[dict[str, Any]]:
        """Return most recently stored memories within a time window.

        Args:
            limit: Maximum results.
            hours: Look back this many hours from now.

        Returns:
            List of recent memory dicts, newest first.
        """
        self._ensure_initialized()

        if not self._conn:
            return []

        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT id, content, category, source, source_module, trust_level,
                   confidence, created_at, access_count, metadata_json
            FROM memories
            WHERE created_at >= ? AND is_active = 1
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (cutoff, limit),
        )
        rows = cursor.fetchall()

        return [
            {
                "content": row["content"],
                "metadata": json.loads(row["metadata_json"] or "{}"),
                "relevance_score": 1.0,
                "source": row["source"],
                "timestamp": row["created_at"],
                "id": row["id"],
                "category": row["category"],
                "source_module": row["source_module"],
                "trust_level": row["trust_level"],
                "confidence": row["confidence"],
                "access_count": row["access_count"],
            }
            for row in rows
        ]

    def close(self) -> None:
        """Close database connections."""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
        self._initialized = False
        logger.debug("[GrimoireReader:%s] Closed", self.module_name)
