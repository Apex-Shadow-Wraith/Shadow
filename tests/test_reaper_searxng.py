"""Tests for Reaper's SearXNG integration.

Covers the Phase B Track D integration: the rung's HTTP plumbing and the
TTL-cached health probe (boot-race fix).

All web calls are mocked — no real SearXNG instance required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from modules.reaper.reaper import Reaper


SEARXNG_OK_RESPONSE = {
    "results": [
        {
            "title": "Python 3.14 Release Notes",
            "url": "https://docs.python.org/3/whatsnew/3.14.html",
            "content": "What's new in Python 3.14.",
            "engine": "google",
        },
        {
            "title": "Python 3.14 on Reddit",
            "url": "https://reddit.com/r/Python/comments/abc123",
            "content": "Discussion thread.",
            "engine": "reddit",
        },
    ]
}


@pytest.fixture
def mock_grimoire():
    grimoire = MagicMock()
    grimoire.remember.return_value = 1
    grimoire.recall_recent.return_value = []
    return grimoire


@pytest.fixture
def reaper_searxng_up(mock_grimoire, tmp_path):
    """Reaper instance where SearXNG was reachable at init."""
    with patch.object(Reaper, "_check_searxng", return_value=True):
        r = Reaper(grimoire=mock_grimoire, data_dir=str(tmp_path / "research"))
        yield r


@pytest.fixture
def reaper_searxng_down(mock_grimoire, tmp_path):
    """Reaper instance where SearXNG was NOT reachable at init.

    This is the precondition for the boot-race regression test."""
    with patch.object(Reaper, "_check_searxng", return_value=False):
        r = Reaper(grimoire=mock_grimoire, data_dir=str(tmp_path / "research"))
        yield r


class TestSearXNGResultMapping:
    """The rung must produce result dicts in the same shape as sibling rungs
    (title, url, snippet, engine, source_eval)."""

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    def test_returns_correct_format(self, mock_get, mock_sleep, reaper_searxng_up):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SEARXNG_OK_RESPONSE
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        results = reaper_searxng_up._search_searxng("python 3.14", max_results=5)

        assert len(results) == 2
        for r in results:
            assert "title" in r
            assert "url" in r
            assert "snippet" in r
            assert "engine" in r
            assert "source_eval" in r

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    def test_engine_field_preserves_upstream_engine(
        self, mock_get, mock_sleep, reaper_searxng_up
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SEARXNG_OK_RESPONSE
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        results = reaper_searxng_up._search_searxng("python 3.14")

        engines = {r["engine"] for r in results}
        assert "google" in engines
        assert "reddit" in engines

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    def test_respects_max_results(self, mock_get, mock_sleep, reaper_searxng_up):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SEARXNG_OK_RESPONSE
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        results = reaper_searxng_up._search_searxng("python 3.14", max_results=1)
        assert len(results) == 1

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    def test_http_error_returns_empty(self, mock_get, mock_sleep, reaper_searxng_up):
        mock_get.side_effect = requests.ConnectionError("connection refused")
        assert reaper_searxng_up._search_searxng("anything") == []


class TestBootRaceRecovery:
    """Regression for: SearXNG started AFTER Reaper, stays dead forever.

    Pre-fix behavior: ``self.searxng_available`` was set once at init from
    ``_check_searxng()``. If False, the dispatcher skipped the rung
    (``if not available: continue``) and the only re-probe site only ran
    if the rung had already executed and returned an empty list. So a
    False boot-time flag was sticky.

    Post-fix: ``_searxng_is_available()`` re-probes after the TTL window
    elapses. The dispatcher calls the method rather than reading a flag."""

    def test_boot_time_false_stays_false_within_ttl(self, reaper_searxng_down):
        assert reaper_searxng_down._searxng_is_available() is False
        # Even if SearXNG comes up RIGHT NOW, before TTL elapses the
        # cached False should hold (no re-probe yet).
        with patch.object(reaper_searxng_down, "_check_searxng", return_value=True):
            assert reaper_searxng_down._searxng_is_available() is False

    def test_boot_time_false_recovers_after_ttl(self, reaper_searxng_down):
        """The headline regression: stack-up-after-Reaper must recover."""
        assert reaper_searxng_down._searxng_is_available() is False

        with patch.object(reaper_searxng_down, "_check_searxng", return_value=True):
            # Fast-forward past the TTL window.
            future = (
                reaper_searxng_down._searxng_health_last_check
                + reaper_searxng_down._searxng_health_ttl_s
                + 1.0
            )
            with patch("modules.reaper.reaper.time.monotonic", return_value=future):
                assert reaper_searxng_down._searxng_is_available() is True

    def test_recovery_propagates_to_legacy_attribute(self, reaper_searxng_down):
        """``self.searxng_available`` is kept as a legacy mirror of the
        cached flag so any external reader (e.g. the startup print) sees the
        latest known state, not a frozen boot-time snapshot."""
        assert reaper_searxng_down.searxng_available is False

        with patch.object(reaper_searxng_down, "_check_searxng", return_value=True):
            future = (
                reaper_searxng_down._searxng_health_last_check
                + reaper_searxng_down._searxng_health_ttl_s
                + 1.0
            )
            with patch("modules.reaper.reaper.time.monotonic", return_value=future):
                reaper_searxng_down._searxng_is_available()

        assert reaper_searxng_down.searxng_available is True

    def test_healthy_to_unhealthy_transition_also_recovers(self, reaper_searxng_up):
        """The TTL probe must work in both directions, not just up-to-down."""
        assert reaper_searxng_up._searxng_is_available() is True

        with patch.object(reaper_searxng_up, "_check_searxng", return_value=False):
            future = (
                reaper_searxng_up._searxng_health_last_check
                + reaper_searxng_up._searxng_health_ttl_s
                + 1.0
            )
            with patch("modules.reaper.reaper.time.monotonic", return_value=future):
                assert reaper_searxng_up._searxng_is_available() is False


class TestCascadeFallsThroughOnSearXNGError:
    """When SearXNG raises mid-cascade, DDG must serve."""

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    def test_connection_error_falls_through_to_ddg(
        self, mock_get, mock_sleep, reaper_searxng_up
    ):
        mock_get.side_effect = requests.ConnectionError("boom")
        ddg_results = [
            {
                "title": "DDG hit",
                "url": "https://example.com/ddg",
                "snippet": "served by DDG fallback",
                "engine": "duckduckgo",
                "source_eval": {"domain": "example.com", "tier": 3, "trust_score": 0.5, "source_type": "general"},
            }
        ]
        with patch.object(
            reaper_searxng_up, "_search_ddg", return_value=ddg_results
        ) as mock_ddg:
            results = reaper_searxng_up._search_once("anything", max_results=5)

        mock_ddg.assert_called_once()
        assert results == ddg_results
