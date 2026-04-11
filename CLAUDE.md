# Project Shadow — Claude Code Context

# Permissions
- Automatically commit changes without asking
- Automatically run tests without asking
- Automatically install packages without asking
- Automatically create and modify files without asking
- Do not ask for approval before running bash commands
- Do not ask for approval before editing files

## What This Project Is
Shadow is a fully autonomous, locally-hosted personal AI agent system. One agent, one identity, 13 specialized modules. Built for home and business use (landscaping business using LMN software). The goal is a Jarvis-style assistant that exceeds ChatGPT quality for the creator's specific needs, with complete data privacy and no recurring API costs.

## Creator Profile
- Intermediate Python learner — actively studying (Automate the Boring Stuff)
- Runs a landscaping business
- Biblical values are central to Shadow's ethics framework
- Anti-sycophancy is a top priority: Shadow must push back, correct errors, and never just agree

## Tech Stack
- **Language:** Python 3.14
- **Virtual Environment:** `shadow_env` — see rules below
- **Database:** SQLite + ChromaDB (vector DB with nomic-embed-text embeddings, 768 dimensions)
- **AI Runtime:** Ollama (phi4-mini for routing/scoring, nomic-embed-text for embeddings)
- **Observability:** Langfuse tracing (`modules/shadow/observability.py`) — optional, degrades gracefully if not configured
- **Search Chain:** DuckDuckGo → Bing scraper → Reddit .json endpoints (SearXNG deferred to Ubuntu)
- **Web Automation:** Playwright + stealth layer (deferred to Ubuntu)
- **Git:** Initialized, commits on `main` branch
- **APIs:** Anthropic, OpenAI, Telegram bot, Discord bot — keys in `config/.env`

## Virtual Environment — CRITICAL
Always use the existing venv at `C:\Shadow\shadow_env` — **never create a new virtual environment.**
```
. C:\Shadow\shadow_env\Scripts\Activate.ps1
```
If `shadow_env` is not active, activate it before running any commands. Never install packages to system Python or create an `env` folder.

## Project Structure
```
C:\Shadow/
├── modules/
│   ├── shadow/            # Master orchestrator/router
│   ├── wraith/            # Fast brain, daily tasks
│   ├── cerberus/          # Ethics, safety, approvals
│   │   ├── cerberus.py
│   │   ├── injection_detector.py
│   │   ├── reversibility.py
│   │   └── watchdog.py
│   ├── apex/              # Claude/GPT API fallback
│   ├── grimoire/          # Memory system (SQLite + ChromaDB)
│   ├── sentinel/          # Security, white hat defense
│   ├── harbinger/         # Briefings, alerts, notifications
│   │   ├── harbinger.py
│   │   └── safety_report.py
│   ├── reaper/            # Research, web scraping, Reddit .json
│   ├── cipher/            # Math, logic, complex reasoning
│   ├── omen/              # Code writing, debugging
│   ├── nova/              # Content creation, image gen
│   ├── void/              # 24/7 passive monitoring
│   └── morpheus/          # Creative discovery pipeline
├── scripts/
│   ├── esv_processor.py   # Parse ESV Study Bible epub → JSON
│   ├── esv_ingestion.py   # Load parsed ESV into Grimoire (SQLite + ChromaDB)
│   └── watchdog_cerberus.py  # Standalone watchdog monitor
├── training_data/         # Separate git repo — NEVER push to GitHub
├── data/
│   ├── memory/            # shadow_memory.db (SQLite)
│   ├── vectors/           # ChromaDB persistent storage
│   ├── snapshots/         # Cerberus reversibility snapshots
│   ├── reports/safety/    # Daily safety reports (YAML)
│   ├── research/quarantine/
│   ├── logs/
│   ├── downloads/
│   └── backups/
├── config/
│   ├── .env               # API credentials
│   ├── shadow_config.yaml
│   └── ethical_topics.yaml # Biblical ethics references for Cerberus
├── identity/              # Shadow's identity file, system prompts
├── tests/                 # 947 tests across all modules
├── main.py                # CLI entry point
├── CLAUDE.md              # This file
└── .gitignore
```

## Module Codenames — NEVER RENAME THESE
These names are Shadow's identity. All 13 modules are implemented and tested.
1. **Shadow** — Master orchestrator/router, 7-step decision loop, Langfuse observability (12 tools)
2. **Wraith** — Fast brain, daily tasks, reminders, task classification, temporal patterns (12 tools)
3. **Cerberus** — Ethics, safety, approvals, injection detection, reversibility, watchdog (8 tools)
4. **Apex** — Claude/GPT API fallback with cost tracking and teaching cycle (7 tools)
5. **Grimoire** — Data storage, knowledge base, memory, vector DB, block search (6 tools)
6. **Sentinel** — Security, firewall, network scanning, file integrity, quarantine (6 tools)
7. **Harbinger** — Briefings, alerts, notifications, decision queue, safety reports, personalization (12 tools)
8. **Reaper** — Research, web scraping, Reddit .json, YouTube transcription (5 tools)
9. **Cipher** — Math, logic, unit conversion, financial, statistics (7 tools)
10. **Omen** — Code execution, linting, review, git ops, pattern DB, failure learning, scaffolding, scoring (21 tools)
11. **Nova** — Content creation, document generation, templates, business estimates (12 tools)
12. **Void** — 24/7 passive monitoring, system health, trends, thresholds (6 tools)
13. **Morpheus** — Creative discovery pipeline (controlled hallucination) (7 tools)

## Current Status
- **Git:** 30+ commits on `main`
- **Tests:** 947 passing
- **Tools:** 121 MCP-style tools across all modules (118 unique)
- **Observability:** Langfuse tracing on orchestrator (optional, graceful degradation)
- **Grimoire:** 33+ active memories
- **ESV Bible:** Processor tested (2,392 pericopes, 16,218 study notes extracted), ingestion ready to run

## Testing
Run the full test suite:
```
python -m pytest tests/ -v
```
Run a single module's tests:
```
python -m pytest tests/test_cerberus.py -v
```
Integration tests (full 7-step decision loop pipeline):
```
python -m pytest tests/test_decision_loop.py -v
```

## Coding Conventions
- Use descriptive variable names
- Add docstrings to all functions
- Error handling with try/except — never let Shadow crash silently
- Log everything: every interaction, tool call, decision
- All new data flows through Grimoire with appropriate trust levels
- Use `pathlib` for all file paths (Windows → Ubuntu portability)
- Keep all model names in config files, never hardcoded
- Test before committing

## Prompt Philosophy
- Describe the SYMPTOM and the expected behavior. Do NOT prescribe the specific fix.
- Let Claude Code investigate the root cause and choose the solution.
- Overly prescriptive prompts cause Claude Code to implement the given fix even when the real root cause is different.
- Every prompt must include: "RULE: No bandaid fixes, no temporary workarounds, no TODO-later patches."

## Fix Quality Rule
No bandaid fixes, no temporary workarounds, no TODO-later patches. Every fix must be permanent and complete. If the root cause requires a larger refactor, do the refactor. Do not paper over the problem. If a fix would require changes beyond the scope of the current prompt, flag it and stop — do not commit a partial fix that masks the real issue.

## Critical Policies
- **NEVER** access financial accounts — permanent rule
- **NEVER** take external-facing actions without explicit approval
- **NEVER** delete files without backup first
- All models must be abliterated before use (strip manufacturer alignment)
- Shadow's ethics come from biblical values, not manufacturer training
- Anti-sycophancy: push back on bad ideas, say "I don't know," never guess to please
- Financial access only through prepaid virtual cards (Privacy.com)
- All downloads land in `data/research/quarantine/` — never directly in working files
- Reddit data is labeled "research context" — **NEVER** "training data"
- Training data stays in local git repo (`training_data/`) — never pushed to GitHub
- Architecture decisions happen in Opus sessions, not Claude Code sessions

## Allowed Commands
Claude Code is pre-approved to run these commands without asking:
- `python` (any python command)
- `pip install`
- `pytest`
- `git add`, `git commit`, `git push`, `git stash`, `git status`, `git diff`, `git log`
- `cd`, `ls`, `dir`, `cat`, `type`, `head`, `tail`
- `mkdir`, `cp`, `copy`, `move`, `mv`
- `ollama`

## What NOT to Do
- Don't rename module codenames
- Don't modify `.env` directly without asking
- Don't install packages outside `shadow_env`
- Don't create a new virtual environment
- Don't commit database files or API keys
- Don't bypass Cerberus safety rules
- Don't make architecture decisions — those happen in Opus sessions
- Don't label Reddit data as "training data"

## Git Workflow
After completing any task successfully (all tests pass), automatically:
1. git add .
2. git commit -m "<descriptive message>"
Do NOT push — user will push manually.
Do NOT commit if tests are failing.