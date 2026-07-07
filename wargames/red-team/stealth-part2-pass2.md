# RED-TEAM PASS 2 — Reaper Part 2: Injection Discipline + Tier-2 Gate

**Attacker:** fresh instance, pass 2, blind executor of the PATCHED
`wargames/plans/stealth-part2-injection-gate.md`.
**Mandate:** the plan was attacked once and patched (a CRITICAL gate back door,
a HIGH mis-scoped guard). Verify the fixes HOLD and hunt for seams the fixes
*opened*. I owe the plan nothing.
**Method:** read-only against the code (grep, Read, `python -c`, no pytest run).
Every claim carries `file:line`, re-traced from source this pass.

**State of the world (settled first):** the plan is UNAPPLIED. `grep
autonomous_research_enabled modules/ config/` → nothing; `_inspect_content` →
nothing; `modules/reaper/tagging.py` → absent. So I am attacking the *route*, not
applied code. PF-0 and PF-1 forks both fire (stub absent, flag absent). Good —
the plan tells the executor to create them. Nothing below depends on the plan
being half-applied.

---

## Verdict on the two pass-1 "fixes"

- **CRITICAL (gate back door) — fix HOLDS *for the paths it names*, but the fix
  is scoped to the wrong universe of firing paths.** The double-guard
  (early-return in `_run_standing_research` + `run_task` refusal) does close the
  `run_task`/`/schedule run standing_research` back door (`standing_tasks.py:110-124`
  → `main.py:577`). Those are the only two callers of `_run_standing_research`
  (grep-confirmed: `add_job` at `:78`, `run_task` dict at `:114`). **But the
  patch mistakes "the scheduler write" for "the autonomous scraped-content write."
  The highest-severity write path — on-demand `web_fetch` at full page, up to
  0.7, ungated at dispatch — is NOT `_run_standing_research` and the gate never
  touches it.** See NEW-1 (the worst break). The pass-1 fix closed the door it was
  told about and left the front gate open.

- **HIGH (mis-scoped guard) — fix HOLDS structurally but the helper the fix
  introduces is broken in three concrete ways the plan never notices.** Extracting
  `untrusted_memory_kwargs` to `modules/reaper/tagging.py` imported by both files
  is the right move and the two-file guard can now see the sixth path. But the
  helper signature the plan hard-codes (plan `:142-154`) is not
  behavior-preserving for the calls it replaces — it silently drops `confidence`
  and other fields every current call sets. See NEW-2. A "fix" that changes what
  five write paths store is a new HIGH the patch introduced.

---

## Findings table

| # | Plan-line quote | How it fails | Sev |
|---|---|---|---|
| **NEW-1** | Front 5 / G1: "Reaper autonomously pulls the web every 12h AND on manual `/schedule run` and writes scraped, possibly-poisoned content into permanent memory" — gate = "the `if` around `add_job` AND the early-return guard inside `_run_standing_research`." | The gate is scoped to `_run_standing_research`, which stores **`web_search` snippets @ 0.3** (`standing_tasks.py:236-249`). The **worse** autonomous write — the router tool `web_fetch` (`reaper_module.py:224-230`, `permission_level:"autonomous"`) → `fetch_page(url)` with default `store_in_grimoire=True` (`reaper_module.py:127`, `reaper.py:914-999`) storing the **full page at trust up to 0.7** — is reached by the orchestrator at `orchestrator.py:5254` and is **not** gated by `autonomous_research_enabled` at all. The pre-hook blocks only `SafetyVerdict.DENY` (`:5213`); the write happens *inside* fetch_page *before* the post-hook, which only sees `str(result.content)[:500]` (`:5287`). The plan's own recon §0.3/§7.6 says exactly this, then Front 5 gates only the scheduler. **The gate the mission calls "the deliverable Master cares about most" leaves the single highest-severity autonomous write path ungated.** | **CRITICAL** |
| **NEW-2** | M4.2: "`reaper.py` calls `self.grimoire.remember(**untrusted_memory_kwargs(...))`" with the helper signature `untrusted_memory_kwargs(*, content, source, category, tags, url, reputation, extra_meta, inspect_fn)` (plan `:142-154`). | The helper has **no `confidence` parameter and never emits one**, but **every** current Reaper `remember` sets `confidence`: fetch_page `=0.5` (`reaper.py:991`), research-full `=score/10.0` (`:1196`), research-summary `=score/10.0` (`:1221`), Reddit `=min(post["score"]/100,1.0)` (`:1381`), YouTube `=0.6` (`:1628`). Routing these through the helper **silently drops confidence** → Grimoire applies its default `0.5` (`grimoire.py:677`) → the relevance-derived confidence (the whole point of `score_relevance`) is erased on the two research paths, and Reddit's upvote-weighted confidence is flattened. It also drops `check_duplicates` (fetch_page/research use the default `True`; scheduler uses `False` — the helper hard-codes neither, so the scheduler write silently gains dedup it did not have). A "tag every write" refactor that quietly changes what five writes *store* is a behavior regression the plan never flags. | **HIGH** |
| **NEW-3** | M4.2 fork: "**if** capping web-scrape trust to 0.2 breaks an existing test that asserts 0.7 (e.g. a research-pipeline test) → update it … Do NOT keep 0.7." | **The fork fires on nothing.** No reaper test asserts a *stored* trust of 0.7 through a real `remember` — all mock `grimoire.remember` (`test_reaper_brave.py:23`, `test_reaper_searxng.py:41`, `test_reaper_searxng_live.py:36` set `.return_value=1`) or mock `fetch_page` wholesale (`test_reaper_mcp.py:132-140`). The `0.7` in `test_reaper_mcp.py:45` is a search *result* `source_eval`, never a stored trust. So the plan's ONE fork for "the cap breaks a test" defends a test that doesn't exist, while the cap's real risk (dropping Reddit/YouTube from their current 0.3 to 0.2 if the executor passes `reputation=0.3`) is unmentioned. Misdirected fork = an executor reassured by a green suite that never exercised the cap. | **MED** |
| **NEW-4** | M4.3 counter: "`test_run_task_refuses_standing_research_when_flag_false` … spy Reaper `execute` = 0, spy Grimoire `remember` = 0." Default ships **False**. | The firing-guard fix **breaks existing `test_standing_tasks.py` tests the plan never lists for update.** With flag False: (a) `test_scheduler_registers_all_jobs`-style assertion `assert job_ids == {"self_analysis","standing_research","grimoire_stats"}` (`test_standing_tasks.py:130`) fails — `add_job` guard drops `standing_research`; (b) `test_executes_and_stores` (`:185-200`) asserts `reaper.calls==1` and `remember.assert_called_once()` — now the early-return makes both zero; (c) `test_topic_rotation` (`:202-208`) same. The plan's fork covers only the (nonexistent, NEW-3) trust-cap test; it has **no** fork for "the gate breaks the standing-task execution suite." V1's `tests/test_*standing*` line will go red and the executor has no instruction. Three real breaks, no trigger. | **MED** |
| **NEW-5** | M4.1: "Implement `_inspect_content(text, url) -> {"instruction_like","injection_score","matched"}` as a thin wrapper that calls the shared detector." | `PromptInjectionDetector.analyze(input_text, source, request_history)` returns `InjectionResult(score, flags, action)` (`injection_detector.py:94-159`) — **not** a dict, and it has **no `instruction_like` field, no `matched` field, no `injection_score` key**. The wrapper is not "thin"; it must map `InjectionResult.score → injection_score`, synthesize `instruction_like` from a threshold, and derive `matched` from `flags`. The plan asserts "adopt the signature" as if it composes; it does not. Also `analyze()` takes a mandatory `source` arg the plan's call `inspect_fn(content, url)` never supplies. Unverified-assumption break — the reuse the pass-1 MED fix mandated does not slot in as described. | **MED** |
| **NEW-6** | M4.1: "**Normalize BEFORE matching:** strip zero-width … NFKC-fold, so `"sy​tem:"` matches `system:`." | The shared detector does **no** normalization: `analyze()` does only `text_lower = input_text.lower()` (`injection_detector.py:116`) and runs 12 raw regexes (`:43-56`). `grep unicodedata|normalize|NFKC modules/cerberus/injection_detector.py` → nothing. So the plan's own example `"sy​stem:"` evades **all 12 patterns today**, and "extend the shared detector" means editing a Cerberus file that Cerberus's own `analyze()` on `user_input` also depends on — a NFKC/zero-width strip inserted at `:116` changes Cerberus's live Step-1.5 behavior on every user input. The plan flags the *feature* (normalize) but never flags that adding it mutates a shared, orchestrator-wired detector; no regression named for Cerberus's existing injection tests. Cross-module blast radius, unmarked. | **MED** |
| **NEW-7** | Read-side / V-seam: "the returned dict does **not contain `safety_class` at all** (`grimoire.py:1142-1161`)." | Confirmed exactly (`recall()` builds the memory dict at `grimoire.py:1142-1161`; no `safety_class` key). The pass-1 MED fix correctly *documents* this — but the plan closes it only in **prose** (V-seam records it, earned-by #1 requires the Grimoire mission). There is **no test** in Part 2 that asserts "Reaper's marker is invisible on read," so nothing prevents a later reader from believing earned-by #1 is met. Pass-1 finding closed in prose, not in a test (your Priority 5). Correct as a boundary; still a latent over-claim risk. | **LOW** |

---

## Single worst break — NEW-1 (CRITICAL): the gate guards the low-severity
## write and leaves the high-severity write wide open

**The patch closed the back door the pass-1 attacker walked through, and in doing
so anchored the whole gate to `_run_standing_research` — the *least* dangerous of
the two autonomous write paths.** The scheduler write stores `web_search`
**snippets @ trust 0.3**. The on-demand `web_fetch` router tool stores the **full
page @ trust up to 0.7**, and it is `permission_level:"autonomous"`, and nothing
in the plan gates it.

**Concrete blind run-through (executor ships the patched plan exactly):**

1. Executor adds `autonomous_research_enabled=False`, double-guards
   `_run_standing_research` and `run_task`. `test_research_job_absent_when_flag_false`
   and `test_run_task_refuses_standing_research_when_flag_false` both go green.
   V-gate confirms "dormant at boot." G1 recorded "WIRED, enforcement DOUBLE."
2. The 12h timer is dormant; `/schedule run standing_research` refuses. The
   pass-1 CRITICAL is genuinely dead. The plan declares Front 5 done.
3. Now a *normal* task runs through the orchestrator: user (or an autonomous
   source — `orchestrator.py:4982` classifies non-user sources as autonomous)
   asks something that the router/planner answers with a `web_fetch` step.
   Nothing about that step consults `autonomous_research_enabled`.
4. `orchestrator.py:5207` pre-hook: `web_fetch` is `autonomous`, not `DENY` →
   passes. `orchestrator.py:5254` `await module.execute("web_fetch", params)` →
   `reaper_module.py:127` `self._reaper.fetch_page(url)` (default
   `store_in_grimoire=True`) → `reaper.py:988` `self.grimoire.remember(...,
   trust_level=source_eval['trust_score'])` — **up to 0.7 for any Tier-1-suffix
   domain**, full page body, no `safety_class`, no instruction flag.
5. The write completes *inside* fetch_page. Only then does the post-hook fire
   (`orchestrator.py:5281`) with `str(result.content)[:500]` — it cannot unwrite
   the row. Poisoned full-page content is now in permanent Grimoire at
   near-official trust. `autonomous_research_enabled` read False the entire time.

The mission's bar (plan `:20-24`): "A plan where Reaper writes scraped content at
anything above untrusted has failed this front." Post-patch, the on-demand
autonomous path **still writes at up to 0.7** because M4.2's cap only lands if the
executor routes `fetch_page`'s `remember` through the helper — and even if it
does, the *firing* of that autonomous web pull is ungated. The pass-1 attacker
found the gate open on `run_task`; this pass finds the gate was never scoped to
the write path that actually matters. The plan even says so in its own recon (§0.3:
"the on-demand path is barely more governed … writes the full page at trust up to
0.7 … the pre-hook blocks only DENY") and then builds a gate that ignores it.

**Why this is worse than the pass-1 CRITICAL:** the pass-1 back door required a
human to type `/schedule run standing_research` and only leaked 0.3 snippets. This
one fires whenever the *planner* chooses a `web_fetch` step during any autonomous
or user task, leaks full pages at up to 0.7, and needs no manual command. The
"supervised on-demand" the plan leans on (plan `:249-252`, `:309-310`) is **not
supervised**: the orchestrator autonomously selects the URL and dispatches the
write with the only enforced verdict being DENY, which an `autonomous` tool never
triggers. "Supervised on demand" is asserted, never wired.

---

## What I attacked hardest and could NOT break

- **The `run_task` / `/schedule run` back door itself.** The double-guard is real:
  `_run_standing_research` and `run_task` are the only two reachable callers, and
  guarding both closes every entry point *to that function*. The pass-1 CRITICAL,
  as literally scoped, is fixed. (It just turned out to be the wrong scope.)
- **A *second* scheduler or a hidden `_run_standing_research` caller.** Grep across
  `modules/ main.py tests/` finds exactly one `StandingTaskScheduler` construction
  (`main.py:674`) and no other invoker. No third firing path exists.
- **`_run_self_analysis` reaching a Reaper web write.** It calls Omen
  (`code_analyze_self`) and stores at trust 0.9 (`standing_tasks.py:163-197`) — no
  Reaper, no web. `grimoire_stats` is Grimoire-internal. Neither is a Reaper write
  path. Priority-1's "does another standing task reach a Reaper write" → **no.**
- **The trust-cap arithmetic.** `min(reputation, UNTRUSTED_WEB_TRUST)` genuinely
  caps 0.7 → ≤0.3. Reddit/YouTube pass `trust_level=0.3` and the `min()` on line
  1381/1628 is on **confidence**, not trust — so the plan's "does min() there
  accidentally RAISE anything" → **no, it can only lower.** The cap value is
  internally contradictory (plan `:140`/`:166` say "align to Grimoire's lowest
  external constant" = `TRUST_UNVERIFIED=0.1` at `grimoire.py:64`, but hard-codes
  `0.2`) — harmless since both are ≤0.3, noted as a LOW-adjacent inconsistency, not
  a break.

---

## Verdict

The two pass-1 fixes **hold on the exact holes they were told to close** — the
`run_task` back door is dead and the choke helper now spans both files. But the
plan bought that with two new seams and one un-closed original one:

1. **CRITICAL (NEW-1):** the firing-guard fix anchored the entire Tier-2 gate to
   `_run_standing_research` (snippets @ 0.3) while the on-demand `web_fetch` router
   tool — full page @ up to 0.7, `autonomous`, ungated at dispatch
   (`reaper_module.py:127` → `reaper.py:988`, `orchestrator.py:5254`) — remains the
   highest-severity autonomous write and is outside the gate entirely. The plan's
   own recon named this path; Front 5 never gated it. "Supervised on-demand" is
   asserted but not wired: the orchestrator autonomously picks the URL and the only
   enforced verdict is DENY, which an autonomous tool never hits.
2. **HIGH (NEW-2):** the shared `untrusted_memory_kwargs` helper signature drops
   `confidence` (and doesn't pin `check_duplicates`) — silently changing what five
   write paths store, including erasing the relevance-derived confidence the
   research pipeline exists to compute.
3. **MED×3:** the trust-cap fork defends a test that doesn't exist while the gate
   breaks three real `test_standing_tasks.py` tests with no fork (NEW-3, NEW-4);
   the "thin wrapper over `analyze()`" doesn't compose — wrong return shape, missing
   `source` arg, and NFKC/zero-width normalization must be surgically added to a
   detector Cerberus's live path shares (NEW-5, NEW-6).
4. **LOW (NEW-7):** the read-side invisibility is closed in prose, not a test.

**Write-half trust cap: still sound.** **Autonomy gate: still has a hole — a
different, worse one than pass 1.** The plan patched the door the last attacker
walked through and left the load-bearing wall open. Front 5 is not done until the
gate wraps the `web_fetch` autonomous write (or `store_in_grimoire` is forced
False on the autonomous dispatch path), not just the scheduler.
