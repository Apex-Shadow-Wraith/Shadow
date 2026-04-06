"""Tests for Reaper Reddit .json backend — research context endpoints."""

from unittest.mock import MagicMock, patch, call
import time

import pytest

from modules.reaper.reaper import Reaper


# ---------------------------------------------------------------------------
# Mock Reddit listing response
# ---------------------------------------------------------------------------

def _make_listing(*posts) -> dict:
    """Build a Reddit-style listing JSON from post dicts."""
    children = []
    for p in posts:
        children.append({
            "kind": "t3",
            "data": {
                "title": p.get("title", "Test Post"),
                "selftext": p.get("selftext", ""),
                "score": p.get("score", 1),
                "permalink": p.get("permalink", "/r/test/comments/abc/test_post/"),
                "url": p.get("url", "https://www.reddit.com/r/test/comments/abc/test_post/"),
                "author": p.get("author", "testuser"),
                "created_utc": p.get("created_utc", 1700000000),
            },
        })
    return {"kind": "Listing", "data": {"children": children, "after": None}}


SAMPLE_LISTING = _make_listing(
    {
        "title": "phi4-mini is great for local routing",
        "selftext": "I've been testing phi4-mini as a lightweight router...",
        "score": 142,
        "permalink": "/r/LocalLLaMA/comments/xyz/phi4mini_great/",
        "author": "llm_enthusiast",
        "created_utc": 1700001000,
    },
    {
        "title": "Ollama 0.5 released with new features",
        "selftext": "Major update just dropped...",
        "score": 305,
        "permalink": "/r/LocalLLaMA/comments/abc/ollama_05/",
        "author": "ollama_fan",
        "created_utc": 1700002000,
    },
)

EMPTY_LISTING = {"kind": "Listing", "data": {"children": [], "after": None}}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def reaper():
    """Create a Reaper with a mock Grimoire (no real DB needed)."""
    mock_grimoire = MagicMock()
    mock_grimoire.remember.return_value = "mem_001"
    with patch("modules.reaper.reaper.Reaper._check_searxng", return_value=False):
        r = Reaper(grimoire=mock_grimoire, data_dir="data/research")
    return r


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSearchRedditJson:
    @patch("modules.reaper.reaper.requests.get")
    @patch("modules.reaper.reaper.time.sleep")
    def test_returns_posts(self, mock_sleep, mock_get, reaper):
        """Successful search returns parsed post data."""
        mock_get.return_value = MagicMock(status_code=200)
        mock_get.return_value.json.return_value = SAMPLE_LISTING
        mock_get.return_value.raise_for_status = MagicMock()

        results = reaper.search_reddit_json("LocalLLaMA", "phi4-mini")

        assert len(results) == 2
        assert results[0]["title"] == "phi4-mini is great for local routing"
        assert results[0]["score"] == 142
        assert results[0]["author"] == "llm_enthusiast"
        assert "LocalLLaMA" in results[0]["url"]
        assert results[1]["score"] == 305

    @patch("modules.reaper.reaper.requests.get")
    @patch("modules.reaper.reaper.time.sleep")
    def test_empty_results(self, mock_sleep, mock_get, reaper):
        """Empty subreddit search returns empty list."""
        mock_get.return_value = MagicMock(status_code=200)
        mock_get.return_value.json.return_value = EMPTY_LISTING
        mock_get.return_value.raise_for_status = MagicMock()

        results = reaper.search_reddit_json("EmptySubreddit", "nothing here")
        assert results == []

    @patch("modules.reaper.reaper.requests.get")
    @patch("modules.reaper.reaper.time.sleep")
    def test_http_error_returns_empty(self, mock_sleep, mock_get, reaper):
        """HTTP errors (429, 500) return empty list gracefully."""
        mock_get.return_value = MagicMock(status_code=429)
        mock_get.return_value.raise_for_status.side_effect = Exception("429 Too Many Requests")

        results = reaper.search_reddit_json("LocalLLaMA", "test")
        assert results == []


class TestMonitorSubredditJson:
    @patch("modules.reaper.reaper.requests.get")
    @patch("modules.reaper.reaper.time.sleep")
    def test_returns_posts(self, mock_sleep, mock_get, reaper):
        """Monitor returns parsed posts from subreddit feed."""
        mock_get.return_value = MagicMock(status_code=200)
        mock_get.return_value.json.return_value = SAMPLE_LISTING
        mock_get.return_value.raise_for_status = MagicMock()

        results = reaper.monitor_subreddit_json("LocalLLaMA", sort="hot", limit=25)

        assert len(results) == 2
        assert results[0]["title"] == "phi4-mini is great for local routing"

        # Verify correct URL was called
        called_url = mock_get.call_args[0][0]
        assert "/r/LocalLLaMA/hot.json" in called_url


class TestUserAgent:
    @patch("modules.reaper.reaper.requests.get")
    @patch("modules.reaper.reaper.time.sleep")
    def test_correct_user_agent(self, mock_sleep, mock_get, reaper):
        """Verify the correct User-Agent header is sent."""
        mock_get.return_value = MagicMock(status_code=200)
        mock_get.return_value.json.return_value = EMPTY_LISTING
        mock_get.return_value.raise_for_status = MagicMock()

        reaper.search_reddit_json("test", "query")

        headers = mock_get.call_args[1].get("headers", {})
        assert headers.get("User-Agent") == "Shadow/1.0 (research context tool)"


class TestRateLimiting:
    @patch("modules.reaper.reaper.requests.get")
    @patch("modules.reaper.reaper.time.sleep")
    def test_delay_between_requests(self, mock_sleep, mock_get, reaper):
        """Verify 2-second delay is applied before each request."""
        mock_get.return_value = MagicMock(status_code=200)
        mock_get.return_value.json.return_value = EMPTY_LISTING
        mock_get.return_value.raise_for_status = MagicMock()

        reaper.search_reddit_json("test", "query1")
        reaper.monitor_subreddit_json("test", "hot")

        # sleep(2) should have been called once per request
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(2)


class TestSearchChainRedditRouting:
    @patch("modules.reaper.reaper.requests.get")
    @patch("modules.reaper.reaper.time.sleep")
    def test_reddit_query_routes_to_json(self, mock_sleep, mock_get, reaper):
        """A query mentioning r/LocalLLaMA should hit Reddit .json before DDG."""
        mock_get.return_value = MagicMock(status_code=200)
        mock_get.return_value.json.return_value = SAMPLE_LISTING
        mock_get.return_value.raise_for_status = MagicMock()

        # SearXNG is already disabled in the fixture
        results = reaper.search("r/LocalLLaMA phi4-mini", max_results=5)

        # Should have results from reddit_json engine
        assert len(results) > 0
        assert results[0]["engine"] == "reddit_json"

        # Verify it called the Reddit .json URL
        called_url = mock_get.call_args[0][0]
        assert "reddit.com" in called_url
        assert ".json" in called_url

    def test_is_reddit_query_detection(self, reaper):
        """Verify Reddit query detection works correctly."""
        assert reaper._is_reddit_query("r/LocalLLaMA phi4-mini") is True
        assert reaper._is_reddit_query("what does reddit say about ollama") is True
        assert reaper._is_reddit_query("python sqlite tutorial") is False

    def test_extract_reddit_target(self, reaper):
        """Verify subreddit and search term extraction."""
        sub, term = reaper._extract_reddit_target("r/LocalLLaMA phi4-mini")
        assert sub == "LocalLLaMA"
        assert "phi4-mini" in term

        sub, term = reaper._extract_reddit_target("r/ollama")
        assert sub == "ollama"
        assert term is None
