"""
Tests for Grimoire MCP Server.

All tests mock the Grimoire class — no real ChromaDB or SQLite needed.
"""

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from modules.grimoire.mcp_server import create_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_grimoire():
    """Create a mock Grimoire instance with sensible defaults."""
    g = MagicMock()
    g.recall.return_value = []
    g.remember.return_value = str(uuid.uuid4())
    g.stats.return_value = {
        "active_memories": 0,
        "inactive_memories": 0,
        "total_stored": 0,
        "vector_count": 0,
        "corrections": 0,
        "unique_tags": 0,
        "by_category": {},
        "by_source": {},
        "db_path": "data/memory/shadow_memory.db",
        "vector_path": "data/vectors",
    }
    return g


@pytest.fixture
def client(mock_grimoire):
    """FastAPI test client with mocked Grimoire."""
    app = create_app(grimoire=mock_grimoire)
    return TestClient(app)


@pytest.fixture
def client_no_grimoire():
    """FastAPI test client with NO Grimoire (None)."""
    app = create_app(grimoire=None)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Recall endpoint
# ---------------------------------------------------------------------------

class TestGrimoireRecall:
    def test_recall_returns_mcp_format(self, client, mock_grimoire):
        """Recall returns standard MCP tool result format."""
        mock_grimoire.recall.return_value = [
            {"id": "abc", "content": "test memory", "relevance": 0.95}
        ]
        resp = client.post("/tools/grimoire_recall", json={"query": "test"})
        assert resp.status_code == 200
        body = resp.json()
        assert "content" in body
        assert body["isError"] is False
        results = json.loads(body["content"][0]["text"])
        assert len(results) == 1
        assert results[0]["content"] == "test memory"

    def test_recall_empty_db(self, client, mock_grimoire):
        """Recall with empty DB returns empty list."""
        mock_grimoire.recall.return_value = []
        resp = client.post("/tools/grimoire_recall", json={"query": "anything"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["isError"] is False
        results = json.loads(body["content"][0]["text"])
        assert results == []

    def test_recall_with_collection(self, client, mock_grimoire):
        """Recall passes collection as category filter."""
        client.post("/tools/grimoire_recall", json={
            "query": "test", "top_k": 3, "collection": "research"
        })
        mock_grimoire.recall.assert_called_once_with(
            query="test", n_results=3, category="research"
        )

    def test_recall_default_top_k(self, client, mock_grimoire):
        """Recall defaults to top_k=5."""
        client.post("/tools/grimoire_recall", json={"query": "test"})
        mock_grimoire.recall.assert_called_once_with(
            query="test", n_results=5, category=None
        )

    def test_recall_embedding_error(self, client, mock_grimoire):
        """Recall returns error on embedding failure, not crash."""
        mock_grimoire.recall.side_effect = RuntimeError("Ollama embedding failed")
        resp = client.post("/tools/grimoire_recall", json={"query": "test"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["isError"] is True
        assert "Ollama embedding failed" in body["content"][0]["text"]


# ---------------------------------------------------------------------------
# Remember endpoint
# ---------------------------------------------------------------------------

class TestGrimoireRemember:
    def test_remember_stores_memory(self, client, mock_grimoire):
        """Remember stores and returns memory ID."""
        mid = str(uuid.uuid4())
        mock_grimoire.remember.return_value = mid
        resp = client.post("/tools/grimoire_remember", json={
            "content": "Shadow uses biblical ethics",
            "category": "identity",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["isError"] is False
        result = json.loads(body["content"][0]["text"])
        assert result["memory_id"] == mid
        mock_grimoire.remember.assert_called_once_with(
            content="Shadow uses biblical ethics",
            category="identity",
            metadata=None,
        )

    def test_remember_with_metadata(self, client, mock_grimoire):
        """Remember passes metadata through."""
        client.post("/tools/grimoire_remember", json={
            "content": "Test",
            "category": "test",
            "metadata": {"source": "claude_code"},
        })
        mock_grimoire.remember.assert_called_once_with(
            content="Test",
            category="test",
            metadata={"source": "claude_code"},
        )

    def test_remember_and_recall(self, client, mock_grimoire):
        """Remember stores, then recall retrieves it."""
        mid = str(uuid.uuid4())
        mock_grimoire.remember.return_value = mid

        # Store
        resp = client.post("/tools/grimoire_remember", json={
            "content": "The project uses Python 3.14",
            "category": "project",
        })
        assert resp.json()["isError"] is False

        # Now set up recall to return the stored memory
        mock_grimoire.recall.return_value = [
            {"id": mid, "content": "The project uses Python 3.14", "relevance": 0.99}
        ]
        resp = client.post("/tools/grimoire_recall", json={"query": "python version"})
        results = json.loads(resp.json()["content"][0]["text"])
        assert len(results) == 1
        assert results[0]["id"] == mid

    def test_remember_error(self, client, mock_grimoire):
        """Remember returns error on failure."""
        mock_grimoire.remember.side_effect = RuntimeError("DB write failed")
        resp = client.post("/tools/grimoire_remember", json={
            "content": "test", "category": "test"
        })
        body = resp.json()
        assert body["isError"] is True


# ---------------------------------------------------------------------------
# Search endpoint
# ---------------------------------------------------------------------------

class TestGrimoireSearch:
    def test_search_basic(self, client, mock_grimoire):
        """Search returns MCP format."""
        mock_grimoire.recall.return_value = [
            {"id": "x", "content": "found", "source_module": "reaper", "created_at": "2026-04-01"}
        ]
        resp = client.post("/tools/grimoire_search", json={"query": "research"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["isError"] is False

    def test_search_with_category_filter(self, client, mock_grimoire):
        """Search passes category filter to recall."""
        client.post("/tools/grimoire_search", json={
            "query": "test",
            "filters": {"category": "research"},
        })
        mock_grimoire.recall.assert_called_once_with(
            query="test", n_results=5, category="research", min_trust=0.0
        )

    def test_search_with_module_filter(self, client, mock_grimoire):
        """Search filters results by source module."""
        mock_grimoire.recall.return_value = [
            {"id": "1", "content": "a", "source_module": "reaper"},
            {"id": "2", "content": "b", "source_module": "wraith"},
        ]
        resp = client.post("/tools/grimoire_search", json={
            "query": "test",
            "filters": {"module": "reaper"},
        })
        results = json.loads(resp.json()["content"][0]["text"])
        assert len(results) == 1
        assert results[0]["source_module"] == "reaper"

    def test_search_with_date_range(self, client, mock_grimoire):
        """Search filters by date range."""
        mock_grimoire.recall.return_value = [
            {"id": "1", "content": "old", "created_at": "2026-01-01"},
            {"id": "2", "content": "new", "created_at": "2026-04-10"},
        ]
        resp = client.post("/tools/grimoire_search", json={
            "query": "test",
            "filters": {"date_range": {"start": "2026-03-01", "end": "2026-05-01"}},
        })
        results = json.loads(resp.json()["content"][0]["text"])
        assert len(results) == 1
        assert results[0]["id"] == "2"

    def test_search_with_min_trust(self, client, mock_grimoire):
        """Search passes min_trust to recall."""
        client.post("/tools/grimoire_search", json={
            "query": "test",
            "filters": {"min_trust": 0.7},
        })
        mock_grimoire.recall.assert_called_once_with(
            query="test", n_results=5, category=None, min_trust=0.7
        )


# ---------------------------------------------------------------------------
# Collections endpoint
# ---------------------------------------------------------------------------

class TestGrimoireCollections:
    def test_collections_returns_categories(self, client, mock_grimoire):
        """Collections endpoint returns category counts."""
        mock_grimoire.stats.return_value = {
            **mock_grimoire.stats.return_value,
            "by_category": {"research": 10, "conversation": 25, "identity": 3},
        }
        resp = client.post("/tools/grimoire_collections", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["isError"] is False
        data = json.loads(body["content"][0]["text"])
        assert data["research"] == 10
        assert data["conversation"] == 25

    def test_collections_empty(self, client, mock_grimoire):
        """Collections with no data returns empty dict."""
        resp = client.post("/tools/grimoire_collections", json={})
        data = json.loads(resp.json()["content"][0]["text"])
        assert data == {}


# ---------------------------------------------------------------------------
# Stats endpoint
# ---------------------------------------------------------------------------

class TestGrimoireStats:
    def test_stats_returns_all_fields(self, client, mock_grimoire):
        """Stats returns all required fields."""
        mock_grimoire.stats.return_value = {
            "active_memories": 33,
            "inactive_memories": 5,
            "total_stored": 38,
            "vector_count": 33,
            "corrections": 2,
            "unique_tags": 8,
            "by_category": {"research": 10},
            "by_source": {"conversation": 20},
            "db_path": "data/memory/shadow_memory.db",
            "vector_path": "data/vectors",
        }
        resp = client.post("/tools/grimoire_stats", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["isError"] is False
        data = json.loads(body["content"][0]["text"])

        required_fields = [
            "total_memories", "inactive_memories", "total_stored",
            "vector_count", "corrections", "unique_tags",
            "by_category", "by_source", "db_size_bytes",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

        assert data["total_memories"] == 33
        assert data["by_category"] == {"research": 10}

    def test_stats_error(self, client, mock_grimoire):
        """Stats returns error on failure."""
        mock_grimoire.stats.side_effect = RuntimeError("DB locked")
        resp = client.post("/tools/grimoire_stats", json={})
        body = resp.json()
        assert body["isError"] is True


# ---------------------------------------------------------------------------
# Server refuses without Grimoire
# ---------------------------------------------------------------------------

class TestServerWithoutGrimoire:
    def test_recall_503_without_grimoire(self, client_no_grimoire):
        """Endpoints return 503 when Grimoire is not initialized."""
        resp = client_no_grimoire.post("/tools/grimoire_recall", json={"query": "test"})
        assert resp.status_code == 503

    def test_remember_503_without_grimoire(self, client_no_grimoire):
        """Remember returns 503 without Grimoire."""
        resp = client_no_grimoire.post("/tools/grimoire_remember", json={
            "content": "test", "category": "test"
        })
        assert resp.status_code == 503

    def test_search_503_without_grimoire(self, client_no_grimoire):
        """Search returns 503 without Grimoire."""
        resp = client_no_grimoire.post("/tools/grimoire_search", json={"query": "test"})
        assert resp.status_code == 503

    def test_collections_503_without_grimoire(self, client_no_grimoire):
        """Collections returns 503 without Grimoire."""
        resp = client_no_grimoire.post("/tools/grimoire_collections", json={})
        assert resp.status_code == 503

    def test_stats_503_without_grimoire(self, client_no_grimoire):
        """Stats returns 503 without Grimoire."""
        resp = client_no_grimoire.post("/tools/grimoire_stats", json={})
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Manifest file
# ---------------------------------------------------------------------------

class TestManifest:
    def test_manifest_exists_and_valid(self):
        """MCP manifest JSON is valid and has all tools."""
        manifest_path = Path("modules/grimoire/mcp_manifest.json")
        assert manifest_path.exists(), "mcp_manifest.json not found"
        with open(manifest_path) as f:
            manifest = json.load(f)
        assert manifest["name"] == "shadow-grimoire"
        assert manifest["version"] == "1.0.0"
        tool_names = {t["name"] for t in manifest["tools"]}
        expected = {
            "grimoire_recall", "grimoire_remember",
            "grimoire_search", "grimoire_collections", "grimoire_stats",
        }
        assert tool_names == expected

    def test_all_tools_have_input_schema(self):
        """Every tool in manifest has an input_schema."""
        with open("modules/grimoire/mcp_manifest.json") as f:
            manifest = json.load(f)
        for tool in manifest["tools"]:
            assert "input_schema" in tool, f"{tool['name']} missing input_schema"
            assert tool["input_schema"]["type"] == "object"
