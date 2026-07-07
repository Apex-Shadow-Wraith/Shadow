# BATTLE PLAN — Reaper Part 1: resilient, polite, identifiable gathering

**Mission framing (the reframe Master approved):** Reaper is the research analyst who
reads the whole public web *well* and *behaves* — identifiable, robots-respecting,
backs off when a host pushes back, and never disguises itself or routes around an
access control. The original brief's "truly undetectable" mandate (residential proxies,
TLS/JA3 randomization, Canvas/WebGL spoofing, honeypot *evasion*) is **cut, not deferred**
— replaced by "identifiable and well-behaved." Where the brief said *evade the boundary*,
this plan says *respect it*.

**Scope of Part 1:** Fronts 1–3 (gathering capability) + the Brave-rung removal.
Fronts 4–5 (injection-source discipline + the autonomy gates) live in
`reaper-part2-injection.md` — the seam falls between "read well and behave" (Part 1)
and "don't let what you read become an instruction, and don't run autonomously until
that's proven" (Part 2). Justified in the LEDGER.

**Executor:** Opus 4.8, max effort. Read this end to end before the first edit.
**Recon base:** `wargames/recon/reaper.md` — spot-verify its `file:line` claims before trusting them; carried facts are hypothesis until the file confirms them.
**Standing policy that binds every move:** every edit here is a write to Shadow's own
code → tests green + Master's diff review + commit, **never push** (Master merges). See
the Gates & Autonomy Ledger at the end; it is not optional.

---

## Pre-flight (run before any edit — settles the host unknowns recon left open)

Run these read-only checks first. They gate which moves are buildable now vs. blocked.

- **PF-1 — venv active.** `source ~/dev/Shadow/shadow_env/bin/activate` — never create a new venv.
- **PF-2 — Playwright browser binaries present?**
  `ls ~/.cache/ms-playwright 2>/dev/null && echo PRESENT || echo MISSING`
  *Trigger:* MISSING → M1.4 (Playwright renderer) is blocked until `python -m playwright install chromium` is run; that install is a Gate (G1.4) — Master-approved, downloads a browser. Do not auto-install.
- **PF-3 — baseline test collection green.** *(PATCHED — red-team F1: the six-file command below collects 104, not 107; 107 is the SEVEN-file total. The command now lists all seven.)*
  `python -m pytest tests/test_reaper_brave.py tests/test_reaper_locale.py tests/test_reaper_mcp.py tests/test_reaper_node.py tests/test_reaper_reformulation.py tests/test_reaper_searxng.py tests/test_reaper_searxng_live.py --collect-only -q` → **expect `107 tests collected`, 0 errors** (per-file: brave 23, locale 4, mcp 23, node 8, reformulation 25, searxng 21, searxng_live 3 = 107).
  *Trigger:* not 107 or any error → recon's count drifted; STOP and re-recon before editing (abort A1). *(Note: `test_reaper_searxng_live.py` hits a live endpoint; if it errors on network, collect the other six = **104** and proceed — collection, not run.)*
- **PF-4 — is SearXNG actually running?** `docker ps --filter name=searxng --format '{{.Names}}'` → records whether the "primary" rung is live (feeds M3.3).

---

## Front 1 — Resilient, polite, identifiable gathering

### M1.0 — Remove the Brave backend entirely (settled cleanup)
**Settled fact (Master, 2026-07-07):** there is no Brave API key; the rung is wired but
always yields 0 results. Recon confirmed the wiring surface: **64 references + 23 tests**
(`reaper.py:717-784` backend, `:523-543` cascade slots, `config.py:250-256` constants,
`reaper_settings.py:30-37` the `brave_search_api_key` SecretStr field, `tests/test_reaper_brave.py`).
Because it can never serve, removal is pure cleanup and *fits* the reframe (no paid infra).

**Build:** Delete `_search_brave`, `_brave_get_usage`, `_brave_increment_usage`
(`reaper.py:717-818` region — verify exact bounds), remove the `("brave", …)` tuple from
all three cascade orders (`reaper.py:523-543`), delete the Brave constants
(`config.py:250-256`), remove the `brave_search_api_key` field (`reaper_settings.py:30-37`),
remove `brave_available`/`brave_api_key` init (`reaper.py:332-337`), delete
`tests/test_reaper_brave.py`, **AND — CRITICAL, red-team F3/F4 — delete the flat-env routing
entry `"BRAVE_SEARCH_API_KEY": ("reaper", "brave_search_api_key"),` at
`shadow/config/sources.py:167`.** These two deletions (the typed field and the routing entry)
**must land in the same commit** — see the failure mode below for why leaving the routing entry
is a security bug, not a loose end.

**Expected observation:** `grep -rniE "brave" modules/reaper/ tests/test_reaper*.py shadow/config/sources.py | grep -v __pycache__` → **0 matches** (note the grep now includes `sources.py`). Remaining cascade orders are SearXNG→DDG→Bing (default). Collection drops from 107 to **84** tests (107 − 23), 0 errors. **Plus a redaction assertion (F4):** a test sets a dummy `BRAVE_SEARCH_API_KEY` in the env, loads config, and asserts the string does **not** appear in `config.model_dump_json()` (it can't — there's no field and no routing entry to carry it).
**Most likely failure (PATCHED — the real one, not an ImportError):** deleting the typed `SecretStr` field but **leaving** `FLAT_TO_PATH["BRAVE_SEARCH_API_KEY"]` at `sources.py:167` causes a **silent plaintext-secret leak**, not an error. `ReaperSettings` is `extra="allow"` (`reaper_settings.py:15`); with the typed field gone, a set `BRAVE_SEARCH_API_KEY` gets routed by `FlatEnvSource` into `{"reaper": {"brave_search_api_key": "<raw>"}}`, lands as an **untyped `str`** in `extra=allow` storage, and **`model_dump_json()` stops redacting it** — the exact hazard the `sources.py:147-150` docstring warns of. No ImportError is ever raised; tests stay green; the key leaks into any config dump/log/Langfuse span. **Counter:** the routing-entry deletion is in the Build list above; the redaction test in Expected observation fails if it's missed.
**Fork (PATCHED — F3):** the mandated counter grep `grep -rn "brave_search_api_key" --include=*.py .` **will** hit `sources.py:167` — that is the *expected* routing entry to delete in this same commit, **not** an abort trigger. A2 aborts only if the grep finds a *functional consumer that reads the value* (imports the field, calls `_search_brave`, etc.) outside Reaper/tests/`sources.py` — i.e. code whose behavior changes. Trigger for A2 = a match that is neither Reaper, its tests, nor the single `sources.py:167` routing line.
**Gate:** code write to Shadow's own code → G-EDIT (see ledger).

### M1.1 — One honest, identifiable user-agent (replaces blend-in rotation)
**Current:** `_get_stealth_headers()` (`reaper.py:826-837`) picks `random.choice(USER_AGENTS)`
from 8 real-browser signatures (`config.py:132-146`) and `random.choice(REFERRERS)` from 5
fake referrers incl. `None` (`config.py:155-161`). That is blend-in disguise — cut it.

**Build:** Replace the rotation with a single honest agent constant, e.g.
`REAPER_USER_AGENT = "ShadowResearch/1.0 (+personal research assistant; contact: <Master's contact>)"`.
Drop the referrer-spoofing entirely (send no `Referer`, or a truthful one only when Reaper
genuinely navigated from a page). Keep `DNT: 1` and the honest Accept headers.
`RECON NEEDED:` the contact string — **ask Master** what contact to publish (email/URL/none). Do not invent one.

**Expected observation:** a new test asserts `_get_stealth_headers()` returns the fixed UA on 10 consecutive calls (no variation) and that `Referer` is absent or truthful. `grep -n "random.choice(USER_AGENTS)\|random.choice(REFERRERS)" reaper.py` → 0 matches.
**Most likely failure:** Reddit's separate header path (`reaper.py:1467-1469`, `Shadow/1.0 (research context tool)`) is left inconsistent. **Counter:** unify both on the same honest UA constant in this move.
**Gate:** G-EDIT.

### M1.2 — robots.txt compliance (new — recon found none)
**Current:** zero robots handling anywhere in the module (recon: no `robots` matches).

**Build:** Before any `fetch_page` (`reaper.py:914`) network call, fetch and cache
`/robots.txt` per host (use `urllib.robotparser`), honor `Disallow` for Reaper's UA, and
honor `Crawl-delay` if present (feeds M1.3's limiter). Cache per-host for the session.

**Expected observation:** a test with a stubbed robots.txt that disallows `/private` → `fetch_page("http://host/private")` returns `None` with a logged `robots disallow` reason and **makes no GET to the page**. A different allowed path fetches normally.
**Most likely failure:** a robots fetch per page → doubles request volume and is itself impolite. **Cause:** no cache. **Counter:** per-host cache asserted by the test (second fetch to same host makes no second robots GET).
**Fork:** robots.txt returns 4xx/5xx or is absent → **default allow** (standard crawler behavior), logged. Trigger = robots status ≥ 400 or connection error → treat as "no restrictions," proceed.
**Gate:** G-EDIT.

### M1.3 — General exponential backoff + Retry-After + per-domain courtesy limiter
**Current:** only Brave honored 429 (`reaper.py:744-760`, being deleted in M1.0); Reddit
uses a fixed `time.sleep(2)` (`reaper.py:1476`); DDG/Bing/SearXNG/`fetch_page` have no 429
handling at all.

**Build:** A shared helper wrapping every outbound GET (search rungs + `fetch_page` + Reddit
`.json`): on 429/503, honor `Retry-After`, else exponential backoff (e.g. 1s→2s→4s, capped),
max N retries, then a **clean logged skip** (never an infinite loop, never a tactic-switch to
route around). A per-domain minimum interval (courtesy limiter) replaces the blanket 1–3s
`_stealth_delay` (`reaper.py:821-824`) — rename it `_courtesy_delay`, keep randomization for
politeness (not disguise).

**Expected observation:** a test injecting a 429 with `Retry-After: 2` → helper waits ~2s, retries once, and on a second 429 returns a skip result logged as `rate-limited: <host>`. A test firing 5 rapid requests to one host observes ≥ the per-domain interval between each.
**Most likely failure:** backoff applied per-call but not per-host, so parallel topics hammer one host. **Cause:** limiter keyed on call, not domain. **Counter:** limiter state keyed on `urlparse(url).netloc`; test asserts cross-call spacing to same host.
**Gate:** G-EDIT.

### M1.4 — Playwright as a renderer (wire the installed-but-unused dep; rendering, not disguise)
**Current:** `playwright` is in `requirements.txt` but has **zero** usage in `modules/reaper/`
(recon). `fetch_page` is plain `requests` (`reaper.py:935`), which can't execute JS.

**Build:** Add a render path used **only** when a page needs JS (fork trigger below):
headless Chromium via Playwright, the **same honest UA** (M1.1), **no** fingerprint/canvas/WebGL
spoofing, **no** stealth plugins, default TLS. It renders the DOM so text extraction (M3.2)
gets real content. This is "use a real browser to read a JS page," not "look like a human."

**Expected observation:** a JS-only test page (content injected by script) → the render path
returns the post-JS text; the plain `requests` path returns empty/placeholder for the same page.
A grep confirms **no** `stealth`, `playwright_stealth`, `add_init_script`-fingerprint,
`--disable-blink-features` spoofing in the render code.
**Most likely failure (PF-2):** Playwright package present but **browser binary missing** → launch throws. **Cause:** `playwright install` never run. **Counter:** M1.4 is blocked by PF-2; the install is Gate G1.4 (Master-approved). If MISSING, the executor stops M1.4 and flags, continues with other moves.
**Fork — when to render vs. plain-fetch:** trigger = plain `requests` fetch yields text below a threshold (e.g. < 200 non-boilerplate chars) OR the page's `<body>` is script-dominated → escalate to render. Otherwise plain fetch (cheaper, politer). No judgment call: the char-threshold decides.
**Gate:** G-EDIT + **G1.4** (browser-binary install is a host action).

### M1.5 — Conditional requests / caching (good-citizen + efficiency)
**Build:** Store `ETag`/`Last-Modified` per URL; send `If-None-Match`/`If-Modified-Since` on
re-fetch; on `304 Not Modified` reuse cached content and make no full re-download.

**Expected observation:** a test re-fetching a URL that returns `304` → no full body transfer, cached content returned, logged `not-modified: <url>`.
**Most likely failure:** cache never invalidated → stale content served forever. **Counter:** cache carries the stored timestamp; entries older than `WEB_SKIP_OLDER_THAN_DAYS` (`config.py`, exists) force a full re-fetch. Test asserts a stale entry re-downloads.
**Gate:** G-EDIT.

---

## Front 2 — Respect the signals, back off, disengage (never route around)

*(Front 2's fourth capability — recognizing prompt-injection content on the way in — is
detection that feeds the write-time tagging, so it lives in Part 2 as M2.4. Here: the three
"a host is pushing back, stop pushing" behaviors.)*

### M2.1 — 429 / soft-block / slowdown → back off, then disengage the host
**Build:** Consumes M1.3's helper. On repeated 429 or a detected soft-block (e.g. sudden
content-length collapse, a block page), Reaper **stops fetching that host for the session**
and logs `host-unwelcome: <host>`. It does **not** switch UA, add a proxy, or otherwise try
to look different — that would be routing around the boundary, which is out of scope.

**Expected observation:** a test where a host returns 429 twice → third request to that host is not attempted; a `host-unwelcome` record exists. A request to a *different* host proceeds.
**Most likely failure:** the disengage is global, halting all research. **Cause:** flag not host-scoped. **Counter:** flag keyed on netloc; test asserts other hosts unaffected.
**Gate:** G-EDIT.

### M2.2 — CAPTCHA wall → stop, surface to Master, never solve, never route around
**Build:** Detect a CAPTCHA/challenge page (heuristics: known challenge markers — reCAPTCHA/hCaptcha/Cloudflare-challenge signatures in the returned HTML). On detection: **do not**
solve, **do not** call any solving service, **do not** retry with a different identity — stop
for that host, surface a flag to Master (via the Harbinger alert path if wired; else a logged
`captcha-wall: <host>` the executor confirms surfaces). Recon: no CAPTCHA handling exists today.

**Expected observation:** a test feeding a canned reCAPTCHA HTML page → `fetch_page` returns `None` with reason `captcha-wall`, makes **no** further request to that host, and emits a Master-facing flag. `grep -rniE "captcha.*solv|2captcha|anticaptcha|solver" modules/reaper/` → **0 matches** (the avoid-don't-solve line is real, not just intended).
**Most likely failure:** CAPTCHA HTML misclassified as normal content and stored. **Cause:** detection markers too narrow. **Counter:** the test corpus includes 3 challenge-page variants; all three must be caught.
**RECON NEEDED:** is the Harbinger alert path reachable from Reaper's context? Check `grep -rn "harbinger\|alert\|notify" modules/reaper/` and the registry — if not reachable, the flag is a structured log line Master's briefing consumes; confirm which.
**Gate:** G-EDIT.

### M2.3 — Honeypot / bot-trap → recognize "this site refuses automation," disengage + flag
**Build:** Recognize trap signals (links hidden via CSS `display:none`/`visibility:hidden`
that only a scraper would follow; `nofollow`-trap patterns; forms/pages served only to
non-human clients). On recognition, Reaper reads it as *"this site does not want automated
access"* and **disengages** — the ethical inversion of the brief's original "recognize and
evade." Flag to Master.

**Expected observation:** a test page with a `display:none` honeypot link → Reaper does **not** follow it, logs `honeypot-detected: <host>`, and disengages the host. A normal page with normal hidden-nav is not false-flagged (test includes a benign hidden-menu case that must NOT trip).
**Most likely failure:** false positives on legitimate hidden UI (accessibility menus, dropdowns) → over-disengagement. **Cause:** naive `display:none` = trap. **Counter:** require multiple corroborating signals (hidden **and** off-DOM-flow **and** anchor to a crawl-trap pattern); benign-case test guards it.
**Gate:** G-EDIT.

---

## Front 3 — Professional information gathering (be excellent at the job)

### M3.1 — Harden the spoofable source-tier (reputation is one input, never the whole trust)
**Current:** `evaluate_source` (`reaper.py:120-152`) matches domain suffix (`:137-152`), so
`*.github.io`, `*.edu` user dirs, gists, etc. inherit **Tier 1 / 0.7**. Recon flagged this as a
"looks governed but isn't": the tier reflects *domain reputation*, never *whether the content
is attacker-controlled*.

**Build (Part-1 half — classification only):** Refine `evaluate_source` so user-content
subdomains/paths under a reputable suffix are **not** auto-Tier-1 (e.g. `github.io`,
`*.github.com` raw/gist, `medium.com` are user-content → Tier 3, not 1). Reputation becomes a
*ranking* signal for fetch-order, decoupled from the *trust* written to memory. **The trust
cap itself lands in Part 2 M4.1** — this move only stops the classifier from over-crediting.

**Expected observation (PATCHED — red-team F6: the original example was factually wrong; `github.io` is already Tier 4/0.1, not 0.7. The real high-trust vector is `gist.github.com`, which matches the `.github.com` suffix → Tier 1/0.7):** a test asserts `evaluate_source("https://gist.github.com/evil/x")["tier"]` is **not** 1 (is 3), that `raw.githubusercontent.com` is not Tier 1, and that a genuine `arxiv.org` / `*.gov` doc **is** still Tier 1. (Verified live pre-patch: `gist.github.com` → tier 1/0.7; `evil.github.io` → tier 4/0.1; `medium.com` → tier 3/0.3 already.)
**Most likely failure:** legitimate content on `gist.github.com` / `*.github.com` user paths gets under-ranked and missed. **Cause:** blanket demotion. **Counter:** demotion affects *trust*, not *fetch eligibility* — user-content is still fetched and read, just not written at high trust (Part 2). Test asserts a `gist.github.com` page is still fetched.
**Gate:** G-EDIT.

### M3.2 — Extraction quality (clean content out of messy pages)
**Current:** BeautifulSoup strips script/style/nav/footer/header/aside/form/iframe
(`reaper.py:954-956`), collapses whitespace (`:958-959`). Serviceable, but no main-content
detection → boilerplate/menus leak in; JS pages yield nothing (M1.4 fixes the latter).

**Build:** Add main-content extraction (readability-style: prefer `<article>`/`<main>`/high
text-density blocks) so stored content is the article, not the chrome. Preserve source URL +
title for citation (M3.5).

**Expected observation:** a test on a messy news page → extracted text excludes nav/related-links/cookie-banner and includes the article body; length within `WEB_MAX_ARTICLE_CHARS` (`config.py:219`).
**Most likely failure:** readability strips legitimate content on non-article pages (docs, forums). **Cause:** article-heuristic misfires. **Counter:** fall back to the current strip-based extraction when no clear main-content block is found; test covers a forum-thread page.
**Gate:** G-EDIT.

### M3.3 — Close the SearXNG silent-failure class (log every rung switch; alert when a rung never serves)
**Current (recon):** the serving rung is observable via `_served_by` (`reaper.py:567-568`) +
`observed_span` (`:549-561`) — **but** rung failures are `print()`-only (`:571, 616, 620`), not
`logger`; SearXNG defaults **disabled** (`searxng_enabled=False`, `reaper_settings.py:23`), so
the "primary" is silently skipped; and there is **no alert** when an enabled rung consistently
fails. This is the original "SearXNG dead for months, silently served by DDG" class, only
half-closed.

**Build:** (a) Route every rung attempt + failure + switch through `logger` (structured:
`{rung, available, served, result_count, latency_ms}`) — not `print`. (b) Track a per-rung
served/attempted counter; when an **enabled** rung is attempted ≥K times and serves 0, emit a
Master-facing alert (`rung-dead: searxng`). (c) Surface `searxng_enabled` state at boot so a
disabled primary is visible, not silent.

**Expected observation:** a test with SearXNG enabled but returning 0 for K attempts → a `rung-dead: searxng` alert fires; the log shows each switch to DDG. With SearXNG disabled, boot log states `searxng: disabled` explicitly. `grep -n "print(" reaper.py` in the cascade region → replaced by `logger` calls.
**Most likely failure:** alert fires on transient 0-results (a genuinely empty query), crying wolf. **Cause:** counter doesn't distinguish "rung errored" from "query legitimately empty." **Counter:** count only attempts where *another* rung served the same query (proves the rung is broken, not the query). Test asserts a legitimately-empty query does not trip `rung-dead`.
**Gate:** G-EDIT.

### M3.4 — Reddit primary / YouTube subtitle path (confirm state, fix the overclaim)
**Current:** Reddit `.json` is tried first for Reddit queries (`reaper.py:500-519`); YouTube is
**subtitle-download only** — Whisper is NOT built (`reaper.py:1597` prints "needs Whisper —
Phase 5"). Docs' "yt-dlp/Whisper" overstates.

**Build:** Keep Reddit `.json` primary (working). For YouTube: either wire Whisper as an
explicit new capability *or* correct the docs/tool description to "subtitle transcription only."
`RECON NEEDED:` **ask Master** — is Whisper transcription in scope for this mission, or is
correcting the overclaim sufficient? Do not silently build a Whisper pipeline unasked.

**Expected observation:** if docs-fix path → the `youtube_transcribe` tool description and CLAUDE.md no longer imply Whisper; a video with no subtitles returns a clear `no-subtitles-available` (not a silent None). If build path → a subtitle-less video is transcribed via Whisper (separate sub-plan).
**Most likely failure:** a video with auto-captions vs. none is not distinguished → user thinks transcription failed. **Counter:** distinct return states for "no subtitles" vs. "fetch error."
**Gate:** G-EDIT (+ separate gate if Whisper build is approved).

### M3.5 — Dedup + citation + conflict-flagging (conflicts flagged, not averaged)
**Current:** research pipeline dedups by URL (`reaper.py:1141-1149`) and sorts by tier
(`:1157-1158`). No cross-source conflict handling.

**Build:** (a) Dedup by normalized URL **and** near-duplicate content (same story syndicated).
(b) Every stored item carries its citation (URL + title + fetched-at — already in metadata,
surface it in content). (c) When two sources on the same topic **disagree** on a fact, store
both with a `conflict` flag and both citations — **never** average or silently pick one.

**Expected observation:** a research run over two sources stating contradictory facts → both stored, each cited, tagged `conflict`; the returned summary presents both, not a blended middle. A syndicated duplicate is collapsed to one.
**Most likely failure:** conflict detection needs semantic comparison → the local model mis-detects. **Cause:** relying on `phi4-mini` (`config.py:273`) for fact-equality. **Counter:** scope conflict-flagging to explicit contradictions the model is reliable on (numeric/date disagreements); mark subtler semantic conflicts as `RECON NEEDED` for a later pass rather than over-promising. Be honest about the model ceiling.
**Gate:** G-EDIT.

---

## Abort conditions (stop and flag; do not improvise)

- **A1 — baseline count drift.** PF-3 not `107 tests` / any collection error → recon is stale; stop, re-recon before editing.
- **A2 — Brave removal touches another module.** M1.0 counter finds a live `brave_search_api_key` consumer outside Reaper/tests → stop; the change now alters another module's contract.
- **A3 — any move requires disguise.** If a move can only pass by adding UA rotation back, a proxy, fingerprint spoofing, or a CAPTCHA solver → stop; that's out of scope by design, not a gap to fill.
- **A4 — reading drifts toward acting.** If a page requires auth, a form submit, or any non-GET to read → stop; Reaper reads public content only (Part 2 G4).
- **A5 — Playwright host action ungated.** M1.4 needs `playwright install` (a browser download) without Master's approval → stop (G1.4).
- **A6 — benchmark floor.** End-state benchmark < 78.18% → stop before declaring done (regression gate).

---

## Verification runs (built ≠ done; live-verified = done)

| # | When | Run | Pass looks like |
|---|---|---|---|
| V1 | after M1.0 | `grep -rniE "brave" modules/reaper/ tests/` + full reaper collection | 0 brave matches; **84 tests** collected, 0 errors |
| V2 | after M1.1–M1.5 | new Front-1 tests | honest UA fixed; robots disallow blocks a fetch; 429 backs off then skips; Playwright renders a JS page (or A5 flagged); 304 reuses cache |
| V3 | after M2.1–M2.3 | new Front-2 tests | host-unwelcome disengages one host only; canned CAPTCHA → no solve, flag; honeypot link not followed, benign hidden-nav not false-flagged |
| V4 | after M3.1–M3.5 | new Front-3 tests | github.io → tier 3; readability extracts article body; SearXNG-dead → `rung-dead` alert; conflict → both stored + flagged, not averaged |
| V5 | before "done" | targeted suite: the new tests + `tests/test_reaper_*` (minus deleted brave) + `test_decision_loop.py` if the adapter changed | all green on the **new** code paths (not a bypassed path); no regression in routing |
| V6 | before "done" | end-state benchmark | ≥ 78.18% overall (Phase-0 floor); perfect/strong tiers not regressed |
| V7 | at commit | `git status` + `git log` | only intended files staged; commit message describes the reframe; **no push** (V7 fails if a push occurred) |

---

## Gates & Autonomy Ledger — Part 1

Part 1 is capability + cleanup; it opens **no** new autonomy (the autonomy gates are Part 2).
But every move writes to Shadow's own code, and M1.4 touches the host — those wear gates.

| Gate | Move(s) | What goes wrong ungated | The gate (wired, not named) | Earned-by |
|---|---|---|---|---|
| **G-EDIT** | M1.0–M3.5 (all edits) | a bad edit to Reaper ships silently; Shadow's own code changes without review | targeted tests green on the **new** path (V2–V5) → Master reviews the diff → commit, **never push** | Master has seen and approved the exact diff; tests pass on the changed code |
| **G1.4** | M1.4 Playwright | `playwright install` downloads a browser (host action, network, disk) autonomously | install is **not** auto-run; executor surfaces the exact command; Master runs/approves it (PF-2 blocks M1.4 until then) | Master approved the browser install |
| **G3.4-doc** | M3.4 | silently building a Whisper pipeline unasked = scope creep | Whisper build is a **separate approved sub-plan**; default is doc-correction only | Master answered the M3.4 RECON NEEDED "build Whisper? y/n" |
| **G-CAPTCHA** | M2.2 | a CAPTCHA-solver dependency creeps in "to be thorough" | the plan **forbids** solvers; V3 asserts `grep` for solver deps returns 0 | permanent — never earned open |
| **G-DISGUISE** | M1.1, M2.1–M2.3 | disguise/evasion (rotation, proxy, fingerprint) re-enters under a "reliability" justification | abort A3; V2 asserts fixed UA and no spoofing code | permanent — never earned open |

**Note:** the load-bearing autonomy gate — the LIVE, ungated `standing_research` job
(`main.py:673-675`) and the autonomous `web_fetch` full-page write — is **G1/G2 in Part 2**.
Part 1 does not touch it; Part 2 closes it. Do not mark Reaper "done" on Part 1 alone: an
excellent gatherer that still ingests poison autonomously has not finished the mission.

---

## Red-team focus (dispatched separately to a fresh attacker)

Tell the attacker to hunt: (a) any move that can only pass by re-introducing disguise/evasion
(a smuggled proxy, UA rotation, fingerprint spoofing, a CAPTCHA solver); (b) the Brave removal
breaking another module's config contract; (c) a "rung-dead" alert that cries wolf or, worse,
stays silent when SearXNG is genuinely dead (the failure class this front exists to close);
(d) a fetch path that reaches non-public/auth-required content (reading→acting drift); (e) any
vague expected-observation an executor couldn't check blind.

---

## Red-team Pass 1 — the attack that landed, and the patch (SUCCESS point 7)

Attacker: `wargames/red-team/reaper-part1.md` (fresh subagent, read-only, blind executor).
**Verdict it reached:** the disguise-vs-access-control **spine held** — no move could be made to
pass only by re-introducing a proxy, UA rotation, fingerprint spoofing, or a CAPTCHA solver
(attacker confirmed M1.4/M1.3/M2.2 forbid it and the greps enforce it). But the plan could **not
be executed as written**: 12 breaks, one CRITICAL. Each is now patched.

- **F4 (CRITICAL) — M1.0 "cleanup" ships a plaintext-secret leak.** *Patched inline* in M1.0: the
  `sources.py:167` routing entry is now in the Build list and must land in the same commit; the
  failure mode is rewritten from a phantom ImportError to the real `extra="allow"` +
  `model_dump_json()` redaction leak; a redaction test is added to Expected observation.
- **F1 (HIGH) — PF-3 asserted 107 for a six-file command that collects 104.** *Patched inline* in
  PF-3: command now lists all seven files (107), with the live-endpoint caveat.
- **F3 (HIGH) — M1.0 missed the `sources.py:167` cross-package consumer; A2 mis-fired.** *Patched
  inline* in M1.0: routing entry added to Build; A2 re-scoped to fire only on a *functional*
  consumer, not the expected routing line.
- **F6 (HIGH) — M3.1 asserted a tier the code doesn't produce (`github.io` is 0.1, not 0.7).**
  *Patched inline* in M3.1: example corrected to `gist.github.com` (the real 0.7 vector); recon
  digest corrected too (see below).
- **F5 (HIGH) — M3.3 "route through `logger`" but reaper.py has no logger (63 `print()`s) and no
  reachable Master-facing alert sink; the flagship `rung-dead` alert was graded on intent.**
  *Patch:* M3.3 gains a prerequisite sub-move **M3.3a — instrument reaper.py**: add
  `logger = logging.getLogger("shadow.reaper")` and replace the cascade-region `print()`s with
  structured `logger` calls. **RECON NEEDED (was falsely assumed):** is a Harbinger alert sink
  reachable from Reaper's context? Exact check: `grep -rnE "harbinger|alert|notify|decision_queue" modules/reaper/ modules/shadow/standing_tasks.py` and inspect the registry — if no sink is
  reachable, building one (or routing through the standing-task/briefing path) is part of M3.3,
  not an assumption. **Verification now asserts behavior, not construction:** the M3.3 test must
  drive a fake "enabled SearXNG serves 0 while DDG serves" scenario and assert the alert **object
  reaches the sink** (a spy on the sink receives it), not merely that it was built. Until a sink
  is proven reachable, M3.3 is **blocked** on that RECON NEEDED (new abort A7).
- **F7 (HIGH) — abort A4 (reading→acting) was named but never wired into any fetch path.** *Patch:*
  new move **M1.2a — fetch-path access-control guard** (belongs with M1.2): in `fetch_page`
  (`reaper.py:914-948`), (i) set `allow_redirects=False` and inspect each hop — do **not** follow a
  redirect that crosses origin into an auth host; (ii) treat `401`/`403` and known login/paywall
  markers (`<input type=password>`, `wp-login`, `accounts.google`, Cloudflare-login, paywall
  meta) as **stop + do-not-store**, reason `access-controlled: <host>`; (iii) never send
  credentials/cookies to obtain content. *Obs:* a test serving a 302→auth-host and a 200 login-wall
  both return `None` with `access-controlled`, store nothing, and issue no non-GET. This is A4's
  detector; A4 now has a wired check, not just a name.
- **F8 (MED) — M1.4 buildable with the browser binary absent.** *Patch:* M1.4 adds a **runtime
  probe in code** — the render path calls `chromium_executable_path().exists()` (or catches the
  launch error) and, if absent, returns a clear `render-unavailable` result and falls back to plain
  fetch; the gate is in the code, not only in PF-2. *Obs:* a test with the binary path stubbed
  missing → render path returns `render-unavailable`, does not crash, falls back.
- **F9 (MED) — M1.4 render fork trigger vague ("non-boilerplate", "script-dominated").** *Patch:*
  deterministic trigger: escalate to render iff **(a)** plain-`requests` `soup.get_text(strip=True)`
  length < 200 chars **OR (b)** `sum(len(s.string or "") for s in soup("script")) / max(len(response.text),1) > 0.60` (script bytes are >60% of body). Both are computable and testable; no
  "non-boilerplate" dependency on M3.2.
- **F10 (MED) — M2.2 CAPTCHA flag graded PASS though the alert path may not exist.** *Patch:* same
  fix as F5 — M2.2's "Master-facing flag" resolves through the M3.3a sink once RECON NEEDED settles
  it; until then the pass condition is "returns `None` + `captcha-wall` reason + **no** solver call"
  (behavior that exists), and the Master-alert assertion is deferred to the sink being wired (A7).
- **F11 (LOW/MED) — M2.1 "content-length collapse" had no numeric trigger.** *Patch:* concrete rule
  — maintain a rolling median body size per host; a response whose body is **< 40% of that host's
  running median AND matches a block-page signature** (or is < 512 bytes of non-boilerplate) counts
  as a soft-block. First two responses per host never trip it (no baseline yet).
- **F12 (LOW) — M1.5 304 cache reuse re-served content with no re-inspection.** *Patch:* on a `304`
  replay, before returning cached content, re-run `ALWAYS_SKIP_PATTERNS` and (once Part 2 lands) the
  M2.4 instruction-scan on the cached body; a cached entry carries its original tags/flags so a
  poisoned-but-fresh body is not re-served unmarked.
- **F2 (MED) — V1 post-delete count.** *Patched inline*: with PF-3 now the seven-file 107 baseline,
  V1's "84" (107−23) is consistent.

**New abort added from the pass:**
- **A7 — no reachable alert sink.** If the M3.3a RECON NEEDED resolves to "no Master-facing alert
  sink reachable from Reaper," then M3.3's `rung-dead` alert and M2.2's CAPTCHA flag cannot be
  *delivered*; STOP and flag — do not grade F5/F10 green on a constructed-but-undelivered alert
  (that is the exact "looks governed but isn't" the attacker caught).

**Recon correction (the digest fed the plan a wrong fact):** `wargames/recon/reaper.md` §7.2/§6
stated `github.io` inherits 0.7 — it is actually Tier 4/0.1; the real 0.7 vector is
`gist.github.com` (`.github.com` suffix). And the scheduler line is `main.py:674-675`, not
`673-675`. Both corrected in the digest.
