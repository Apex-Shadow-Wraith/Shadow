# Project Shadow — Claude Code Context

## What This Project Is
Shadow is a fully autonomous, locally-hosted personal AI agent system. One agent, one identity, 13 modules. Built for home and business use (landscaping business using LMN software). The goal is a Jarvis-style assistant that exceeds ChatGPT quality for the creator's specific needs, with complete data privacy and no recurring API costs.

## Creator Profile
- Intermediate Python learner — actively studying (Automate the Boring Stuff)
- Runs a landscaping business
- Biblical values are central to Shadow's ethics framework
- Anti-sycophancy is a top priority: Shadow must push back, correct errors, and never just agree

## Tech Stack
- **Language:** Python 3.12
- **Virtual Environment:** shadow_env (activate: `.\shadow_env\Scripts\activate`)
- **Database:** SQLite + ChromaDB (vector DB with nomic-embed-text embeddings)
- **AI Runtime:** Ollama (phi4-mini for routing/scoring, nomic-embed-text for embeddings)
- **Search:** SearXNG (Docker, self-hosted) + DuckDuckGo (fallback)
- **Web Automation:** Playwright + stealth layer
- **Git:** Initialized, commits on master branch

## Project Structure
```
C:\Shadow/
├── modules/
│   ├── grimoire/          # Memory system — BUILT (SQLite + ChromaDB)
│   ├── reaper/            # Research & web scraping — BUILT
│   ├── shadow_core/       # Master orchestrator/router
│   ├── wraith/            # Fast brain, daily tasks
│   ├── cerberus/          # Ethics, safety, approvals
│   ├── apex/              # Claude/GPT API fallback
│   ├── sentinel/          # Security, white hat defense
│   ├── harbinger/         # Briefings, alerts, notifications
│   ├── cipher/            # Math, logic, complex reasoning
│   ├── omen/              # Code writing, debugging
│   ├── nova/              # Content creation, image gen
│   ├── void/              # 24/7 passive monitoring
│   └── morpheus/          # Creative discovery pipeline
├── data/
│   ├── memory/            # shadow_memory.db (SQLite, live)
│   ├── vectors/           # ChromaDB persistent storage (live)
│   ├── research/quarantine/
│   ├── training/          # LoRA training data (future)
│   ├── logs/
│   ├── downloads/
│   ├── browsing_history/
│   └── backups/
├── config/
│   └── .env               # API credentials (Reddit, Discord, etc.)
├── services/
│   └── searxng/           # Docker config for SearXNG
├── identity/              # Shadow's identity file, system prompts
├── prompts/               # Module-specific system prompts
├── docs/                  # Project documentation
├── tests/
│   └── test_shadow_memory.py
├── run_research.py        # One-command standing research runner
└── .gitignore
```

## Module Codenames — NEVER RENAME THESE
These names are Shadow's identity. Preserve them always:
1. **Shadow** — Master orchestrator/router
2. **Wraith** — Fast brain, daily tasks, core agent loop
3. **Cerberus** — Ethics, safety, approvals, action auditing
4. **Apex** — Claude/GPT API fallback
5. **Grimoire** — Data storage, knowledge base, memory, vector DB
6. **Sentinel** — Security, firewall, white hat defense
7. **Harbinger** — Briefings, alerts, notifications, reports
8. **Reaper** — Research, web scraping, stealth browsing
9. **Cipher** — Math, logic, complex reasoning
10. **Omen** — Code writing, debugging
11. **Nova** — Content creation, image generation
12. **Void** — 24/7 passive monitoring
13. **Morpheus** — Creative discovery pipeline (controlled hallucination)

## Built Modules (Session 7-8)

### Grimoire (Memory System)
- **Location:** `modules/grimoire/grimoire.py`
- SQLite + ChromaDB dual storage
- Functions: `remember()`, `recall()`, `correct()`, `forget()`, `find_conflicts()`, `get_pointer_index()`
- Dedup threshold: >92% similarity = merge, not duplicate
- Embedding: nomic-embed-text via Ollama (768 dimensions)
- Input truncated to 2000 chars before embedding (crash fix, Session 8)
- Retry with exponential backoff (3 attempts)
- Trust levels: 1.0 (user correction) → 0.0 (unverified)
- Currently 31 active memories

### Reaper (Research Module)
- **Location:** `modules/reaper/reaper.py`
- Dual search: SearXNG (primary) → DuckDuckGo (fallback)
- Query expansion via phi4-mini (3 variants per query)
- Relevance gate: phi4-mini scores 1-10 (7+ store full, 4-6 summary, <4 skip)
- Source trust hierarchy: Tier 1 official (0.7), Tier 2 journalism (0.5), Tier 3 community (0.3), Tier 4 unverified (0.1)
- Stealth layer: user agent rotation, timing randomization, referrer spoofing, clean sessions
- Standing research: 4 topics (AI Developments, AI Leaks, Shadow Tools, Hardware & Pricing)

## Coding Conventions
- Use descriptive variable names
- Add docstrings to all functions
- Error handling with try/except — never let Shadow crash silently
- Log everything: every interaction, tool call, decision
- All new data flows through Grimoire with appropriate trust levels
- Test before committing

## Critical Policies
- **NEVER** access financial accounts — permanent rule
- **NEVER** take external-facing actions without explicit approval
- **NEVER** delete files without backup first
- All models must be abliterated before use (strip manufacturer alignment)
- Shadow's ethics come from biblical values, not manufacturer training
- Anti-sycophancy: push back on bad ideas, say "I don't know," never guess to please
- Financial access only through prepaid virtual cards (Privacy.com)
- All downloads land in data/research/quarantine/ — never directly in working files

## Git Info
- Repo: C:\Shadow
- Branch: master
- .gitignore excludes: shadow_env/, *.db, .env, __pycache__/, data/, logs/

## What NOT to Do
- Don't rename module codenames
- Don't modify .env directly without asking
- Don't install packages outside the virtual environment
- Don't commit database files or API keys
- Don't bypass Cerberus safety rules
- Don't make architecture decisions without discussion — those happen in Opus sessions

## Allowed Commands
The following commands are pre-approved and do not need confirmation:
- python (any python command)
- pip install
- pytest
- git add, git commit, git status, git diff, git log
- cd, ls, dir, cat, type, head, tail
- mkdir, cp, copy, move, mv
- ollama