"""
Reaper MCP Server — Exposes Reaper's research capabilities via HTTP.
====================================================================
FastAPI-based MCP server so Claude Code (and other MCP clients) can
search the web, fetch pages, and get research summaries during coding
sessions.

Endpoints:
    POST /tools/reaper_search    — Web search via DDG/Brave/SearXNG
    POST /tools/reaper_fetch     — Fetch + extract content from a URL
    POST /tools/reaper_summarize — Search + synthesize into a summary

Config: shadow_config.yaml → mcp.reaper (host, port)

Usage:
    python -m modules.reaper.mcp_server          # Standalone
    uvicorn modules.reaper.mcp_server:app --port 8101  # Direct

Author: Patrick (with Claude Opus 4.6)
Project: Shadow • Module: Reaper MCP
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("shadow.reaper.mcp")

app = FastAPI(
    title="Reaper MCP Server",
    description="Shadow's research tools exposed via MCP protocol",
    version="1.0.0",
)

# Lazy-initialized Reaper instance — set by create_app() or startup event
_reaper = None


def get_reaper():
    """Get the initialized Reaper instance."""
    if _reaper is None:
        raise HTTPException(
            status_code=503,
            detail="Reaper not initialized. Server is starting up.",
        )
    return _reaper


def create_app(reaper_instance=None, grimoire_instance=None):
    """Create the FastAPI app with an initialized Reaper.

    Args:
        reaper_instance: Pre-built Reaper instance (for testing).
        grimoire_instance: Grimoire instance (used if reaper_instance is None).

    Returns:
        The configured FastAPI app.
    """
    global _reaper

    if reaper_instance is not None:
        _reaper = reaper_instance
    elif grimoire_instance is not None:
        from modules.reaper.reaper import Reaper
        _reaper = Reaper(grimoire=grimoire_instance)
    return app


# =========================================================================
# REQUEST / RESPONSE MODELS
# =========================================================================

class SearchRequest(BaseModel):
    """Request body for reaper_search."""
    query: str = Field(..., description="Search query string")
    max_results: int = Field(default=5, ge=1, le=20, description="Max results to return")
    source: str = Field(default="auto", description="Search backend: ddg, brave, searxng, or auto")


class SearchResult(BaseModel):
    """A single search result."""
    title: str
    url: str
    snippet: str
    engine: str = ""
    source_eval: Optional[dict] = None


class SearchResponse(BaseModel):
    """Response body for reaper_search."""
    results: list[SearchResult]
    query: str
    source: str
    count: int


class FetchRequest(BaseModel):
    """Request body for reaper_fetch."""
    url: str = Field(..., description="URL to fetch and extract content from")
    extract_mode: str = Field(default="text", description="Extraction mode: text, markdown, or raw")


class FetchResponse(BaseModel):
    """Response body for reaper_fetch."""
    url: str
    title: str
    content: str
    content_length: int
    source_evaluation: dict
    extract_mode: str


class SummarizeRequest(BaseModel):
    """Request body for reaper_summarize."""
    query: str = Field(..., description="Topic to search and summarize")
    max_sources: int = Field(default=3, ge=1, le=10, description="Max sources to synthesize")


class SummarizeResponse(BaseModel):
    """Response body for reaper_summarize."""
    query: str
    summary: str
    sources: list[dict]
    source_count: int


# =========================================================================
# ENDPOINTS
# =========================================================================

@app.post("/tools/reaper_search", response_model=SearchResponse)
async def reaper_search(req: SearchRequest):
    """Search the web via Reaper's search backends.

    Uses the configured cascade (DDG/Brave/SearXNG) with automatic
    fallback if the primary backend fails.
    """
    reaper = get_reaper()

    # Override backend if explicitly requested
    original_backend = getattr(reaper, "search_backend", "ddg")
    if req.source != "auto":
        reaper.search_backend = req.source

    try:
        results = reaper.search(query=req.query, max_results=req.max_results)
    finally:
        reaper.search_backend = original_backend

    return SearchResponse(
        results=[
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("snippet", ""),
                engine=r.get("engine", ""),
                source_eval=r.get("source_eval"),
            )
            for r in results
        ],
        query=req.query,
        source=req.source,
        count=len(results),
    )


@app.post("/tools/reaper_fetch", response_model=FetchResponse)
async def reaper_fetch(req: FetchRequest):
    """Fetch and extract content from a URL.

    Supports text extraction with stealth headers and safety checks.
    """
    reaper = get_reaper()

    result = reaper.fetch_page(
        url=req.url,
        store_in_grimoire=False,
    )

    if result is None:
        raise HTTPException(
            status_code=422,
            detail=f"Could not fetch or extract content from: {req.url}",
        )

    content = result.get("content", "")

    # Apply extract_mode
    if req.extract_mode == "raw":
        pass  # Return as-is
    elif req.extract_mode == "markdown":
        # Basic markdown: keep paragraph breaks, strip excessive whitespace
        import re
        content = re.sub(r"\n{3,}", "\n\n", content)
    else:
        # "text" mode (default): clean text
        import re
        content = re.sub(r"\n{3,}", "\n\n", content)

    return FetchResponse(
        url=result["url"],
        title=result["title"],
        content=content,
        content_length=result["content_length"],
        source_evaluation=result["source_evaluation"],
        extract_mode=req.extract_mode,
    )


@app.post("/tools/reaper_summarize", response_model=SummarizeResponse)
async def reaper_summarize(req: SummarizeRequest):
    """Search for a topic and synthesize results into a summary.

    Searches for the query, fetches top results, and uses Reaper's
    summarize method to create a consolidated summary.
    """
    reaper = get_reaper()

    # Search for results
    search_results = reaper.search(query=req.query, max_results=req.max_sources)

    if not search_results:
        return SummarizeResponse(
            query=req.query,
            summary="No results found for the given query.",
            sources=[],
            source_count=0,
        )

    # Fetch and summarize each source
    sources = []
    combined_text = []

    for result in search_results[:req.max_sources]:
        url = result.get("url", "")
        if not url:
            continue

        page = reaper.fetch_page(url=url, store_in_grimoire=False)
        if page and page.get("content"):
            snippet = page["content"][:2000]
            sources.append({
                "title": page.get("title", result.get("title", "")),
                "url": url,
                "content_length": page.get("content_length", 0),
            })
            combined_text.append(
                f"Source: {page.get('title', 'Unknown')}\n{snippet}"
            )

    if not combined_text:
        # Couldn't fetch any pages, summarize from snippets
        for r in search_results[:req.max_sources]:
            sources.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content_length": len(r.get("snippet", "")),
            })
            combined_text.append(
                f"Source: {r.get('title', 'Unknown')}\n{r.get('snippet', '')}"
            )

    full_text = "\n\n---\n\n".join(combined_text)
    summary = reaper.summarize(full_text, max_words=250)

    return SummarizeResponse(
        query=req.query,
        summary=summary,
        sources=sources,
        source_count=len(sources),
    )


# =========================================================================
# STANDALONE ENTRY POINT
# =========================================================================

if __name__ == "__main__":
    import yaml
    import uvicorn

    config_path = Path("config/shadow_config.yaml")
    host = "127.0.0.1"
    port = 8101

    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
        mcp_config = config.get("mcp", {}).get("reaper", {})
        host = mcp_config.get("host", host)
        port = mcp_config.get("port", port)

    # Initialize Grimoire + Reaper
    from modules.grimoire import Grimoire
    from modules.reaper.reaper import Reaper

    grimoire = Grimoire()
    create_app(reaper_instance=Reaper(grimoire=grimoire))

    print(f"[Reaper MCP] Starting on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
