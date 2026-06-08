"""Live integration test for Reaper's SearXNG rung.

Skipped by default. Set ``RUN_SEARXNG_LIVE=1`` to enable. Requires the
SearXNG stack at ``services/searxng/`` to be running.

What this exercises that the mocked unit tests cannot:
    - Real HTTP round-trip to localhost:8888.
    - The /healthz probe used by ``_check_searxng()``.
    - End-to-end ToolResult.metadata population from a real cascade run.
    - Soft-check that Langfuse spans emit without crashing when the search
      runs through the orchestrator's observability wiring.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_SEARXNG_LIVE") != "1",
    reason="Set RUN_SEARXNG_LIVE=1 with the SearXNG stack running to enable",
)


@pytest.fixture
def reaper_module_live(tmp_path, monkeypatch):
    from modules.reaper.reaper import Reaper
    from modules.reaper.reaper_module import ReaperModule
    from shadow.config import config

    monkeypatch.setattr(config.reaper, "searxng_enabled", True)

    grimoire = MagicMock()
    grimoire.remember.return_value = 1
    grimoire.recall_recent.return_value = []

    module = ReaperModule(config={}, grimoire_instance=grimoire)
    # ReaperModule lazily builds its internal Reaper inside initialize().
    # We bypass the async init lifecycle for live tests and inject a Reaper
    # directly so the live HTTP path is exercised.
    module._reaper = Reaper(grimoire=grimoire, data_dir=str(tmp_path / "research"))
    return module


def test_health_probe_hits_live_endpoint(reaper_module_live):
    assert reaper_module_live._reaper._check_searxng() is True
    assert reaper_module_live._reaper._searxng_is_available() is True


@pytest.mark.asyncio
async def test_live_search_returns_results_and_metadata(reaper_module_live):
    result = await reaper_module_live.execute(
        "web_search", {"query": "python 3.14 release notes", "max_results": 3},
    )

    assert result.success is True
    assert isinstance(result.content, list)
    assert len(result.content) > 0
    assert result.metadata is not None
    # The plan's amendment C: assert the RUNG that served — not the upstream
    # engine field, since SearXNG aggregates many engines and the engine
    # field legitimately reads e.g. "startpage" or "duckduckgo" even when the
    # SearXNG rung served.
    assert result.metadata["backend"] == "searxng"
    # Upstream engine is open-ended (SearXNG ships with more enabled by
    # default than what's listed in our settings.yml); just assert non-empty.
    assert isinstance(result.metadata["engine"], str)
    assert result.metadata["engine"]
    assert result.metadata["was_reformulated"] in {True, False}
    assert isinstance(result.metadata["final_query"], str)


@pytest.mark.asyncio
async def test_live_search_emits_spans_without_error(reaper_module_live):
    """Soft-check: if Langfuse is reachable, spans get sent. If not, the
    observed_span context manager yields None and we still complete. Either
    way, the call must not raise."""
    result = await reaper_module_live.execute(
        "web_search", {"query": "rtx 5090 review", "max_results": 3},
    )
    assert result.success is True
