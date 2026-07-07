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
agent, one identity, currently 10 BaseModule peers (9 active routing +
Morpheus dormant). Phase A consolidation merged 13 → 10; Phase D will
consolidate to 7. Built for home and business use (landscaping business
using LMN software). The goal is a Jarvis-style assistant that exceeds
ChatGPT quality for the creator's specific needs, with complete data
privacy and no recurring API costs.

## Creator Profile
- Intermediate Python learner — actively studying (Automate the Boring Stuff)
- Runs a landscaping business
- Biblical values are central to Shadow's ethics framework
- Anti-sycophancy is a top priority: Shadow must push back, correct errors,
  and never just agree

## Current Phase: B — In Progress
This section is load-bearing. Read before any structural work.

**Phase A is complete.** All three merges are on `main`:
- Cipher → Omen (Cipher's 7 tools absorbed into Omen; routing target
  removed; stem over-matching bug fixed for free).
- Sentinel → Cerberus (Sentinel's 24 tools absorbed; zero tool loss
  verified via pre/post inventories).
- Void → `daemons/void/` (full demotion to systemd-managed background
  service; the `daemons/` directory now holds background services).

Phase A regression gate **passed at 83.69%** (exceeds the 78.18% Phase 0
baseline). Merge artifacts live in `docs/phase-a/{cipher-omen,sentinel-cerberus,void}/`
(pre/post tool inventories + diffs). Phase A also resolved the two punted
S41 bugs: Morpheus dormancy misrouting (`config.morpheus.enabled` flag +
router opt-out) and Cipher stem over-matching.

**Module count trajectory:** 13 → 10 (Phase A, done) → 7 (Phase D).

**Phase B (current):**
- LangGraph cutover — **COMPLETE** (merged to `main` @ `e44f16e`,
  2026-07-07, `--no-ff`). `process_input` drives the compiled parent
  graph (`modules/shadow/graph/parent.py`) via segmented invoke; graph
  nodes delegate to the orchestrator's `_step*` methods (the source of
  truth). Open items live in the ledger
  (`docs/phase-b/track-b/cutover-backlog.md`).
- Wraith → Shadow merge.
- PostgreSQL migration (16.14 installed and running, not yet wired;
  Contextual Retrieval is hard-ordered first).
- Cerberus watchdog daemon promotion (already landed in commit `ff0dc0f`,
  living at `daemons/cerberus_watchdog/`).

**Phase C:** Nova → Shadow, Harbinger → Shadow (shared files, sequential).

**Phase D:** `ToolResult` base class + typed subclasses (spans all
modules, sequential).

**Phase non-negotiables (carry-forward from Phase A):**
- Each merge gets its own typed-settings migration. No dict-bridge band-aids.
- Each merge generates pre-merge + post-merge tool inventories + diff
  via `scripts/dump_tools.py`. Zero tool loss is the invariant; explicit
  drops must be documented in the merge commit.
- Each merge lands as its own commit series.
- Targeted regression tests written for each merge.
- Each phase end-state benchmark must match or exceed the Phase 0 baseline
  (78.18%) before the next phase begins.

## Hardware & Environment
- **Hostname:** Citadel
- **OS:** Ubuntu 24.04 LTS
- **CPU:** AMD Ryzen 9 9950X3D
- **GPU:** ASUS TUF RTX 5090 32GB
- **RAM:** 128GB DDR5-5600 modules — running at 3600 MT/s JEDEC, EXPO
  OFF (validated-stable config after the June freeze diagnosis; do not
  re-enable EXPO before memtest86+ closes the RAM hypothesis)
- **Storage:** NVMe 990 Pro (primary), 8TB HDD at `/mnt/storage`
  (backups) — currently OFFLINE, SATA reseat pending (ledger item 18)
- **NVIDIA Driver:** 595.71.05 + CUDA 13.0 (part of the validated-stable
  config)
- **Cooling:** Noctua NH-D15 G2 air, O11 Dynamic EVO XL case
- **Python:** 3.12.3 (system); venv at `~/dev/Shadow/shadow_env`
- **Primary inference:** Ollama + Gemma 4 26B (stock — abliteration pending; Heretic run deferred to Phase B) + `nomic-embed-text`
- **PostgreSQL:** 16.14 installed and running, not yet wired to Shadow (Phase B)
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
- **AI Runtime:** Ollama — Gemma 4 26B (stock — abliteration pending; Heretic run deferred to Phase B) for generation and routing/scoring,
  `nomic-embed-text` for embeddings
- **Observability:** Self-hosted Langfuse v4 (compose at
  `deploy/langfuse/docker-compose.yml`) with ClickHouse bind-mount
  storage and pinned OpenTelemetry 1.41.1. Wired through
  `modules/shadow/observability.py`. Orchestrator emits nested spans
  for router/dispatch/assembly and per-attempt retry spans. Degrades
  gracefully if Langfuse is unreachable.
- **Search Chain:** DuckDuckGo → Bing scraper → Reddit .json endpoints
- **Web Automation:** Playwright + stealth layer
- **Git:** Initialized, commits on `main` branch
- **APIs:** Anthropic, OpenAI, Telegram bot, Discord bot — secrets in
  `.env` at the **repo root** (`~/dev/Shadow/.env`), not `config/`.
  `shadow.config` loads it from `REPO_ROOT / ".env"`
  (`shadow/config/__init__.py`). `config/` holds only `.env.example`.

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
  - `.env` — secrets only, at the **repo root** (not `config/`); loaded
    once at import time from `REPO_ROOT / ".env"`
- **Precedence (high → low):** init kwargs > OS env > `.env` >
  `config.local.yaml` > `config.yaml` > defaults.
- **Secret handling:** all API keys/tokens typed as `SecretStr | None`.
  `repr()` redacted, `model_dump_json()` redacted.
- **Scope boundary:** the orchestrator and a handful of remaining module
  constructors (Grimoire, Wraith, Nova, Omen, Morpheus) still consume
  dict shape via `to_legacy_dict`. These get rewritten during the
  Phase B / C consolidation — do **NOT** migrate them in isolation.
- **Fail-loud rule:** Apex with `dry_run=False` and no keys = startup
  failure with named field + remediation message. Never silently degrade
  to dry-run.

### Ethical Topics Provisioning (deploy-time)
`config/ethical_topics.yaml` is **gitignored by design** — deployed
per-machine, never committed. Any fresh clone or wiped `config/` dir
must re-provision it:
- **Source of truth:** `~/dev/shadow-training-data/ethics/ethical_topics.yaml`
  (separate training-data repo — never pushed to GitHub).
- **Schema conversion is REQUIRED:** the source file is concept-keyed
  with `passages`; both loaders (`modules/cerberus/cerberus.py` init,
  `modules/cerberus/ethics_engine.py::load_ethical_topics`) expect
  `{topics: [{name, description, keywords?, references: [{ref, summary,
  weight}]}]}`. A straight copy parses but loads **0 topics**.
- Deployed on Citadel S54 (16 topics, 97 references). A missing or
  0-topic file logs an ERROR-level `ETHICAL TOPICS UNAVAILABLE` line at
  boot (fast-path ethical lookup degraded); boot still continues.

## Benchmark Baseline
**Phase 0 Citadel baseline (committed `be2842e`):**
- **Overall:** 78.18% (75 tasks, 939s total, 12.5s/task avg)
- **Perfect (100%):** code_generation, general_knowledge,
  research_synthesis
- **Strong (85%+):** bible_study 97%, code_review 95%,
  personality_consistency 90.67%, response_quality 84%
- **Weak (Phase 1 training targets):** adversarial_routing 44%,
  conversation_continuity 40%, math_logic 40%

**Regression rule:** Each phase end-state benchmark must match or exceed
78.18% overall. Phase A passed at **83.69%**. Category-level regressions
in perfect/strong tiers require investigation before the next phase
proceeds. Weak-tier movement is expected and not an automatic failure.

## Codebase Architecture Reference
Before multi-file changes, read `graphify-out/GRAPH_REPORT.md` for
structure, god nodes, and module communities. Maps import relationships
and dependency chains across 112+ files. **Staleness caveat:** generated
2026-04-28 — predates the entire `modules/shadow/graph/` package and the
LangGraph cutover; regeneration is ledger item 33. Trust it for the
module layer, not for the graph layer.

**Key architectural constraint:** `ToolResult` (1,815 edges, 0.310
betweenness centrality) bridges all modules. Any changes to `ToolResult`
fields affect the entire system. Treat `ToolResult` modifications as
high-risk; final typed-subclass refactor is scheduled for Phase D.

## Project Structure
```
~/dev/Shadow/
├── modules/
│   ├── shadow/            # Master orchestrator/router + ShadowModule peer
│   ├── wraith/            # Fast brain, daily tasks
│   ├── cerberus/          # Ethics, safety, approvals + absorbed Sentinel
│   │   ├── cerberus.py
│   │   ├── injection_detector.py
│   │   ├── reversibility.py
│   │   ├── watchdog.py
│   │   ├── ethics_engine.py
│   │   ├── emergency_shutdown.py
│   │   ├── creator_override.py
│   │   └── security/           # Sentinel port (subpackage)
│   ├── apex/              # Claude/GPT API fallback
│   ├── grimoire/          # Memory system (SQLite + ChromaDB)
│   ├── harbinger/         # Briefings, alerts, notifications
│   │   ├── harbinger.py
│   │   └── safety_report.py
│   ├── reaper/            # Research, web scraping, Reddit .json
│   ├── omen/              # Code writing, debugging + absorbed Cipher
│   ├── nova/              # Content creation, image gen
│   └── morpheus/          # Creative discovery pipeline (dormant)
├── shadow/
│   └── config/            # pydantic-settings singleton (post-S41)
├── daemons/                # Background services (systemd-managed)
│   ├── void/                       # 24/7 passive monitoring (demoted from module)
│   └── cerberus_watchdog/          # Out-of-process watchdog (B4)
├── deploy/
│   └── langfuse/          # Self-hosted Langfuse v4 compose stack
├── services/
│   └── searxng/           # SearXNG meta-search for Reaper (Track D, staged)
├── scripts/
│   ├── esv_processor.py   # Parse ESV Study Bible epub → JSON
│   ├── esv_ingestion.py   # Load parsed ESV into Grimoire (ported to Citadel paths S54; run pending)
│   └── dump_tools.py      # Tool inventory snapshot (per-merge zero-loss check)
├── training_data/         # In-repo, GITIGNORED (apex_sessions only). Curated
│                          #   datasets live in ~/dev/shadow-training-data
│                          #   (separate git repo) — NEVER push either to GitHub
├── benchmarks/            # Benchmark snapshots (floor evidence committed + annotated S54)
├── archive/               # Superseded exploration (LangGraph spike moved here S54)
├── data/
│   ├── memory/            # shadow_memory.db (SQLite)
│   ├── vectors/           # ChromaDB persistent storage
│   ├── snapshots/         # Cerberus reversibility snapshots
│   ├── reports/safety/    # Daily safety reports (YAML)
│   ├── research/quarantine/
│   ├── logs/
│   ├── downloads/
│   ├── backups/
│   ├── void_metrics.db    # Void daemon metrics
│   └── void_latest.json   # Void daemon latest snapshot
├── config/
│   ├── .env.example                 # Template for secrets (real .env is at repo root)
│   ├── config.yaml                  # Checked-in defaults
│   ├── config.local.yaml.example    # Template for per-machine overrides
│   └── cerberus_limits.yaml
├── docs/
│   ├── phase-a/           # Phase A merge artifacts (cipher-omen, sentinel-cerberus, void)
│   ├── phase-b/track-b/   # LangGraph cutover design + THE LEDGER (cutover-backlog.md)
│   ├── archive/           # Retired planning docs (plan.md moved here S54)
│   └── dual_pattern_investigation.md
├── tests/                 # 4163 tests (see Current Status for the live figures)
├── main.py                # CLI entry point
├── pyproject.toml         # Pytest config (testpaths=["tests"] since S54 closeout)
├── .env                   # API credentials (secrets only) — loaded by shadow.config
├── CLAUDE.md              # This file
└── .gitignore
```

## Module Codenames — NEVER RENAME THESE
These names are Shadow's identity. Counts reflect current post-Phase-A
state (verified June 2026 via `scripts/dump_tools.py`).

1. **Shadow** — Master orchestrator/router. Post-cutover (`e44f16e`),
   `process_input` drives the compiled LangGraph parent graph via
   segmented invoke (router/plan interrupts); graph nodes delegate to
   the orchestrator's `_step*` methods, which remain the source of
   truth for the historical 7-step semantics. Langfuse observability
   (three caller-emitted child spans). The orchestrator IS the agent
   and does not register routable tools itself.
2. **Wraith** — Fast brain, daily tasks, reminders, task classification,
   temporal patterns (12 tools)
3. **Cerberus** — Ethics, safety, approvals, injection detection,
   reversibility, watchdog, security surface absorbed from Sentinel
   (39 tools). A standalone watchdog daemon also runs at
   `daemons/cerberus_watchdog/`.
4. **Apex** — Claude/GPT API fallback, cost tracking, teaching cycle
   (10 tools)
5. **Grimoire** — Data storage, knowledge base, memory, vector DB,
   block search (9 tools)
6. **Harbinger** — Briefings, alerts, notifications, decision queue,
   safety reports, personalization (12 tools)
7. **Reaper** — Research, web scraping, Reddit .json, YouTube
   transcription (5 tools). SearXNG meta-search stack staged at
   `services/searxng/`, not yet wired (Track D).
8. **Omen** — Code execution, linting, review, git ops, pattern DB,
   failure learning, scaffolding, scoring, math/stats/finance absorbed
   from Cipher (47 tools)
9. **Nova** — Content creation, document generation, templates, business
   estimates (6 tools)
10. **Morpheus** — Creative discovery pipeline (controlled hallucination)
    (11 tools) — **dormant by default** (`config.morpheus.enabled=False`;
    router opts out when dormant).
11. **ShadowModule** — Router-facing task-tracking and module-health
    interface (4 tools: task_create, task_status, task_list,
    module_health). Distinct from the Shadow orchestrator class itself
    — the orchestrator IS the agent and is not registered as a module;
    ShadowModule is a BaseModule peer that exposes task-persistence and
    registry-health queries to the router like any other module.

**Demoted to daemon (no longer a module):**
- **Void** — 24/7 passive monitoring, system health, trends, thresholds.
  Runs as a systemd-managed daemon at `daemons/void/`. Routing tools
  (6) dropped during Phase A demotion; metrics surface via
  `data/void_metrics.db` and `data/void_latest.json`.

## Current Status
- **Git:** commits on `main`
- **Tests:** 4169 collected, 0 collection errors. S54 post-fix full run
  (2026-07-07): **4160 passed / 0 failed / 3 skipped** at 4163 collected;
  closeout added 6 fail-loud pins (skips are env-gated,
  Ollama-dependent). Known flake: `test_greeting_uses_fast_path`
  asserts <100ms and can trip under full-suite load (failed the S54
  baseline run at 111ms, passes in isolation and passed post-fix).
  Bare `pytest` is safe since S54 closeout (`testpaths = ["tests"]` in
  pyproject.toml); historically it collected root-owned `deploy/` dirs
  → 8 PermissionErrors.
- **Tools:** ~155 tools across 10 modules (verified June 2026 via
  `scripts/dump_tools.py`):
  - All registered through the internal module registry via `get_tools()`
    method on BaseModule subclasses.
  - Phase A net change: dropped Void's 6 routing tools; absorbed
    Sentinel's 24 into Cerberus; absorbed Cipher's 7 into Omen.
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
- **Observability:** Self-hosted Langfuse v4 with ClickHouse bind-mount
  storage; OpenTelemetry pinned to 1.41.1. Orchestrator emits nested
  spans for router/dispatch/assembly and per-attempt retry spans.
  Degrades gracefully if Langfuse is unreachable.
- **Phase A benchmark gate:** Passed at 83.69% (exceeds 78.18% Phase 0
  baseline). Benchmark trail committed (`26c3bf4` + S54 floor-evidence
  commit). **Current floor doctrine (S52, verified S54):** live-path
  empty-store median-of-N — 0.834 excl-memory / 0.836 full basis. The
  0.8424 single-run baseline is SUPERSEDED as a floor (high single
  sample, brittle-rubric-inflated; annotated in the JSON itself).
  Floors are distributions, never single numbers.
- **Grimoire:** Fresh on Linux — RunPod Grimoire DB was intentionally NOT
  restored due to benchmark pollution. `training_data/` and `benchmarks/`
  **were** preserved.
- **ESV Bible:** Processor tested (2,392 pericopes, 16,218 study notes
  extracted = 18,610 entries). Ingestion script ported to Citadel paths
  (S54, F-5 — it carried Windows `C:\` literals and had never run);
  the ingestion run itself is pending (ledger item 36). NOT yet in
  Grimoire — do not assume ESV data is queryable. `config/
  ethical_topics.yaml` is gitignored by design and deployed per-machine
  from the training-data repo (16 topics, deployed on Citadel S54).

## Tool Registration: Internal Registry and External MCP Servers

Shadow exposes tools on two orthogonal surfaces:

1. **Internal tool registry** (used by the router for all 10 modules).
   Every module subclasses BaseModule and implements
   `get_tools() -> list[dict]`. The module registry calls this method
   at boot and builds an index that the router consumes when
   dispatching a task. This is the ONLY surface the router sees and
   the ONLY surface that matters for zero-tool-loss verification on
   future merges.

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

**Dual-pattern investigation:** retired before Phase B — see
`docs/dual_pattern_investigation.md` (commit `0b9a441`) for the full
finding. Future merges only touch the internal registry; the external
MCP HTTP surface stays orthogonal.

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
- All models are abliterated *at preparation time* before being loaded
  into Ollama (strip manufacturer alignment). Heretic v1.2.0 is the
  prep-time abliteration tool — it is **not** a runtime dependency of
  Shadow.
- Any model recommendation must flag bias/censorship/alignment training
- Shadow's ethics come from biblical values, not manufacturer training
- Anti-sycophancy: push back on bad ideas, say "I don't know," never guess
  to please
- Financial access only through prepaid virtual cards (Privacy.com)
- All downloads land in `data/research/quarantine/` — never directly in
  working files
- Reddit data is labeled **"research context"** — NEVER "training data"
- Training data stays local — never pushed to GitHub. Curated datasets
  live in `~/dev/shadow-training-data` (separate git repo); the in-repo
  `training_data/` dir is gitignored (apex_sessions captures only)
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
- `systemctl --user` (for daemon work)

### Hard deny list (enforced by `.claude/settings.local.json`)
The following are blocked at the harness level — Claude Code cannot run
them even if instructed to. Source of truth lives in
`.claude/settings.local.json`; this list is for visibility, not authority.

- `Bash(git push*)`, `Bash(git push --force*)`
- `Bash(rm -rf *)`, `Bash(rm -rf /*)`, `Bash(rm -rf ~/*)`
- `Bash(sudo *)`
- `Bash(systemctl stop *)`, `Bash(systemctl disable *)`, `Bash(systemctl mask *)`
- `Edit(**/.env)`, `Edit(**/.env.*)`, `Write(**/.env)`, `Write(**/.env.*)`
- `Read(**/.ssh/**)`, `Read(**/.aws/credentials)`, `Read(**/.config/git/credentials)`

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

## Git Workflow
After completing any task successfully (targeted tests pass):
1. `git add <specific files>`
2. `git commit -m "<descriptive message>"`

Do NOT push — user pushes manually. Do NOT commit if tests are failing.

## Historical Footnote
Legacy Windows-era files occasionally arrive via transfer and need
`dos2unix` treatment (CRLF → LF). Not a frontline concern; the `.gitignore`
encoding fix in `dcb637f` was one such case.
