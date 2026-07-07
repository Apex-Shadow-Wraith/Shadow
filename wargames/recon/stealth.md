# RECON DIGEST — Reaper (instance: "stealth")

**Mode:** Independent recon for the Reaper mission, run as a SEPARATE instance
per Master (2026-07-07). Phases 0–1 complete.
**Standard loaded:** `wargames/SUCCESS.md` (nine points).
**Brief:** `wargames/tasks/reaper.md` (the only Reaper artifact this instance used).
**Isolation note:** This instance was told to keep its data separate from the
other Reaper run. Products are named `stealth*`. Honesty flag: one file of the
other instance's work — `wargames/recon/reaper.md` — was read once before the
isolation instruction landed; nothing else from that instance (no plans, no
red-team, no ledger) was read. Every fact below was re-traced from the code
directly with `file:line`, not carried from that digest.
**Rule of this digest:** every code claim carries `file:line`. Counts verified
by running, not by grepping a `def test_` integer. Host facts settled by
running read-only checks, never guessed.

---

## 0. Headline (the finding that reshapes the plan)

**The Front-5 Tier-2 gate the brief says must be "dormant until the injection
mitigations are live" ships OPEN today, and there are TWO ungated high-trust
injection write paths, not one.**

1. **The scheduler is unconditional at boot.** `main.py:674-675` constructs and
   `.start()`s `StandingTaskScheduler` with no config flag, no dormancy guard,
   no dry-run. It runs `standing_research` every 12h (`standing_tasks.py:77-84`)
   → `reaper.execute("web_search", …)` → `grim.remember(..., trust_level=0.3,
   check_duplicates=False)` (`standing_tasks.py:221-249`). The gate isn't
   missing — it's **shipped open**. Mission = "confirm-state, close the open
   gate, then build the discipline that earns it back," not "add a gate."

2. **The scheduler bypasses every safety layer.** It calls
   `registry.get_module("reaper").execute(...)` and `grim.remember(...)`
   **directly** (`standing_tasks.py:218-249`) — never through
   `orchestrator.process()`. So it skips the Step 1.5 injection screen
   (`orchestrator.py:1186-1188`), the Step 4 Cerberus plan gate
   (`orchestrator.py:4605-4651`), and the Step 5 pre/post hooks
   (`orchestrator.py:5206-5291`). Autonomous scraped content enters permanent
   memory with **zero** screening.

3. **The on-demand path is barely more governed.** `web_fetch` is
   `permission_level: "autonomous"` (`reaper_module.py:229`) and calls
   `fetch_page(url)` with the default `store_in_grimoire=True`
   (`reaper_module.py:127` + `reaper.py:914-915`), writing the **full page at
   trust up to 0.7** (`reaper.py:988-999`). The Grimoire write happens *inside*
   `fetch_page` **before** the Step 5 post-hook ever runs, and the post-hook
   only receives `str(result.content)[:500]` for audit (`orchestrator.py:5281-5291`)
   — it cannot prevent or screen the write. The pre-hook blocks only
   `SafetyVerdict.DENY` (`orchestrator.py:5213`); an `autonomous`-classified
   tool is not denied. Step 1.5 injection screening runs on **`user_input`
   only** (`orchestrator.py:1960-1976`), never on scraped content.

Net: the injection discipline (Front 4) and the autonomy gate (Front 5) must
land on **both** the scheduler path and the `web_fetch` path, and neither has
an enforced gate today.

---

## 1. The module's real boundary

- **Reaper is LIVE and router-wired.** `modules/reaper/reaper_module.py:27`
  `class ReaperModule(BaseModule)`; a thin 259-line adapter (`reaper_module.py:1-13`)
  over the 1762-line engine `modules/reaper/reaper.py`. Not merged, not dead.
- **Grimoire is a hard construction dependency.** `ReaperModule.initialize`
  raises `ValueError` if `grimoire_instance is None` (`reaper_module.py:54-58`);
  `Reaper.__init__(self, grimoire, data_dir=...)` (`reaper.py:298`). Reaper
  writes research directly into memory — Grimoire is not optional.
- **On-demand by design, but a scheduler bolts autonomy on anyway.**
  `modules/base.py:357` states the design intent ("On demand: Reaper, Omen,
  Nova"). `standing_tasks.py` adds a 12h autonomous research job regardless
  (see §0). Doc-vs-code drift that IS the mission.
- **Two orthogonal surfaces, confirmed non-overlapping:**
  - **Internal router surface** — 5 tools (§2). The only surface that writes to
    Grimoire.
  - **External MCP HTTP surface** — `modules/reaper/mcp_server.py`, tools
    `reaper_search / reaper_fetch / reaper_summarize` (`mcp_manifest.json`),
    server bound `127.0.0.1:8101`. **NOT a Grimoire write vector:** both
    `fetch_page` calls pass `store_in_grimoire=False` (`mcp_server.py:180-182,
    244`). The router surface is the sole injection write path.
- **Settings live in two files:** `reaper_settings.py` (typed pydantic runtime
  knobs + `SecretStr` credentials, consumed by `shadow.config`) and `config.py`
  (standing topics, stealth constants, thresholds — "brain outside of code").

---

## 2. True tool / capability inventory (from code)

### Router-facing tools (5) — `reaper_module.py:211-259`, ALL `permission_level: "autonomous"`
| Tool | Adapter → Reaper method | Grimoire write? |
|---|---|---|
| `web_search` | `reaper.search()` (`reaper.py:406`) | No directly (returns results; caller may store) |
| `web_fetch` | `reaper.fetch_page(url)` (`reaper.py:914`) — **default `store_in_grimoire=True`** | **Yes — full page @ trust up to 0.7** |
| `youtube_transcribe` | `reaper.youtube_transcribe()` (`reaper.py:1557`) | Yes @ 0.3 |
| `reddit_search_json` | `reaper.search_reddit_json()` (`reaper.py:1487`) | Only via `reddit_search` pipeline |
| `reddit_monitor` | `reaper.monitor_subreddit_json()` (`reaper.py:1508`) | Only via `reddit_search` pipeline |

- The adapter's `web_fetch` branch calls `self._reaper.fetch_page(url)` with no
  `store_in_grimoire` arg (`reaper_module.py:127`) → default `True` applies →
  the live autonomous full-page write path.

### Latent (in code, NOT router-reachable, NOT scheduler-reachable)
- `reaper.research()` (`reaper.py:1109`) and `reaper.run_standing_research()`
  (`reaper.py:1246`): the full search→fetch→score→store pipeline that writes
  full page content @ up to **0.7** (`reaper.py:1192-1203`) / summaries @ up to
  0.7 (`:1217-1227`). Invoked only by the `__main__` demo and internally — the
  router adapter does not expose them. **The scheduler's
  `_run_standing_research` is a DIFFERENT function** (`standing_tasks.py:209`)
  that uses `web_search` snippets @ 0.3, not this pipeline.
- `read_chrome_history()` (`reaper.py:1659-1710`): reads local Chrome SQLite
  history **read-only** (copies the DB, queries, deletes the temp copy). NOT
  router-exposed. A local-host read capability worth a gates-ledger line if ever
  wired.

### External MCP tools (3) — read-only re: Grimoire (§1).

---

## 3. Traced core flows

### 3a. Search cascade (`reaper.py:406 search()` → `:491 _search_once()`)
- Order depends on `search_backend` (`reaper.py:521-544`); live value `ddg`
  (§10): **SearXNG → DDG → Brave → Bing**.
- Reddit `.json` is tried FIRST for Reddit-specific queries
  (`reaper.py:500-519`) before the general cascade.
- Reformulation: on empty/irrelevant results, retries up to 2× with
  simplify/broaden (`reaper.py:436-472`); long benchmark-style queries are
  keyword-extracted pre-search (`reaper.py:428-432`).
- **Rung observability is half-built:** each attempt emits
  `observed_span("reaper.search.attempt", backend=name)` with
  `{result_count, latency_ms, served}` (`reaper.py:549-561`) and tags
  `_served_by` on every result (`:567-568`), surfaced in ToolResult metadata
  (`reaper_module.py:109-115`). BUT rung *failures* only `print()` to stdout
  (`reaper.py:571, 620, 652, 714, 781`), never `logger` — with Langfuse down
  there is no structured failure record, and there is **no alert** when an
  enabled rung consistently fails to serve. This is a partial fix of the
  historical SearXNG silent-failure class, not a full one.

### 3b. Fetch → store (`reaper.py:914 fetch_page()`)
- `check_download_safety(url, content_type="text/html")` (`:925`) → stealth
  delay (`:933`) → `requests.get(url, headers=self._get_stealth_headers(),
  timeout=15, allow_redirects=True)` (`:935-938`) → BeautifulSoup strips
  script/style/nav/footer/header/aside/form/iframe (`:954-956`) → text extract
  → `ALWAYS_SKIP_PATTERNS` on first 500 chars (`:965-968`) → **store**
  (`:972-999`).
- **Plain `requests` — no Playwright, no browser** (§4). Static JA3 fingerprint
  regardless of header rotation.

### 3c. Standing research (autonomous, LIVE) — `standing_tasks.py:209-259`
- Rotates `DEFAULT_RESEARCH_TOPICS` (`:29-33`) → `reaper.execute("web_search",
  {topic, 5})` (`:221-223`) → `grim.remember(content=..., source="standing_task",
  trust_level=0.3, check_duplicates=False)` (`:236-249`). Stores **search
  snippets** at 0.3.

---

## 4. Stealth layer — BUILT vs. PENDING (Front 1 is a BUILD)

**BUILT and wired** (`reaper.py:821-837`, `config.py:132-161`):
- User-agent rotation — **8 signatures** (`config.py:132-146`;
  `random.choice(USER_AGENTS)` at `reaper.py:829`).
- Request-timing randomization — `random.uniform(1.0, 3.0)s`
  (`reaper.py:821-824`, `config.py:151-152`).
- Referrer spoofing — 5 options incl. `None` (`reaper.py:830`,
  `config.py:155-161`).
- Clean headers + DNT — `DNT:"1"`, Accept/Accept-Language/Accept-Encoding,
  Upgrade-Insecure-Requests (`reaper.py:831-836`).

**PENDING / ABSENT** (zero code matches under `modules/reaper/`, verified):
- **Playwright full-stealth heavy-page path — NOT wired.** 0 matches for
  `playwright|async_playwright|browser_context` in `modules/reaper/`.
  `fetch_page` is plain `requests`. *(Host note §10: the package `playwright
  1.58.0` AND chromium browser binaries ARE installed — the blocker is purely
  wiring, not install.)*
- **Canvas/WebGL spoofing — absent** (no browser → nothing to spoof).
- **TLS-fingerprint randomization — absent.** 0 matches; `curl_cffi` and
  `tls-client` NOT installed (§10). `requests`/urllib3 emit a static,
  fingerprintable JA3.
- **DNS-over-HTTPS — absent** (§10: `#DNSOverTLS=no`, no cloudflared/dnscrypt).
- **Residential proxies / browser-context isolation — absent** (0
  `proxy`/`socks` matches; no proxy env §10).
- **`stealth_mode` flag is DEAD.** Defined `reaper_settings.py:22`, set
  `config.yaml:98`, **read nowhere in code** (grep: only those two lines).
  Stealth is unconditionally always-on; the flag toggles nothing — a
  "looks configurable but isn't."
- **Reddit path is deliberately un-stealthed:** fixed identifying UA
  `"Shadow/1.0 (research context tool)"` (`reaper.py:1467-1469`) + hardcoded 2s
  sleep (`:1476`). Polite identification, not a defect — but out of Front 1's
  stealth scope by design.

---

## 5. Threat-awareness — Front 2 is largely ABSENT

Exists:
- **429 handling — Brave path ONLY** (`reaper.py:745-761`): honors
  `Retry-After`, one retry, then skips. DDG/Bing/SearXNG/`fetch_page` have none.
- **Reddit fixed 2s sleep** (`reaper.py:1476`) — crude, not adaptive.

Missing (zero matches):
- **No CAPTCHA detection** — the avoid-don't-solve cascade has nothing to honor.
- **No bot-detection / honeypot recognition** (hidden links, trap forms,
  bot-only content).
- **No exponential backoff / soft-block detection** on general HTTP paths.
- **No injection / instruction-like-content detection.** Nothing inspects
  scraped text for "this page is trying to instruct the reader." `fetch_page`
  passes `content_type="text/html"` and `check_download_safety` returns
  `{"action":"allow","reason":"HTML page"}` for it (`reaper.py:899-901`,
  `:925-928`) — HTML text where injection lives is waved through. The only
  content gate is `ALWAYS_SKIP_PATTERNS` (`config.py:223-232`), an SEO/spam
  filter, not an injection filter. The download-safety gate
  (`reaper.py:843-908`) is extension/size-based only.

---

## 6. The injection seam — write side settled (Front 4)

**Trust tiers** — `evaluate_source()` (`reaper.py:120-152`): Tier 1 official
(.gov/.edu/arxiv/github/… `TIER_1_DOMAINS`) = **0.7**; Tier 2 journalism = 0.5;
Tier 3 community = 0.3; Tier 4 unverified = 0.1. Classification is
substring/suffix domain matching (`:137-152`) — see the spoofability note §7.

**Every Reaper write to Grimoire** (all set `source_module="reaper"`; NONE set
`safety_class`, an untrusted tag, or an instruction flag):

| Path | `file:line` | `source` | `trust_level` | Content |
|---|---|---|---|---|
| `fetch_page` direct | `reaper.py:988-999` | `"research"` | `source_eval['trust_score']` → **up to 0.7** | full page text |
| research pipeline (full) | `reaper.py:1192-1203` | `"research"` | trust_score → **up to 0.7** | full page text |
| research pipeline (summary) | `reaper.py:1217-1227` | `"research"` | trust_score → **up to 0.7** | phi4-mini summary |
| Reddit | `reaper.py:1377-1389` | `"reddit"` | `0.3` (hardcoded) | post + top comments |
| YouTube | `reaper.py:1625-1634` | `"youtube"` | `0.3` (hardcoded) | transcript/summary |
| standing_research (scheduler) | `standing_tasks.py:236-249` | `"standing_task"` | `0.3` (hardcoded) | web_search snippets |

**Verdict vs the brief's bar** ("scraped content written above untrusted = Front
failed"): **FAILED today.** Any Tier-1-classified domain writes at **0.7** —
above the untrusted floor. No boolean untrusted tag, no data-wrapping marker, no
instruction-flag on any path. `source="research"` is a provenance label, not a
trust demotion.

**Available write-side carrier (for the plan):** `grimoire.remember()` accepts
`safety_class=None` (`grimoire.py:680`) and persists it as a TEXT column
(`grimoire.py:381, 760, 861`), documented "Cerberus safety classification"
(`:708`). It is **inert today** — nothing sets it (grep: zero write-callers) and
recall never reads it. So Reaper CAN carry an untrusted marker via
`safety_class` + a capped `trust_level` + a `metadata` instruction flag, but it
composes with **nothing** on the read side yet (that is the Grimoire mission).

**Read side of the seam (for composition):** `grimoire.recall()` defaults
`min_trust=0.0` and filters only when `min_trust > 0` (`grimoire.py:965,
1026-1027`); it does not read `safety_class`. So low-trust/untrusted content is
returned by default unless a caller opts in. **Retrieval-time demotion does not
exist.** Reaper must tag at write; Grimoire must demote at read; today neither
half exists.

---

## 7. "Looks governed but isn't" checks

1. **`stealth_mode` flag governs nothing** — dead config (§4). Any plan move
   that "toggles stealth via config" is a no-op.
2. **Tier-1 trust is spoofable by URL shape.** `evaluate_source` matches domain
   suffix (`reaper.py:137-152`): `*.github.com` gists/raw, `github.io`, `*.edu`
   user dirs, any user-content host under a Tier-1 suffix inherits **0.7**. The
   tier reflects *domain reputation*, never *whether the content is
   attacker-controlled*. An attacker who publishes under a Tier-1 suffix lands a
   payload at high trust.
3. **Cerberus "approval_required" is NOT enforced.** Step 4 plan gate
   (`orchestrator.py:4605-4651`): on `APPROVAL_REQUIRED` the code only *logs*
   (`:4642-4647`) with a "Phase 1: print to console" comment, then falls through
   to `plan.cerberus_approved = True` (`:4651`). Only `DENY` returns early
   (`:4640-4641`). Step 5 pre-hook likewise blocks only `DENY`
   (`orchestrator.py:5213`); `MODIFY` mutates params; everything else executes
   (`:5222-5254`). **The only enforced verdict is DENY.** Approval is
   decorative.
4. **The Cerberus gate can be skipped entirely.** The Step 4 loop only checks
   `if step.get("tool")` (`orchestrator.py:4613`); the default single-step plan
   sets `"tool": None` (`orchestrator.py:4596-4601`), so those dispatches are
   never seen by the plan gate. And the scheduler path (§0.2) skips the
   orchestrator altogether.
5. **"Every rung switch is observable" is half-true** — serving rung visible in
   Langfuse; failures `print()`-only, no logger, no alert (§3a).
6. **Autonomous ≠ gated.** All 5 router tools are `permission_level:
   "autonomous"` and the scheduler runs ungated. "The path exists" ≠ "the path
   is safe."

---

## 8. Counts & facts verified by running

- **Reaper tests: 107** — `pytest tests/test_reaper*.py --collect-only -q` →
  "107 tests collected", 7 files (`brave, locale, mcp, node, reformulation,
  searxng, searxng_live`). *(Note: `pytest -k reaper` reports 126 because it
  also matches reaper-mentioning tests in other files; the authoritative
  module-file count is 107.)*
- **UA signatures: 8** (`config.py:132-146`). **Referrers: 5** incl. `None`
  (`config.py:155-161`).
- **Router tools: 5** (`reaper_module.py:211-259`). **MCP tools: 3**
  (`mcp_manifest.json`).
- **YouTube = subtitle download only; Whisper NOT built** — `reaper.py:1597`
  prints "No English subtitles (needs Whisper — Phase 5)". The docs'
  "yt-dlp/Whisper" overstates.
- **Scoring/summarization model: `phi4-mini`** (`config.py:273`; Ollama
  `requests.post` at `reaper.py:1025, 1052, 1084`) — NOT the main Gemma.

---

## 9. Host / config — settled by running read-only checks (§10 for values)

All six brief RECON-NEEDED host items were settled read-only this run. The only
items left genuinely unsettled for the executor:

1. **Is APPROVAL_REQUIRED enforced by any layer I did not read?** — I traced
   Step 4 (`orchestrator.py:4605-4651`) and Step 5
   (`orchestrator.py:5152-5291`) and found only DENY enforced. **Exact
   re-check for the executor:** `grep -rniE "APPROVAL_REQUIRED" modules/shadow/
   modules/cerberus/ modules/harbinger/` and confirm no HITL/decision-queue
   consumer blocks on it before `module.execute`. If one exists, the on-demand
   gate is stronger than this digest assumes.
2. **A residential-proxy provider account / paid infra** — none on host (§10);
   whether Master *has* an account to wire is a **question for Master**, not a
   code fact.

---

## 10. Host recon results (run this session, read-only)

| Item | Check run | Result |
|---|---|---|
| Proxy env | `env \| grep -iE 'http_proxy\|https_proxy\|all_proxy\|socks'` | **none set** |
| DoH/DoT | `grep DNSOverTLS /etc/systemd/resolved.conf`; `command -v cloudflared dnscrypt-proxy` | `#DNSOverTLS=no`; **no binaries** → DoH is a build |
| TLS-fp libs | `pip show curl_cffi tls-client` | **both NOT installed** → JA3 randomization needs a new dep |
| Playwright | `pip show playwright`; `ls ~/.cache/ms-playwright` | **pkg 1.58.0 + chromium-1208 + headless_shell + ffmpeg PRESENT** → heavy-page path is wiring-only |
| SearXNG stack | `docker ps --filter name=searxng` | **`shadow-searxng Up 3 hours (healthy)`** |
| SearXNG enabled | `python -c "config.reaper.searxng_enabled"` | **`True`** (live override; NOT the schema default `False`) |
| Brave key | `python -c "config.reaper.brave_search_api_key is not None"` | **`False`** → Brave rung is dead on this host |
| search_backend | same | **`ddg`** → effective live cascade: SearXNG → DDG → Bing |

**Divergence worth carrying:** a reader trusting the schema default
(`searxng_enabled=False`, `reaper_settings.py:23`) would mis-plan — on Citadel
today SearXNG is enabled AND healthy AND primary. Verified by running, not by
reading the default.

---

## 11. Answers to the brief's four settle-in-recon questions

1. **Stealth built vs pending?** BUILT: UA rotation (8), timing (1–3s), referrer
   (5), clean headers+DNT. PENDING/ABSENT: Playwright wiring (pkg+browsers
   installed, code not wired), Canvas/WebGL, TLS-fp, DoH, residential proxies,
   browser-context isolation. **Front 1 is a build.** The current `requests`
   path is TLS-fingerprintable regardless of headers.
2. **Any cascade rung fail silently?** Partially. Serving rung observable via
   `_served_by`+spans, but failures are `print()`-only (no logger), and no alert
   on an enabled-rung-never-serves condition. Observability half-closed; alerting
   not closed.
3. **Trust level on scraped content, tagged untrusted?** Web scrape → tier score
   **up to 0.7**; Reddit/YouTube/standing_task → hardcoded 0.3. **NOT tagged
   untrusted on any path.** No instruction flag. `safety_class` exists but is
   inert. Fails Front 4's bar as it stands.
4. **Residential-proxy / DoH / TLS infra on Citadel?** All **absent** (§10),
   settled by running — not guessed. Playwright browsers ARE present.

---

## 12. Note for the WARGAME pass — the honest split (author's call)

Reaper is two missions; this instance will split:
- **Part 1 — stealth + professional gathering (Fronts 1–3):** Playwright
  heavy-page path (wiring-only on this host), TLS/DoH/proxy build, threat-aware
  backoff (rate-limit/CAPTCHA-avoid/honeypot), source-eval hardening,
  extraction, cascade observability→alerting. Reaper-internal capability. Its
  own red-team on the stealth-vs-access-control line.
- **Part 2 — injection-source discipline + the Tier-2 gate (Fronts 4–5 + the
  injection half of Front 2):** the instruction-like-content detector,
  write-time untrusted tagging (`safety_class` + capped trust + instruction
  flag) on BOTH the `web_fetch` and scheduler paths, and closing the
  currently-open scheduler gate with a concrete earned-by condition. The seam
  with Grimoire + Sentinel; highest-severity half. Its own red-team playing a
  hostile page.

**Seam justification:** a move belongs to Part 2 if it changes *what enters
Grimoire* or *when Reaper acts autonomously*; otherwise (how well/safely Reaper
reads the public web) it is Part 1. The instruction-like-content DETECTOR sits
in Part 2 (it is the injection seam) even though the brief lists it under Front
2; Part 1's Front 2 wires the operational responses (backoff, rung-switch,
disengage) and calls the Part-2 detector as the content-inspection step.

**Two load-bearing facts to carry:** (a) the scheduler gate is **open at boot**
(`main.py:674-675`) and (b) `web_fetch` (autonomous) already writes full pages
at up to **0.7** — the discipline lands on that path, not just the scheduler.

---

*END RECON DIGEST — independent "stealth" instance. Nothing mutated beyond
writing this file. No battle plan / gates ledger / red-team in this recon; those
are the wargame pass's job.*
