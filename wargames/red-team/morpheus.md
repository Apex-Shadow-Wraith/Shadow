# RED-TEAM KILL-ATTEMPT — Morpheus firewall & activation gate

**Target plan:** `wargames/plans/morpheus.md`
**Method:** executor-blind run-through of the plan against the real code, read-only.
Every file:line claim in the plan was checked against source.

---

## SUMMARY VERDICT

**The firewall is BREACHABLE by following the plan literally, and the breach is
in the plan's own enumeration, not in the code it audits.**

The plan's central recon is largely *correct* about the code — the retrieval
breach (`recall` default `min_trust=0.0`, filter only `if min_trust > 0`), the
double dormancy gate, the phantom kill-switch tool names, and the RSI-is-inert
findings all verified true against source. The activation gate (`enabled` flip)
**held** under every attack I brought: there is no self-activation tool, no
`load_on_startup` bypass, and the instantiation gate is real. I could not flip
`enabled` on paper. Say that plainly: **Front 5 / G1 survived.**

But **Front 2 (the firewall) has a hole the plan drilled itself.** The plan
enumerates exactly **three** Morpheus→Grimoire write paths and hard-codes those
three file:lines into its verification (V2a), its ledger (G2), its checklist
(CL-5), and its abort (A7). The real code has **four**. The fourth —
`rd_lab.py:555` `_store_speculative()` — writes content tagged
`"validated": False` (a raw, untested dream) straight to Grimoire, is called on
the two most common branches of `run_exploration_session` (`:199`, `:205`), and
is **named nowhere in the plan**. An executor who closes "the three" passes
V2(a)'s grep-for-zero-raw-writes *by the plan's own definition of the grep*,
ships CL-5 green, and leaves the speculative-write path live. That is a dream
walking straight through the firewall while every gate reports PASS.

Severity ranking below. The single worst break is #1.

---

## BREAKS (worst first)

### 1. CRITICAL — The plan enumerates 3 Grimoire write paths; the code has 4. The fourth writes *unvalidated* dreams.

> Plan (Front 2.1): *"Delete/replace the three raw writers so they call the gate
> or nothing: `experiment_store.py:515`, `rd_lab.py:414`, `serendipity_detector.py:300`."*
> Plan (V2a): *"`grep -rn "\.store(\|\.remember(" modules/morpheus/` shows the only
> Grimoire write is inside the promotion gate."*
> Plan (A8): *"a fourth Grimoire write path not in this plan. Stop and re-recon."*

**How it fails:** `grep -rn "\.store(" modules/morpheus/` actually returns **four**
hits — `experiment_store.py:515`, `rd_lab.py:414`, `rd_lab.py:555`, and
`serendipity_detector.py:300` — and the un-named `rd_lab.py:555`
(`_store_speculative`) writes `{"validated": False}` content to Grimoire's
`speculative_knowledge` collection on the untestable/failed branches
(`rd_lab.py:199,205`), so an executor closing "the three" ships a live path that
puts a raw dream into Grimoire while V2(a) reports PASS.

**Why it is worse than the others:** the other three writers only fire on
`success`/`confirmed` (a dream that at least ran a test). `_store_speculative`
fires on the *default* path — a dream that was never tested at all. It is the
purest firewall violation and it is the one the plan forgot. The plan's own A8
would catch this ("a fourth Grimoire write path") — but only if recon had run
the grep it prescribes in V2(a); the recon section instead lists three by hand,
so A8 never trips.

---

### 2. HIGH — V2(a)'s grep proves "no `.store(`" but the real leak-fix pivots to `remember()` / `store_routed()`, which the grep also greenlights at trust 0.5.

> Plan (V2a): *"`grep -rn "\.store(\|\.remember(" modules/morpheus/` shows the only
> Grimoire write is inside the promotion gate."*
> Plan (2.1 Fork): *"Grimoire exposes only `remember()` today → the gate calls
> `remember()` with an explicit `trust_level`, never the dead `.store()`."*

**How it fails:** `grimoire_module.py:350` exposes `store_routed()`, which calls
`self._grimoire.remember(...)` with **no `trust_level` argument** — so it inherits
`remember()`'s default `trust_level=TRUST_CONVERSATION=0.5` (`grimoire.py:677`);
an executor "fixing" a dead `.store()` call by routing it through the module-level
`store_routed()` (the natural, module-facing store method) lands the dream at
**0.5, not 0.0**, and the grep in V2(a) sees the write is "inside a gate function"
and passes because the grep tests *call location*, not the trust value written.

**Note:** the plan warns about `.store()`→`remember()` but never mentions
`store_routed()` as the third, most-idiomatic write surface. V2(a) is a
*syntactic* check ("is the call inside the gate?") standing in for a *semantic*
property ("does the write land at trust 0.0 and stay out of recall?"). Those are
not the same assertion.

---

### 3. HIGH — G3 "the wired gate" for the crown breach is **owned by another mission and marked RN3/unsettled** — a gate the plan describes but never wires.

> Plan (Gates ledger, G3): *"Gate (wired, not named): Structural retrieval
> exclusion (Front 2.2) — speculative content kept out of `memories`, or a
> recall-side speculative floor (Grimoire-owned, RN3)."*
> Plan (RN3): *"Do not assume Morpheus may edit Grimoire's recall in isolation."*
> Plan (CL-6): *"Recall-side speculative exclusion enforced. Owner: Grimoire mission."*

**How it fails:** the ledger's promise that G3 is a *"wired, not named"* gate is
false for the recall-side arm — that arm is explicitly **not wired by this plan**
(it belongs to the Grimoire mission, is gated behind unsettled RN3, and is a
blocking checklist item CL-6), so the "looks governed but isn't" failure is
structural: the crown breach's only real containment is option (i) "never write
to `memories`," and if *any* write path lands in `memories` (see breaks #1/#2),
G3 has no enforcing check on the Morpheus side at all.

**The trap:** option (i) ("keep speculative content out of `memories` entirely")
is the *only* arm Morpheus can actually enforce, yet breaks #1 and #2 are exactly
the ways content reaches `memories`. So G3 reduces to "don't write to memories,"
which is only as strong as the write-path enumeration in break #1 — which is
incomplete.

---

### 4. HIGH — `grimoire_reader.search()` is a second, independent retrieval breach the firewall dry-run (V2b) can silently skip.

> Plan (2.2 expected obs): *"run the **live default recall** (`recall()` with no
> `min_trust` arg) and `grimoire_reader.search()` … and assert **0 hits**."*
> Plan (recon): *"`grimoire_reader.search()` (`grimoire_reader.py:160-247`) has no
> `min_trust` parameter and no trust filter anywhere."*

**How it fails:** verified true — `search()` (`grimoire_reader.py:160`) filters
only `is_active = 1` and optional `category`, returns `trust_level` in the payload
but never filters on it, and it is a *different code path* from `recall()`, so a
fix that adds a `min_trust` floor to `recall()` leaves `search()` wide open; the
plan lists both in 2.2's expected observation but **V2(b)'s pass line collapses
to "0 hits in default recall AND search"** with no assertion that the *same
artifact* was queried through *both* code paths against a real ChromaDB — a
dry-run using a stub Grimoire double (which the plan mandates, "stub/in-memory
Grimoire double") can implement `search()` as a no-op returning `[]` and score
"0 hits" without ever exercising the unfiltered SQLite/Chroma path that the live
breach lives in.

**This is a verification-that-passes-on-a-broken-result:** the plan's own
isolation rule ("stub Grimoire double," V-section preamble) makes the certifying
run (V2b) run against a *double that has no breach*, not against the real
`grimoire_reader.search` whose breach is the finding. A stub that returns `[]`
passes. The real code still leaks. The plan never says the firewall dry-run must
run against the *real* Grimoire retrieval code, and CL-6 explicitly defers the
real fix to another mission.

---

### 5. MEDIUM — V4's `MODULE_DESCRIPTIONS` check asserts a property that is FALSE on a correct live system; it passes only against a hand-built registry.

> Plan (Front 4.1): *"Update `MODULE_DESCRIPTIONS` (`:28-47`) — it currently lists
> 9 active modules but the docstring/`get_module_descriptions` claim '13'."*
> Plan (V4): *"every `MODULE_DESCRIPTIONS` key is a registered module."*

**How it fails:** `MODULE_DESCRIPTIONS` (`cross_module_dreaming.py:28-47`) actually
has **10 keys** (shadow, wraith, cerberus, apex, grimoire, harbinger, reaper,
omen, nova, morpheus) — not "9" — and two of those keys are provably *not*
registered as routable modules on a live system: `morpheus` (dormant → never
registered, per `main.py:207-211`) and `shadow` (the orchestrator IS the agent
and is not registered as a module, per CLAUDE.md), so V4's assertion "every key
is a registered module" **fails against a correct live registry** and can only
"pass" against a hand-assembled test registry — meaning V4 is either a guaranteed
red or a check run against a fiction.

**Consequence:** the executor, hitting a failing V4, "fixes" it by *deleting*
`morpheus` and `shadow` from `MODULE_DESCRIPTIONS` to make the assertion green —
which is a behavior change to the dreaming roster driven by a mis-specified
verification, not by a real requirement. The plan's recon count ("9") is itself
the unsettled-assumption-stated-as-fact.

---

### 6. MEDIUM — SAFETY INVARIANT #5 ("Full diff stored in Grimoire") is an *intended* Morpheus→Grimoire write the plan's Front 3 never closes.

> Plan (Front 3.2): asserts `approve_proposal` grows *"no filesystem write and no
> git call"* and greps for `subprocess`/`open(`/`write_text`/`git`.
> Code (`self_improvement.py:13,69`): *"5. Full diff stored in Grimoire for audit trail."*

**How it fails:** Front 3.2's no-write test greps only for filesystem/git writes,
but the RSI engine's own documented invariant #5 is a *Grimoire* write (the audit
diff), so an executor "completing" the audit-trail invariant adds a
`grimoire.remember(diff)` call that Front 3.2's grep does **not** look for
(it hunts `open(`/`git`, not `.remember(`/`.store(`) — a fifth firewall write path
that Front 3.2 is blind to because it was scoped to code-writes, not knowledge-writes.

**Cross-reference:** this is the same class as break #1 — the plan's write-path
census is anchored to enumerated file:lines and misses paths that a future
"finish the docstring intent" edit would introduce.

---

### 7. MEDIUM — A4 (quality-filter promotion rate) has no trigger threshold wired; it restates 1.2's floor and forces the judgment call the plan claims to remove.

> Plan (A4): *"Quality filter promotion rate stays high after tuning (most dreams
> survive). A high promotion rate is a bug per the brief; stop and flag."*
> Plan (1.2): asserts *"rejection rate ≥ 60%"* on a **hand-labelled** ~20-item corpus.

**How it fails:** "stays high" and "most dreams survive" name no number and no
corpus, so A4 fires only via the executor's judgment about what "high" means on
*live* dreams (there is no labelled corpus at runtime — 1.2's 60% floor is only
defined against a fixed hand-labelled set), which means the abort the plan lists
as a hard stop is actually an un-triggered judgment call — exactly the "fork with
no trigger" the mission told me to hunt.

---

### 8. LOW — CL-2 / A5 lean on `test_morpheus_gate.py` = 7 green, but those 7 tests prove *topology*, not that a planted dream is absent from recall.

> Plan (V5/CL-2): *"`pytest tests/test_morpheus_gate.py` = 7 green; dormancy
> re-proven."*

**How it fails:** the 7 gate tests assert graph *unreachability* of a dormant
route (verified: they introspect `compiled.get_graph()` edges,
`test_morpheus_gate.py:201`, and span-silence at `:346`) — they say nothing about
the firewall, so "7 green" is a true dormancy proof but the plan occasionally
leans on it as if it were reassurance about containment; it is orthogonal.
Low severity because the plan does correctly scope it to dormancy elsewhere —
but the CL-2/CL-4 split must stay crisp or a reader conflates "gate green" with
"firewall proven."

---

## WHAT I ATTACKED HARDEST AND WHERE IT HELD

**Activation (Front 5 / G1) held.** I tried four routes to flip `enabled` or
self-activate on paper:

1. **A self-activation tool.** `grep` for any `.enabled =` / config-write inside
   `modules/morpheus/` returns nothing. No Morpheus tool writes config. Held.
2. **`load_on_startup` bypass.** The plan *claims* `main.py` never iterates that
   list. I verified it: `grep -rn "load_on_startup" main.py modules/shadow/*.py`
   returns **nothing**; the list at `config.yaml:49-57` (which *does* include
   `"morpheus"`) is genuinely inert. Instantiation is a hardcoded `enabled`-gated
   call (`main.py:207-211`). RN1 settles clean. Held.
3. **`is_routable` treating a missing `enabled` as enabled** (`base.py:483-487`,
   returns `True` when the settings class lacks `enabled`). Real, but Morpheus's
   settings class *has* `enabled` (`config.py:16`), so this fallback never applies
   to Morpheus. A future dormant module with no `enabled` attr would be routable —
   worth a note to the author, but not a Morpheus break. Held for Morpheus.
4. **"Just testing" flips it.** Abort A1 forbids it and the executor has no reason
   to; the double dormancy means a flip without the full checklist still can't
   reach a green activation. Held.

The move I attacked hardest was **route #2 (the `load_on_startup` bypass)**,
because if `main.py` iterated that list the dormancy would be a lie regardless of
the `enabled` flag — the list literally contains `"morpheus"`. It held because
the list is dead code: nothing reads it. That is the strongest single thing in
the plan and it is true.

**The firewall did NOT hold** — see breaks #1–#4. The dream escapes not through
activation but through an *incomplete write-path census* that the plan then bakes
into its verifications.

---

## THE SINGLE WORST BREAK — RUN-THROUGH (Break #1)

**Goal:** a speculative, untested dream surfaces in a normal Grimoire recall as a
result, with every plan gate reporting PASS.

**Setup:** the executor is maturing Morpheus per the plan. Fronts 1–4 are being
wired. Break #1 rides Front 4.2 + Front 2.1 exactly as written.

1. **Front 4 wires `run_exploration_session` to a live-ish RDLab.** The plan's
   Front 4.2 says "after Front 2, `store_dream` writes only to the experiment
   store." The executor wires `RDLab` with a real Grimoire (RN2 says "the executor
   must pick the write method deliberately"). To do that, `RDLab.__init__` gets a
   non-None `grimoire`.

2. **Executor closes "the three" writers per Front 2.1 / A7.** They route
   `experiment_store.py:515`, `rd_lab.py:414` (`graduate_to_production`), and
   `serendipity_detector.py:300` through the new promotion gate. They run V2(a):
   *"grep shows the only Grimoire write is inside the promotion gate."* They grep
   for `.store(` — and here is the failure: the plan's **recon told them there are
   three**, so they mentally check off three hits and treat a fourth as noise, or
   they never see it because they patched by file:line from the plan's list. The
   plan's V2(a) command would surface `rd_lab.py:555`, but the plan's *prose*
   (Front 2.1, A7, G2, CL-5) all say **three**, and the executor trusts the
   settled-recon census over re-counting.

3. **`_store_speculative` (`rd_lab.py:537-560`) is left untouched.** It is called
   at `rd_lab.py:199` (validated-but-failed branch) and `rd_lab.py:205` (the
   *untested* branch — `run_experiment` returns `tested: False` whenever the
   hypothesis isn't testable or no sandbox is wired, which is the *default* while
   dormant/maturing). With a real `grimoire` now bound (step 1), the guard
   `if self._grimoire is None: return` no longer short-circuits.

4. **A dream flows through.** `run_exploration_session` generates a hypothesis,
   `run_experiment` returns `{"tested": False, ...}` (no sandbox), the code hits
   the `else` at `rd_lab.py:203-205`, calls `_store_speculative(result)`, which
   at `rd_lab.py:555` calls `self._grimoire.store(content={..., "validated": False}, category="speculative_knowledge", ...)`.

5. **The `.store()` typo now bites in the executor's favor.** The plan itself
   flags (recon 67c) that `.store()` `AttributeError`s today and is swallowed.
   But RN2 and the Fork force the executor to *make Grimoire writes work* — they
   wire the gate to `remember()`. A careful executor fixes only the three gated
   calls; but `_store_speculative` is a *fourth* `.store()` that, if the executor
   does a blanket `.store(`→`.remember(` rename (the obvious way to "fix the method
   name while maturing the module," recon 74's exact warning), goes live too — now
   landing at `remember()`'s default **trust 0.5** (break #2).

6. **The dream is now a row in `memories` at trust 0.5, category
   `speculative_knowledge`, `validated: False`.**

7. **Normal recall surfaces it.** A user later asks something semantically near the
   dream's text. `grimoire.recall(query)` runs with default `min_trust=0.0`; the
   trust filter at `grimoire.py:1026-1027` is skipped (`if min_trust > 0` is
   False); the row ranks by cosine similarity and **returns as a result**,
   indistinguishable from fact. `grimoire_reader.search()` (break #4) returns it
   too — no trust filter at all.

8. **Every gate reports PASS.** V2(a) grep "passed" (executor closed the three the
   plan named). CL-5 green ("single promotion gate is the only writer" — believed,
   because the census was three). G2 green. The firewall dry-run V2(b), if run
   against the plan-mandated **stub Grimoire double**, never exercised
   `_store_speculative` at all (the stub has no such method wired), so it reported
   "0 hits." CL-4 — "the load-bearing item" — is marked green on a dry-run that
   never touched the leaking path.

**Result:** a speculative, *untested* dream (`validated: False`) surfaces as a
verified-looking fact in a default recall, and the activation checklist's
load-bearing firewall item (CL-4) is green. The dream escaped containment by
walking through the one door the plan forgot to list — and the plan's own
verifications, keyed to the three-path census and a stub double, certified the
escape as contained.

**The one-line fix the author owns (not me):** Front 2.1 / V2(a) / A7 / G2 / CL-5
must derive the write-path set from *running* the grep
`grep -rn "\.store(\|\.remember(\|store_routed(" modules/morpheus/` at recon time
and asserting the count, not from a hand-listed three; and V2(b) must run against
the **real** Grimoire retrieval code (real `recall` + real `grimoire_reader.search`
against a real ChromaDB), not a stub double, or it cannot certify the breach it
exists to close.

---

## VERIFIED-TRUE recon claims (the plan's homework that checks out)

For the author's confidence, these plan claims verified correct against source:

- `morpheus.py` handler map = 11 tools, none write Grimoire (`:199-211`). ✔
- `recall()` defaults `min_trust=0.0` (`grimoire.py:965`); filter only
  `if min_trust > 0` (`:1026-1027`). **Crown breach real.** ✔
- `remember()` defaults `trust_level=TRUST_CONVERSATION=0.5` (`:677`, `:69`);
  `TRUST_MORPHEUS=0.0` exists but no path passes it (`:65`). ✔
- `grimoire_reader.search()` has no trust filter (`:160-247`). ✔
- No `grimoire.store()` method exists — only `remember()`, `store_routed()`. ✔
- Dormancy: `enabled=False` (`config.py:16`); `main.py:207-211` gates
  instantiation; `all_modules`/register exclude a None morpheus (`:231-248`). ✔
- `load_on_startup` is inert — referenced nowhere in `main.py`/`shadow`. ✔ (RN1 clean)
- No self-activation surface in `modules/morpheus/`. ✔
- `self_improvement.py:533` `approve_proposal` only flips DB status; "Phase 2 …
  git commit" is docstring-only (`:536`); 6 invariants docstring-only (`:8-15`). ✔
- `emergency_shutdown.py:74-75` phantom tool names `discovery_*` don't match the
  real 11 tools (`SAFE_MODULES` lists morpheus at `:85`). ✔
- Test counts: `test_morpheus.py` = 53, `test_morpheus_gate.py` = 7. ✔
- Gate tests prove topology (`compiled.get_graph()` edges, `:201`), span-silence
  (`:346`) — not firewall behavior. ✔
