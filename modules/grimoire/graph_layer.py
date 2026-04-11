"""
GraphLayer — Embedded Knowledge Graph for Grimoire
====================================================
Stores entities as nodes and relationships as directed edges in SQLite.
Enables traversal queries: "what is related to X through Y?"

ChromaDB finds similar content. GraphLayer finds connected content.
Both results merged by Grimoire for richer retrieval.

Uses SQLite with recursive CTEs for graph traversal — zero external
dependencies, same deployment model as the rest of Shadow.

Author: Patrick (with Claude Opus 4.6)
Module: Grimoire sub-component
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("grimoire.graph")

# Valid entity types — what kinds of nodes can exist in the graph
VALID_ENTITY_TYPES = {
    "person", "concept", "tool", "module", "project",
    "technology", "organization", "location", "event",
}

# Valid relationship types — what kinds of edges can connect nodes
VALID_RELATION_TYPES = {
    "uses", "depends_on", "created_by", "related_to", "part_of",
    "improves", "contradicts", "supersedes", "implements", "learned_from",
}

# Conflict edge types — used by find_conflicts()
_CONFLICT_TYPES = {"contradicts", "supersedes"}


class GraphLayer:
    """Embedded knowledge graph using SQLite alongside ChromaDB.

    Stores entities as nodes and relationships as edges.
    Enables traversal queries: "what is related to X through Y?"
    ChromaDB finds similar content. GraphLayer finds connected content.
    Both results merged for richer retrieval.
    """

    def __init__(self, db_path: str) -> None:
        """Initialize SQLite-backed graph at the given path.

        Creates schema (entities + relationships tables) if not exists.

        Args:
            db_path: File path for the SQLite database.
                     Use ":memory:" for testing.
        """
        self.db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._create_schema()

    # -----------------------------------------------------------------
    # Schema
    # -----------------------------------------------------------------

    def _create_schema(self) -> None:
        """Create graph tables if they don't exist."""
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                name            TEXT PRIMARY KEY,
                entity_type     TEXT NOT NULL,
                source_memory_id TEXT,
                metadata        TEXT DEFAULT '{}',
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                source          TEXT NOT NULL,
                target          TEXT NOT NULL,
                relation_type   TEXT NOT NULL,
                confidence      REAL NOT NULL DEFAULT 0.5,
                source_memory_id TEXT,
                created_at      TEXT NOT NULL,
                FOREIGN KEY (source) REFERENCES entities(name),
                FOREIGN KEY (target) REFERENCES entities(name)
            )
        """)

        # Indexes for fast traversal
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_rel_source
            ON relationships(source)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_rel_target
            ON relationships(target)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_rel_type
            ON relationships(relation_type)
        """)

        self.conn.commit()

    # -----------------------------------------------------------------
    # Node operations
    # -----------------------------------------------------------------

    def add_entity(
        self,
        name: str,
        entity_type: str,
        source_memory_id: str,
        metadata: dict | None = None,
    ) -> None:
        """Add or update an entity node.

        Deduplicates by name — if entity already exists, updates
        entity_type, metadata, and updated_at.

        Args:
            name: Entity name (primary key).
            entity_type: One of VALID_ENTITY_TYPES.
            source_memory_id: UUID of the memory that sourced this entity.
            metadata: Optional dict of extra data (stored as JSON).
        """
        if entity_type not in VALID_ENTITY_TYPES:
            raise ValueError(
                f"Invalid entity_type '{entity_type}'. "
                f"Must be one of: {sorted(VALID_ENTITY_TYPES)}"
            )

        now = datetime.now().isoformat()
        meta_json = json.dumps(metadata or {})

        self.conn.execute("""
            INSERT INTO entities (name, entity_type, source_memory_id,
                                  metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                entity_type = excluded.entity_type,
                source_memory_id = excluded.source_memory_id,
                metadata = excluded.metadata,
                updated_at = excluded.updated_at
        """, (name, entity_type, source_memory_id, meta_json, now, now))
        self.conn.commit()

    def get_entity(self, name: str) -> dict | None:
        """Fetch a single entity by name. Returns None if not found."""
        row = self.conn.execute(
            "SELECT * FROM entities WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    # -----------------------------------------------------------------
    # Edge operations
    # -----------------------------------------------------------------

    def add_relationship(
        self,
        source: str,
        target: str,
        relation_type: str,
        confidence: float,
        source_memory_id: str,
    ) -> None:
        """Add a directed edge between two entities.

        Both source and target entities must already exist.

        Args:
            source: Name of the source entity.
            target: Name of the target entity.
            relation_type: One of VALID_RELATION_TYPES.
            confidence: Edge confidence, 0.0–1.0.
            source_memory_id: UUID of the memory that sourced this relationship.
        """
        if relation_type not in VALID_RELATION_TYPES:
            raise ValueError(
                f"Invalid relation_type '{relation_type}'. "
                f"Must be one of: {sorted(VALID_RELATION_TYPES)}"
            )
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"Confidence must be 0.0–1.0, got {confidence}")

        # Verify endpoints exist
        src = self.get_entity(source)
        tgt = self.get_entity(target)
        if src is None:
            raise ValueError(f"Source entity '{source}' does not exist")
        if tgt is None:
            raise ValueError(f"Target entity '{target}' does not exist")

        now = datetime.now().isoformat()
        self.conn.execute("""
            INSERT INTO relationships
                (source, target, relation_type, confidence,
                 source_memory_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (source, target, relation_type, confidence,
              source_memory_id, now))
        self.conn.commit()

    # -----------------------------------------------------------------
    # Traversal queries
    # -----------------------------------------------------------------

    def query_neighbors(
        self,
        entity_name: str,
        max_depth: int = 2,
        relation_filter: list[str] | None = None,
    ) -> list[dict]:
        """BFS traversal from an entity up to max_depth hops.

        Returns all reachable nodes and the edges used to reach them.
        Follows edges in both directions (outgoing and incoming).

        Args:
            entity_name: Starting entity name.
            max_depth: Maximum hops from start (default 2).
            relation_filter: Optional list of relation types to follow.
                             None means follow all types.

        Returns:
            List of dicts, each with keys:
                - name, entity_type, source_memory_id (node info)
                - depth (hops from start)
                - via_relation, via_source (edge that reached this node)
        """
        if self.get_entity(entity_name) is None:
            return []

        # Build optional relation filter clause
        if relation_filter:
            placeholders = ",".join("?" for _ in relation_filter)
            type_clause = f"AND relation_type IN ({placeholders})"
            type_params = list(relation_filter)
        else:
            type_clause = ""
            type_params = []

        # Iterative BFS — one SQL query per depth level
        # Avoids SQLite's "multiple recursive references" limitation
        visited: set[str] = {entity_name}
        frontier: set[str] = {entity_name}
        results: list[dict] = []

        for depth in range(1, max_depth + 1):
            if not frontier:
                break

            # Find all neighbors of the current frontier
            placeholders_f = ",".join("?" for _ in frontier)
            frontier_list = list(frontier)

            # Outgoing edges
            out_query = f"""
                SELECT target AS neighbor, relation_type, source AS via
                FROM relationships
                WHERE source IN ({placeholders_f})
                  {type_clause}
            """
            out_rows = self.conn.execute(
                out_query, frontier_list + type_params
            ).fetchall()

            # Incoming edges
            in_query = f"""
                SELECT source AS neighbor, relation_type, target AS via
                FROM relationships
                WHERE target IN ({placeholders_f})
                  {type_clause}
            """
            in_rows = self.conn.execute(
                in_query, frontier_list + type_params
            ).fetchall()

            next_frontier: set[str] = set()
            for row in list(out_rows) + list(in_rows):
                neighbor = row["neighbor"]
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                next_frontier.add(neighbor)

                entity = self.get_entity(neighbor)
                results.append({
                    "name": neighbor,
                    "entity_type": entity["entity_type"] if entity else None,
                    "source_memory_id": (
                        entity["source_memory_id"] if entity else None
                    ),
                    "depth": depth,
                    "via_relation": row["relation_type"],
                    "via_source": row["via"],
                })

            frontier = next_frontier

        # Sort by depth then name for deterministic output
        results.sort(key=lambda r: (r["depth"], r["name"]))
        return results

    def query_path(
        self,
        source: str,
        target: str,
        max_depth: int = 4,
    ) -> list[dict] | None:
        """Find shortest path between two entities.

        Uses iterative BFS with parent tracking. Follows directed edges
        in both directions.

        Args:
            source: Starting entity name.
            target: Destination entity name.
            max_depth: Maximum path length to search (default 4).

        Returns:
            List of dicts representing the path (nodes), or None
            if no path exists within max_depth.
        """
        if self.get_entity(source) is None or self.get_entity(target) is None:
            return None

        if source == target:
            entity = self.get_entity(source)
            return [{"name": source, "entity_type": entity["entity_type"]}]

        # Iterative BFS with parent tracking
        visited: dict[str, str | None] = {source: None}  # node → parent
        frontier: set[str] = {source}

        for _ in range(max_depth):
            if not frontier:
                break

            placeholders = ",".join("?" for _ in frontier)
            frontier_list = list(frontier)

            # Get neighbors (both directions)
            out_rows = self.conn.execute(f"""
                SELECT source, target FROM relationships
                WHERE source IN ({placeholders})
            """, frontier_list).fetchall()

            in_rows = self.conn.execute(f"""
                SELECT source, target FROM relationships
                WHERE target IN ({placeholders})
            """, frontier_list).fetchall()

            next_frontier: set[str] = set()
            for row in out_rows:
                neighbor = row["target"]
                if neighbor not in visited:
                    visited[neighbor] = row["source"]
                    next_frontier.add(neighbor)
                    if neighbor == target:
                        break
            else:
                for row in in_rows:
                    neighbor = row["source"]
                    if neighbor not in visited:
                        visited[neighbor] = row["target"]
                        next_frontier.add(neighbor)
                        if neighbor == target:
                            break

            if target in visited:
                break
            frontier = next_frontier

        if target not in visited:
            return None

        # Reconstruct path from target back to source
        path_names: list[str] = []
        current = target
        while current is not None:
            path_names.append(current)
            current = visited[current]
        path_names.reverse()

        result = []
        for name in path_names:
            entity = self.get_entity(name)
            if entity:
                result.append({
                    "name": name,
                    "entity_type": entity["entity_type"],
                    "source_memory_id": entity["source_memory_id"],
                })
        return result

    # -----------------------------------------------------------------
    # Conflict detection
    # -----------------------------------------------------------------

    def find_conflicts(self, entity_name: str) -> list[dict]:
        """Return all 'contradicts' or 'supersedes' edges involving this entity.

        Checks both directions — entity as source or target.

        Args:
            entity_name: Entity to check for conflicts.

        Returns:
            List of dicts with edge info (source, target, relation_type,
            confidence, source_memory_id).
        """
        rows = self.conn.execute("""
            SELECT source, target, relation_type, confidence,
                   source_memory_id, created_at
            FROM relationships
            WHERE (source = ? OR target = ?)
              AND relation_type IN ('contradicts', 'supersedes')
            ORDER BY created_at DESC
        """, (entity_name, entity_name)).fetchall()
        return [dict(row) for row in rows]

    # -----------------------------------------------------------------
    # Stats
    # -----------------------------------------------------------------

    def get_entity_stats(self) -> dict:
        """Count nodes by type, edges by type, and total graph size.

        Returns:
            Dict with keys: total_entities, total_relationships,
            entities_by_type (dict), relationships_by_type (dict).
        """
        # Count entities by type
        entity_rows = self.conn.execute("""
            SELECT entity_type, COUNT(*) as cnt
            FROM entities
            GROUP BY entity_type
        """).fetchall()
        entities_by_type = {row["entity_type"]: row["cnt"] for row in entity_rows}

        # Count relationships by type
        rel_rows = self.conn.execute("""
            SELECT relation_type, COUNT(*) as cnt
            FROM relationships
            GROUP BY relation_type
        """).fetchall()
        rels_by_type = {row["relation_type"]: row["cnt"] for row in rel_rows}

        total_entities = sum(entities_by_type.values())
        total_relationships = sum(rels_by_type.values())

        return {
            "total_entities": total_entities,
            "total_relationships": total_relationships,
            "entities_by_type": entities_by_type,
            "relationships_by_type": rels_by_type,
        }

    # -----------------------------------------------------------------
    # Merge (deduplication)
    # -----------------------------------------------------------------

    def merge_entities(self, keep: str, remove: str) -> None:
        """Merge two entity nodes — redirect all edges from 'remove' to 'keep'.

        After merging, 'remove' is deleted. Used for deduplication when
        two names refer to the same real-world entity.

        Args:
            keep: Entity name to keep.
            remove: Entity name to absorb and delete.

        Raises:
            ValueError: If either entity does not exist.
        """
        if self.get_entity(keep) is None:
            raise ValueError(f"Keep entity '{keep}' does not exist")
        if self.get_entity(remove) is None:
            raise ValueError(f"Remove entity '{remove}' does not exist")

        cursor = self.conn.cursor()

        # Redirect all edges where 'remove' is the source
        cursor.execute(
            "UPDATE relationships SET source = ? WHERE source = ?",
            (keep, remove)
        )
        # Redirect all edges where 'remove' is the target
        cursor.execute(
            "UPDATE relationships SET target = ? WHERE target = ?",
            (keep, remove)
        )
        # Remove self-loops that may have been created
        cursor.execute(
            "DELETE FROM relationships WHERE source = ? AND target = ?",
            (keep, keep)
        )
        # Delete the absorbed entity
        cursor.execute("DELETE FROM entities WHERE name = ?", (remove,))

        self.conn.commit()

    # -----------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
