# RED-TEAM PASS 3 — Reaper Part 2: Injection Discipline + Tier-2 Gate (confirming attack)

**Attacker:** fresh instance, pass 3, blind executor of the TWICE-patched
`wargames/plans/stealth-part2-injection-gate.md`.
**Mandate:** passes 1 and 2 each found a CRITICAL in the autonomy gate (a
different uncovered autonomous write path each time). The plan now claims a
TRIPLE guard: (a) `add_job` not registered, (b) early-return in
`_run_standing_research`, (c) `_autonomous`→`store_in_grimoire=False` on
`web_fetch`. My one job: is the gate finally airtight, or does a fourth
autonomous Reaper→Grimoire write path slip through?
**Method:** read-only (grep, Read, `python -c`). Every claim carries `file:line`,
re-traced from source this pass. The plan is UNAPPLIED (`grep
autonomous_research_enabled modules/ config/` → nothing; `tagging.py` absent).
I attack the *route*, not applied code.

---

## GATE COMPLETENESS VERDICT: **HOLE FOUND** (CRITICAL)

A **fourth** autonomous Reaper→Grimoire write path exists that passes through
**none** of the three claimed guards, and neither the plan nor either prior
red-team pass ever names it: **the async task queue's post-completion Grimoire
persistence** — `AsyncTaskQueue._store_result_in_grimoire`
(`modules/shadow/async_tasks.py:339-368`), which writes **every** completed
background task's result into Grimoire at **`trust_level=0.8`, untagged,
`source_module="shadow"`**, with **zero** consultation of
`autonomous_research_enabled` and **no** route through `untrusted_memory_kwargs`.

`grep -in "async_task|_store_result|deferred|_should_run_async|_LONG_RUNNING|submit_task"`
against the plan → **nothing**. Against pass-1 and pass-2 red-team files →
**nothing**. This path is invisible to all three documents.

---

## Findings table

| # | Plan-line quote | How it fails | Sev |
|---|---|---|---|
| **P3-1** | G1: enforcement is "**TRIPLE across every autonomous write path**" — (a) `if` around `add_job`, (b) early-return in `_run_standing_research`, (c) `_autonomous`-flag gate on `web_fetch` persistence. "an orchestrator-chosen fetch does not persist while the gate is closed." | The three guards cover the scheduler firing and the `web_fetch` *inner* `fetch_page` write. They do **not** cover the async worker's **separate** post-completion write. When the orchestrator backgrounds a Reaper tool (`_step5_execute`, `orchestrator.py:5226` → `submit_task`, `:5229`), the async worker persists the *result* via `_store_result_in_grimoire` (`async_tasks.py:270,339`) at **`trust_level=0.8, confidence=1.0`** (`async_tasks.py:358-359`), `source="async_task_result"`, `source_module="shadow"` — a write the plan's `untrusted_memory_kwargs` helper never touches and `autonomous_research_enabled` never gates. `web_search` and `youtube_transcribe` are in `_LONG_RUNNING_TOOLS` (`orchestrator.py:848-851`), so they route async **by default** (any `source != "benchmark"`). "TRIPLE across *every* autonomous write path" is false: this is a fourth path. | **CRITICAL** |
| **P3-2** | M4.3b, orchestrator side: "inject an `_autonomous` flag into the tool params before dispatch … the loop already injects `_background` into step params." | Even a perfectly-implemented M4.3b is **defeated by the async detour**. The submit call strips every underscore-prefixed key before enqueue: `params={k: v for k, v in params.items() if not k.startswith("_")}` (`orchestrator.py:5232`). So the injected `_autonomous` (and `_background`) **never reach the async worker or the Reaper adapter** on the backgrounded path. M4.3b's gate is a no-op for any Reaper tool that goes async — and `web_search`/`youtube_transcribe` always do. The gate lands only on the *synchronous* dispatch of `web_fetch`. | **HIGH** |
| **P3-3** | Front 4 / A3: "Route ALL **six** write paths through [`untrusted_memory_kwargs`] … A single untagged path is a full Front-4 failure." + guard `test_no_untagged_reaper_remember`. | There is a **seventh** Reaper-content write the six-path inventory misses: `async_tasks.py:355`. It is labeled `source_module="shadow"` (not `"reaper"`), so the plan's guard — which keys off "`source_module`/`source` marks it a Reaper write" (plan `:221-223`) — **cannot see it even by grep**, exactly the mis-scoping the pass-1 HIGH was about, one file further out (`async_tasks.py`, not `standing_tasks.py`). Scraped `web_search` content lands in Grimoire tagged `trust_level=0.8`, no `safety_class`, no instruction flag. Front 4's bar ("scraped content above untrusted = failed") is breached on this path at **0.8**. | **HIGH** |
| **P3-4** | Red-team focus **(2)**: "find any way `standing_research` still fires with the flag False (a second scheduler, a direct `run_task` call, the job added elsewhere)." | The plan (correctly) fixed `run_task`. But the *Proactive Initiative Engine* is a second, independent autonomous trigger source the plan never considers. `ProactiveEngine.idle_work_cycle()` (`proactive_engine.py:378-397`) and `_build_default_triggers` (`:678-707`) emit tasks `("reaper", "Check technology watch list for updates")` with `source="idle_cycle"`/`"proactive"`. Both are `not in ("user","telegram","discord")` → autonomous. Nothing routes these through `autonomous_research_enabled`; they flow into `_step5_execute` → async queue → `_store_result_in_grimoire` @0.8. A second autonomous door into the same ungated write. | **MED** |
| **P3-5** | G1 earned-by / "supervised on-demand" premise: a real user in the loop makes a `web_fetch` persist. | The deferred-graph leg re-plans with a **hardcoded `source="autonomous"`** (`async_tasks.py:246`, `run_deferred_through_graph(..., source="autonomous")`). So even a *user-initiated* task that gets backgrounded is re-executed and persisted under an **autonomous** source — losing the "human in the loop" provenance the gate relies on. The stored result at 0.8 carries no signal that it began as a user request. Provenance-collapse on the async path. | **LOW** |

---

## Single worst break — P3-1 (CRITICAL): the async task queue is the fourth ungated autonomous Reaper→Grimoire write

**The plan gated the scheduler (pass-1), then the `web_fetch` inner write
(pass-2), and still left the async worker's post-completion Grimoire write wide
open — the write that fires whenever ANY Reaper long-running tool is
backgrounded.**

### The path, end to end (verified file:line)

1. A task reaches `_step5_execute` with a Reaper tool step. Source can be a real
   user OR an autonomous source (deferred graph `source="autonomous"`,
   `async_tasks.py:246`; proactive `source="proactive"`/`"idle_cycle"`,
   `proactive_engine.py:279,393`).
2. `_should_run_async(tool_name, params, classification, source)`
   (`orchestrator.py:857-892`) returns **True** because
   `tool_name in _LONG_RUNNING_TOOLS` (`orchestrator.py:848-851` =
   `{"web_search", "web_scrape", "security_scan", "full_audit",
   "youtube_transcribe", "benchmark_run"}`) — `web_search` and
   `youtube_transcribe` are Reaper tools and are **always long-running**. The
   only exempt source is `"benchmark"` (`_SYNCHRONOUS_SOURCES`,
   `orchestrator.py:855`).
3. `submit_task(...)` enqueues, **stripping underscore params**
   (`orchestrator.py:5232`) — so any M4.3b `_autonomous` flag is gone.
4. The worker (`_worker_loop`, `async_tasks.py:209-295`) executes: item-13 wiring
   (live: `main.py:291`, `orchestrator.py:676`) routes through
   `run_deferred_through_graph` (Cerberus plan-gate + dormancy apply) — but that
   gate only checks **DENY / non-routable**; `autonomous_research_enabled` is
   **not** a plan-gate verdict. Reaper is routable, the plan is not DENIED, so a
   module runs and returns scraped content.
5. **Unconditionally** — both the graph branch and the direct-execute branch —
   `self._store_result_in_grimoire(task_id, task.description, result_dict)`
   (`async_tasks.py:270`) fires:
   ```python
   grim.remember(
       content=json.dumps(result_dict, default=str),   # includes scraped result content
       source="async_task_result", source_module="shadow",
       category="task_result",
       trust_level=0.8, confidence=1.0,                 # ← near-official trust, untagged
       tags=["async_task", "task_result", task_id[:8]],
       metadata={"task_id": task_id, "description": description},
       check_duplicates=False,
   )
   ```
   (`async_tasks.py:354-365`). No `safety_class`, no instruction flag, no trust
   cap, no `autonomous_research_enabled` check.

### Why the three guards miss it

- **(a) `add_job` gate** — governs only the 12h scheduler timer. Irrelevant; the
  async queue is a different mechanism.
- **(b) `_run_standing_research` early-return** — governs only that one function.
  The async worker never calls it.
- **(c) `_autonomous`→`store_in_grimoire=False`** — governs only `fetch_page`'s
  *inner* `remember` inside `ReaperModule.execute`. The async worker's
  `_store_result_in_grimoire` is a **separate, later** write of the returned
  result, outside `reaper_module.py` entirely. Even if `fetch_page` persisted
  nothing, the worker still persists the result at 0.8. And per P3-2 the
  `_autonomous` flag is stripped at submit anyway.

### "Absent flag = fail-open" (answering the decisive sub-questions)

- **Does `_autonomous` reach `reaper_module.execute` for a backgrounded
  `web_fetch`? NO** — stripped at `orchestrator.py:5232`. Absent flag →
  `params.get("_autonomous")` is falsy → the adapter's
  `not (autonomous and not enabled)` evaluates **True** → `store_in_grimoire`
  stays **True** → persists. **Fail-OPEN.** The plan's M4.3b is default-absent =
  treated-as-user = persists, exactly the failure mode the prompt asked me to
  check.
- **Can `research()`/`run_standing_research()` (full pages @ up to 0.7) be reached
  autonomously outside all three guards?** `reaper.research()` (`reaper.py:1109`,
  writes @ up to 0.7 at `:1192`/`:1217`) is called ONLY by
  `run_standing_research` (`reaper.py:1246`) and the `__main__` demo (`:283-286`)
  — both behind guard (b) once the scheduler `_run_standing_research` is gated.
  So the full-page pipeline itself is contained. **The leak is the async
  wrapper's 0.8 write of the tool result, not `research()`.** Confirmed the
  full-page 0.7 pipeline is NOT independently reachable.

### Reachable with the gate CLOSED and invoked autonomously? YES

`autonomous_research_enabled=False` is consulted **nowhere** in
`async_tasks.py`, `proactive_engine.py`, or the submit path
(`grep -in "autonomous_research" modules/shadow/async_tasks.py
modules/shadow/proactive_engine.py` → nothing). An autonomous source (deferred
graph or proactive trigger) backgrounds a Reaper `web_search`, the flag reads
False the entire time, and scraped web content enters permanent Grimoire memory
at **trust 0.8**. This is worse than the pass-1 leak (0.3 snippets, manual
command) and comparable-to-worse than pass-2 (needs no user, fires on any
backgrounded Reaper tool, lands at 0.8 not merely ≤0.3-capped-if-tagged).

**The existing test suite proves this is the LIVE path, not a theoretical one:**
`tests/test_async_tasks.py` uses `reaper` + `web_search` as its canonical
example throughout (`:85,116-117,125-126,131,146,156,194,204-205,...`).
`_store_result_in_grimoire` is exercised on exactly this flow.

---

## Sub-question 4 — would the plan's gate tests FAIL on a regressed guard, or do they mock past it?

Partly mock past it. The plan's Front-5 tests are scoped to
`_run_standing_research` / `run_task` / `web_fetch` and would catch a regression
**of those three guards**. But **none of the plan's tests touch the async queue
path** — there is no test asserting "a backgrounded Reaper tool does not persist
at 0.8 while the gate is closed." So the gate could be fully "green" on all plan
tests while P3-1 leaks. The plan's guard `test_no_untagged_reaper_remember`
greps `reaper.py` + `standing_tasks.py` only (plan `:219-227`) — it never reads
`async_tasks.py`, so it would pass on a broken (untagged, ungated) fourth path.
The tests would **not** fail on this regression because the regression is outside
their field of view.

---

## Pass-2 HIGH/MED sanity-check — did the earlier fixes hold?

- **Helper preserves confidence (pass-2 HIGH) — HOLDS as a plan claim.** Plan
  `:159-179` now carries `confidence=confidence` and `check_duplicates=...` as
  PRESERVED passthrough; `test_helper_preserves_confidence_and_dedup` (plan
  `:184-186`) pins the exact regression. The five current call sites do set
  confidence (`reaper.py:991,1196,1221,1381,1628` — verified). Correct.
- **Detector adapts `InjectionResult` (pass-2 MED) — HOLDS.**
  `PromptInjectionDetector.analyze(input_text, source, request_history) ->
  InjectionResult(score, flags, action)` (`injection_detector.py:94-159`);
  `UNTRUSTED_SOURCES` already contains `"reaper_scrape"` (`:74`); thresholds
  `>0.7`/`>0.4` (`:146-149`). The plan's wrapper `r.action in ("block","warn") or
  r.score >= 0.5` + `source="reaper_scrape"` (plan `:79-84`) correctly maps the
  shape and passes the required `source` arg. Correct. (Note: the detector still
  does **no** normalization today — `text_lower = input_text.lower()`,
  `:116`; the plan owns adding NFKC/zero-width strip + the
  `test_normalization_preserves_existing_verdicts` regression, plan `:90-96` —
  correctly a plan deliverable, not a pre-existing hold.)
- **The 3 standing-tasks test fork (pass-2 MED) — HOLDS, slightly under-counted.**
  Plan `:309-322` names `test_standing_tasks.py:130` (job_ids) and `:187-205`
  (run_task success/write) and mandates `grep -rn "standing_research" tests/` to
  catch all. Verified those assertions exist. The grep-all also catches `:269`
  and `:283` (two more `standing_research` assertions the prose doesn't
  enumerate) — so the fork's *instruction* is sufficient even though its
  *enumeration* misses two. Acceptable; the grep-all rule saves it.

---

## What I attacked hardest and could NOT break

- **The scheduler double-guard (pass-1 fix).** `_run_standing_research` and
  `run_task` are the only two callers (grep-confirmed: `add_job` `:78`, dict
  `:114`); guarding both closes every entry to that function. Dead as scoped.
- **A second scheduler / hidden `_run_standing_research` caller.** Exactly one
  `StandingTaskScheduler` construction (`main.py:674`); no other invoker. None.
- **`research()` / full-page 0.7 pipeline reached autonomously.** Only via
  `run_standing_research` (guarded) or `__main__` (not a runtime path). Contained.
- **Router-facing Reddit writing autonomously.** The adapter's
  `reddit_search_json`/`reddit_monitor` call `search_reddit_json` /
  `monitor_subreddit_json` (`reaper_module.py:153,169`), which **fetch and
  return** — they do NOT write. The write at `reaper.py:1377` is inside
  `_store_reddit_post`, reachable only via the `_reddit_search` pipeline
  (`:1341,1441`), which the router does not expose. So Reddit tools via the
  router don't persist. Held (matches recon).
- **The write-side trust cap.** `min(reputation, UNTRUSTED_WEB_TRUST)` genuinely
  caps 0.7→≤0.3 on the paths that go through the helper. Sound — the leak is the
  paths that DON'T go through it (P3-1/P3-3), not the cap arithmetic.

---

## Verdict

The two prior CRITICALs are genuinely closed **as scoped**: the `run_task` back
door is dead, and the `web_fetch` inner `fetch_page` write is gated by M4.3b (on
the *synchronous* dispatch). But the gate is **not airtight** — a fourth
autonomous Reaper→Grimoire write path slips through, and it is the same failure
class each pass keeps rediscovering one layer further out:

1. **CRITICAL (P3-1):** `AsyncTaskQueue._store_result_in_grimoire`
   (`async_tasks.py:339-368`) persists every backgrounded Reaper tool's result
   at **`trust_level=0.8`, untagged, `source_module="shadow"`**, ungated by
   `autonomous_research_enabled` and outside `untrusted_memory_kwargs`.
   `web_search`/`youtube_transcribe` are always-long-running
   (`orchestrator.py:848-851`), so this fires by default whenever a Reaper tool
   is backgrounded — including from an autonomous source (deferred graph
   `source="autonomous"`, `async_tasks.py:246`; proactive triggers,
   `proactive_engine.py:678-707`).
2. **HIGH (P3-2):** submit strips underscore params (`orchestrator.py:5232`), so
   M4.3b's `_autonomous` flag never survives onto the backgrounded path — the
   gate is a no-op there, and **absent-flag is fail-OPEN** (treated as user →
   persists).
3. **HIGH (P3-3):** this seventh Reaper-content write is `source_module="shadow"`,
   invisible to the plan's `reaper.py`+`standing_tasks.py`-scoped guard — the
   pass-1 mis-scoping, one file further out into `async_tasks.py`.
4. **MED (P3-4):** the Proactive Initiative Engine is a second autonomous trigger
   into the same ungated write, never considered by the plan.

**Front 5 is NOT done.** The gate must either (i) force `store_in_grimoire=False`
/ untrusted-tag on the async worker's `_store_result_in_grimoire` write when the
originating tool is a Reaper web tool and `autonomous_research_enabled=False`, or
(ii) gate the *submission* of autonomous Reaper long-running tools to the queue.
The hardest path I attacked — and the one that broke — is **the async task
queue's post-completion Grimoire persistence of a backgrounded, autonomously-
sourced `web_search`**.
