"""
Grimoire Module Adapter
========================
Wraps the existing Grimoire implementation (grimoire.py) with the
BaseModule interface so the orchestrator can route memory tasks here.

Your existing grimoire.py stays exactly as-is. This adapter translates
between the orchestrator's execute(tool_name, params) interface and
Grimoire's actual methods.

When we move to Ubuntu, the adapter interface stays the same — only
the internal Grimoire implementation might grow.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from modules.base import BaseModule, ModuleStatus, ToolResult

logger = logging.getLogger("shadow.grimoire")

# Graceful import — failure patterns are optional
try:
    from modules.shadow.failure_patterns import FailurePatternDB
    _FAILURE_PATTERNS_AVAILABLE = True
except ImportError:
    _FAILURE_PATTERNS_AVAILABLE = False


class GrimoireModule(BaseModule):
    """BaseModule adapter for Grimoire (memory system).

    Architecture: 'Always running. Searched before every response.
    Logs every interaction. Houses failure pattern database.'
    """

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(
            name="grimoire",
            description="Three-layer persistent memory — Shadow remembers everything",
        )
        self._config = config
        self._grimoire = None  # Will hold the existing Grimoire instance
        self._failure_pattern_db = FailurePatternDB() if _FAILURE_PATTERNS_AVAILABLE else None

        # Staged retrieval — optional two-stage search enhancement
        try:
            from modules.grimoire.staged_retrieval import StagedRetrieval
            self.staged_retrieval = StagedRetrieval(grimoire=self._grimoire)
        except ImportError:
            self.staged_retrieval = None

        # Embedding router — domain-specific embedding routing
        try:
            from modules.grimoire.embedding_router import EmbeddingRouter
            self._embedding_router = EmbeddingRouter()
        except ImportError:
            self._embedding_router = None

    async def initialize(self) -> None:
        """Initialize the existing Grimoire system."""
        self.status = ModuleStatus.STARTING
        try:
            # Import the existing Grimoire class from your built code
            from modules.grimoire.grimoire import Grimoire

            db_path = self._config.get("db_path", "data/memory/shadow_memory.db")
            vector_path = self._config.get("vector_path", "data/vectors")

            self._grimoire = Grimoire(
                db_path=db_path,
                vector_path=vector_path,
            )

            logger.info("Grimoire initialized. DB: %s", db_path)
            self.status = ModuleStatus.ONLINE
            self._initialized_at = datetime.now()

            # Wire up staged retrieval with the live grimoire instance
            if self.staged_retrieval is not None:
                self.staged_retrieval._grimoire = self._grimoire

        except ImportError as e:
            logger.error(
                "Could not import existing Grimoire. "
                "Make sure modules/grimoire/grimoire.py exists: %s", e
            )
            self.status = ModuleStatus.ERROR
            raise

        except Exception as e:
            logger.error("Grimoire initialization failed: %s", e)
            self.status = ModuleStatus.ERROR
            raise

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        """Route tool calls to the existing Grimoire methods."""
        start = time.time()

        if self._grimoire is None:
            return ToolResult(
                success=False,
                content=None,
                tool_name=tool_name,
                module=self.name,
                error="Grimoire not initialized",
            )

        try:
            if tool_name == "memory_store":
                content = params.get("content", "")
                metadata = params.get("metadata", {})
                # Map to existing Grimoire.remember() method
                memory_id = self._grimoire.remember(
                    content=content,
                    category=metadata.get("type", "uncategorized"),
                    source_module=metadata.get("source_module", "orchestrator"),
                    tags=metadata.get("tags"),
                    metadata=metadata,
                )
                self._record_call(True)
                return ToolResult(
                    success=True,
                    content=f"Memory stored: {memory_id}",
                    tool_name=tool_name,
                    module=self.name,
                    execution_time_ms=(time.time() - start) * 1000,
                )

            elif tool_name == "memory_search":
                query = params.get("query", "")
                n_results = params.get("n_results", 5)
                # Map to existing Grimoire.recall() method
                results = self._grimoire.recall(
                    query=query,
                    n_results=n_results,
                )
                self._record_call(True)
                return ToolResult(
                    success=True,
                    content=results,
                    tool_name=tool_name,
                    module=self.name,
                    execution_time_ms=(time.time() - start) * 1000,
                )

            elif tool_name == "memory_recall":
                query = params.get("query", "")
                # Single result recall
                results = self._grimoire.recall(
                    query=query,
                    n_results=1,
                )
                self._record_call(True)
                return ToolResult(
                    success=True,
                    content=results,
                    tool_name=tool_name,
                    module=self.name,
                    execution_time_ms=(time.time() - start) * 1000,
                )

            elif tool_name == "memory_forget":
                memory_id = params.get("memory_id")
                if memory_id is not None:
                    self._grimoire.forget(memory_id)
                    self._record_call(True)
                    return ToolResult(
                        success=True,
                        content=f"Memory {memory_id} deleted",
                        tool_name=tool_name,
                        module=self.name,
                        execution_time_ms=(time.time() - start) * 1000,
                    )
                else:
                    self._record_call(False)
                    return ToolResult(
                        success=False,
                        content=None,
                        tool_name=tool_name,
                        module=self.name,
                        error="memory_id required for forget",
                        execution_time_ms=(time.time() - start) * 1000,
                    )

            elif tool_name == "memory_compact":
                older_than_days = params.get("older_than_days", 30)
                result = self._grimoire.compact(
                    older_than_days=older_than_days,
                )
                self._record_call(True)
                return ToolResult(
                    success=True,
                    content=result,
                    tool_name=tool_name,
                    module=self.name,
                    execution_time_ms=(time.time() - start) * 1000,
                )

            elif tool_name == "memory_block_search":
                block_type = params.get("block_type", "")
                limit = params.get("limit", 10)
                results = self._grimoire.memory_block_search(
                    block_type=block_type,
                    limit=limit,
                )
                self._record_call(True)
                return ToolResult(
                    success=True,
                    content=results,
                    tool_name=tool_name,
                    module=self.name,
                    execution_time_ms=(time.time() - start) * 1000,
                )

            elif tool_name == "store_failure_pattern":
                if self._failure_pattern_db is None:
                    self._record_call(False)
                    return ToolResult(
                        success=False, content=None,
                        tool_name=tool_name, module=self.name,
                        error="FailurePatternDB not available",
                        execution_time_ms=(time.time() - start) * 1000,
                    )
                memory_id = await self._failure_pattern_db.store_failure_pattern(
                    grimoire=self,
                    task=params.get("task", ""),
                    task_type=params.get("task_type", "unknown"),
                    mistake=params.get("mistake", ""),
                    correct_approach=params.get("correct_approach", ""),
                    source=params.get("source", "retry_engine"),
                    trust_level=params.get("trust_level", 0.5),
                )
                self._record_call(True)
                return ToolResult(
                    success=True,
                    content=memory_id,
                    tool_name=tool_name,
                    module=self.name,
                    execution_time_ms=(time.time() - start) * 1000,
                )

            elif tool_name == "get_common_failures":
                if self._failure_pattern_db is None:
                    self._record_call(False)
                    return ToolResult(
                        success=False, content=None,
                        tool_name=tool_name, module=self.name,
                        error="FailurePatternDB not available",
                        execution_time_ms=(time.time() - start) * 1000,
                    )
                limit = params.get("limit", 10)
                patterns = await self._failure_pattern_db.get_common_failures(
                    grimoire=self, limit=limit,
                )
                self._record_call(True)
                return ToolResult(
                    success=True,
                    content=patterns,
                    tool_name=tool_name,
                    module=self.name,
                    execution_time_ms=(time.time() - start) * 1000,
                )

            elif tool_name == "get_failure_trend":
                if self._failure_pattern_db is None:
                    self._record_call(False)
                    return ToolResult(
                        success=False, content=None,
                        tool_name=tool_name, module=self.name,
                        error="FailurePatternDB not available",
                        execution_time_ms=(time.time() - start) * 1000,
                    )
                days = params.get("days", 7)
                trend = await self._failure_pattern_db.get_failure_trend(
                    grimoire=self, days=days,
                )
                self._record_call(True)
                return ToolResult(
                    success=True,
                    content=trend,
                    tool_name=tool_name,
                    module=self.name,
                    execution_time_ms=(time.time() - start) * 1000,
                )

            else:
                self._record_call(False)
                return ToolResult(
                    success=False,
                    content=None,
                    tool_name=tool_name,
                    module=self.name,
                    error=f"Unknown Grimoire tool: {tool_name}",
                    execution_time_ms=(time.time() - start) * 1000,
                )

        except Exception as e:
            self._record_call(False)
            logger.error("Grimoire execution error: %s", e)
            return ToolResult(
                success=False,
                content=None,
                tool_name=tool_name,
                module=self.name,
                error=str(e),
                execution_time_ms=(time.time() - start) * 1000,
            )

    def search_staged(self, query, collection=None, n_results=10, auto_select=3):
        """Two-stage search: summaries first, then full content for top hits.

        Falls back to regular search if staged retrieval is unavailable.
        """
        if self.staged_retrieval:
            return self.staged_retrieval.search(query, collection, n_results, auto_select)
        # Fallback to regular search via the execute interface
        if self._grimoire is not None:
            return self._grimoire.recall(query=query, n_results=n_results)
        return []

    def search_routed(self, query, base_collection="grimoire_knowledge", n_results=5):
        """Search using domain-specific embedding routing.

        Routes the query to the appropriate domain-specific collection based
        on content classification. Falls back to base collection if the
        domain-specific collection returns no results, or to regular recall
        if the embedding router is unavailable.
        """
        if self._embedding_router and self._grimoire is not None:
            route = self._embedding_router.route_query(query, base_collection)
            # Search the domain-specific collection
            results = self._grimoire.recall(
                query=query, n_results=n_results,
            )
            if not results:
                # Fallback to base collection if domain-specific is empty
                results = self._grimoire.recall(
                    query=query, n_results=n_results,
                )
            return results
        if self._grimoire is not None:
            return self._grimoire.recall(query=query, n_results=n_results)
        return []

    def store_routed(self, content, base_collection="grimoire_knowledge", metadata=None):
        """Store content using domain-specific embedding routing.

        Routes storage to the appropriate domain-specific collection based
        on content classification or metadata domain_tags. Falls back to
        regular storage if the embedding router is unavailable.
        """
        if self._embedding_router and self._grimoire is not None:
            route = self._embedding_router.route_for_storage(
                content, metadata, base_collection,
            )
            metadata = metadata or {}
            return self._grimoire.remember(
                content=content,
                category=metadata.get("type", "uncategorized"),
                source_module=metadata.get("source_module", "orchestrator"),
                tags=metadata.get("tags"),
                metadata=metadata,
            )
        if self._grimoire is not None:
            metadata = metadata or {}
            return self._grimoire.remember(
                content=content,
                category=metadata.get("type", "uncategorized"),
                source_module=metadata.get("source_module", "orchestrator"),
                tags=metadata.get("tags"),
                metadata=metadata,
            )
        return None

    async def shutdown(self) -> None:
        """Grimoire shutdown. Close connections."""
        if self._grimoire is not None:
            self._grimoire.close()
        logger.info("Grimoire shutting down. Memories persist on disk.")
        self.status = ModuleStatus.OFFLINE

    def get_tools(self) -> list[dict[str, Any]]:
        """Grimoire's MCP tools."""
        return [
            {
                "name": "memory_store",
                "description": "Save a new memory with metadata and trust level",
                "parameters": {
                    "content": "str — what to remember",
                    "metadata": "dict — category, source, trust_level, tags",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "memory_search",
                "description": "Semantic search across active memory (ChromaDB)",
                "parameters": {
                    "query": "str — what to search for",
                    "n_results": "int — max results (default 5)",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "memory_recall",
                "description": "Retrieve specific memory by ID or exact match",
                "parameters": {
                    "query": "str — what to recall",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "memory_forget",
                "description": "Explicit delete from both ChromaDB and SQLite",
                "parameters": {
                    "memory_id": "int — ID of memory to delete",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "memory_compact",
                "description": "Soft-archive old low-access memories to reduce search noise",
                "parameters": {
                    "older_than_days": "int — archive memories older than N days (default 30)",
                },
                "permission_level": "approval_required",
            },
            {
                "name": "memory_block_search",
                "description": "Search memories by content block type (code, error, plan, etc.)",
                "parameters": {
                    "block_type": "str — block type to search for",
                    "limit": "int — max results (default 10)",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "store_failure_pattern",
                "description": "Store a failure pattern so Shadow learns from mistakes",
                "parameters": {
                    "task": "str — the original task that failed",
                    "task_type": "str — classification (code, math, research, ethics)",
                    "mistake": "str — what approach was wrong",
                    "correct_approach": "str — what actually worked",
                    "source": "str — retry_engine or apex_learning",
                    "trust_level": "float — 0.7 for Apex, 0.5 for self-discovery",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "get_common_failures",
                "description": "Return most frequently matched failure patterns for growth tracking",
                "parameters": {
                    "limit": "int — max results (default 10)",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "get_failure_trend",
                "description": "Analyze failure pattern trends — is Shadow learning or stagnating?",
                "parameters": {
                    "days": "int — number of days to analyze (default 7)",
                },
                "permission_level": "autonomous",
            },
        ]
