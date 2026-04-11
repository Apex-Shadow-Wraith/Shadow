"""
Tests for Reaper MCP Server.
All web calls are mocked — no real network requests.
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from modules.reaper.mcp_server import app, create_app


@pytest.fixture
def mock_reaper():
    """Create a mock Reaper instance with standard method signatures."""
    reaper = MagicMock()
    reaper.search_backend = "ddg"
    return reaper


@pytest.fixture
def client(mock_reaper):
    """Create a test client with a mock Reaper."""
    create_app(reaper_instance=mock_reaper)
    return TestClient(app)


# =========================================================================
# SEARCH ENDPOINT
# =========================================================================

class TestReaperSearch:
    """POST /tools/reaper_search — web search."""

    def test_search_returns_results(self, client, mock_reaper):
        mock_reaper.search.return_value = [
            {
                "title": "Python Tutorial",
                "url": "https://docs.python.org/3/tutorial/",
                "snippet": "The Python Tutorial — an informal introduction.",
                "engine": "duckduckgo",
                "source_eval": {"tier": 1, "trust_score": 0.7},
            },
            {
                "title": "Learn Python",
                "url": "https://realpython.com/",
                "snippet": "Real Python tutorials and articles.",
                "engine": "duckduckgo",
                "source_eval": {"tier": 4, "trust_score": 0.1},
            },
        ]

        resp = client.post("/tools/reaper_search", json={
            "query": "python tutorial",
            "max_results": 5,
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2
        assert data["query"] == "python tutorial"
        assert len(data["results"]) == 2
        assert data["results"][0]["title"] == "Python Tutorial"
        assert data["results"][0]["url"] == "https://docs.python.org/3/tutorial/"
        assert data["results"][0]["snippet"] == "The Python Tutorial — an informal introduction."

    def test_search_with_title_url_snippet(self, client, mock_reaper):
        """Each result must have title, url, snippet."""
        mock_reaper.search.return_value = [
            {"title": "T", "url": "https://example.com", "snippet": "S", "engine": "brave"},
        ]

        resp = client.post("/tools/reaper_search", json={"query": "test"})
        result = resp.json()["results"][0]
        assert "title" in result
        assert "url" in result
        assert "snippet" in result

    def test_search_source_parameter(self, client, mock_reaper):
        """Source parameter should switch backend."""
        mock_reaper.search.return_value = []

        client.post("/tools/reaper_search", json={
            "query": "test",
            "source": "brave",
        })

        # The reaper.search should have been called
        mock_reaper.search.assert_called_once_with(query="test", max_results=5)

    def test_search_source_auto_default(self, client, mock_reaper):
        """Default source should be 'auto'."""
        mock_reaper.search.return_value = []
        resp = client.post("/tools/reaper_search", json={"query": "test"})
        assert resp.json()["source"] == "auto"

    def test_search_restores_backend_after_override(self, client, mock_reaper):
        """Backend should be restored after source override."""
        mock_reaper.search_backend = "ddg"
        mock_reaper.search.return_value = []

        client.post("/tools/reaper_search", json={
            "query": "test",
            "source": "brave",
        })

        assert mock_reaper.search_backend == "ddg"

    def test_search_empty_results(self, client, mock_reaper):
        mock_reaper.search.return_value = []

        resp = client.post("/tools/reaper_search", json={"query": "xyznonexistent"})
        assert resp.status_code == 200
        assert resp.json()["count"] == 0
        assert resp.json()["results"] == []

    def test_search_missing_query_returns_422(self, client):
        resp = client.post("/tools/reaper_search", json={})
        assert resp.status_code == 422


# =========================================================================
# FETCH ENDPOINT
# =========================================================================

class TestReaperFetch:
    """POST /tools/reaper_fetch — fetch and extract from URL."""

    def test_fetch_extracts_text(self, client, mock_reaper):
        mock_reaper.fetch_page.return_value = {
            "url": "https://example.com/article",
            "title": "Test Article",
            "content": "This is the article text content.\n\nSecond paragraph.",
            "content_length": 52,
            "source_evaluation": {"tier": 4, "trust_score": 0.1, "domain": "example.com"},
            "memory_id": None,
        }

        resp = client.post("/tools/reaper_fetch", json={
            "url": "https://example.com/article",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Test Article"
        assert "article text content" in data["content"]
        assert data["content_length"] == 52
        assert data["extract_mode"] == "text"

    def test_fetch_markdown_mode(self, client, mock_reaper):
        mock_reaper.fetch_page.return_value = {
            "url": "https://example.com",
            "title": "Page",
            "content": "Line 1\n\n\n\n\nLine 2",
            "content_length": 20,
            "source_evaluation": {"tier": 4},
            "memory_id": None,
        }

        resp = client.post("/tools/reaper_fetch", json={
            "url": "https://example.com",
            "extract_mode": "markdown",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["extract_mode"] == "markdown"
        # Excessive newlines should be collapsed
        assert "\n\n\n" not in data["content"]

    def test_fetch_raw_mode(self, client, mock_reaper):
        raw_content = "Line 1\n\n\n\n\nLine 2"
        mock_reaper.fetch_page.return_value = {
            "url": "https://example.com",
            "title": "Page",
            "content": raw_content,
            "content_length": len(raw_content),
            "source_evaluation": {"tier": 4},
            "memory_id": None,
        }

        resp = client.post("/tools/reaper_fetch", json={
            "url": "https://example.com",
            "extract_mode": "raw",
        })

        assert resp.status_code == 200
        assert resp.json()["content"] == raw_content

    def test_fetch_failure_returns_422(self, client, mock_reaper):
        mock_reaper.fetch_page.return_value = None

        resp = client.post("/tools/reaper_fetch", json={
            "url": "https://blocked.example.com/malware.exe",
        })
        assert resp.status_code == 422

    def test_fetch_passes_store_false(self, client, mock_reaper):
        """MCP fetch should NOT store in Grimoire."""
        mock_reaper.fetch_page.return_value = {
            "url": "https://example.com",
            "title": "X",
            "content": "text",
            "content_length": 4,
            "source_evaluation": {},
            "memory_id": None,
        }

        client.post("/tools/reaper_fetch", json={"url": "https://example.com"})
        mock_reaper.fetch_page.assert_called_once_with(
            url="https://example.com",
            store_in_grimoire=False,
        )

    def test_fetch_missing_url_returns_422(self, client):
        resp = client.post("/tools/reaper_fetch", json={})
        assert resp.status_code == 422


# =========================================================================
# SUMMARIZE ENDPOINT
# =========================================================================

class TestReaperSummarize:
    """POST /tools/reaper_summarize — search + synthesize."""

    def test_summarize_combines_sources(self, client, mock_reaper):
        mock_reaper.search.return_value = [
            {"title": "Source 1", "url": "https://a.com", "snippet": "A content"},
            {"title": "Source 2", "url": "https://b.com", "snippet": "B content"},
        ]
        mock_reaper.fetch_page.side_effect = [
            {
                "title": "Source 1 Full",
                "content": "Full content from source A about the topic.",
                "content_length": 42,
                "source_evaluation": {"tier": 1},
            },
            {
                "title": "Source 2 Full",
                "content": "Full content from source B with more detail.",
                "content_length": 44,
                "source_evaluation": {"tier": 2},
            },
        ]
        mock_reaper.summarize.return_value = "Combined summary of both sources about the topic."

        resp = client.post("/tools/reaper_summarize", json={
            "query": "test topic",
            "max_sources": 3,
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "test topic"
        assert "Combined summary" in data["summary"]
        assert data["source_count"] == 2
        assert len(data["sources"]) == 2

    def test_summarize_no_results(self, client, mock_reaper):
        mock_reaper.search.return_value = []

        resp = client.post("/tools/reaper_summarize", json={"query": "nothing"})
        assert resp.status_code == 200
        assert resp.json()["source_count"] == 0
        assert "No results" in resp.json()["summary"]

    def test_summarize_falls_back_to_snippets(self, client, mock_reaper):
        """When fetch_page fails, summarize from search snippets."""
        mock_reaper.search.return_value = [
            {"title": "Result 1", "url": "https://a.com", "snippet": "Snippet text here"},
        ]
        mock_reaper.fetch_page.return_value = None  # Fetch fails
        mock_reaper.summarize.return_value = "Summary from snippets."

        resp = client.post("/tools/reaper_summarize", json={"query": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_count"] == 1
        mock_reaper.summarize.assert_called_once()

    def test_summarize_respects_max_sources(self, client, mock_reaper):
        mock_reaper.search.return_value = [
            {"title": f"R{i}", "url": f"https://r{i}.com", "snippet": f"S{i}"}
            for i in range(5)
        ]
        mock_reaper.fetch_page.return_value = None
        mock_reaper.summarize.return_value = "Summary"

        resp = client.post("/tools/reaper_summarize", json={
            "query": "test",
            "max_sources": 2,
        })

        data = resp.json()
        assert data["source_count"] == 2


# =========================================================================
# BACKEND SWITCHING
# =========================================================================

class TestSourceSwitching:
    """Test that source parameter switches between search backends."""

    def test_source_ddg(self, client, mock_reaper):
        mock_reaper.search.return_value = [
            {"title": "DDG", "url": "https://x.com", "snippet": "s", "engine": "duckduckgo"},
        ]

        resp = client.post("/tools/reaper_search", json={
            "query": "test",
            "source": "ddg",
        })

        assert resp.json()["source"] == "ddg"

    def test_source_brave(self, client, mock_reaper):
        mock_reaper.search.return_value = [
            {"title": "Brave", "url": "https://x.com", "snippet": "s", "engine": "brave"},
        ]

        resp = client.post("/tools/reaper_search", json={
            "query": "test",
            "source": "brave",
        })

        assert resp.json()["source"] == "brave"

    def test_source_searxng(self, client, mock_reaper):
        mock_reaper.search.return_value = []

        resp = client.post("/tools/reaper_search", json={
            "query": "test",
            "source": "searxng",
        })

        assert resp.json()["source"] == "searxng"


# =========================================================================
# ERROR HANDLING
# =========================================================================

class TestErrorHandling:
    """Test error handling on network failures."""

    def test_search_exception_raises(self, client, mock_reaper):
        """Search exceptions should propagate."""
        mock_reaper.search.side_effect = Exception("Network failure")

        with pytest.raises(Exception, match="Network failure"):
            client.post("/tools/reaper_search", json={"query": "test"})

    def test_fetch_exception_raises(self, client, mock_reaper):
        mock_reaper.fetch_page.side_effect = Exception("Connection reset")

        with pytest.raises(Exception, match="Connection reset"):
            client.post("/tools/reaper_fetch", json={"url": "https://example.com"})

    def test_server_not_initialized(self):
        """Server should return 503 if Reaper not initialized."""
        import modules.reaper.mcp_server as mod
        old_reaper = mod._reaper
        mod._reaper = None
        try:
            test_client = TestClient(app, raise_server_exceptions=False)
            resp = test_client.post("/tools/reaper_search", json={"query": "test"})
            assert resp.status_code == 503
        finally:
            mod._reaper = old_reaper
