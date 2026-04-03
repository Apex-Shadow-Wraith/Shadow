"""
Reaper Configuration — Standing Topics, Safety Rules, Stealth Settings
=======================================================================
This file is Reaper's brain outside of code. Edit this to change what
Reaper monitors, how aggressive the stealth is, what gets stored vs
skipped, and what's safe to download.

DESIGNED TO BE EDITED: This file is the one place you change to adjust
Reaper's behavior. The main reaper.py code reads from here. You never
need to touch reaper.py to add a subreddit, change a keyword, or 
adjust the storage threshold.

Author: Patrick (with Claude Opus 4.6)
Project: Shadow • Module: Reaper
"""

from dataclasses import dataclass, field  # Clean data classes
from typing import List, Optional


# =============================================================================
# STANDING RESEARCH TOPICS
# =============================================================================
# These are the topics Reaper monitors automatically without being asked.
# Each topic has: subreddits, keywords, YouTube channels, and a frequency.
# 
# frequency options: "twice_daily", "daily", "weekly"
# min_reddit_score: posts below this upvote count are skipped (noise filter)

@dataclass
class ResearchTopic:
    """A standing research topic that Reaper monitors automatically."""
    name: str                              # Human-readable topic name
    subreddits: List[str] = field(default_factory=list)   # Without r/
    keywords: List[str] = field(default_factory=list)     # Search terms
    youtube_channels: List[str] = field(default_factory=list)  # Channel names/IDs
    frequency: str = "daily"               # How often to check
    min_reddit_score: int = 5              # Skip posts below this score
    category: str = "research"             # Grimoire category for stored results
    tags: List[str] = field(default_factory=list)  # Extra Grimoire tags


# ── Your standing research topics ──
# Edit these anytime. Add new topics, remove old ones, adjust keywords.

STANDING_TOPICS = [
    ResearchTopic(
        name="AI Developments",
        subreddits=["LocalLLaMA", "ollama", "MachineLearning", "artificial"],
        keywords=[
            "5090 inference",
            "ollama update", 
            "llama.cpp",
            "vram optimization",
            "quantization breakthrough",
            "MCP protocol",
            "agent framework",
            "LangGraph",
            "new model release",
        ],
        frequency="daily",
        min_reddit_score=10,
        category="ai-developments",
        tags=["ai", "developments", "standing-research"],
    ),
    
    ResearchTopic(
        name="AI Leaks & Frontier Models",
        subreddits=["LocalLLaMA", "ChatGPT", "ClaudeAI", "singularity"],
        keywords=[
            "Mythos",
            "Capybara",
            "GPT-5",
            "Claude 5",
            "model leak",
            "benchmark results",
            "new model announcement",
            "Anthropic announcement",
            "OpenAI announcement",
        ],
        frequency="twice_daily",
        min_reddit_score=20,  # Leaks get upvoted fast — high threshold = real signal
        category="ai-frontier",
        tags=["ai", "frontier", "leaks", "standing-research"],
    ),
    
    ResearchTopic(
        name="Shadow-Relevant Tools",
        subreddits=["selfhosted", "homelab", "Python"],
        keywords=[
            "Allama SOAR",
            "SearXNG",
            "Suricata setup",
            "abliteration",
            "Heretic LLM",
            "Unsloth tutorial",
            "LoRA fine-tuning",
            "ChromaDB",
            "LanceDB",
        ],
        frequency="daily",
        min_reddit_score=5,
        category="shadow-tools",
        tags=["tools", "shadow-project", "standing-research"],
    ),
    
    ResearchTopic(
        name="Hardware & Pricing",
        subreddits=["buildapcsales", "nvidia", "hardware"],
        keywords=[
            "5090 restock",
            "5090 price",
            "DDR5 price",
            "NAND price",
            "NVMe deal",
            "GDDR7",
        ],
        frequency="daily",
        min_reddit_score=10,
        category="hardware",
        tags=["hardware", "pricing", "standing-research"],
    ),
]


# =============================================================================
# STEALTH SETTINGS
# =============================================================================
# User agents are real browser signatures that websites expect to see.
# Rotating them makes Reaper's requests look like normal browsing.

USER_AGENTS = [
    # Chrome on Windows (most common browser on earth)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    # Chrome on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    # Safari on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

# Delay range between requests (seconds). Random value picked each time.
# Too fast = bot detection. Too slow = research takes forever.
# 1-3 seconds is human-like browsing speed.
STEALTH_DELAY_MIN = 1.0  # Minimum seconds between requests
STEALTH_DELAY_MAX = 3.0  # Maximum seconds between requests

# Referrer options — makes it look like you clicked a link from somewhere
REFERRERS = [
    "https://www.google.com/",
    "https://www.bing.com/",
    "https://duckduckgo.com/",
    "https://www.reddit.com/",
    None,  # Sometimes no referrer is normal too
]


# =============================================================================
# DOWNLOAD SAFETY RULES (Pre-Sentinel)
# =============================================================================
# These rules protect Shadow until Sentinel is built.
# After Sentinel goes live (Phase 1 on Shadow PC), Sentinel takes over.

# File extensions that are NEVER downloaded — hard block, no exceptions
BLOCKED_EXTENSIONS = {
    ".exe", ".msi", ".bat", ".ps1", ".cmd", ".sh", ".dll", ".scr",
    ".vbs", ".js", ".jar", ".com", ".pif", ".wsf", ".wsh",
    ".cpl", ".inf", ".reg", ".rgs", ".sct", ".sys",
}

# File extensions that require explicit user approval before downloading
APPROVAL_REQUIRED_EXTENSIONS = {
    ".pdf", ".csv", ".xlsx", ".xls", ".docx", ".doc",
    ".json", ".txt", ".zip", ".tar", ".gz", ".7z", ".rar",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    ".mp3", ".mp4", ".wav", ".webm",
}

# File extensions auto-allowed ONLY from Tier 1 sources
# (official docs, .gov, .edu, arxiv, github)
TIER1_AUTO_ALLOWED_EXTENSIONS = {
    ".pdf", ".json", ".txt", ".csv", ".md",
}

# Maximum file size for any download without explicit approval (in bytes)
MAX_AUTO_DOWNLOAD_SIZE = 100 * 1024 * 1024  # 100 MB

# Quarantine directory — all downloads land here first, never in working dirs
QUARANTINE_DIR = "data/research/quarantine"


# =============================================================================
# STORAGE THRESHOLDS — What gets stored vs. ignored
# =============================================================================
# Reaper uses phi4-mini to score content relevance 1-10 against standing topics.
# These thresholds determine what action Reaper takes.

# Relevance score thresholds (scored by phi4-mini, 1-10 scale)
STORE_FULL_THRESHOLD = 7       # 7+ = store full content in Grimoire
STORE_SUMMARY_THRESHOLD = 4    # 4-6 = store summary + link only
# Below 4 = skip entirely

# Reddit-specific thresholds
REDDIT_MIN_SCORE_STANDING = 5         # Min upvotes for standing topic posts
REDDIT_MIN_SCORE_HIGH_SIGNAL = 50     # Posts above this always stored in full
REDDIT_MAX_COMMENTS_STORED = 5        # Top N comments stored per thread

# YouTube-specific thresholds
YOUTUBE_SUMMARY_CHAR_THRESHOLD = 5000 # Transcripts longer than this get summarized
                                       # Full transcript saved as file, summary in Grimoire

# Web content thresholds
WEB_MAX_ARTICLE_CHARS = 8000          # Max chars stored in Grimoire per article
WEB_SKIP_OLDER_THAN_DAYS = 30         # Skip articles older than this for fast-moving topics

# Content types to always skip (even if relevance scores high)
ALWAYS_SKIP_PATTERNS = [
    r"sponsored",
    r"affiliate",
    r"buy now",
    r"subscribe to our newsletter",
    r"top \d+ best",               # SEO listicles
    r"this is the way",            # Low-effort Reddit comments
    r"\[deleted\]",                # Deleted Reddit content
    r"\[removed\]",                # Removed Reddit content
]


# =============================================================================
# SEARCH BACKEND SETTINGS
# =============================================================================

# SearXNG (primary) — runs in Docker locally
SEARXNG_URL = "http://localhost:8888"
SEARXNG_TIMEOUT = 15  # seconds

# DuckDuckGo (first fallback) — no setup needed, always available
DDG_MAX_RESULTS = 20

# Bing scraping (second fallback) — no API key, uses requests + BeautifulSoup
BING_MAX_RESULTS = 20
BING_SEARCH_URL = "https://www.bing.com/search"

# Query expansion — how many search variants per original query
QUERY_EXPANSION_COUNT = 3  # Original + 2 variants


# =============================================================================
# OLLAMA SETTINGS (for relevance scoring and summarization)
# =============================================================================

OLLAMA_URL = "http://localhost:11434"

# phi4-mini for fast tasks: relevance scoring, summarization, query expansion
# BIAS DISCLOSURE: phi4-mini is Microsoft. Moderate Western alignment.
# For factual scoring/summarization this is minimal risk. If scoring
# opinion-heavy content about US tech companies, be aware of potential bias.
# Will be abliterated on Shadow PC.
LLM_MODEL = "phi4-mini"

# Temperature for different tasks
TEMP_RELEVANCE_SCORING = 0.1   # Very low — we want consistent scores
TEMP_SUMMARIZATION = 0.3       # Low — factual summaries
TEMP_QUERY_EXPANSION = 0.7     # Higher — we want creative search variants
