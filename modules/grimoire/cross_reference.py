"""
Cross-Reference Linker — Auto-discover and link related Grimoire memories.

When a new memory is stored, CrossReferenceLinker finds semantically similar
existing memories and creates bidirectional links between them. This lets
retrieval follow relationship chains — if you find one relevant memory,
you can walk its links to find related context that might not match the
original query directly.

Links are stored in SQLite (not ChromaDB) for fast graph queries. ChromaDB
is great for vector search but terrible for relationship traversal.

Author: Patrick (with Claude Opus 4.6)
Project: Shadow
Module: Grimoire — Cross-Reference subsystem
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime

logger = logging.getLogger("grimoire.cross_reference")


class CrossReferenceLinker:
    """
    Discovers and manages semantic links between Grimoire memories.

    Uses Grimoire's recall() to find related entries by meaning, then stores
    bidirectional links in a dedicated SQLite table for fast graph traversal.

    Usage:
        linker = CrossReferenceLinker(grimoire)

        # After storing a new memory, find and link related ones
        count = linker.auto_link_new_entry(new_memory_id)

        # Get all links for a memory
        links = linker.get_links(memory_id)

        # Build a full graph for visualization
        graph = linker.build_link_graph()
    """

    def __init__(self, grimoire):
        """
        Initialize the linker with a reference to Grimoire.

        Args:
            grimoire: A Grimoire instance. We use its recall() for semantic
                      search and its SQLite connection for link storage.
        """
        self.grimoire = grimoire
        self.conn = grimoire.conn
        self._create_table()

    def _create_table(self):
        """Create the cross_references table if it doesn't exist."""
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cross_references (
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                similarity REAL NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (source_id, target_id)
            )
        """)
        # Index for fast lookups from either direction
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_xref_target
            ON cross_references (target_id)
        """)
        self.conn.commit()

    def link_related(self, entry_id: str, threshold: float = 0.75) -> list[dict]:
        """
        Find entries related to the given entry by semantic similarity.

        Retrieves the entry's content, searches for similar memories via
        Grimoire's recall(), filters by threshold, and stores bidirectional
        links for any matches above the threshold.

        Args:
            entry_id: UUID of the memory to find links for.
            threshold: Minimum similarity score (0.0-1.0) to create a link.
                       Default 0.75 — high enough to avoid noise, low enough
                       to catch meaningful connections.

        Returns:
            List of dicts: {related_id, similarity_score, snippet}
            Empty list if no related entries found or entry doesn't exist.
        """
        # Fetch the entry's content from SQLite
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT content FROM memories WHERE id = ? AND is_active = 1",
            (entry_id,)
        )
        row = cursor.fetchone()
        if not row:
            logger.warning("Cross-ref: entry %s not found or inactive", entry_id)
            return []

        content = row["content"]

        # Use Grimoire's recall to find similar memories
        # Request extra results so we have room after filtering
        results = self.grimoire.recall(content, n_results=20)

        links = []
        now = datetime.now().isoformat()

        for result in results:
            related_id = result["id"]

            # Skip self-reference
            if related_id == entry_id:
                continue

            similarity = result.get("relevance", 0.0)

            # Only link if above threshold
            if similarity < threshold:
                continue

            # Store bidirectional link (both directions)
            self._store_link(entry_id, related_id, similarity, now)

            links.append({
                "related_id": related_id,
                "similarity_score": similarity,
                "snippet": result["content"][:200]
            })

        if links:
            logger.info(
                "Cross-ref: linked %s to %d related entries (threshold=%.2f)",
                entry_id[:8], len(links), threshold
            )

        return links

    def _store_link(self, source_id: str, target_id: str,
                    similarity: float, created_at: str):
        """
        Store a bidirectional link between two memories.

        Uses INSERT OR REPLACE so re-linking updates the similarity score
        if the relationship is re-evaluated later.
        """
        cursor = self.conn.cursor()

        # Forward link: source -> target
        cursor.execute("""
            INSERT OR REPLACE INTO cross_references
            (source_id, target_id, similarity, created_at)
            VALUES (?, ?, ?, ?)
        """, (source_id, target_id, similarity, created_at))

        # Reverse link: target -> source
        cursor.execute("""
            INSERT OR REPLACE INTO cross_references
            (source_id, target_id, similarity, created_at)
            VALUES (?, ?, ?, ?)
        """, (target_id, source_id, similarity, created_at))

        self.conn.commit()

    def get_links(self, entry_id: str) -> list[dict]:
        """
        Get all cross-references for a memory.

        Returns links in both directions — memories this entry links TO
        and memories that link TO this entry. Since we store bidirectionally,
        querying source_id covers both.

        Args:
            entry_id: UUID of the memory to get links for.

        Returns:
            List of dicts: {related_id, similarity, created_at}
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT target_id, similarity, created_at
            FROM cross_references
            WHERE source_id = ?
            ORDER BY similarity DESC
        """, (entry_id,))

        return [
            {
                "related_id": row["target_id"],
                "similarity": row["similarity"],
                "created_at": row["created_at"]
            }
            for row in cursor.fetchall()
        ]

    def build_link_graph(self, collection: str = None) -> dict:
        """
        Build a graph of all cross-references for visualization.

        Returns a node/edge structure suitable for graph rendering (e.g.,
        D3.js, NetworkX, or simple JSON export).

        Args:
            collection: Optional category filter. If provided, only include
                        memories in this category. None = all memories.

        Returns:
            Dict with:
                - nodes: list of {id, label} (label = first 80 chars of content)
                - edges: list of {source, target, weight} (weight = similarity)
        """
        cursor = self.conn.cursor()

        # Get all unique memory IDs involved in cross-references
        if collection:
            # Filter: only memories in the specified category
            cursor.execute("""
                SELECT DISTINCT cr.source_id, cr.target_id, cr.similarity
                FROM cross_references cr
                JOIN memories m1 ON cr.source_id = m1.id AND m1.is_active = 1
                JOIN memories m2 ON cr.target_id = m2.id AND m2.is_active = 1
                WHERE m1.category = ? AND m2.category = ?
            """, (collection, collection))
        else:
            cursor.execute("""
                SELECT DISTINCT cr.source_id, cr.target_id, cr.similarity
                FROM cross_references cr
                JOIN memories m1 ON cr.source_id = m1.id AND m1.is_active = 1
                JOIN memories m2 ON cr.target_id = m2.id AND m2.is_active = 1
            """)

        rows = cursor.fetchall()

        # Collect unique node IDs and build edges
        # Use a set for deduplication since links are bidirectional
        node_ids = set()
        seen_edges = set()
        edges = []

        for row in rows:
            source = row["source_id"]
            target = row["target_id"]
            similarity = row["similarity"]

            node_ids.add(source)
            node_ids.add(target)

            # Deduplicate edges — only keep one direction (alphabetically first)
            edge_key = tuple(sorted([source, target]))
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                edges.append({
                    "source": edge_key[0],
                    "target": edge_key[1],
                    "weight": similarity
                })

        # Fetch labels for all nodes
        nodes = []
        for node_id in node_ids:
            cursor.execute(
                "SELECT content FROM memories WHERE id = ?",
                (node_id,)
            )
            row = cursor.fetchone()
            label = row["content"][:80] if row else "unknown"
            nodes.append({"id": node_id, "label": label})

        return {"nodes": nodes, "edges": edges}

    def auto_link_new_entry(self, entry_id: str, threshold: float = 0.75) -> int:
        """
        Called after remember() — finds and creates links for a new entry.

        This is the main integration point. After Grimoire stores a new memory,
        this method finds related existing memories and creates bidirectional
        links to them.

        Args:
            entry_id: UUID of the newly stored memory.
            threshold: Minimum similarity to create a link.

        Returns:
            Count of links created.
        """
        links = self.link_related(entry_id, threshold=threshold)
        return len(links)
