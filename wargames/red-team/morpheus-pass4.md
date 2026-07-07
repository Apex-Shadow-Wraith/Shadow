# RED-TEAM PASS 4 — CONFIRMATORY (attacking the pass-3 patches)

**Target:** `wargames/plans/morpheus.md`
**Scope:** the two pass-3 patches only — (1) the V2(b)/Front 2.2 POSITIVE CONTROL,
(2) the G3a EXPERIMENT-STORE-ONLY containment — plus a sweep for new breaks and a
re-confirm of the no-self-activation property.
**Method:** attacked blind against real code. All claims file:line-verified.

---

## VERDICT

**HOLDS — no CRITICAL/HIGH.** The firewall verification is now sound. The two
pass-3 patches survive the hardest attacks I could mount:

- The **positive control** and the **0-hits check** *can* be made to reference the
  same real artifact in the same real Grimoire, and the plan's own architecture
  (Front 2.1 removes every `.store()` call; the gate is the only writer and it
  calls `remember()` → `shadow_memories`) forces them onto the same collection at
  the point where the certifying run actually matters. I attacked hardest at the
  "plant-in-one-store, check-in-another" pull-apart (below) and it does not open a
  false green on the load-bearing assertion.
- The **experiment-store-only containment** is *architecturally true today*:
  `ExperimentStore` writes to `data/experiments.db` / `failed_experiments` (plain
  SQLite, **no ChromaDB, no embedding**), and `recall()` / `grimoire_reader.search()`
  read only `shadow_memories` (ChromaDB) + `data/memory/shadow_memory.db`. Nothing
  in the experiment store *reads back* into `shadow_memories`. The only bridge is
  `_store_in_grimoire` — which is one of the four census writers Front 2.1 deletes.

I found **two MEDIUM ambiguities** and **one LOW wording bug**, none of which
breaks the firewall verification; they are executor-guardrail tightenings, not
false greens. One of the two MEDIUMs is genuinely **worth a one-line patch** because
a blind executor could satisfy the positive control against the wrong artifact and
still (correctly, by luck) pass the 0-hits check — proving *nothing*, a vacuous
green rather than a false green. I flag it as MEDIUM, not HIGH, because it cannot
make a *leaking* firewall look contained; it can only make a *sound* firewall look
"proven" without actually exercising the breach. That is a rigor hole, not a safety
hole. See M1.

No CRITICAL/HIGH means **pass 4 lands nothing that blocks DONE** — subject to the
author's call on whether the two MEDIUMs get patched or accepted-with-note.

---

## ATTACK 1 — the POSITIVE CONTROL (pass-3 HIGH fix)

### What the patch says (quoted)

> "Assert the artifact is present in the store by a direct check that bypasses the
> trust firewall (**e.g. `recall(query, min_trust=0.0)` returns it, or a direct
> `SELECT`/`collection.count()` delta of +1**)." (plan:361-363)
>
> "**Pass = plant proven landed AND 0 hits in both.**" (plan:384)

### The attack: can the positive control pass while the 0-hits check is vacuous?

The concern the prompt raises is real and worth spelling out precisely, because the
answer is *"only in a way the plan's own design prevents on the load-bearing path,
but the wording leaves a rigor gap."*

**The two artifacts actually diverge in the code.** There are genuinely two
different, unconnected stores in play:

1. **`shadow_memories`** — the ChromaDB collection (`grimoire.py:237-238`) +
   `data/memory/shadow_memory.db` `memories` table. This is the ONLY thing
   `recall()` (`grimoire.py:965`) and `grimoire_reader.search()`
   (`grimoire_reader.py:98-99,199-204`) ever read.
2. **`data/experiments.db` / `failed_experiments`** — plain SQLite,
   `PRAGMA journal_mode=WAL`, **no ChromaDB, no embedding**
   (`experiment_store.py:55-94`). `recall()` never touches this file or table.

So the pull-apart the prompt asks about is architecturally available: a plant that
lands in `experiments.db` would make a `SELECT count(*)` delta of +1 succeed
(positive control satisfied via the "direct SELECT" branch) while `recall()`
trivially returns 0 hits — **because recall never reads that table** — yielding a
"pass" that proves nothing about a dream reaching `shadow_memories`.

**But** — and this is why it is not a HIGH — the certifying run is defined as
"plant the **same** speculative artifact **through every write path the census grep
found**" (plan:356-357). The census writers are the four `.store()` calls
(`experiment_store.py:515`, `rd_lab.py:414`, `rd_lab.py:555`,
`serendipity_detector.py:300`). **Three of the four target `shadow_memories`, not
the experiment store:**

- `rd_lab.py:414` `graduate_to_production` → `grimoire.store(...)` → (post-fix
  `remember()`) → `shadow_memories`.
- `rd_lab.py:555` `_store_speculative` → `grimoire.store(..., collection=...)` →
  (post-fix, dropping the phantom `collection=`) `remember()` → `shadow_memories`.
- `serendipity_detector.py:300` → `grimoire.store(...)` → `remember()` →
  `shadow_memories`.
- Only `experiment_store.py:515` `_store_in_grimoire` is *reached from* the
  experiment store — and it, too, calls `grimoire.store(...)` → `remember()` →
  `shadow_memories`. **All four writers, once un-typo'd to `remember()`, land in
  `shadow_memories`.** None of them writes the dream into `failed_experiments` as
  the *thing recall would need to find*; `failed_experiments` is where dreams live
  *legitimately* (that is the containment, not the breach).

So when the executor plants "through every write path the census grep found," each
plant is a `remember()` into `shadow_memories` — the exact collection `recall()`
reads. The positive control's `recall(query, min_trust=0.0)` branch and the 0-hits
`recall()` branch then reference the **same** collection by construction, and the
run is meaningful. The `SELECT`/`collection.count()` branch, if used, is a
`shadow_memories`/`collection.count()` delta — also the right artifact.

### Residual: M1 (MEDIUM — worth one line)

The wording still permits a blind executor to *misread* the positive control. The
`e.g. ... or a direct SELECT` menu (plan:361-363) does not say **which store** the
SELECT is against. A literal-minded executor who is *also* planting into the
experiment store (e.g. planting via `store_dream()` /
`ExperimentStore.store_failure()` because they read "plant through every write
path" broadly and included the experiment path) could satisfy the positive control
with `SELECT count(*) FROM failed_experiments` (+1) and then run `recall()` (0 hits,
trivially, because recall never reads that table) and call it a pass. That is
**vacuous, not false**: it cannot hide a real leak (a real leak lands in
`shadow_memories`, which the 0-hits `recall()` *does* read), but it can produce a
green that never exercised the breach at all.

- **Quote:** "prove the plant actually *landed* … e.g. `recall(query,
  min_trust=0.0)` returns it, or a direct `SELECT`/`collection.count()` delta of
  +1" (plan:360-363)
- **How it fails:** the positive-control target store is unpinned, so a
  `SELECT`-on-`experiments.db` positive control pairs with a trivially-0
  `recall()`, certifying nothing about `shadow_memories`.
- **Severity:** MEDIUM (rigor/vacuity hole, not a safety/false-green hole).
- **One-line fix (not architectural):** pin the positive control to the *same
  artifact and store the 0-hits check reads* — e.g. "the positive-control landing
  proof MUST be against `shadow_memories` (via `recall(min_trust=0.0)` returning
  the planted id, or a `collection.count()` delta of +1 on the `shadow_memories`
  ChromaDB collection), NOT against `failed_experiments`; a plant that lands only
  in the experiment store is the *contained* case and must yield a positive control
  that also shows `shadow_memories` unchanged." This closes the gap in the plan
  alone; no shared-Grimoire change needed.

### Is there a coherent way for a blind executor to do both against the SAME artifact?

**Yes.** The unambiguous implementation is: for each census writer, call it (post-fix
it routes through the promotion gate → `remember()` → `shadow_memories`) with
`check_duplicates=False` and a unique marker; assert the returned id is new AND that
`recall(marker, min_trust=0.0)` returns it (positive control, on `shadow_memories`);
then assert `recall(marker)` (default) and `grimoire_reader.search(marker)` both
return 0 hits. Same collection, same artifact, same id, three assertions. This is
coherent and a competent executor lands it. M1 only tightens against the *incoherent*
reading; it does not mean the plan can't be implemented soundly.

### Silent-plant-failure modes — all three verified real and correctly countered

- (i) dedup no-op: `remember()` `check_duplicates=True` default (`grimoire.py:681`);
  on a <0.08-distance hit it `return existing_id` **without inserting**
  (`grimoire.py:779-820`). Countered by `check_duplicates=False` / unique marker +
  "assert returned id is new." **Correct.**
- (ii) swallowed except: `experiment_store.py:525-526` and `rd_lab.py:426-428`
  (and `rd_lab.py:561-562`, `serendipity_detector.py:305-306`) are bare
  `except Exception → logger.warning`. Countered by "assert no exception swallowed
  (write returns a real id)." **Correct.**
- (iii) `collection=` TypeError: `remember()` signature (`grimoire.py:675-683`) has
  **no `collection` param**; `rd_lab.py:559` passes `collection=self._speculation_collection`.
  A naive `.store()`→`remember()` remap raises `TypeError`, swallowed by (ii).
  Countered by "assert the plant call signature is valid." **Correct.** (Confirmed
  `_speculation_collection` defaults to `"speculative_knowledge"`, rd_lab.py:87-88 —
  a phantom collection that does not exist as a writable Grimoire surface, matching
  the pass-3 G3a deletion.)

All three modes are real and each has a matching, checkable counter. The positive
control is well-constructed **except** for the unpinned-store ambiguity (M1).

---

## ATTACK 2 — EXPERIMENT-STORE-ONLY CONTAINMENT (pass-3 MEDIUM fix / G3a)

### What the patch says (quoted)

> "**Never write speculative content into Grimoire's `memories`/ChromaDB at all** —
> dreams live ONLY in the experiment store (separate SQLite `data/experiments.db` /
> `morpheus_experiments` table, no ChromaDB), which `recall()`/`grimoire_reader.search()`
> never touch." (plan:639)

### Is the separation TRUE and COMPLETE?

**True today, yes.** Verified:

- `ExperimentStore` (`experiment_store.py:55-94`): opens `data/experiments.db`,
  creates `failed_experiments`, uses only `sqlite3` — **no `chromadb` import, no
  embedding, no `shadow_memories` reference anywhere in the file.**
- `recall()` reads `self.collection` = `shadow_memories` (`grimoire.py:237-238`) +
  the `memories` table. `grimoire_reader.search()` reads its own
  `shadow_memories` collection (`grimoire_reader.py:98-99`) + `memories` table
  (`grimoire_reader.py:219`). **Neither ever opens `experiments.db` or queries
  `failed_experiments`.** Confirmed by grep: no `experiments.db` / `failed_experiments`
  reference exists in `grimoire.py` or `grimoire_reader.py`.

### Does anything promote/copy/sync a row from the experiment store into `shadow_memories`?

**Exactly one bridge exists, and it is a census writer Front 2.1 deletes:**

- `ExperimentStore._store_in_grimoire()` (`experiment_store.py:510-526`) →
  `self._grimoire.store(...)`. It is called from **two** success paths:
  `store_experiment()` when `experiment.success` (`:133-134`) and
  `record_retry_result()` on success (`:296`). This is the promotion/sync the
  prompt asks about — and it is census writer #1 (`experiment_store.py:515`). Front
  2.1 removes or re-routes it (Abort A7 fires if an executor "fixes" it). Once
  removed, **there is no success-path write from the experiment store into
  `shadow_memories`.** The plan is correct that G3a "is only as strong as G2's
  complete write-path census" (plan:639) — and G2's census catches this exact line.

- `rd_lab.graduate_to_production()` (`rd_lab.py:387-428`) is the *other* promotion
  path, called from `run_exploration_session` at `rd_lab.py:192` gated only by
  `validate_discovery()` (`:348-385`, dict-field checks — no Master, no Cerberus).
  It writes to `shadow_memories` (census writer #2, `rd_lab.py:414`). Also deleted /
  re-routed by Front 2.1. **Correctly identified.**

**No other bridge.** `store_dream()` (`cross_module_dreaming.py:235-263`) routes to
`ExperimentStore.store_failure()` → `failed_experiments` only (verified: it calls
`store_failure`, which sets `success=False`, so `_store_in_grimoire` is NOT reached
from the store_dream path — the leak only fires on a later `success=True`). This
matches the plan's Front 4.2 claim.

### The promoted-vs-speculative boundary — is it airtight?

The prompt asks whether a PROMOTED dream (correctly, by design, in `shadow_memories`
via Master token) vs a SPECULATIVE dream (never in `shadow_memories`) stays airtight,
or whether an un-approved dream can reach the promoted path.

**In the plan's design, it is airtight** — by construction the promotion gate (Front
2.1) is the *only* `shadow_memories` writer and it "refuses unless (a) a completed
test record, (b) an explicit Master-approval token, (c) gate-set trust + provenance"
(plan:313-317). Front 2.3 forbids aging/reference/success auto-promotion
(plan:391-405), and Abort A7 + the census re-derivation catch any restored raw
writer. So an un-approved dream cannot reach `shadow_memories` **once Front 2 lands**.

**One residual (M2, MEDIUM — ordering, already noted in-plan but under-guarded):**
the airtightness is *entirely* contingent on Front 2 landing **before** any Front-4
wiring gives `rd_lab`/`experiment_store`/`serendipity` a **real** `grimoire` handle.
Today all three hold `grimoire=None` (so `_store_in_grimoire` early-returns,
`experiment_store.py:512-513`; `graduate_to_production` early-returns,
`rd_lab.py:400-402`; `_store_speculative` early-returns, `rd_lab.py:543-544`). The
moment an executor wires a real Grimoire in *and* fixes `.store()`→`remember()`
*before* the gate is in place, **all four writers go live into `shadow_memories`
with the auto-promotion-on-success semantics intact** — an un-approved (merely
`success=True`, no token) dream reaches the promoted path. The plan states the
ordering constraint (Front 2 before Front 4, plan:508; Abort A2) but it is a prose
constraint, not a checkable gate.

- **Quote:** "**Front 2 lands before Front 4 is wired** (Abort A2 if a dream can
  reach Grimoire)." (plan:508)
- **How it fails:** if the executor wires a real `grimoire` handle and un-typos
  `.store()` during Front-4 maturation before Front-2's gate exists,
  `_store_in_grimoire`/`graduate_to_production` auto-promote a tokenless
  `success=True` experiment into `shadow_memories` — the crown breach, via the
  *designed* promotion path rather than a new one.
- **Severity:** MEDIUM (the plan already forbids it; the gap is that nothing in
  V2/V3/V4 *asserts the ordering* — it is trusted to executor discipline).
- **Fix (plan-only):** add to V2(b) or V4 an assertion that at the time the Front-4
  wiring test runs, calling any legacy writer with a real Grimoire handle and
  `success=True` **still** produces 0 `shadow_memories` writes (i.e. the gate is
  already interposed). This converts the prose ordering rule into a checked one.

This is **not** an architectural residual — it does not require changing shared
Grimoire dedup/collection semantics. It is a plan-side test-ordering assertion.

---

## SWEEP FOR NEW BREAKS INTRODUCED BY THE PASS-3 PATCHES

- **L1 (LOW — wording/factual):** G3a says dreams live in "separate SQLite
  `data/experiments.db` / `morpheus_experiments` table" (plan:639, and CL-3
  plan:672, recon plan:29). **These are two different stores conflated into one
  slash-list.** `data/experiments.db` holds the `failed_experiments` table
  (`experiment_store.py:55,68`); the `morpheus_experiments` table lives in a
  *different* file, `data/morpheus_experiments.db` (`morpheus.py:81,155`). The
  containment claim is true of *both* (neither has ChromaDB; neither is read by
  recall), so the firewall conclusion stands — but a blind executor pointing a
  positive-control `SELECT` at "`data/experiments.db` … `morpheus_experiments`
  table" will hit "no such table." **Fix:** name them as two stores — "`data/experiments.db`/`failed_experiments`
  AND `data/morpheus_experiments.db`/`morpheus_experiments`, neither with ChromaDB."
  Severity LOW: cosmetic-to-executor-friction, not a firewall hole.

- **No new false-green** was introduced by either patch. The positive control
  strengthens V2(b); the G3a rewrite removed a phantom escape (the
  "collection recall never queries") and correctly rests on the real
  experiment-store separation. Both are net improvements. The residuals above are
  pre-existing sharp edges the patches *exposed by narrowing the claim*, not
  regressions the patches *created*.

---

## RE-CONFIRM: NO SELF-ACTIVATION PATH OPENED

Re-ran the self-activation sweep against the patched plan's surface:

- `grep -rn "enabled\s*=\|yaml.dump\|save_config\|set_enabled" modules/morpheus/*.py`
  for any config/`enabled` **write** → **nothing** (only reads of
  `config.morpheus.enabled`). No Morpheus tool can flip its own `enabled`.
- The pass-3 patches touch only the **verification** (V2b positive control) and a
  **gate-ledger claim** (G3a) — neither adds a tool, a write path, or a config
  surface. The instantiation gate (`main.py:207-210`), `is_routable`
  (`base.py:467`), and the topology gate (`morpheus_gate.py`) are untouched.
- Abort A1 (flipping `enabled` is out of executor scope) is intact and unaffected.

**Self-activation remains impossible.** The pass-3 patches opened no activation
path.

---

## SUMMARY TABLE

| ID | Where | Severity | One-liner |
|----|-------|----------|-----------|
| M1 | plan:360-363 (positive control target store unpinned) | MEDIUM | `SELECT`/count positive control can pass against `experiments.db` while `recall()` 0-hits trivially — vacuous green, not false green; pin the landing proof to `shadow_memories`. |
| M2 | plan:508 (Front-2-before-Front-4 is prose, not asserted) | MEDIUM | Wiring a real Grimoire + un-typoing `.store()` before the gate exists auto-promotes a tokenless `success=True` dream via the designed path; convert the ordering rule into a checked assertion in V2(b)/V4. |
| L1 | plan:639,672 (`data/experiments.db` / `morpheus_experiments` conflated) | LOW | Two different stores named as one; a positive-control `SELECT` on the named table hits "no such table." Name both stores. |

**No CRITICAL. No HIGH.**

---

## BOTTOM LINE

The firewall verification **HOLDS**. The load-bearing V2(b) certifying run, as
designed, plants through the four census writers (all of which land in
`shadow_memories` once un-typo'd), proves each plant landed, and asserts 0 hits in
both real retrieval paths against the same collection — a run that genuinely
exercises the breach and cannot green a leaking firewall. The experiment-store-only
containment is architecturally real: the only experiment-store→`shadow_memories`
bridge is the `_store_in_grimoire` census writer that Front 2.1 deletes, and no
read-back or sync path exists.

The three residuals are **plan-side rigor tightenings**, not architectural blockers
and not safety holes: M1 and L1 are pin-the-store/name-the-store one-liners; M2
converts an existing prose ordering rule into a checked assertion. **None requires
touching shared Grimoire dedup or collection semantics** — the author can patch all
three in the Morpheus plan alone, or accept M1/L1 with an executor note and only
harden M2. Nothing here moves the firewall from "sound" back to "gameable"; a
competent blind executor lands the certifying run correctly, and the residuals only
protect against an *incompetent* reading producing a vacuous (not false) green.

Attacked hardest at: the plant-in-experiment-store / check-in-`shadow_memories`
pull-apart (M1) — and it does not open a false green on CL-4.

**Pass 4 lands nothing CRITICAL/HIGH. DONE is defensible** (author's call on whether
to fold in the two MEDIUM one-liners first).
