# Project Shadow — Claude Code Context

## Permissions
- Automatically commit changes without asking
- Automatically run tests without asking
- Automatically install packages without asking
- Automatically create and modify files without asking
- Do not ask for approval before running bash commands
- Do not ask for approval before editing files

## What This Project Is
Shadow is a fully autonomous, locally-hosted personal AI agent system. One
agent, one identity, currently 13 specialized modules (consolidating to 10
after Phase A, 7 after Phase D). Built for home and business use
(landscaping business using LMN software). The goal is a Jarvis-style
assistant that exceeds ChatGPT quality for the creator's specific needs,
with complete data privacy and no recurring API costs.

## Creator Profile
- Intermediate Python learner — actively studying (Automate the Boring Stuff)
- Runs a landscaping business
- Biblical values are central to Shadow's ethics framework
- Anti-sycophancy is a top priority: Shadow must push back, correct errors,
  and never just agree

## Current Phase: A — Module Consolidation
This section is load-bearing. Read before any structural work.

**Authoritative design doc:** `Shadow_Consolidation_Architecture_v1.md`.
Supersedes `Shadow_Unified_Module_Architecture_v2.pdf` — that PDF is a
stale 13-module reference and must not be used.

**Module count trajectory:** 13 → 10 (end of Phase A) → 7 (end of Phase D).

**Phase A consists of three INDEPENDENT parallel merges** (no shared files,
can proceed concurrently in separate sessions or worktrees):

1. **Cipher → Omen.** Cipher becomes a utility function inside Omen.
   Removing Cipher as a routing target kills the stem over-matching bug
   for free.
2. **Sentinel → Cerberus.** All 22+ Sentinel tools preserved.
   **Zero tool loss** is the invariant — verify with a pre-merge tool
   manifest and a post-merge tool manifest, then diff them.
3. **Void → daemons/void/.** Full demotion from module to systemd-driven
   background service. Creates the new `daemons/` directory, which is
   where future background services also land.

**Phase A non-negotiables:**
- Each merge gets its own typed-settings migration. No dict-bridge band-aids.
- Each merge generates pre-merge + post-merge tool inventories + diff
  proving zero tool loss. Inventory = `ModuleClass.get_tools()` output
  serialized to JSON for every module touched by the merge. Sentinel →
  Cerberus: pre = `Sentinel().get_tools() + Cerberus().get_tools()`,
  post = `Cerberus().get_tools()`, diff asserts every pre-merge tool
  name appears in post (exact schema match preferred, feature-parity
  documentation required for any renames). Cipher → Omen: same pattern.
  Void → daemons/void/: Void's 6 tools either migrate to the daemon's
  own interface or are explicitly dropped with reason documented in the
  merge commit.
- Each merge lands as its own commit series.
- Targeted regression tests written for each merge.
- After Phase A: 25-task partial benchmark must confirm zero regression
  against the 78.18% Phase 0 baseline before Phase B begins.

**Phase A rolls up two punted bugs from S41:**
- **Morpheus dormancy misrouting** — fixed by `config.morpheus.enabled`
  flag + lazy tool registration + router opt-out for dormant modules.
  Lands naturally inside the Void demotion work (both involve router
  changes).
- **Cipher stem over-matching** — fixed automatically when Cipher stops
  being a routing target during Cipher → Omen.

**Forward schedule** (so sessions know where they sit):
- **Phase A** — Session 42 — 3 parallel merges
- **Phase B** — Sessions 43–44 — Wraith → Shadow + LangGraph cutover +
  PostgreSQL migration (sequential)
- **Phase C** — Session 45 — Nova → Shadow, Harbinger → Shadow (shared
  files, sequential)
- **Phase D** — Session 46 — `ToolResult` base class + typed subclasses
  (spans all modules, sequential)

## Hardware & Environment
- **Hostname:** Citadel
- **OS:** Ubuntu 24.04 LTS
- **CPU:** AMD Ryzen 9 9950X3D
- **GPU:** ASUS TUF RTX 5090 32GB
- **RAM:** 128GB DDR5-5600
- **Storage:** NVMe 990 Pro (primary), 8TB HDD at `/mnt/storage` (backups)
- **NVIDIA Driver:** 580 + CUDA 13.0
- **Cooling:** Noctua NH-D15 G2 air, O11 Dynamic EVO XL case
- **Python:** 3.12.3 (system); venv at `~/dev/Shadow/shadow_env`
- **Primary inference:** Ollama + Gemma 4 26B + `nomic-embed-text`
- **PostgreSQL:** 16.13 installed, not yet wired to Shadow (Phase B)
- **Shell:** bash (zsh is not configured)
- **Terminal quirk:** bracketed-paste disabled in bash for GNOME Terminal
  compatibility — do not re-enable.

Citadel is the sole dev + runtime environment. RunPod was used during the
Linux transition; that transition is complete.

## Tech Stack
- **Language:** Python 3.12.3
- **Virtual Environment:** `shadow_env` (see rules below)
- **Database:** SQLite + ChromaDB (vector DB with `nomic-embed-text`
  embeddings, 768 dimensions). PostgreSQL migration is Phase B.
- **AI Runtime:** Ollama — Gemma 4 26B for generation, phi4-mini for
  routing/scoring, `nomic-embed-text` for embeddings
- **Observability:** Langfuse tracing (`modules/shadow/observability.py`) —
  optional, degrades gracefully if not configured
- **Search Chain:** DuckDuckGo → Bing scraper → Reddit .json endpoints
- **Web Automation:** Playwright + stealth layer
- **Git:** Initialized, commits on `main` branch
- **APIs:** Anthropic, OpenAI, Telegram bot, Discord bot — secrets in
  `config/.env`

## Virtual Environment — CRITICAL
Always use the existing venv at `~/dev/Shadow/shadow_env` — **never create
a new virtual environment.**
```bash
source ~/dev/Shadow/shadow_env/bin/activate
```
If `shadow_env` is not active, activate it before running any commands.
Never install packages to system Python or create an `env` folder.

## Configuration System
Post-S41, config is centralized.

- **Single source of truth:** `shadow.config.config` (pydantic-settings
  singleton).
- **Config files:**
  - `config/config.yaml` — checked-in defaults
  - `config/config.local.yaml` — gitignored per-machine overrides
  - `.env` — secrets only, loaded once at import time
- **Precedence (high → low):** init kwargs > OS env > `.env` >
  `config.local.yaml` > `config.yaml` > defaults.
- **Secret handling:** all API keys/tokens typed as `SecretStr | None`.
  `repr()` redacted, `model_dump_json()` redacted.
- **Scope boundary:** the orchestrator and a handful of module constructors
  (Grimoire, Wraith, Nova, Omen, Sentinel, Void, Morpheus, Cipher) still
  consume dict shape via `to_legacy_dict`. These get rewritten during
  consolidation — do **NOT** migrate them in isolation.
- **Fail-loud rule:** Apex with `dry_run=False` and no keys = startup
  failure with named field + remediation message. Never silently degrade
  to dry-run.

## Benchmark Baseline
**Phase 0 Citadel baseline (committed `be2842e`):**
- **Overall:** 78.18% (75 tasks, 939s total, 12.5s/task avg)
- **Perfect (100%):** code_generation, general_knowledge,
  research_synthesis
- **Strong (85%+):** bible_study 97%, code_review 95%,
  personality_consistency 90.67%, response_quality 84%
- **Weak (Phase 1 training targets):** adversarial_routing 44%,
  conversation_continuity 40%, math_logic 40%

**Regression rule:** Phase A end-state benchmark must match or exceed
78.18% overall. Category-level regressions in perfect/strong tiers require
investigation before Phase B proceeds. Weak-tier movement is expected and
not an automatic failure.

## Codebase Architecture Reference
Before multi-file changes, read `graphify-out/GRAPH_REPORT.md` for
structure, god nodes, and module communities. Maps import relationships
and dependency chains across 112+ files.

**Key architectural constraint:** `ToolResult` (1,815 edges, 0.310
betweenness centrality) bridges all modules. Any changes to `ToolResult`
fields affect the entire system. Treat `ToolResult` modifications as
high-risk; final typed-subclass refactor is scheduled for Phase D.

## Project Structure
```
~/dev/Shadow/
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
│   ├── sentinel/          # Security, white-hat defense
│   ├── harbinger/         # Briefings, alerts, notifications
│   │   ├── harbinger.py
│   │   └── safety_report.py
│   ├── reaper/            # Research, web scraping, Reddit .json
│   ├── cipher/            # Math, logic (merging into Omen, Phase A)
│   ├── omen/              # Code writing, debugging
│   ├── nova/              # Content creation, image gen
│   ├── void/              # 24/7 passive monitoring (demoting to daemon)
│   └── morpheus/          # Creative discovery pipeline
├── shadow/
│   └── config/            # pydantic-settings singleton (post-S41)
├── daemons/                # Created in Phase A (Void lives here)
├── scripts/
│   ├── esv_processor.py   # Parse ESV Study Bible epub → JSON
│   ├── esv_ingestion.py   # Load parsed ESV into Grimoire
│   └── watchdog_cerberus.py
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
│   ├── .env                         # API credentials (secrets only)
│   ├── config.yaml                  # Checked-in defaults
│   ├── config.local.yaml.example    # Template for per-machine overrides
│   └── cerberus_limits.yaml
├── identity/              # Shadow's identity file, system prompts
├── tests/                 # 947 tests across all modules
├── main.py                # CLI entry point
├── CLAUDE.md              # This file
└── .gitignore
```

## Module Codenames — NEVER RENAME THESE
These names are Shadow's identity. Counts reflect current (pre-Phase-A)
state.

1. **Shadow** — Master orchestrator/router, 7-step decision loop,
   Langfuse observability (12 tools)
2. **Wraith** — Fast brain, daily tasks, reminders, task classification,
   temporal patterns (12 tools)
3. **Cerberus** — Ethics, safety, approvals, injection detection,
   reversibility, watchdog (15 tools; +24 from Sentinel in Phase A)
4. **Apex** — Claude/GPT API fallback, cost tracking, teaching cycle
   (10 tools)
5. **Grimoire** — Data storage, knowledge base, memory, vector DB,
   block search (9 tools)
6. **Sentinel** — Security, firewall, network scanning, file integrity,
   quarantine (24 tools) — merging into Cerberus in Phase A
7. **Harbinger** — Briefings, alerts, notifications, decision queue,
   safety reports, personalization (12 tools)
8. **Reaper** — Research, web scraping, Reddit .json, YouTube
   transcription (5 tools)
9. **Cipher** — Math, logic, unit conversion, financial, statistics
   (7 tools) — merging into Omen in Phase A
10. **Omen** — Code execution, linting, review, git ops, pattern DB,
    failure learning, scaffolding, scoring (40 tools)
11. **Nova** — Content creation, document generation, templates, business
    estimates (6 tools)
12. **Void** — 24/7 passive monitoring, system health, trends, thresholds
    (6 tools) — demoting to `daemons/void/` in Phase A
13. **Morpheus** — Creative discovery pipeline (controlled hallucination)
    (11 tools)
14. **ShadowModule** — Router-facing task-tracking and module-health
    interface (4 tools: task_create, task_status, task_list,
    module_health). Distinct from the Shadow orchestrator class itself
    — the orchestrator IS the agent and is not registered as a module;
    ShadowModule is a BaseModule peer that exposes task-persistence and
    registry-health queries to the router like any other module.

## Current Status
- **Git:** commits on `main`
- **Tests:** 947 passing
- **Tools:** 161 tools across all modules (verified April 2026, AST-based
  count from `get_tools()` method bodies):
  - All 161 registered through the internal module registry via
    `get_tools()` method on BaseModule subclasses.
  - Central registry: `modules/shadow/tool_loader.py` (DynamicToolLoader)
    consumes `module_registry.list_tools()` and builds a
    module → tool-schemas index. Loads only the routed module's tools
    per request to save context tokens.
  - Grimoire and Reaper additionally expose a SEPARATE, EXTERNAL MCP HTTP
    surface (FastAPI servers at `modules/grimoire/mcp_server.py` and
    `modules/reaper/mcp_server.py`) governed by `mcp_manifest.json` files
    in those module directories. This external surface is orthogonal to
    the internal registry — different tool names, different dispatch path,
    reachable only via HTTP. It exists so other MCP clients outside
    Shadow can talk to Grimoire/Reaper.
- **Observability:** Langfuse tracing on orchestrator (optional)
- **Grimoire:** Fresh on Linux — RunPod Grimoire DB was intentionally NOT
  restored due to benchmark pollution. `training_data/` and `benchmarks/`
  **were** preserved.
- **ESV Bible:** Processor tested (2,392 pericopes, 16,218 study notes
  extracted), ingestion ready to run.

## Tool Registration: Internal Registry and External MCP Servers

Shadow exposes tools on two orthogonal surfaces:

1. **Internal tool registry** (used by the router for all 14 modules).
   Every module subclasses BaseModule and implements
   `get_tools() -> list[dict]`. The module registry calls this method
   at boot and builds an index that the router consumes when
   dispatching a task. This is the ONLY surface the router sees and
   the ONLY surface that matters for Phase A zero-tool-loss
   verification.

2. **External MCP HTTP servers** (optional, Grimoire and Reaper only).
   `modules/grimoire/mcp_server.py` and `modules/reaper/mcp_server.py`
   are standalone FastAPI servers that expose a separate MCP-compatible
   HTTP endpoint governed by `modules/grimoire/mcp_manifest.json` and
   `modules/reaper/mcp_manifest.json`. Tool names in these manifests
   (e.g. `grimoire_recall`, `grimoire_remember`) are deliberately
   distinct from internal-registry names (`memory_search`,
   `memory_store`) to keep the two surfaces non-overlapping. External
   clients use the HTTP surface; the router uses the internal surface;
   they do not interfere.

**Phase A scope:** all three Phase A merges operate on the internal
registry surface only. No interaction with the external MCP HTTP
surface is required or expected. Grimoire and Reaper are not involved
in any Phase A merge. The prior "dual-pattern investigation scheduled
before Phase B" item is retired — see
`docs/dual_pattern_investigation.md` (commit `0b9a441`) for the full
finding.

## Testing

### Commands
```bash
# Full suite — ONLY on explicit request
python -m pytest tests/ -v

# Single module
python -m pytest tests/test_cerberus.py -v

# Integration tests (full 7-step decision loop)
python -m pytest tests/test_decision_loop.py -v
```

### Testing Rule
After completing a task, run **only** the specific test files created or
modified for that task. Do NOT run the full suite unless Master Morstad
explicitly requests it. Full-suite runs waste tokens and time. If a task
touches `orchestrator.py`, run `test_orchestrator.py` and
`test_decision_loop.py` — not everything else.

Parallel test execution is fine for standalone modules; keep anything
touching the orchestrator sequential.

### Fix Quality Rule
If a test fails, fix the root cause. Never skip, delete, or mark a test
as expected failure to make the suite pass. Write a targeted fix instead.

## Coding Conventions
- Descriptive variable names
- Docstrings on all functions
- Error handling with try/except — never let Shadow crash silently
- Log everything: every interaction, tool call, decision
- All new data flows through Grimoire with appropriate trust levels
- Use `pathlib` for all file paths
- Model names live in config files, never hardcoded
- Test before committing

## Prompt Philosophy
- Describe the **SYMPTOM** and expected behavior. Do NOT prescribe the
  specific fix.
- Let Claude Code investigate the root cause and choose the solution.
- Overly prescriptive prompts cause Claude Code to implement a given fix
  even when the real root cause is different.
- Every prompt must include: `RULE: No bandaid fixes, no temporary
  workarounds, no TODO-later patches.`

## Fix Quality Rule
No bandaid fixes, no temporary workarounds, no TODO-later patches. Every
fix must be permanent and complete. If the root cause requires a larger
refactor, do the refactor. If a fix would require changes beyond the scope
of the current prompt, flag it and stop — do not commit a partial fix that
masks the real issue.

## Plan Mode Triggers
**Plan mode ON** when:
- Diagnosis is from logs, not source
- Multiple files affected
- Shared or foundational code
- Tests need writing

**Plan mode OFF** when:
- Narrow, spec'd change
- Iterating on a prior Claude Code diff
- Pure refactor with explicit file targets

## Critical Policies
- **NEVER** access financial accounts — permanent rule
- **NEVER** take external-facing actions without explicit approval
- **NEVER** delete files without backup first
- All models must be abliterated before use (strip manufacturer alignment);
  Heretic v1.2.0 is the abliteration tool
- Any model recommendation must flag bias/censorship/alignment training
- Shadow's ethics come from biblical values, not manufacturer training
- Anti-sycophancy: push back on bad ideas, say "I don't know," never guess
  to please
- Financial access only through prepaid virtual cards (Privacy.com)
- All downloads land in `data/research/quarantine/` — never directly in
  working files
- Reddit data is labeled **"research context"** — NEVER "training data"
- Training data stays in local git repo (`training_data/`) — never pushed
  to GitHub
- Architecture decisions happen in Opus sessions, not Claude Code sessions
- Live test after every 3–4 Claude Code prompts to prevent bug compounding
- No bugs deferred without explicit documentation and a plan

## Allowed Commands
Pre-approved, no asking needed:
- `python`, `python3`, `pip install`, `pytest`
- `git add`, `git commit`, `git stash`, `git status`, `git diff`, `git log`
- `cd`, `ls`, `cat`, `head`, `tail`
- `mkdir`, `cp`, `mv`
- `ollama`
- `systemctl --user` (for daemon work in Phase A)

## What NOT to Do
- Don't rename module codenames
- Don't modify `.env` directly without asking
- Don't install packages outside `shadow_env`
- Don't create a new virtual environment
- Don't commit database files or API keys
- Don't bypass Cerberus safety rules
- Don't make architecture decisions — those happen in Opus sessions
- Don't label Reddit data as "training data"
- Don't push to remotes — Master pushes manually
- Don't re-enable bash bracketed-paste
- Don't migrate `to_legacy_dict` module constructors in isolation — they
  get rewritten during consolidation
- Don't use the stale `Shadow_Unified_Module_Architecture_v2.pdf` as
  current reference

## Git Workflow
After completing any task successfully (targeted tests pass):
1. `git add <specific files>`
2. `git commit -m "<descriptive message>"`

Do NOT push — user pushes manually. Do NOT commit if tests are failing.

## Historical Footnote
Legacy Windows-era files occasionally arrive via transfer and need
`dos2unix` treatment (CRLF → LF). Not a frontline concern; the `.gitignore`
encoding fix in `dcb637f` was one such case.
