"""
Shadow Research Runner — One command to research everything
============================================================
This is the script you run to trigger Reaper's standing research.
One command. All topics. All subreddits. All keywords.
Results stored in Grimoire. Report printed when done.

Usage:
    cd C:\\Shadow
    shadow_env\\Scripts\\activate
    python run_research.py

    # Or run a single topic:
    python run_research.py "AI Leaks & Frontier Models"

REQUIRES:
    - Ollama running with nomic-embed-text + phi4-mini
    - SearXNG running (docker-compose up -d) OR duckduckgo-search installed
    - Reddit API credentials in environment (optional — skips Reddit if missing)

Author: Patrick (with Claude Opus 4.6)
Project: Shadow • Session 7
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Importing the centralized config singleton triggers .env loading and
# YAML settings construction exactly once for the whole process.
from shadow.config import config  # noqa: F401

from modules.grimoire import Grimoire
from modules.reaper import Reaper


def main():
    print("=" * 60)
    print(f"  SHADOW RESEARCH RUNNER — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Initialize modules
    grimoire = Grimoire(
        db_path="data/memory/shadow_memory.db",
        vector_path="data/vectors"
    )
    reaper = Reaper(grimoire)

    # Check if a specific topic was requested
    if len(sys.argv) > 1:
        topic_name = " ".join(sys.argv[1:])
        print(f"\n  Running single topic: {topic_name}")
        result = reaper.run_single_topic(topic_name)
    else:
        print(f"\n  Running ALL standing topics...")
        result = reaper.run_standing_research()

    # Show final Grimoire stats
    print("\n" + "=" * 60)
    print("  GRIMOIRE STATUS AFTER RESEARCH")
    print("=" * 60)
    stats = grimoire.stats()
    print(f"  Active memories: {stats['active_memories']}")
    print(f"  By category:")
    for cat, count in stats.get('by_category', {}).items():
        print(f"    {cat}: {count}")

    # Clean up
    reaper.close()
    grimoire.close()

    print("\n✅ Research run complete.")


if __name__ == "__main__":
    main()
