"""Tests for Reaper's SearXNG integration.

Covers the Phase B Track D integration: the rung's HTTP plumbing, the
TTL-cached health probe (boot-race fix), and downstream concerns
(observability spans, ToolResult metadata) introduced in later steps.

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
def reaper_searxng_up(mock_grimoire, tmp_path, monkeypatch):
    """Reaper instance where SearXNG was reachable at init."""
    from shadow.config import config

    monkeypatch.setattr(config.reaper, "searxng_enabled", True)
    with patch.object(Reaper, "_check_searxng", return_value=True):
        r = Reaper(grimoire=mock_grimoire, data_dir=str(tmp_path / "research"))
        yield r


@pytest.fixture
def reaper_searxng_down(mock_grimoire, tmp_path, monkeypatch):
    """Reaper instance where SearXNG was NOT reachable at init.

    This is the precondition for the boot-race regression test."""
    from shadow.config import config

    monkeypatch.setattr(config.reaper, "searxng_enabled", True)
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


class TestSearXNGDisabledFlag:
    """The decorative searxng_enabled flag must now actually skip the rung."""

    def test_disabled_flag_short_circuits_probe(
        self, reaper_searxng_up, monkeypatch
    ):
        from shadow.config import config

        monkeypatch.setattr(config.reaper, "searxng_enabled", False)
        with patch.object(
            reaper_searxng_up, "_check_searxng", return_value=True
        ) as mock_probe:
            assert reaper_searxng_up._searxng_is_available() is False
            # Must not have hit the network — the flag short-circuits BEFORE
            # the probe.
            mock_probe.assert_not_called()

    def test_disabled_rung_skipped_in_cascade(self, reaper_searxng_up, monkeypatch):
        from shadow.config import config

        monkeypatch.setattr(config.reaper, "searxng_enabled", False)
        ddg_results = [
            {
                "title": "DDG hit",
                "url": "https://example.com",
                "snippet": "",
                "engine": "duckduckgo",
                "source_eval": {"domain": "example.com", "tier": 3, "trust_score": 0.5, "source_type": "general"},
            }
        ]
        with patch.object(
            reaper_searxng_up, "_search_searxng"
        ) as mock_searxng, patch.object(
            reaper_searxng_up, "_search_ddg", return_value=ddg_results
        ):
            results = reaper_searxng_up._search_once("anything", max_results=5)

        # Disabled rung must not be invoked even though _searxng_is_available
        # was probed by the cascade.
        mock_searxng.assert_not_called()
        assert results == ddg_results


class TestCascadeOrderRespectsBackendSetting:
    """``config.reaper.search_backend`` selects which rung leads. The
    decorative ``self.search_backend = "ddg"`` hardcode is now gone."""

    def _stub_results(self, engine_name):
        return [
            {
                "title": f"{engine_name} hit",
                "url": f"https://example.com/{engine_name}",
                "snippet": "",
                "engine": engine_name,
                "source_eval": {"domain": "example.com", "tier": 3, "trust_score": 0.5, "source_type": "general"},
            }
        ]

    def test_ddg_default_puts_searxng_first(self, reaper_searxng_up, monkeypatch):
        reaper_searxng_up.search_backend = "ddg"
        with patch.object(
            reaper_searxng_up,
            "_search_searxng",
            return_value=self._stub_results("searxng"),
        ) as mock_searxng, patch.object(
            reaper_searxng_up, "_search_ddg"
        ) as mock_ddg:
            results = reaper_searxng_up._search_once("query", max_results=5)

        mock_searxng.assert_called_once()
        mock_ddg.assert_not_called()
        assert results[0]["engine"] == "searxng"

    def test_brave_backend_puts_brave_first_when_key_present(
        self, reaper_searxng_up, monkeypatch
    ):
        reaper_searxng_up.search_backend = "brave"
        reaper_searxng_up.brave_available = True
        with patch.object(
            reaper_searxng_up, "_brave_get_usage", return_value=0
        ), patch.object(
            reaper_searxng_up,
            "_search_brave",
            return_value=self._stub_results("brave"),
        ) as mock_brave, patch.object(
            reaper_searxng_up, "_search_searxng"
        ) as mock_searxng:
            results = reaper_searxng_up._search_once("query", max_results=5)

        mock_brave.assert_called_once()
        mock_searxng.assert_not_called()
        assert results[0]["engine"] == "brave"

    def test_searxng_backend_explicit_keeps_searxng_first(
        self, reaper_searxng_up, monkeypatch
    ):
        reaper_searxng_up.search_backend = "searxng"
        with patch.object(
            reaper_searxng_up,
            "_search_searxng",
            return_value=self._stub_results("searxng"),
        ) as mock_searxng, patch.object(
            reaper_searxng_up, "_search_ddg"
        ) as mock_ddg:
            results = reaper_searxng_up._search_once("query", max_results=5)

        mock_searxng.assert_called_once()
        mock_ddg.assert_not_called()


class TestToolResultMetadata:
    """The Reaper adapter at reaper_module.py must populate ToolResult.metadata
    with the backend used, reformulation flag, and final query, so the router
    can reason about provenance without walking the result list."""

    @pytest.fixture
    def reaper_module(self, mock_grimoire, tmp_path, monkeypatch):
        """Build a real ReaperModule wired to a Reaper with SearXNG up."""
        from modules.reaper.reaper_module import ReaperModule
        from shadow.config import config

        monkeypatch.setattr(config.reaper, "searxng_enabled", True)
        with patch.object(Reaper, "_check_searxng", return_value=True):
            module = ReaperModule(config={}, grimoire_instance=mock_grimoire)
            # Replace the internally-built Reaper with one rooted at tmp_path
            # so test artifacts stay out of the repo.
            module._reaper = Reaper(
                grimoire=mock_grimoire, data_dir=str(tmp_path / "research"),
            )
        return module

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    @pytest.mark.asyncio
    async def test_metadata_records_backend_used(
        self, mock_get, mock_sleep, reaper_module
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SEARXNG_OK_RESPONSE
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        result = await reaper_module.execute(
            "web_search", {"query": "python 3.14", "max_results": 3}
        )

        assert result.success is True
        assert result.metadata is not None
        # Backend records the RUNG that served (searxng/ddg/brave/bing),
        # distinct from the upstream engine within that rung.
        assert result.metadata["backend"] == "searxng"
        assert result.metadata["engine"] in {"google", "reddit"}
        assert result.metadata["was_reformulated"] is False
        assert result.metadata["final_query"] == "python 3.14"

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    @pytest.mark.asyncio
    async def test_metadata_records_empty_backend_when_no_results(
        self, mock_get, mock_sleep, reaper_module
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": []}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        # Also disable DDG so the cascade exits empty.
        reaper_module._reaper.ddg_available = False
        reaper_module._reaper.bing_available = False

        result = await reaper_module.execute(
            "web_search", {"query": "asdfqwerty", "max_results": 3}
        )

        assert result.success is True
        assert result.metadata is not None
        assert result.metadata["backend"] is None


class TestObservabilitySpans:
    """Search() must emit a parent span and one child span per attempted rung.
    Verified by monkey-patching observed_span and recording every entry."""

    def _record_spans(self, monkeypatch):
        from contextlib import contextmanager

        calls = []

        class FakeSpan:
            def __init__(self, name):
                self.name = name
                self.metadata = None

            def update(self, metadata=None):
                self.metadata = metadata

        @contextmanager
        def fake_observed_span(name, **metadata):
            span = FakeSpan(name)
            calls.append({"name": name, "open_metadata": metadata, "span": span})
            yield span

        monkeypatch.setattr(
            "modules.reaper.reaper.observed_span", fake_observed_span
        )
        return calls

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    def test_parent_and_child_spans_emit(
        self, mock_get, mock_sleep, reaper_searxng_up, monkeypatch
    ):
        calls = self._record_spans(monkeypatch)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SEARXNG_OK_RESPONSE
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        reaper_searxng_up.search("python 3.14", max_results=3)

        names = [c["name"] for c in calls]
        # Parent span first.
        assert names[0] == "reaper.search"
        # At least one child attempt span — the SearXNG rung.
        assert "reaper.search.attempt" in names

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    def test_child_span_records_backend_and_count(
        self, mock_get, mock_sleep, reaper_searxng_up, monkeypatch
    ):
        calls = self._record_spans(monkeypatch)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SEARXNG_OK_RESPONSE
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        reaper_searxng_up.search("python 3.14", max_results=3)

        # First child span is the SearXNG attempt (DDG order default).
        child = next(c for c in calls if c["name"] == "reaper.search.attempt")
        assert child["open_metadata"]["backend"] == "searxng"
        assert child["span"].metadata is not None
        assert child["span"].metadata["backend"] == "searxng"
        assert child["span"].metadata["result_count"] == 2
        assert child["span"].metadata["served"] is True
        assert isinstance(child["span"].metadata["latency_ms"], float)

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    def test_parent_span_records_backend_used(
        self, mock_get, mock_sleep, reaper_searxng_up, monkeypatch
    ):
        calls = self._record_spans(monkeypatch)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # Pretend Google was the upstream that served.
        mock_resp.json.return_value = SEARXNG_OK_RESPONSE
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        reaper_searxng_up.search("python 3.14", max_results=3)

        parent = next(c for c in calls if c["name"] == "reaper.search")
        assert parent["span"].metadata is not None
        # Parent records which RUNG served (searxng/ddg/brave/bing),
        # distinct from the upstream engine name within that rung.
        assert parent["span"].metadata["backend_used"] == "searxng"
        assert parent["span"].metadata["upstream_engine"] in {"google", "reddit"}
        assert parent["span"].metadata["result_count"] == 2


class TestTypedSettingsOverrideBaseUrl:
    """A per-machine override of ``searxng_base_url`` must be honored by
    both the health probe and the search call (no hidden hardcodes left)."""

    def test_probe_uses_settings_base_url(self, mock_grimoire, tmp_path, monkeypatch):
        """Construct Reaper directly so the real _check_searxng body runs
        (the standard fixture mocks it at init to skip the network)."""
        from shadow.config import config

        monkeypatch.setattr(config.reaper, "searxng_enabled", True)
        monkeypatch.setattr(
            config.reaper, "searxng_base_url", "http://searx.example:9999"
        )
        with patch("modules.reaper.reaper.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_get.return_value = mock_resp

            Reaper(grimoire=mock_grimoire, data_dir=str(tmp_path / "research"))

            called_url = mock_get.call_args[0][0]
            assert called_url.startswith("http://searx.example:9999/healthz")

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    def test_search_uses_settings_base_url(
        self, mock_get, mock_sleep, reaper_searxng_up, monkeypatch
    ):
        monkeypatch.setattr(
            reaper_searxng_up._settings, "searxng_base_url", "http://searx.example:9999"
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SEARXNG_OK_RESPONSE
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        reaper_searxng_up._search_searxng("test")

        called_url = mock_get.call_args[0][0]
        assert called_url.startswith("http://searx.example:9999/search")
