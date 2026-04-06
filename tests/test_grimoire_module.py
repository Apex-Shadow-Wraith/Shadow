"""
Tests for GrimoireModule — Memory Tool Adapter
================================================
Tests the BaseModule adapter layer for Grimoire's new tools:
memory_compact and memory_block_search.

Uses mocks to avoid needing Ollama/ChromaDB running.
"""

import pytest
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

from modules.base import ModuleStatus, ToolResult
from modules.grimoire.grimoire_module import GrimoireModule


@pytest.fixture
def grimoire_module() -> GrimoireModule:
    """Create a GrimoireModule with a mocked internal Grimoire."""
    config = {"db_path": ":memory:", "vector_path": "/tmp/test_vectors"}
    module = GrimoireModule(config)
    # Mock the internal Grimoire instance so we don't need Ollama/ChromaDB
    module._grimoire = MagicMock()
    module.status = ModuleStatus.ONLINE
    module._initialized_at = datetime.now()
    return module


# --- Memory Compact Tests ---

class TestMemoryCompact:
    @pytest.mark.asyncio
    async def test_success(self, grimoire_module: GrimoireModule):
        grimoire_module._grimoire.compact.return_value = {
            "archived_count": 5,
            "archived_ids": ["a", "b", "c", "d", "e"],
        }

        result = await grimoire_module.execute("memory_compact", {
            "older_than_days": 60,
        })
        assert result.success is True
        assert result.content["archived_count"] == 5
        grimoire_module._grimoire.compact.assert_called_once_with(older_than_days=60)

    @pytest.mark.asyncio
    async def test_default_days(self, grimoire_module: GrimoireModule):
        grimoire_module._grimoire.compact.return_value = {
            "archived_count": 0,
            "archived_ids": [],
        }

        result = await grimoire_module.execute("memory_compact", {})
        assert result.success is True
        grimoire_module._grimoire.compact.assert_called_once_with(older_than_days=30)

    @pytest.mark.asyncio
    async def test_zero_results(self, grimoire_module: GrimoireModule):
        grimoire_module._grimoire.compact.return_value = {
            "archived_count": 0,
            "archived_ids": [],
        }

        result = await grimoire_module.execute("memory_compact", {
            "older_than_days": 1,
        })
        assert result.success is True
        assert result.content["archived_count"] == 0

    @pytest.mark.asyncio
    async def test_compact_error_propagates(self, grimoire_module: GrimoireModule):
        grimoire_module._grimoire.compact.side_effect = RuntimeError("DB locked")

        result = await grimoire_module.execute("memory_compact", {})
        assert result.success is False
        assert "DB locked" in result.error


# --- Memory Block Search Tests ---

class TestMemoryBlockSearch:
    @pytest.mark.asyncio
    async def test_success(self, grimoire_module: GrimoireModule):
        grimoire_module._grimoire.memory_block_search.return_value = [
            {"id": "mem1", "content": "test code", "matching_blocks": [{"type": "code"}]},
        ]

        result = await grimoire_module.execute("memory_block_search", {
            "block_type": "code",
            "limit": 5,
        })
        assert result.success is True
        assert len(result.content) == 1
        grimoire_module._grimoire.memory_block_search.assert_called_once_with(
            block_type="code", limit=5,
        )

    @pytest.mark.asyncio
    async def test_default_limit(self, grimoire_module: GrimoireModule):
        grimoire_module._grimoire.memory_block_search.return_value = []

        result = await grimoire_module.execute("memory_block_search", {
            "block_type": "error",
        })
        assert result.success is True
        grimoire_module._grimoire.memory_block_search.assert_called_once_with(
            block_type="error", limit=10,
        )

    @pytest.mark.asyncio
    async def test_invalid_block_type_propagates(self, grimoire_module: GrimoireModule):
        grimoire_module._grimoire.memory_block_search.side_effect = ValueError(
            "Invalid block type 'bogus'"
        )

        result = await grimoire_module.execute("memory_block_search", {
            "block_type": "bogus",
        })
        assert result.success is False
        assert "Invalid" in result.error


# --- Tool Definition Tests ---

class TestGrimoireToolDefinitions:
    def test_get_tools_count(self, grimoire_module: GrimoireModule):
        tools = grimoire_module.get_tools()
        assert len(tools) == 6  # 4 original + 2 new

    def test_new_tools_present(self, grimoire_module: GrimoireModule):
        tool_names = [t["name"] for t in grimoire_module.get_tools()]
        assert "memory_compact" in tool_names
        assert "memory_block_search" in tool_names

    def test_compact_requires_approval(self, grimoire_module: GrimoireModule):
        tools = {t["name"]: t for t in grimoire_module.get_tools()}
        assert tools["memory_compact"]["permission_level"] == "approval_required"
        assert tools["memory_block_search"]["permission_level"] == "autonomous"

    def test_all_tools_have_required_fields(self, grimoire_module: GrimoireModule):
        for tool in grimoire_module.get_tools():
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert "permission_level" in tool


# --- Unknown Tool Test ---

class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_tool(self, grimoire_module: GrimoireModule):
        result = await grimoire_module.execute("nonexistent_tool", {})
        assert result.success is False
        assert "Unknown" in result.error
