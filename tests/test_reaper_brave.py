"""
Tests for Reaper's Brave Search API integration.
All web calls are mocked — no real API requests.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
from pydantic import SecretStr

from modules.reaper.reaper import Reaper


@pytest.fixture
def mock_grimoire():
    """Create a minimal mock Grimoire for Reaper init."""
    grimoire = MagicMock()
    grimoire.remember.return_value = 1
    grimoire.recall_recent.return_value = []
    return grimoire


@pytest.fixture
def reaper(mock_grimoire, tmp_path, monkeypatch):
    """Create a Reaper instance with Brave API key set via the config singleton."""
    from shadow.config import config

    monkeypatch.setattr(
        config.reaper, "brave_search_api_key", SecretStr("test-brave-key-123")
    )
    with patch.object(Reaper, "_check_searxng", return_value=False):
        r = Reaper(grimoire=mock_grimoire, data_dir=str(tmp_path / "research"))
        r.search_backend = "brave"
        yield r


@pytest.fixture
def reaper_no_brave(mock_grimoire, tmp_path, monkeypatch):
    """Create a Reaper instance without a Brave API key."""
    from shadow.config import config

    monkeypatch.setattr(config.reaper, "brave_search_api_key", None)
    with patch.object(Reaper, "_check_searxng", return_value=False):
        r = Reaper(grimoire=mock_grimoire, data_dir=str(tmp_path / "research"))
        yield r


BRAVE_RESPONSE = {
    "web": {
        "results": [
            {
                "title": "Python 3.14 Release Notes",
                "url": "https://docs.python.org/3/whatsnew/3.14.html",
                "description": "What's new in Python 3.14 — major features and changes.",
            },
            {
                "title": "Python 3.14 on Reddit",
                "url": "https://reddit.com/r/Python/comments/abc123",
                "description": "Discussion about the Python 3.14 release.",
            },
            {
                "title": "Python 3.14 Tutorial",
                "url": "https://realpython.com/python-314/",
                "description": "A comprehensive guide to Python 3.14 features.",
            },
        ]
    }
}


class TestBraveSearchResults:
    """Test _search_brave returns correct format."""

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    def test_returns_correct_format(self, mock_get, mock_sleep, reaper):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = BRAVE_RESPONSE
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        results = reaper._search_brave("python 3.14", max_results=5)

        assert len(results) == 3
        for r in results:
            assert "title" in r
            assert "url" in r
            assert "snippet" in r
            assert "engine" in r
            assert "source_eval" in r
            assert r["engine"] == "brave"

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    def test_result_content_matches_api(self, mock_get, mock_sleep, reaper):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = BRAVE_RESPONSE
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        results = reaper._search_brave("python 3.14")

        assert results[0]["title"] == "Python 3.14 Release Notes"
        assert results[0]["url"] == "https://docs.python.org/3/whatsnew/3.14.html"
        assert "Python 3.14" in results[0]["snippet"]

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    def test_respects_max_results(self, mock_get, mock_sleep, reaper):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = BRAVE_RESPONSE
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        results = reaper._search_brave("python 3.14", max_results=2)
        assert len(results) == 2

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    def test_sends_api_key_header(self, mock_get, mock_sleep, reaper):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = BRAVE_RESPONSE
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        reaper._search_brave("test query")

        call_kwargs = mock_get.call_args
        assert call_kwargs.kwargs["headers"]["X-Subscription-Token"] == "test-brave-key-123"

    def test_returns_empty_without_api_key(self, reaper_no_brave):
        assert reaper_no_brave.brave_available is False
        results = reaper_no_brave._search_brave("test")
        assert results == []

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    def test_source_eval_included(self, mock_get, mock_sleep, reaper):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = BRAVE_RESPONSE
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        results = reaper._search_brave("python 3.14")
        # docs.python.org should be Tier 1
        assert results[0]["source_eval"]["tier"] == 1
        # reddit.com should be Tier 3
        assert results[1]["source_eval"]["tier"] == 3


class TestBraveRateLimiting:
    """Test rate limit (429) handling."""

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    def test_retries_on_429(self, mock_get, mock_sleep, reaper):
        rate_limited = MagicMock()
        rate_limited.status_code = 429
        rate_limited.headers = {"Retry-After": "2"}

        success = MagicMock()
        success.status_code = 200
        success.json.return_value = BRAVE_RESPONSE
        success.raise_for_status.return_value = None

        mock_get.side_effect = [rate_limited, success]

        results = reaper._search_brave("test query")
        assert len(results) == 3
        assert mock_get.call_count == 2

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    def test_gives_up_after_double_429(self, mock_get, mock_sleep, reaper):
        rate_limited = MagicMock()
        rate_limited.status_code = 429
        rate_limited.headers = {"Retry-After": "2"}

        mock_get.return_value = rate_limited

        results = reaper._search_brave("test query")
        assert results == []
        assert mock_get.call_count == 2

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    def test_retry_after_capped_at_10s(self, mock_get, mock_sleep, reaper):
        rate_limited = MagicMock()
        rate_limited.status_code = 429
        rate_limited.headers = {"Retry-After": "60"}

        success = MagicMock()
        success.status_code = 200
        success.json.return_value = BRAVE_RESPONSE
        success.raise_for_status.return_value = None

        mock_get.side_effect = [rate_limited, success]

        reaper._search_brave("test query")
        # time.sleep is called for stealth delay and rate limit
        # Check the rate limit sleep is capped at 10
        sleep_calls = [c.args[0] for c in mock_sleep.call_args_list]
        assert any(s == 10 for s in sleep_calls)


class TestBraveMonthlyCounter:
    """Test monthly usage counter increments and resets."""

    def test_initial_usage_is_zero(self, reaper, tmp_path):
        usage_file = str(tmp_path / "brave_usage.json")
        with patch("modules.reaper.reaper.BRAVE_USAGE_FILE", usage_file):
            assert reaper._brave_get_usage() == 0

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    def test_usage_increments_on_search(self, mock_get, mock_sleep, reaper, tmp_path):
        usage_file = str(tmp_path / "brave_usage.json")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = BRAVE_RESPONSE
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        with patch("modules.reaper.reaper.BRAVE_USAGE_FILE", usage_file):
            assert reaper._brave_get_usage() == 0
            reaper._search_brave("query 1")
            assert reaper._brave_get_usage() == 1
            reaper._search_brave("query 2")
            assert reaper._brave_get_usage() == 2

    def test_usage_resets_on_new_month(self, reaper, tmp_path):
        """Counter resets when month changes."""
        usage_file = tmp_path / "brave_usage.json"
        usage_file.write_text(json.dumps({
            "month": "2025-01",
            "count": 1500,
            "last_query": "2025-01-31T23:59:59",
        }))

        with patch("modules.reaper.reaper.BRAVE_USAGE_FILE", str(usage_file)):
            assert reaper._brave_get_usage() == 0

    def test_usage_file_written_correctly(self, reaper, tmp_path):
        usage_file = str(tmp_path / "brave_usage.json")
        with patch("modules.reaper.reaper.BRAVE_USAGE_FILE", usage_file):
            reaper._brave_increment_usage()
            data = json.loads(Path(usage_file).read_text())
            assert data["month"] == datetime.now().strftime("%Y-%m")
            assert data["count"] == 1
            assert "last_query" in data


class TestBraveQuotaFallback:
    """Test fallback to DDG when over Brave quota."""

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    def test_warns_at_threshold(self, mock_get, mock_sleep, reaper, capsys):
        """Should print warning when approaching quota."""
        with patch.object(reaper, "_brave_get_usage", return_value=1800):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = BRAVE_RESPONSE
            mock_resp.raise_for_status.return_value = None
            mock_get.return_value = mock_resp

            reaper._search_brave("test")
            captured = capsys.readouterr()
            assert "quota warning" in captured.out.lower()

    @patch("modules.reaper.reaper.time.sleep")
    def test_skips_when_over_quota(self, mock_sleep, reaper):
        """Should return empty and skip API call when over monthly quota."""
        with patch.object(reaper, "_brave_get_usage", return_value=2000):
            results = reaper._search_brave("test")
            assert results == []

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    def test_cascade_falls_to_ddg_when_brave_exhausted(self, mock_get, mock_sleep, reaper):
        """When Brave is over quota, _search_once should cascade to DDG."""
        reaper.search_backend = "brave"
        reaper.ddg_available = True
        with patch.object(reaper, "_brave_get_usage", return_value=2000):
            with patch.object(reaper, "_search_ddg", return_value=[{"title": "DDG result", "url": "https://example.com", "snippet": "test"}]) as mock_ddg:
                results = reaper._search_once("test", max_results=5)
                mock_ddg.assert_called_once()
                assert results[0]["title"] == "DDG result"


class TestBackendSelection:
    """Test backend selection from config."""

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    def test_brave_backend_tries_brave_first(self, mock_get, mock_sleep, reaper):
        reaper.search_backend = "brave"
        with patch.object(reaper, "_search_brave", return_value=[{"title": "Brave", "url": "https://example.com", "snippet": "x"}]) as mock_brave:
            with patch.object(reaper, "_search_ddg") as mock_ddg:
                results = reaper._search_once("test")
                mock_brave.assert_called_once()
                mock_ddg.assert_not_called()

    @patch("modules.reaper.reaper.time.sleep")
    def test_ddg_backend_tries_ddg_first(self, mock_sleep, reaper):
        reaper.search_backend = "ddg"
        reaper.searxng_available = False
        with patch.object(reaper, "_search_ddg", return_value=[{"title": "DDG", "url": "https://example.com", "snippet": "x"}]) as mock_ddg:
            with patch.object(reaper, "_search_brave") as mock_brave:
                results = reaper._search_once("test")
                mock_ddg.assert_called_once()
                mock_brave.assert_not_called()

    @patch("modules.reaper.reaper.time.sleep")
    def test_default_backend_is_ddg(self, mock_sleep, mock_grimoire, tmp_path, monkeypatch):
        from shadow.config import config
        monkeypatch.setattr(config.reaper, "brave_search_api_key", SecretStr("key"))
        with patch.object(Reaper, "_check_searxng", return_value=False):
            r = Reaper(grimoire=mock_grimoire, data_dir=str(tmp_path / "research"))
            assert r.search_backend == "ddg"


class TestBraveErrorHandling:
    """Test error handling on network failures."""

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    def test_connection_error_returns_empty(self, mock_get, mock_sleep, reaper):
        mock_get.side_effect = requests.ConnectionError("Connection refused")
        results = reaper._search_brave("test")
        assert results == []

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    def test_timeout_returns_empty(self, mock_get, mock_sleep, reaper):
        mock_get.side_effect = requests.Timeout("Request timed out")
        results = reaper._search_brave("test")
        assert results == []

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    def test_500_error_returns_empty(self, mock_get, mock_sleep, reaper):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
        mock_get.return_value = mock_resp
        results = reaper._search_brave("test")
        assert results == []

    @patch("modules.reaper.reaper.time.sleep")
    @patch("modules.reaper.reaper.requests.get")
    def test_malformed_json_returns_empty(self, mock_get, mock_sleep, reaper):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}  # No "web" key
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        results = reaper._search_brave("test")
        assert results == []
