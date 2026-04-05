"""
Tests for Morpheus — Creative Discovery Pipeline
===================================================
"""

import json
import pytest
from pathlib import Path
from typing import Any

from modules.base import ModuleStatus, ToolResult
from modules.morpheus.morpheus import Morpheus


@pytest.fixture
def morpheus(tmp_path: Path) -> Morpheus:
    config = {"queue_file": str(tmp_path / "morpheus_queue.json")}
    return Morpheus(config)


@pytest.fixture
async def online_morpheus(morpheus: Morpheus) -> Morpheus:
    await morpheus.initialize()
    return morpheus


class TestMorpheusLifecycle:
    @pytest.mark.asyncio
    async def test_initialize(self, morpheus: Morpheus):
        await morpheus.initialize()
        assert morpheus.status == ModuleStatus.ONLINE

    @pytest.mark.asyncio
    async def test_shutdown(self, morpheus: Morpheus):
        await morpheus.initialize()
        await morpheus.shutdown()
        assert morpheus.status == ModuleStatus.OFFLINE

    def test_get_tools(self, morpheus: Morpheus):
        tools = morpheus.get_tools()
        assert len(tools) == 5
        names = [t["name"] for t in tools]
        assert "discovery_queue_add" in names
        assert "speculative_store" in names


class TestDiscoveryQueue:
    @pytest.mark.asyncio
    async def test_add_topic(self, online_morpheus: Morpheus):
        r = await online_morpheus.execute("discovery_queue_add", {
            "topic": "What if LLMs could dream?",
            "source": "user",
        })
        assert r.success is True
        assert r.content["topic"] == "What if LLMs could dream?"
        assert r.content["speculative"] is True
        assert r.content["trust_level"] == 0.0

    @pytest.mark.asyncio
    async def test_empty_topic_fails(self, online_morpheus: Morpheus):
        r = await online_morpheus.execute("discovery_queue_add", {"topic": ""})
        assert r.success is False

    @pytest.mark.asyncio
    async def test_list_queue(self, online_morpheus: Morpheus):
        await online_morpheus.execute("discovery_queue_add", {"topic": "Idea 1"})
        await online_morpheus.execute("discovery_queue_add", {"topic": "Idea 2"})
        r = await online_morpheus.execute("discovery_queue_list", {})
        assert r.success is True
        assert r.content["total"] == 2

    @pytest.mark.asyncio
    async def test_list_filtered_by_status(self, online_morpheus: Morpheus):
        await online_morpheus.execute("discovery_queue_add", {"topic": "Idea"})
        r = await online_morpheus.execute("discovery_queue_list", {
            "status_filter": "queued",
        })
        assert r.content["total"] == 1
        r2 = await online_morpheus.execute("discovery_queue_list", {
            "status_filter": "evaluated",
        })
        assert r2.content["total"] == 0


class TestDiscoveryEvaluate:
    @pytest.mark.asyncio
    async def test_evaluate_tier_1(self, online_morpheus: Morpheus):
        add = await online_morpheus.execute("discovery_queue_add", {
            "topic": "Novel algorithm",
        })
        r = await online_morpheus.execute("discovery_evaluate", {
            "discovery_id": add.content["id"],
            "tier": 1,
            "notes": "High potential",
        })
        assert r.success is True
        assert r.content["tier"] == 1
        assert r.content["status"] == "evaluated"
        # FIREWALL: trust level must remain 0.0
        assert r.content["trust_level"] == 0.0
        assert r.content["speculative"] is True

    @pytest.mark.asyncio
    async def test_evaluate_tier_4(self, online_morpheus: Morpheus):
        add = await online_morpheus.execute("discovery_queue_add", {"topic": "Bad idea"})
        r = await online_morpheus.execute("discovery_evaluate", {
            "discovery_id": add.content["id"],
            "tier": 4,
            "notes": "Not useful",
        })
        assert r.content["tier"] == 4

    @pytest.mark.asyncio
    async def test_invalid_tier_fails(self, online_morpheus: Morpheus):
        add = await online_morpheus.execute("discovery_queue_add", {"topic": "Test"})
        r = await online_morpheus.execute("discovery_evaluate", {
            "discovery_id": add.content["id"],
            "tier": 5,
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_evaluate_nonexistent_fails(self, online_morpheus: Morpheus):
        r = await online_morpheus.execute("discovery_evaluate", {
            "discovery_id": "999", "tier": 1,
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_evaluate_missing_id_fails(self, online_morpheus: Morpheus):
        r = await online_morpheus.execute("discovery_evaluate", {"tier": 1})
        assert r.success is False


class TestDiscoveryArchive:
    @pytest.mark.asyncio
    async def test_archive(self, online_morpheus: Morpheus):
        add = await online_morpheus.execute("discovery_queue_add", {"topic": "Archive me"})
        r = await online_morpheus.execute("discovery_archive", {
            "discovery_id": add.content["id"],
        })
        assert r.success is True
        assert r.content["status"] == "archived"

    @pytest.mark.asyncio
    async def test_archive_nonexistent_fails(self, online_morpheus: Morpheus):
        r = await online_morpheus.execute("discovery_archive", {"discovery_id": "999"})
        assert r.success is False


class TestSpeculativeStore:
    @pytest.mark.asyncio
    async def test_store_speculative(self, online_morpheus: Morpheus):
        r = await online_morpheus.execute("speculative_store", {
            "content": "What if neural networks could self-modify?",
            "topic": "self-modifying AI",
        })
        assert r.success is True
        # FIREWALL: these must ALWAYS be True/0.0
        assert r.content["speculative"] is True
        assert r.content["trust_level"] == 0.0
        assert r.content["source_type"] == "morpheus_speculative"
        assert r.content["verified"] is False

    @pytest.mark.asyncio
    async def test_firewall_metadata(self, online_morpheus: Morpheus):
        r = await online_morpheus.execute("speculative_store", {
            "content": "Idea", "topic": "test",
        })
        assert r.metadata["speculative"] is True
        assert r.metadata["trust_level"] == 0.0

    @pytest.mark.asyncio
    async def test_empty_content_fails(self, online_morpheus: Morpheus):
        r = await online_morpheus.execute("speculative_store", {
            "content": "", "topic": "test",
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_empty_topic_fails(self, online_morpheus: Morpheus):
        r = await online_morpheus.execute("speculative_store", {
            "content": "test", "topic": "",
        })
        assert r.success is False


class TestPersistence:
    @pytest.mark.asyncio
    async def test_queue_persists(self, tmp_path: Path):
        config = {"queue_file": str(tmp_path / "queue.json")}

        m1 = Morpheus(config)
        await m1.initialize()
        await m1.execute("discovery_queue_add", {"topic": "Persist me"})
        await m1.shutdown()

        m2 = Morpheus(config)
        await m2.initialize()
        r = await m2.execute("discovery_queue_list", {})
        assert r.content["total"] == 1
        assert r.content["items"][0]["topic"] == "Persist me"
        await m2.shutdown()


class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_tool(self, online_morpheus: Morpheus):
        r = await online_morpheus.execute("nonexistent", {})
        assert r.success is False
