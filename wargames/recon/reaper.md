# RECON DIGEST — Reaper

**Mode:** RECON-only (per Master, 2026-07-07). Phases 0–1 complete. **No plan written.**
**Standard loaded:** `wargames/SUCCESS.md` (nine points) — byte-identical to the staged copy.
**Brief:** `wargames/tasks/reaper.md`.
**Rule of this digest:** every code claim carries `file:line`. Carried context is hypothesis; the file is truth. Counts verified by running, not by grep.

This is the settled-facts base the wargame pass builds on. Whoever runs the WARGAME reads this instead of re-reading the module blind — but **spot-verify a few `file:line` claims before trusting them**, and treat every `RECON NEEDED` as unsettled until its exact check is run.

---

## 0. Headline (the finding that reshapes the plan)

**The Tier-2 web-facing autonomy the brief says must be "dormant until the injection mitigations are live" is LIVE and UNGATED today.** `main.py:674-675` unconditionally constructs and `start()`s `StandingTaskScheduler` at boot — no dormancy flag, no dry-run guard, no config gate. That scheduler runs `standing_research` on a **12-hour interval** (`standing_tasks.py:77-84`), which calls Reaper `web_search` and writes the results into Grimoire (`standing_tasks.py:209-249`). So Front 5's load-bearing gate is not merely missing — the system currently ships with the gate **open**. The mission is therefore "confirm-state, close the open gate, then build the discipline that earns it back," not "add a gate to a dormant capability."

Second-order: the router-reachable `web_fetch` tool (`reaper_module.py:125-135`, `permission_level: "autonomous"` at `:229`) writes **full scraped page content** to Grimoire at **trust up to 0.7** (`reaper.py:988-999`) every time Shadow autonomously fetches a page. That is the live high-trust injection write path, independent of the scheduler.

---

## 1. The module's real boundary

- **Reaper is a LIVE, router-wired module.** `modules/reaper/reaper_module.py:27` `class ReaperModule(BaseModule)`; wired via the registry; not merged, not dead, not half-wired. The heavy implementation is `modules/reaper/reaper.py` (1761 lines); `reaper_module.py` (259 lines) is a thin BaseModule adapter over it (`reaper_module.py:1-13` docstring says so).
- **Construction dependency:** Reaper requires a Grimoire instance at init (`reaper_module.py:54-63`; `reaper.py` `Reaper(grimoire=..., data_dir=...)`). It writes research directly into memory — Grimoire is not optional.
- **On-demand by design, but with an autonomous scheduler path.** `modules/base.py:357` states the intent: *"On demand: Reaper, Omen, Nova. Scheduled: Harbinger, Morpheus."* The design says Reaper is on-demand — but `standing_tasks.py` bolts a 12h autonomous research job onto it anyway (see §0). Doc-vs-code drift that matters.
- **Two orthogonal surfaces, confirmed non-overlapping** (matches CLAUDE.md):
  - **Internal router surface** — 5 tools (see §2). The only surface the router dispatches, and the only one that writes to Grimoire.
  - **External MCP HTTP surface** — `modules/reaper/mcp_server.py`, manifest tools `['reaper_search','reaper_fetch','reaper_summarize']` (verified by parsing `mcp_manifest.json`). **This surface never writes to Grimoire:** both `fetch_page` calls pass `store_in_grimoire=False` (`mcp_server.py:180-182, 244`). So the MCP surface is NOT an injection write vector — the router surface is.
- **Settings live in two places:** `modules/reaper/reaper_settings.py` (typed pydantic runtime knobs + secrets, consumed by `shadow.config`) and `modules/reaper/config.py` (standing topics, stealth constants, thresholds — "brain outside of code").

---

## 2. True tool / capability inventory (verified from code)

### Router-facing tools (5) — `reaper_module.py:211-259`, all `permission_level: "autonomous"`
| Tool | Adapter → Reaper method | Grimoire write? |
|---|---|---|
| `web_search` | `reaper.search()` (`reaper.py:406`) | No (returns results; caller may store) |
| `web_fetch` | `reaper.fetch_page(url)` (`reaper.py:914`) — **default `store_in_grimoire=True`** | **Yes — full page @ trust up to 0.7** |
| `youtube_transcribe` | `reaper.youtube_transcribe()` (`reaper.py:1557`) | Yes — @ trust 0.3 |
| `reddit_search_json` | `reaper.search_reddit_json()` (`reaper.py:1487`) | Via research pipeline only |
| `reddit_monitor` | `reaper.monitor_subreddit_json()` (`reaper.py:1508`) | Via research pipeline only |

- Docs' "5 tools" count is **correct** but the labeling differs: two of the five are Reddit tools; "research" = `web_search`, "web scraping" = `web_fetch`.
- **`web_fetch` is the live autonomous full-page write path.** The adapter calls `self._reaper.fetch_page(url)` with no `store_in_grimoire` arg (`reaper_module.py:127`), so the default `True` (`reaper.py:915`) applies.

### Latent (in code, NOT router-reachable, NOT scheduler-reachable)
- `reaper.research()` (`reaper.py:1109`) and `reaper.run_standing_research()` (`reaper.py:1246`) — the full search→fetch→score→store pipeline that writes full page content @ **0.7**. Only invoked by `reaper.py:283-297` (the `__main__` demo) and internally (`reaper.py:1266, 1297`). The router adapter does **not** expose them. *(Note: the scheduler's `standing_tasks._run_standing_research` is a DIFFERENT function — it uses `web_search`, not this pipeline.)*

### External MCP tools (3) — `reaper_search`, `reaper_fetch`, `reaper_summarize` — read-only re: memory (§1).

---

## 3. Traced core flows

### 3a. Search cascade (`reaper.py:406 search()` → `:491 _search_once()`)
- Order is `search_backend`-config-dependent (`reaper.py:521-544`), default `"ddg"` (`reaper_settings.py:20`):
  - default `ddg`: **SearXNG → DDG → Brave → Bing**
  - `brave`: Brave → SearXNG → DDG → Bing
  - `searxng`: SearXNG → Brave → DDG → Bing
- **Reddit `.json` is tried first for Reddit-specific queries** (`reaper.py:500-519`) before the general cascade.
- Reformulation: on zero results, query is reformulated and retried (`reaper.py:430-458`); `_reformulation` metadata attached (`:574-586`).
- **Observability of rung switch:** each attempt emits `observed_span("reaper.search.attempt", backend=name)` with `{result_count, latency_ms, served}` (`reaper.py:549-561`), and the serving rung is tagged `_served_by` on every result (`:567-568`), surfaced in the ToolResult metadata (`reaper_module.py:109-115`).

### 3b. Fetch → store (`reaper.py:914 fetch_page()`)
- Stealth delay (`:933`) → `requests.get(url, headers=self._get_stealth_headers(), timeout=15)` (`:935-938`) → BeautifulSoup text extraction, strips script/style/nav/etc. (`:951-959`) → `ALWAYS_SKIP_PATTERNS` check on first 500 chars (`:964-968`) → **store** (`:988-999`).
- **Uses plain `requests` — no Playwright, no browser.** (See §4.)

### 3c. Standing research (autonomous, LIVE) — `standing_tasks.py:209-249`
- Picks next topic from `DEFAULT_RESEARCH_TOPICS` (`:29-33`: "ollama updates", "llama.cpp updates", "RTX 5090 pricing") → `reaper.execute("web_search", {topic, 5})` (`:221-223`) → `grim.remember(content=..., source="standing_task", trust_level=0.3, ...)` (`:236-249`). Stores **search snippets** at 0.3, `check_duplicates=False`.

---

## 4. Stealth layer — built vs. pending (Front 1 is a BUILD, not a polish)

**BUILT and wired** (`reaper.py:821-837`, `config.py:132-161`):
- User-agent rotation — **8 signatures** verified (`config.py:132-146`: 3× Chrome/Win, 2× Firefox/Win, 1× Chrome/Mac, 1× Edge, 1× Safari/Mac). `random.choice(USER_AGENTS)` (`reaper.py:829`).
- Request-timing randomization — `random.uniform(1.0, 3.0)s` (`reaper.py:821-824`, `config.py:151-152`).
- Referrer spoofing — `random.choice(REFERRERS)`, 5 options incl. `None` (`reaper.py:830`, `config.py:155-161`).
- Clean headers + DNT — `DNT: "1"`, Accept/Accept-Language/Accept-Encoding, Upgrade-Insecure-Requests (`reaper.py:831-836`).

**PENDING / ABSENT** (confirmed by zero code matches):
- **Playwright full-stealth heavy-page path — NOT wired.** `playwright` is in `requirements.txt` but there is **zero** `playwright`/`async_playwright`/`browser_context` usage anywhere under `modules/reaper/`. `fetch_page` is plain `requests` (`reaper.py:935`). *Installed ≠ wired* — exactly the brief's suspicion.
- **Canvas/WebGL fingerprint spoofing — absent** (no browser at all → nothing to spoof).
- **TLS-fingerprint randomization — absent.** Zero `ja3`/`tls`/`ssl_context`/`curl_cffi` matches. `requests`/urllib3 emit a static, highly-fingerprintable JA3.
- **DNS-over-HTTPS — absent.** Zero `doh`/`dns.over` matches.
- **Residential proxies / browser-context isolation — absent.** Zero `proxy`/`socks` matches.
- **`stealth_mode` config flag is DEAD.** Defined at `reaper_settings.py:22` (`stealth_mode: bool = True`) and **read nowhere** (only match is the definition). Stealth is unconditionally always-on; the flag toggles nothing — a "looks configurable but isn't."
- **Reddit path is NOT stealthed** (deliberately): fixed identifying UA `"Shadow/1.0 (research context tool)"` (`reaper.py:1467-1469`) and a hardcoded 2s sleep (`:1476`), bypassing UA rotation. Polite-identification, not a stealth defect — but note it for Front 1 scope.

---

## 5. Threat-awareness — Front 2 is largely ABSENT

What exists:
- **429 handling — Brave-API path ONLY** (`reaper.py:744-760`): honors `Retry-After`, one retry, then skips. Not general; DDG/Bing/SearXNG/fetch have no 429 handling.
- **Reddit fixed rate-limit** — unconditional 2s sleep (`reaper.py:1476`). Crude, not adaptive backoff.

What is MISSING (zero matches):
- **No CAPTCHA detection** anywhere (the avoid-don't-solve cascade doesn't exist to honor).
- **No bot-detection / honeypot recognition** (hidden links, trap forms, bot-only content).
- **No exponential backoff / soft-block detection** on the general HTTP paths.
- **No injection / instruction-like-content detection.** Nothing inspects scraped text for "this page is trying to instruct the reader." HTML pages are declared **"always safe to fetch"** (`reaper.py:899-901`) — the only content gate is `ALWAYS_SKIP_PATTERNS` (`config.py:223-232`), an SEO/spam filter, not an injection filter. Front 2's subtle core (recognize a prompt-injection payload on the way in and flag it) is **unbuilt**.

The download-safety gate (`reaper.py:843-908`) is extension/size-based only (`BLOCKED_EXTENSIONS` hard-refuse; Tier-1 auto-allow safe extensions; approval-required list). It does not inspect page *content* — and HTML text (where injection lives) is waved through.

---

## 6. The injection seam — write side settled with `file:line` (Front 4)

**Trust tiers** (`reaper.py:120-152 evaluate_source()`): Tier 1 official (.gov/.edu/arxiv/github + `TIER_1_DOMAINS`) = **0.7**; Tier 2 journalism = 0.5; Tier 3 community = 0.3; Tier 4 unverified/unknown = 0.1. Classification is **substring/suffix domain matching** (`:137-152`) — see the "looks governed but isn't" note in §7.

**Every Reaper write to Grimoire** (all set `source_module="reaper"`; NONE set an untrusted-source tag or an instruction-flag):

| Path | `file:line` | `source` | `trust_level` | Content |
|---|---|---|---|---|
| `fetch_page` direct | `reaper.py:988-991` | `"research"` | `source_eval['trust_score']` → **up to 0.7** | full page text |
| research pipeline (full) | `reaper.py:1192-1195` | `"research"` | `source_evaluation['trust_score']` → **up to 0.7** | full page text |
| research pipeline (summary) | `reaper.py:1217-1220` | `"research"` | `source_evaluation['trust_score']` → **up to 0.7** | phi4 summary |
| Reddit | `reaper.py:1377-1381` | `"reddit"` | `0.3` (hardcoded) | post + top comments |
| YouTube | `reaper.py:1625-1628` | `"youtube"` | `0.3` (hardcoded) | transcript/summary |
| standing_research (scheduler) | `standing_tasks.py:236-249` | `"standing_task"` | `0.3` (hardcoded) | web_search snippets |

**Verdict against the brief's bar** ("a plan where Reaper writes scraped content at anything above untrusted has failed this front"): **FAILED today.** Web-scraped content from any Tier-1-classified domain is written at **0.7** — *above* Grimoire's documented "research ~0.5" and far above an untrusted floor. There is **no** boolean "untrusted-source" tag, **no** "wrap as data" marker, and **no** instruction-like-content flag on any write path. `source="research"` is a provenance label, not a trust demotion. The one honest signal present is `source_module="reaper"`.

**Read side of the seam (Grimoire, for composition):** `grimoire.recall()` defaults **`min_trust=0.0`** (`grimoire.py:965`) and only filters when `min_trust > 0` (`:1026-1027`). So untrusted/low-trust content is returned by default unless a caller opts in. Retrieval-time demotion / data-wrapping is **not** enforced by default — that mechanism is the Grimoire-mission deliverable, and it does not exist yet. Reaper tags at write; Grimoire must demote at read; today neither the untrusted tag nor the default demotion exists.

---

## 7. "Looks governed but isn't" checks

1. **`stealth_mode` flag** — governs nothing; dead config (§4). Any plan move that "disables stealth via config" is a no-op.
2. **Tier-1 trust is spoofable by URL shape.** `evaluate_source` matches on domain suffix (`reaper.py:137-152`). **CORRECTED (red-team, 2026-07-07):** `github.io` does **NOT** inherit 0.7 — it is not in `TIER_1_DOMAINS`, evaluating to Tier 4/0.1. The real high-trust vector is **`gist.github.com`** (matches the `.github.com` suffix → Tier 1/0.7); `raw.githubusercontent.com` is 0.1; `medium.com` is already Tier 3/0.3. So an attacker who can publish under a Tier-1-*suffix* host (e.g. a public gist) lands a payload at **0.7**. The tier reflects *domain reputation*, never *whether the content is attacker-controlled*.
3. **"Every rung switch is observable" is only half-true.** `_served_by` + the `observed_span` make the serving rung visible *in Langfuse metadata* (`reaper.py:549-568`). But: (a) rung failures otherwise only `print()` to stdout — not `logger` (`reaper.py:571, 616, 620`), so with Langfuse down there is no structured record; (b) **SearXNG defaults DISABLED** (`searxng_enabled=False`, `reaper_settings.py:23`) — `_searxng_is_available()` returns `False` when disabled (`reaper.py:372-374`), so the "primary" rung is silently skipped and the cascade starts at DDG by default; (c) there is **no alert** when an enabled rung consistently fails over. This is a partially-closed version of the original SearXNG silent-failure class, not a fully-closed one.
4. **Autonomous ≠ gated.** All 5 router tools are `permission_level: "autonomous"` (`reaper_module.py`), and the scheduler runs ungated (§0). "The path exists" is emphatically not "the path is safe."

---

## 8. Counts & facts verified by running

- **Reaper tests: 107 collected** across the 7 `tests/test_reaper*.py` files (`pytest --collect-only`, 0 errors). Files: `brave, locale, mcp, node, reformulation, searxng, searxng_live`.
- **User-agent signatures: 8** (`config.py:132-146`).
- **Referrer options: 5** incl. `None` (`config.py:155-161`).
- **Router tools: 5** (`reaper_module.py:211-259`); **MCP tools: 3** (`mcp_manifest.json`).
- **SearXNG config flags: 4** — `searxng_enabled` (default `False`), `searxng_base_url` (`http://localhost:8888`), `searxng_timeout_s` (15), `searxng_health_ttl_s` (60) (`reaper_settings.py:23-28`).
- **Relevance scoring / summarization model: `phi4-mini`** per `config.py:266-278` (Ollama at `:11434`), NOT the main Gemma — a config-vs-CLAUDE.md drift worth noting (Ollama `requests.post` call sites `reaper.py:1025, 1052, 1084`).
- **YouTube = subtitle download only; Whisper NOT built** — `reaper.py:1597` prints "No English subtitles (needs Whisper — Phase 5)". Docs' "yt-dlp/Whisper" overstates: only `yt-dlp` subtitle path exists (`reaper.py:1561-1600`).

---

## 9. RECON NEEDED (host/config — settle before or at the top of the WARGAME/execution; do NOT guess)

Host-infrastructure and secret-dependent facts recon could not settle read-only-in-repo. Each has its exact check:

1. **Residential proxy infra on Citadel?** — none in code/config. Check: `env | grep -iE 'http_proxy|https_proxy|all_proxy'`; ask Master whether a residential-proxy provider account exists. Absent → Front 1 proxy layer is a from-scratch build + a paid-infra Master gate.
2. **DNS-over-HTTPS on Citadel?** — Check: `resolvectl status | grep -iE 'DNSOverTLS|DNS over'` and `grep -iE 'DNSOverTLS|DoH' /etc/systemd/resolved.conf`; `command -v cloudflared dnscrypt-proxy`. Absent → DoH is a build.
3. **TLS-fingerprint randomization capability?** — Check `shadow_env`: `pip show curl_cffi tls-client 2>/dev/null`. Absent → JA3 randomization needs a new dependency (e.g. `curl_cffi`), which changes the `requests`-based fetch path.
4. **Playwright browsers actually downloaded?** — `playwright` the package is in `requirements.txt`, but browser binaries are separate. Check: `ls ~/.cache/ms-playwright 2>/dev/null` or `python -m playwright install --dry-run`. Missing binaries → the heavy-page path can't run even after it's wired.
5. **Is the SearXNG Docker stack running?** — `services/searxng/docker-compose.yml` exists; runtime state unknown read-only. Check: `docker ps --filter name=searxng`. (And `searxng_enabled` is `False` by default in typed settings — confirm the per-machine `config.local.yaml`.)
6. **Is a Brave API key configured?** — `brave_search_api_key` is `SecretStr | None` (`reaper_settings.py:30-37`); `.env` is unreadable by policy. Brave rung is live only if the key is set (`reaper.py:332-337`). Check with Master / `config.reaper.brave_search_api_key is not None`.

---

## 10. Answers to the brief's four settle-in-recon questions

1. **How much of the stealth layer is built vs. pending?** BUILT: UA rotation (8), timing randomization (1–3s), referrer spoofing (5), clean headers + DNT. PENDING/ABSENT: Playwright (installed-not-wired), Canvas/WebGL, TLS-fingerprint, DoH, residential proxies, browser-context isolation. **Front 1 is a build, not a polish** — and the current fetch path (`requests`) is fingerprintable at the TLS layer regardless of headers.
2. **Does any cascade rung fail silently to a fallback?** Partially. The serving rung is observable via `_served_by` + Langfuse spans, but rung failures are `print()`-only (not logged), SearXNG defaults disabled (so the primary is silently skipped), and there is no alert on an enabled-rung-never-serves condition. The original SearXNG failure class is mitigated for observability, not fully closed for alerting.
3. **What trust level does scraped content get, and is it tagged untrusted?** Web scrape → **URL-reputation tier score, up to 0.7 (Tier-1)**; Reddit/YouTube/standing_task → hardcoded 0.3. **NOT tagged untrusted on any path**; no instruction-flag; `source` is a provenance label only. This fails the brief's Front-4 bar as it stands.
4. **Residential-proxy / DoH / TLS infra on Citadel?** Absent in code; host state is **RECON NEEDED** (§9.1–9.3) with exact checks — not guessed.

---

## 11. Note for the WARGAME pass — likely honest split (the author's call, flagged not decided)

Reaper is plausibly two missions, mirroring the Sentinel split:
- **Part 1 — stealth + professional gathering (Fronts 1–3):** the Playwright heavy-page path, TLS/DoH/proxy build, threat-aware back-off, source-eval + extraction quality, cascade observability/alerting. Self-contained; its own red-team on the stealth-vs-access-control line.
- **Part 2 — injection-source discipline + the Tier-2 gate (Fronts 4–5):** write-time untrusted tagging, the instruction-like-content flag, and closing the currently-open standing-research gate with a concrete earned-by condition. This is the seam with Grimoire + Sentinel and the highest-severity half; its own red-team playing a hostile page.

The seam falls cleanly because Fronts 4–5 compose with the Grimoire/Sentinel missions and gate the autonomy, while Fronts 1–3 are Reaper-internal capability. **Decision deferred to the wargame pass; justify in the LEDGER if taken.**

Two facts the wargame pass must carry as load-bearing: (a) the standing-research gate is currently **open at boot** (`main.py:674-675`) — the plan closes it, not adds it to a dormant capability; (b) `web_fetch` (autonomous) already writes full pages at up to **0.7** — the injection discipline must land on *that* path, not just the scheduler.

---

*END RECON DIGEST — RECON mode stops here. No battle plan, no Gates & Autonomy Ledger, no red-team pass in this run (those are the WARGAME pass's job). Nothing in this run mutated system state beyond writing this digest and staging `wargames/tasks/reaper.md`.*
