"""
Grimoire MCP Server — Expose Shadow's memory system over HTTP.

FastAPI-based MCP server that lets Claude Code (and other MCP clients)
read/write Shadow's memories during coding sessions.

Run standalone:
    python -m modules.grimoire.mcp_server
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from modules.grimoire.grimoire import Grimoire

logger = logging.getLogger("grimoire.mcp")

# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class RecallRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=50)
    collection: Optional[str] = None


class RememberRequest(BaseModel):
    content: str
    category: str = "uncategorized"
    metadata: Optional[Dict[str, Any]] = None


class SearchRequest(BaseModel):
    query: str
    filters: Optional[Dict[str, Any]] = None
    top_k: int = Field(default=5, ge=1, le=50)


class MCPToolResult(BaseModel):
    """Standard MCP tool result wrapper."""
    content: List[Dict[str, Any]]
    isError: bool = False


# ---------------------------------------------------------------------------
# App Factory
# ---------------------------------------------------------------------------

def create_app(grimoire: Optional[Grimoire] = None) -> FastAPI:
    """Create the FastAPI app, optionally injecting a Grimoire instance."""

    app = FastAPI(
        title="Shadow Grimoire MCP Server",
        version="1.0.0",
        description="Shadow's persistent memory system exposed as MCP tools.",
    )

    # CORS for local access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store grimoire on app state so endpoints can access it
    app.state.grimoire = grimoire

    def _grimoire() -> Grimoire:
        g = app.state.grimoire
        if g is None:
            raise HTTPException(status_code=503, detail="Grimoire not initialized")
        return g

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    @app.post("/tools/grimoire_recall", response_model=MCPToolResult)
    async def grimoire_recall(req: RecallRequest):
        """Semantic search — find memories by meaning."""
        logger.debug("grimoire_recall query=%r top_k=%d", req.query, req.top_k)
        try:
            results = _grimoire().recall(
                query=req.query,
                n_results=req.top_k,
                category=req.collection,
            )
            return MCPToolResult(content=[{"type": "text", "text": json.dumps(results, default=str)}])
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("grimoire_recall failed: %s", exc)
            return MCPToolResult(
                content=[{"type": "text", "text": f"Error: {exc}"}],
                isError=True,
            )

    @app.post("/tools/grimoire_remember", response_model=MCPToolResult)
    async def grimoire_remember(req: RememberRequest):
        """Store a new memory."""
        logger.debug("grimoire_remember category=%r len=%d", req.category, len(req.content))
        try:
            memory_id = _grimoire().remember(
                content=req.content,
                category=req.category,
                metadata=req.metadata,
            )
            return MCPToolResult(content=[{"type": "text", "text": json.dumps({"memory_id": memory_id})}])
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("grimoire_remember failed: %s", exc)
            return MCPToolResult(
                content=[{"type": "text", "text": f"Error: {exc}"}],
                isError=True,
            )

    @app.post("/tools/grimoire_search", response_model=MCPToolResult)
    async def grimoire_search(req: SearchRequest):
        """Full-text search with filters."""
        logger.debug("grimoire_search query=%r filters=%r", req.query, req.filters)
        try:
            filters = req.filters or {}
            category = filters.get("category")
            results = _grimoire().recall(
                query=req.query,
                n_results=req.top_k,
                category=category,
                min_trust=filters.get("min_trust", 0.0),
            )
            # Apply date_range filter if provided
            date_range = filters.get("date_range")
            if date_range and isinstance(date_range, dict):
                start = date_range.get("start")
                end = date_range.get("end")
                if start or end:
                    filtered = []
                    for r in results:
                        created = r.get("created_at", "")
                        if start and created < start:
                            continue
                        if end and created > end:
                            continue
                        filtered.append(r)
                    results = filtered

            # Apply module filter if provided
            module_filter = filters.get("module")
            if module_filter:
                results = [r for r in results if r.get("source_module") == module_filter]

            return MCPToolResult(content=[{"type": "text", "text": json.dumps(results, default=str)}])
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("grimoire_search failed: %s", exc)
            return MCPToolResult(
                content=[{"type": "text", "text": f"Error: {exc}"}],
                isError=True,
            )

    @app.post("/tools/grimoire_collections", response_model=MCPToolResult)
    async def grimoire_collections():
        """List all collections (categories) and their counts."""
        logger.debug("grimoire_collections")
        try:
            stats = _grimoire().stats()
            collections = stats.get("by_category", {})
            return MCPToolResult(content=[{"type": "text", "text": json.dumps(collections, default=str)}])
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("grimoire_collections failed: %s", exc)
            return MCPToolResult(
                content=[{"type": "text", "text": f"Error: {exc}"}],
                isError=True,
            )

    @app.post("/tools/grimoire_stats", response_model=MCPToolResult)
    async def grimoire_stats():
        """Return total memories, per-collection counts, DB size."""
        logger.debug("grimoire_stats")
        try:
            raw = _grimoire().stats()
            db_path = Path(raw.get("db_path", ""))
            db_size = db_path.stat().st_size if db_path.exists() else 0

            stats_out = {
                "total_memories": raw.get("active_memories", 0),
                "inactive_memories": raw.get("inactive_memories", 0),
                "total_stored": raw.get("total_stored", 0),
                "vector_count": raw.get("vector_count", 0),
                "corrections": raw.get("corrections", 0),
                "unique_tags": raw.get("unique_tags", 0),
                "by_category": raw.get("by_category", {}),
                "by_source": raw.get("by_source", {}),
                "db_size_bytes": db_size,
            }
            return MCPToolResult(content=[{"type": "text", "text": json.dumps(stats_out, default=str)}])
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("grimoire_stats failed: %s", exc)
            return MCPToolResult(
                content=[{"type": "text", "text": f"Error: {exc}"}],
                isError=True,
            )

    return app


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

def _load_config() -> Dict[str, Any]:
    """Load MCP config from shadow_config.yaml."""
    config_path = Path("config/shadow_config.yaml")
    if config_path.exists():
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("mcp", {}).get("grimoire", {})
    return {}


def main():
    """Start the Grimoire MCP server."""
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    config = _load_config()
    host = config.get("host", "127.0.0.1")
    port = config.get("port", 8100)

    if not config.get("enabled", True):
        logger.error("Grimoire MCP server is disabled in config. Exiting.")
        sys.exit(1)

    # Init Grimoire — fail fast if it can't start
    try:
        grimoire = Grimoire()
        logger.info("Grimoire initialized successfully.")
    except Exception as exc:
        logger.critical("Failed to initialize Grimoire: %s", exc)
        sys.exit(1)

    app = create_app(grimoire)
    logger.info("Starting Grimoire MCP server on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port, log_level="debug")


if __name__ == "__main__":
    main()
