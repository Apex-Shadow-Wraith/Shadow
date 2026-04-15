"""
Tests for Reaper search locale/region settings.
Ensures all search backends explicitly request English results
regardless of server locale or datacenter location.
"""

from unittest.mock import MagicMock, patch, call

import pytest

from modules.reaper.reaper import Reaper


@pytest.fixture
def reaper():
    """Create a Reaper instance with delays disabled for testing."""
    mock_grimoire = MagicMock()
    r = Reaper(grimoire=mock_grimoire)
    r.stealth_min_delay = 0
    r.stealth_max_delay = 0
    return r


class TestDDGRegion:
    """DuckDuckGo search must pass region='us-en' explicitly."""

    @patch("modules.reaper.reaper.DDGS")
    def test_ddg_passes_region_parameter(self, mock_ddgs_cls, reaper):
        """Verify ddgs.text() is called with region='us-en'."""
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = [
            {"title": "Result", "href": "https://example.com", "body": "snippet"},
        ]

        results = reaper._search_ddg("test query", max_results=5)

        mock_ddgs.text.assert_called_once()
        call_kwargs = mock_ddgs.text.call_args
        assert call_kwargs.kwargs.get("region") == "us-en" or \
            (len(call_kwargs.args) >= 2 and call_kwargs.args[1] == "us-en"), \
            f"Expected region='us-en' in call: {call_kwargs}"

    @patch("modules.reaper.reaper.DDGS")
    def test_ddg_returns_results_with_region(self, mock_ddgs_cls, reaper):
        """Verify results are returned normally with the region parameter."""
        mock_ddgs = MagicMock()
        mock_ddgs_cls.return_value.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = [
            {"title": "English Result", "href": "https://example.com", "body": "English snippet"},
        ]

        results = reaper._search_ddg("python tutorial", max_results=5)

        assert len(results) == 1
        assert results[0]["title"] == "English Result"
        assert results[0]["engine"] == "duckduckgo"


class TestSearXNGLanguage:
    """SearXNG search must pass language='en' in request params."""

    @patch("modules.reaper.reaper.requests.get")
    def test_searxng_passes_language_parameter(self, mock_get, reaper):
        """Verify SearXNG request includes language='en'."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        reaper._search_searxng("test query", max_results=5)

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs.args[1] if len(call_kwargs.args) > 1 else call_kwargs.kwargs.get("params", {})
        assert params.get("language") == "en", \
            f"Expected language='en' in SearXNG params: {params}"


class TestBingLocale:
    """Bing scraper must pass setlang='en' and cc='US' in request params."""

    @patch("modules.reaper.reaper.requests.get")
    def test_bing_passes_locale_parameters(self, mock_get, reaper):
        """Verify Bing request includes setlang='en' and cc='US'."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body></body></html>"
        mock_get.return_value = mock_response

        reaper._search_bing("test query", max_results=5)

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs.args[1] if len(call_kwargs.args) > 1 else call_kwargs.kwargs.get("params", {})
        assert params.get("setlang") == "en", \
            f"Expected setlang='en' in Bing params: {params}"
        assert params.get("cc") == "US", \
            f"Expected cc='US' in Bing params: {params}"
