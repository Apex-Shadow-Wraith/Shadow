"""
Reaper — Shadow's Research & Data Collection Module (Full Build)
================================================================
Reaper is Shadow's only connection to the outside world. Everything it
finds flows into Grimoire with appropriate trust levels. Everything it
does follows the stealth and safety rules in config.py.

DESIGN PRINCIPLES:
    1. Reaper COLLECTS and EVALUATES. Grimoire STORES.
    2. Two search backends: SearXNG (primary) → DuckDuckGo (fallback)
    3. Every request uses stealth basics (user agent rotation, delays, clean headers)
    4. Download safety layer protects until Sentinel is built
    5. Relevance gate prevents Grimoire from filling with noise
    6. Standing research runs automatically — you don't type queries

ADDITIONAL PACKAGES NEEDED:
    pip install beautifulsoup4     (HTML parsing)
    pip install duckduckgo-search  (fallback search backend)

    Already installed from setup checklist:
    pip install praw               (Reddit API)
    pip install yt-dlp             (YouTube subtitles)
    pip install requests           (HTTP)

Author: Patrick (with Claude Opus 4.6)
Project: Shadow • Module: Reaper (Module #7)
"""

import json
import os
import re
import random
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
import requests

# Optional imports — Reaper loads even if these aren't installed yet
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    print("[Reaper] WARNING: beautifulsoup4 not installed → pip install beautifulsoup4")

try:
    from duckduckgo_search import DDGS
    HAS_DDG = True
except ImportError:
    HAS_DDG = False
    print("[Reaper] WARNING: duckduckgo-search not installed → pip install duckduckgo-search")

try:
    import praw
    HAS_PRAW = True
except ImportError:
    HAS_PRAW = False
    print("[Reaper] WARNING: praw not installed → pip install praw")

# Import Reaper's configuration
from .config import (
    STANDING_TOPICS, USER_AGENTS, STEALTH_DELAY_MIN, STEALTH_DELAY_MAX,
    REFERRERS, BLOCKED_EXTENSIONS, APPROVAL_REQUIRED_EXTENSIONS,
    TIER1_AUTO_ALLOWED_EXTENSIONS, MAX_AUTO_DOWNLOAD_SIZE, QUARANTINE_DIR,
    STORE_FULL_THRESHOLD, STORE_SUMMARY_THRESHOLD,
    REDDIT_MIN_SCORE_STANDING, REDDIT_MIN_SCORE_HIGH_SIGNAL,
    REDDIT_MAX_COMMENTS_STORED, YOUTUBE_SUMMARY_CHAR_THRESHOLD,
    WEB_MAX_ARTICLE_CHARS, WEB_SKIP_OLDER_THAN_DAYS,
    ALWAYS_SKIP_PATTERNS, SEARXNG_URL, SEARXNG_TIMEOUT,
    DDG_MAX_RESULTS, QUERY_EXPANSION_COUNT,
    OLLAMA_URL, LLM_MODEL,
    TEMP_RELEVANCE_SCORING, TEMP_SUMMARIZATION, TEMP_QUERY_EXPANSION,
)


# =============================================================================
# SOURCE EVALUATION — Trust hierarchy (matches Memory System Design Doc)
# =============================================================================

TIER_1_DOMAINS = {
    "docs.python.org", "pytorch.org", "huggingface.co",
    "developer.nvidia.com", "ollama.com", "arxiv.org",
    "github.com", "gitlab.com", "ietf.org", "w3.org",
    ".gov", ".edu",
}

TIER_2_DOMAINS = {
    "reuters.com", "apnews.com", "nytimes.com", "washingtonpost.com",
    "bbc.com", "bbc.co.uk", "theguardian.com", "economist.com",
    "arstechnica.com", "wired.com", "theregister.com",
    "techcrunch.com", "theverge.com",
}

TIER_3_DOMAINS = {
    "reddit.com", "stackoverflow.com", "stackexchange.com",
    "news.ycombinator.com", "dev.to", "medium.com",
    "discord.com", "wikipedia.org",
}


def evaluate_source(url):
    """
    Evaluate URL trustworthiness. Returns tier (1-4) and trust score.
    Trust scores match Memory System Design Doc Section 6:
        Tier 1 (official)    = 0.7
        Tier 2 (journalism)  = 0.5
        Tier 3 (community)   = 0.3
        Tier 4 (unverified)  = 0.1
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
    except Exception:
        return {"domain": "unknown", "tier": 4, "trust_score": 0.1, "source_type": "unknown"}

    for d in TIER_1_DOMAINS:
        if d.startswith("."):
            if domain.endswith(d):
                return {"domain": domain, "tier": 1, "trust_score": 0.7, "source_type": "official"}
        elif domain == d or domain.endswith("." + d):
            return {"domain": domain, "tier": 1, "trust_score": 0.7, "source_type": "official"}

    for d in TIER_2_DOMAINS:
        if domain == d or domain.endswith("." + d):
            return {"domain": domain, "tier": 2, "trust_score": 0.5, "source_type": "journalism"}

    for d in TIER_3_DOMAINS:
        if domain == d or domain.endswith("." + d):
            return {"domain": domain, "tier": 3, "trust_score": 0.3, "source_type": "community"}

    return {"domain": domain, "tier": 4, "trust_score": 0.1, "source_type": "unverified"}


# =============================================================================
# MAIN REAPER CLASS
# =============================================================================

class Reaper:
    """
    Shadow's research and data collection module.

    Usage:
        from modules.grimoire import Grimoire
        from modules.reaper import Reaper

        grimoire = Grimoire()
        reaper = Reaper(grimoire)

        # Run all standing research (one command does everything)
        report = reaper.run_standing_research()

        # Ad-hoc research on a specific topic
        results = reaper.research("Allama SOAR integration guide")

        # Fetch and store a specific page
        reaper.fetch_page("https://docs.python.org/3/tutorial/")

        # YouTube transcript
        reaper.youtube_transcribe("https://youtube.com/watch?v=...")

        reaper.close()
        grimoire.close()
    """

    def __init__(self, grimoire, data_dir="data/research"):
        """
        Initialize Reaper with a Grimoire instance for storage.

        Args:
            grimoire: Initialized Grimoire instance. Reaper stores everything
                      through Grimoire — never directly to database.
            data_dir: Where raw files (transcripts, quarantine) are stored.
        """
        self.grimoire = grimoire
        self.data_dir = Path(data_dir)

        # Create directory structure
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "youtube").mkdir(exist_ok=True)
        (self.data_dir / "web").mkdir(exist_ok=True)
        (self.data_dir / "reddit").mkdir(exist_ok=True)
        Path(QUARANTINE_DIR).mkdir(parents=True, exist_ok=True)

        # Check which search backends are available
        self.searxng_available = self._check_searxng()
        self.ddg_available = HAS_DDG

        print(f"[Reaper] Initialized")
        print(f"[Reaper] SearXNG: {'✅ Available' if self.searxng_available else '❌ Not running'}")
        print(f"[Reaper] DuckDuckGo: {'✅ Available' if self.ddg_available else '❌ Not installed'}")
        print(f"[Reaper] Standing topics: {len(STANDING_TOPICS)}")

        if not self.searxng_available and not self.ddg_available:
            print("[Reaper] ⚠️  NO SEARCH BACKEND AVAILABLE")
            print("[Reaper] Start SearXNG or: pip install duckduckgo-search")

    # =========================================================================
    # SEARCH BACKENDS
    # =========================================================================

    def _check_searxng(self):
        """Check if SearXNG is running and responding."""
        try:
            response = requests.get(
                f"{SEARXNG_URL}/search",
                params={"q": "test", "format": "json"},
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False

    def search(self, query, max_results=10):
        """
        Search the web using best available backend.
        Tries SearXNG first (better results), falls back to DuckDuckGo.

        Args:
            query: Search query string
            max_results: Maximum results to return

        Returns:
            List of dicts: [{"title": ..., "url": ..., "snippet": ...}, ...]
        """
        # Try SearXNG first
        if self.searxng_available:
            results = self._search_searxng(query, max_results)
            if results:
                return results
            # SearXNG returned nothing — re-check if it's still running
            self.searxng_available = self._check_searxng()

        # Fall back to DuckDuckGo
        if self.ddg_available:
            return self._search_ddg(query, max_results)

        print(f"[Reaper] No search backend available for: '{query}'")
        return []

    def _search_searxng(self, query, max_results=10):
        """Search using local SearXNG instance (aggregates Google+Bing+DDG+more)."""
        self._stealth_delay()

        try:
            response = requests.get(
                f"{SEARXNG_URL}/search",
                params={
                    "q": query,
                    "format": "json",
                    "categories": "general",
                },
                timeout=SEARXNG_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("results", [])[:max_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", ""),
                    "engine": item.get("engine", "searxng"),
                    "source_eval": evaluate_source(item.get("url", "")),
                })

            print(f"[Reaper] SearXNG: {len(results)} results for '{query[:50]}'")
            return results

        except Exception as e:
            print(f"[Reaper] SearXNG error: {e}")
            return []

    def _search_ddg(self, query, max_results=10):
        """Search using DuckDuckGo (fallback). No API key needed."""
        if not HAS_DDG:
            return []

        self._stealth_delay()

        try:
            with DDGS() as ddgs:
                raw_results = list(ddgs.text(
                    query,
                    max_results=min(max_results, DDG_MAX_RESULTS)
                ))

            results = []
            for item in raw_results:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("href", ""),
                    "snippet": item.get("body", ""),
                    "engine": "duckduckgo",
                    "source_eval": evaluate_source(item.get("href", "")),
                })

            print(f"[Reaper] DuckDuckGo: {len(results)} results for '{query[:50]}'")
            return results

        except Exception as e:
            print(f"[Reaper] DuckDuckGo error: {e}")
            return []

    # =========================================================================
    # STEALTH UTILITIES
    # =========================================================================

    def _stealth_delay(self):
        """Random delay between requests to mimic human browsing."""
        delay = random.uniform(STEALTH_DELAY_MIN, STEALTH_DELAY_MAX)
        time.sleep(delay)

    def _get_stealth_headers(self):
        """Generate request headers that look like a normal browser."""
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Referer": random.choice(REFERRERS) or "",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    # =========================================================================
    # DOWNLOAD SAFETY (Pre-Sentinel)
    # =========================================================================

    def check_download_safety(self, url, content_type=None, content_length=None):
        """
        Evaluate whether a download is safe.

        Returns:
            Dict with:
                - action: "allow", "block", "ask_permission"
                - reason: Why this decision was made
                - details: Additional info for the permission request
        """
        parsed = urlparse(url)
        path = parsed.path.lower()
        source_eval = evaluate_source(url)

        # ── Blocked extensions — always refuse ──
        for ext in BLOCKED_EXTENSIONS:
            if path.endswith(ext):
                return {
                    "action": "block",
                    "reason": f"Blocked file type: {ext}",
                    "details": f"Executable/script files are never downloaded. URL: {url}"
                }

        # ── Size check ──
        if content_length and content_length > MAX_AUTO_DOWNLOAD_SIZE:
            return {
                "action": "ask_permission",
                "reason": f"Large file: {content_length / 1024 / 1024:.1f} MB",
                "details": f"Files over 100MB need approval. URL: {url}"
            }

        # ── Tier 1 auto-allow for safe extensions ──
        if source_eval["tier"] == 1:
            for ext in TIER1_AUTO_ALLOWED_EXTENSIONS:
                if path.endswith(ext):
                    return {
                        "action": "allow",
                        "reason": f"Tier 1 source + safe extension ({ext})",
                        "details": f"Auto-approved: {source_eval['domain']}"
                    }

        # ── Approval-required extensions ──
        for ext in APPROVAL_REQUIRED_EXTENSIONS:
            if path.endswith(ext):
                size_str = f"\nSize: {content_length / 1024:.0f} KB" if content_length else ""
                return {
                    "action": "ask_permission",
                    "reason": f"File download requires approval: {ext}",
                    "details": (
                        f"URL: {url}\n"
                        f"Source: {source_eval['domain']} "
                        f"(Tier {source_eval['tier']}, "
                        f"{source_eval['source_type']}){size_str}"
                    )
                }

        # ── HTML pages are always safe to fetch ──
        if content_type and "text/html" in content_type:
            return {"action": "allow", "reason": "HTML page", "details": ""}

        # ── Unknown: ask to be safe ──
        return {
            "action": "ask_permission",
            "reason": "Unknown content type",
            "details": f"URL: {url}, Content-Type: {content_type}"
        }

    # =========================================================================
    # CONTENT EXTRACTION
    # =========================================================================

    def fetch_page(self, url, category="research", tags=None,
                   store_in_grimoire=True):
        """
        Fetch a web page with stealth headers, extract text, evaluate source,
        optionally store in Grimoire.
        """
        if not HAS_BS4:
            print("[Reaper] beautifulsoup4 required → pip install beautifulsoup4")
            return None

        # Safety check
        safety = self.check_download_safety(url, content_type="text/html")
        if safety["action"] == "block":
            print(f"[Reaper] BLOCKED: {safety['reason']}")
            return None

        source_eval = evaluate_source(url)

        # Fetch with stealth headers
        self._stealth_delay()
        try:
            response = requests.get(
                url, headers=self._get_stealth_headers(),
                timeout=15, allow_redirects=True
            )
            response.raise_for_status()
        except requests.ConnectionError:
            print(f"[Reaper] Connection failed: {url}")
            return None
        except requests.Timeout:
            print(f"[Reaper] Timeout: {url}")
            return None
        except requests.HTTPError as e:
            print(f"[Reaper] HTTP error: {e}")
            return None

        # Extract text
        soup = BeautifulSoup(response.text, "html.parser")
        page_title = soup.title.string.strip() if soup.title and soup.title.string else "No title"

        for element in soup(["script", "style", "nav", "footer", "header",
                            "aside", "form", "iframe"]):
            element.decompose()

        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)

        if not text.strip():
            return None

        # Check skip patterns
        for pattern in ALWAYS_SKIP_PATTERNS:
            if re.search(pattern, text[:500], re.IGNORECASE):
                print(f"[Reaper] Skipped (pattern: {pattern})")
                return None

        # Store in Grimoire
        memory_id = None
        if store_in_grimoire:
            content = text[:WEB_MAX_ARTICLE_CHARS]
            if len(text) > WEB_MAX_ARTICLE_CHARS:
                content += "\n\n[TRUNCATED]"

            memory_content = (
                f"Web Page: {page_title}\n"
                f"URL: {url}\n"
                f"Source: {source_eval['source_type']} "
                f"(Tier {source_eval['tier']})\n\n{content}"
            )

            all_tags = [source_eval['domain']]
            if tags:
                all_tags.extend(tags)

            memory_id = self.grimoire.remember(
                content=memory_content, source="research",
                source_module="reaper", category=category,
                trust_level=source_eval['trust_score'], confidence=0.5,
                tags=all_tags,
                metadata={
                    "url": url, "page_title": page_title,
                    "source_evaluation": source_eval,
                    "content_length": len(text),
                    "fetched_at": datetime.now().isoformat()
                }
            )

        return {
            "url": url, "title": page_title,
            "content": text, "content_length": len(text),
            "source_evaluation": source_eval, "memory_id": memory_id
        }

    # =========================================================================
    # RELEVANCE SCORING — The gate between raw data and Grimoire
    # =========================================================================

    def score_relevance(self, content, topic_name="general"):
        """
        Use phi4-mini to score content relevance 1-10.
        7+ = store full | 4-6 = store summary | below 4 = skip
        """
        sample = content[:2000]
        prompt = (
            f"Score the relevance of this content to '{topic_name}' "
            f"on a scale of 1-10. Is it actionable? Current? Substantive?\n"
            f"Respond with ONLY a single number.\n\n"
            f"CONTENT:\n{sample}\n\nSCORE:"
        )

        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": LLM_MODEL, "prompt": prompt, "stream": False,
                    "options": {"temperature": TEMP_RELEVANCE_SCORING, "num_predict": 5}
                },
                timeout=30
            )
            response.raise_for_status()
            raw = response.json().get("response", "").strip()
            match = re.search(r"\b(\d+)\b", raw)
            if match:
                return max(1, min(10, int(match.group(1))))
        except Exception as e:
            print(f"[Reaper] Relevance scoring failed: {e}")

        return 5  # Safe default

    def summarize(self, text, max_words=150):
        """Summarize content using phi4-mini."""
        sample = text[:6000]
        prompt = (
            f"Summarize in {max_words} words or less. Key facts and decisions only."
            f"\n\nTEXT:\n{sample}\n\nSUMMARY:"
        )

        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": LLM_MODEL, "prompt": prompt, "stream": False,
                    "options": {"temperature": TEMP_SUMMARIZATION, "num_predict": 300}
                },
                timeout=60
            )
            response.raise_for_status()
            return response.json().get("response", "").strip() or text[:500]
        except Exception:
            return text[:500]

    # =========================================================================
    # QUERY EXPANSION
    # =========================================================================

    def expand_query(self, query):
        """
        Use phi4-mini to generate search variants for better coverage.
        "RTX 5090 thermals" → ["RTX 5090 thermals", "5090 temperature review", ...]
        """
        prompt = (
            f"Generate {QUERY_EXPANSION_COUNT - 1} alternative search queries "
            f"for this topic. Different angles, different words. "
            f"One query per line, nothing else.\n\n"
            f"ORIGINAL: {query}\n\nALTERNATIVES:"
        )

        variants = [query]

        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": LLM_MODEL, "prompt": prompt, "stream": False,
                    "options": {"temperature": TEMP_QUERY_EXPANSION, "num_predict": 100}
                },
                timeout=30
            )
            response.raise_for_status()
            raw = response.json().get("response", "")

            for line in raw.strip().split("\n"):
                cleaned = line.strip().lstrip("0123456789.-) ")
                if cleaned and len(cleaned) > 5 and cleaned != query:
                    variants.append(cleaned)

        except Exception as e:
            print(f"[Reaper] Query expansion failed: {e}")

        return variants[:QUERY_EXPANSION_COUNT]

    # =========================================================================
    # RESEARCH PIPELINE — The full flow
    # =========================================================================

    def research(self, topic, urls=None, category="research", tags=None,
                 expand_queries=True):
        """
        Full research pipeline. Search → fetch → score → store.

        If URLs provided: fetch those specific pages.
        If no URLs: search web, fetch top results, score relevance, store.
        """
        print(f"\n[Reaper] ═══ Researching: '{topic}' ═══")

        all_tags = ["research"]
        if tags:
            all_tags.extend(tags)

        # Specific URLs: just fetch them
        if urls:
            results = []
            for url in urls:
                result = self.fetch_page(url, category=category, tags=all_tags)
                if result:
                    results.append(result)
            return {
                "topic": topic, "sources_found": len(urls),
                "stored": len(results), "skipped": len(urls) - len(results),
                "results": results
            }

        # Expand query for better coverage
        queries = self.expand_query(topic) if expand_queries else [topic]
        print(f"[Reaper] Queries: {queries}")

        # Search all variants, deduplicate by URL
        all_search_results = []
        seen_urls = set()

        for query in queries:
            for r in self.search(query, max_results=10):
                url = r.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_search_results.append(r)

        print(f"[Reaper] Found {len(all_search_results)} unique URLs")

        if not all_search_results:
            return {"topic": topic, "sources_found": 0, "stored": 0,
                    "skipped": 0, "results": []}

        # Sort by source tier (best first)
        all_search_results.sort(key=lambda r: r.get("source_eval", {}).get("tier", 4))

        # Fetch, score, store
        stored = 0
        skipped = 0
        stored_results = []
        fetch_limit = min(len(all_search_results), 8)

        for result in all_search_results[:fetch_limit]:
            url = result["url"]
            title = result.get("title", "")

            page = self.fetch_page(
                url, category=category, tags=all_tags,
                store_in_grimoire=False  # We control storage via relevance score
            )

            if not page:
                skipped += 1
                continue

            score = self.score_relevance(page["content"], topic)
            print(f"[Reaper] Relevance: {score}/10 — {title[:50]}...")

            if score >= STORE_FULL_THRESHOLD:
                # Store full content
                content = page["content"][:WEB_MAX_ARTICLE_CHARS]
                memory_content = (
                    f"Research: {topic}\nPage: {page['title']}\n"
                    f"URL: {url}\nSource: {page['source_evaluation']['source_type']} "
                    f"(Tier {page['source_evaluation']['tier']})\n"
                    f"Relevance: {score}/10\n\n{content}"
                )

                memory_id = self.grimoire.remember(
                    content=memory_content, source="research",
                    source_module="reaper", category=category,
                    trust_level=page["source_evaluation"]["trust_score"],
                    confidence=score / 10.0,
                    tags=all_tags + [page["source_evaluation"]["domain"]],
                    metadata={
                        "url": url, "relevance_score": score,
                        "source_evaluation": page["source_evaluation"],
                        "research_topic": topic, "storage_type": "full"
                    }
                )
                stored += 1
                page["memory_id"] = memory_id
                page["storage_type"] = "full"
                stored_results.append(page)

            elif score >= STORE_SUMMARY_THRESHOLD:
                # Store summary only
                summary = self.summarize(page["content"])
                memory_content = (
                    f"Research Summary: {topic}\nPage: {page['title']}\n"
                    f"URL: {url}\nRelevance: {score}/10\n\n{summary}"
                )

                memory_id = self.grimoire.remember(
                    content=memory_content, source="research",
                    source_module="reaper", category=category,
                    trust_level=page["source_evaluation"]["trust_score"],
                    confidence=score / 10.0,
                    tags=all_tags + ["summary-only"],
                    metadata={
                        "url": url, "relevance_score": score,
                        "research_topic": topic, "storage_type": "summary"
                    }
                )
                stored += 1
                page["memory_id"] = memory_id
                page["storage_type"] = "summary"
                stored_results.append(page)
            else:
                skipped += 1
                print(f"[Reaper] Skipped (score {score}): {title[:50]}...")

        print(f"\n[Reaper] Complete: {stored} stored, {skipped} skipped")
        return {
            "topic": topic, "sources_found": len(all_search_results),
            "stored": stored, "skipped": skipped, "results": stored_results
        }

    # =========================================================================
    # STANDING RESEARCH — One command runs everything
    # =========================================================================

    def run_standing_research(self):
        """
        Run research on ALL standing topics from config.py.
        This is the one command that does everything.
        """
        print("\n" + "=" * 60)
        print("[Reaper] ═══ STANDING RESEARCH RUN ═══")
        print(f"[Reaper] Topics: {len(STANDING_TOPICS)}")
        print(f"[Reaper] Time: {datetime.now().isoformat()}")
        print("=" * 60)

        all_results = {}

        for topic in STANDING_TOPICS:
            print(f"\n[Reaper] ─── Topic: {topic.name} ───")

            topic_results = {"web_research": [], "reddit_posts": []}

            # Web research for each keyword
            for keyword in topic.keywords:
                result = self.research(
                    topic=keyword, category=topic.category,
                    tags=topic.tags, expand_queries=False
                )
                topic_results["web_research"].append(result)

            # Reddit monitoring
            for subreddit in topic.subreddits:
                posts = self.reddit_search(
                    subreddit_name=subreddit, keywords=topic.keywords,
                    min_score=topic.min_reddit_score,
                    category=topic.category, tags=topic.tags
                )
                topic_results["reddit_posts"].extend(posts)

            all_results[topic.name] = topic_results

        report = self._generate_research_report(all_results)
        print(report)

        return all_results

    def run_single_topic(self, topic_name):
        """Run research for one specific standing topic by name."""
        for topic in STANDING_TOPICS:
            if topic.name.lower() == topic_name.lower():
                print(f"\n[Reaper] Running: {topic.name}")
                results = {"web_research": [], "reddit_posts": []}

                for keyword in topic.keywords:
                    results["web_research"].append(
                        self.research(topic=keyword, category=topic.category,
                                     tags=topic.tags, expand_queries=False)
                    )
                for subreddit in topic.subreddits:
                    results["reddit_posts"].extend(
                        self.reddit_search(
                            subreddit_name=subreddit, keywords=topic.keywords,
                            min_score=topic.min_reddit_score,
                            category=topic.category, tags=topic.tags)
                    )
                return results

        print(f"[Reaper] Topic not found: '{topic_name}'")
        print(f"[Reaper] Available: {[t.name for t in STANDING_TOPICS]}")
        return None

    # =========================================================================
    # REDDIT MONITORING
    # =========================================================================

    def reddit_search(self, subreddit_name, keywords, min_score=5,
                      limit_per_keyword=5, category="research", tags=None):
        """
        Search a subreddit for posts matching keywords.
        Filters by minimum score. Stores matches in Grimoire.
        """
        if not HAS_PRAW:
            return []

        client_id = os.environ.get("REDDIT_CLIENT_ID")
        client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
        user_agent = os.environ.get("REDDIT_USER_AGENT", "Shadow/1.0")

        if not client_id or not client_secret:
            print("[Reaper] Reddit credentials not set. Skipping.")
            return []

        try:
            reddit = praw.Reddit(
                client_id=client_id, client_secret=client_secret,
                user_agent=user_agent
            )
            reddit.read_only = True  # Safety: never post
        except Exception as e:
            print(f"[Reaper] Reddit connection failed: {e}")
            return []

        stored_posts = []
        seen_ids = set()

        for keyword in keywords:
            try:
                subreddit = reddit.subreddit(subreddit_name)
                for post in subreddit.search(keyword, limit=limit_per_keyword,
                                             sort="relevance", time_filter="week"):
                    if post.id in seen_ids or post.score < min_score:
                        continue
                    seen_ids.add(post.id)

                    post_url = f"https://reddit.com{post.permalink}"
                    memory_content = (
                        f"Reddit: r/{subreddit_name}\n"
                        f"Title: {post.title}\n"
                        f"Score: {post.score} | Comments: {post.num_comments}\n"
                        f"URL: {post_url}\n"
                    )

                    if post.selftext:
                        body = post.selftext[:1500]
                        if len(post.selftext) > 1500:
                            body += "\n[TRUNCATED]"
                        memory_content += f"\n{body}"

                    all_tags = ["reddit", f"r/{subreddit_name}".lower()]
                    if tags:
                        all_tags.extend(tags)

                    memory_id = self.grimoire.remember(
                        content=memory_content, source="reddit",
                        source_module="reaper", category=category,
                        trust_level=0.3,
                        confidence=min(post.score / 100.0, 1.0),
                        tags=all_tags,
                        metadata={
                            "reddit_url": post_url, "reddit_score": post.score,
                            "reddit_comments": post.num_comments,
                            "subreddit": subreddit_name,
                            "keyword_matched": keyword,
                        }
                    )

                    stored_posts.append({
                        "title": post.title, "score": post.score,
                        "url": post_url, "memory_id": memory_id,
                    })
                    print(f"[Reaper] Reddit [{post.score}↑] {post.title[:55]}...")

            except Exception as e:
                print(f"[Reaper] Reddit error r/{subreddit_name} '{keyword}': {e}")

        return stored_posts

    # =========================================================================
    # YOUTUBE (Subtitles Only)
    # =========================================================================

    def youtube_transcribe(self, url, category="research", tags=None):
        """Download YouTube subtitles and store. Long transcripts get summarized."""
        print(f"[Reaper] YouTube: {url}")

        try:
            result = subprocess.run(
                ["yt-dlp", "--dump-json", "--no-download", url],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                print(f"[Reaper] yt-dlp error: {result.stderr[:200]}")
                return None
            info = json.loads(result.stdout)
            title = info.get("title", "Unknown")
            channel = info.get("channel", "Unknown")
            duration = info.get("duration", 0)
            video_id = info.get("id", "unknown")
        except Exception as e:
            print(f"[Reaper] YouTube info failed: {e}")
            return None

        sub_path = self.data_dir / "youtube" / video_id
        try:
            subprocess.run(
                ["yt-dlp", "--write-auto-sub", "--write-sub",
                 "--sub-lang", "en", "--sub-format", "vtt",
                 "--skip-download", "--output", str(sub_path), url],
                capture_output=True, text=True, timeout=60
            )
        except subprocess.TimeoutExpired:
            return None

        sub_file = None
        for ext in [".en.vtt", ".en.auto.vtt"]:
            candidate = self.data_dir / "youtube" / f"{video_id}{ext}"
            if candidate.exists():
                sub_file = candidate
                break

        if not sub_file:
            print("[Reaper] No English subtitles (needs Whisper — Phase 5)")
            return None

        clean = self._clean_vtt(sub_file.read_text(encoding="utf-8"))
        if not clean.strip():
            return None

        # Long transcripts: summary in Grimoire, full file on disk
        if len(clean) > YOUTUBE_SUMMARY_CHAR_THRESHOLD:
            summary = self.summarize(clean, max_words=300)
            memory_content = (
                f"YouTube Summary: '{title}' by {channel}\n"
                f"URL: {url} | Duration: {duration // 60}m {duration % 60}s\n"
                f"Full transcript: {sub_file}\n\n{summary}"
            )
            storage_note = "summary"
        else:
            memory_content = (
                f"YouTube: '{title}' by {channel}\n"
                f"URL: {url} | Duration: {duration // 60}m {duration % 60}s\n\n"
                f"{clean}"
            )
            storage_note = "full"

        all_tags = ["youtube", channel.lower().replace(" ", "-")]
        if tags:
            all_tags.extend(tags)

        memory_id = self.grimoire.remember(
            content=memory_content, source="youtube",
            source_module="reaper", category=category,
            trust_level=0.3, confidence=0.6, tags=all_tags,
            metadata={
                "url": url, "video_id": video_id, "title": title,
                "channel": channel, "duration_seconds": duration,
                "transcript_file": str(sub_file), "storage_type": storage_note,
            }
        )

        print(f"[Reaper] YouTube stored ({storage_note}): {title[:50]}...")
        return {"memory_id": memory_id, "title": title, "storage": storage_note}

    def _clean_vtt(self, vtt_text):
        """Clean WebVTT: remove timestamps, formatting, deduplicate."""
        lines = vtt_text.split("\n")
        clean_lines = []
        seen = set()
        for line in lines:
            if line.strip().startswith("WEBVTT") or "-->" in line:
                continue
            if not line.strip() or line.strip().isdigit():
                continue
            clean = re.sub(r"<[^>]+>", "", line).strip()
            if clean and clean not in seen:
                seen.add(clean)
                clean_lines.append(clean)
        return " ".join(clean_lines)

    # =========================================================================
    # BROWSER HISTORY
    # =========================================================================

    def read_chrome_history(self, limit=50, hours_back=24):
        """Read recent Chrome browsing history (read-only)."""
        if os.name == "nt":
            chrome_path = Path(os.environ.get("LOCALAPPDATA", "")) / \
                "Google" / "Chrome" / "User Data" / "Default" / "History"
        else:
            chrome_path = Path.home() / ".config" / "google-chrome" / \
                "Default" / "History"

        if not chrome_path.exists():
            return []

        temp_db = self.data_dir / "chrome_history_temp.db"
        try:
            shutil.copy2(str(chrome_path), str(temp_db))
        except PermissionError:
            print("[Reaper] Chrome running — can't read history")
            return []

        try:
            conn = sqlite3.connect(str(temp_db))
            conn.row_factory = sqlite3.Row
            cutoff_us = int(
                (datetime.now().timestamp() - hours_back * 3600)
                * 1000000 + 11644473600 * 1000000
            )
            cursor = conn.cursor()
            cursor.execute("""
                SELECT urls.url, urls.title, urls.visit_count, visits.visit_time
                FROM urls JOIN visits ON urls.id = visits.url
                WHERE visits.visit_time > ?
                ORDER BY visits.visit_time DESC LIMIT ?
            """, (cutoff_us, limit))

            history = []
            for row in cursor.fetchall():
                unix_ts = (row["visit_time"] / 1000000) - 11644473600
                history.append({
                    "url": row["url"], "title": row["title"],
                    "visit_count": row["visit_count"],
                    "visit_time": datetime.fromtimestamp(unix_ts).isoformat()
                })
            conn.close()
            temp_db.unlink(missing_ok=True)
            return history
        except Exception as e:
            print(f"[Reaper] Chrome history error: {e}")
            if temp_db.exists():
                temp_db.unlink(missing_ok=True)
            return []

    # =========================================================================
    # REPORTING
    # =========================================================================

    def _generate_research_report(self, results):
        """Generate formatted report from standing research results."""
        lines = [
            "", "=" * 60,
            f"  REAPER RESEARCH REPORT — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "=" * 60,
        ]

        total_stored = 0
        total_reddit = 0

        for topic_name, topic_data in results.items():
            lines.append(f"\n  ─── {topic_name} ───")

            for research in topic_data.get("web_research", []):
                s = research.get("stored", 0)
                total_stored += s
                if s > 0:
                    lines.append(f"    Web: {s} sources for '{research.get('topic', '')}'")

            posts = topic_data.get("reddit_posts", [])
            total_reddit += len(posts)
            if posts:
                lines.append(f"    Reddit: {len(posts)} posts")
                for p in posts[:3]:
                    lines.append(f"      [{p['score']}↑] {p['title'][:55]}...")

        lines.extend([
            f"\n{'=' * 60}",
            f"  TOTALS: {total_stored} web + {total_reddit} Reddit",
            f"{'=' * 60}"
        ])
        return "\n".join(lines)

    def get_briefing_data(self):
        """Gather recent data for Harbinger's daily briefing."""
        return {
            "generated_at": datetime.now().isoformat(),
            "research": self.grimoire.recall_recent(limit=10, source="research"),
            "reddit": self.grimoire.recall_recent(limit=10, source="reddit"),
            "youtube": self.grimoire.recall_recent(limit=5, source="youtube"),
        }

    def close(self):
        """Clean shutdown."""
        print("[Reaper] Shut down cleanly.")
