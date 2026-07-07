# RED-TEAM PASS 3 — Morpheus firewall, confirmatory attack on the pass-1 patches

**Scope:** confirmatory. Pass 1 landed 8 breaks; the author patched all 8. This
pass attacks the *patches* only, against the real code (read-only), to decide
whether they close the hole or move it. Nothing was changed.

**Target files read:** `modules/morpheus/{rd_lab,experiment_store,serendipity_detector,cross_module_dreaming}.py`,
`modules/grimoire/{grimoire,grimoire_reader,grimoire_module}.py`,
`wargames/plans/morpheus.md`, `wargames/red-team/morpheus.md`.

---

## VERDICT (up front)

**Still breakable — one HIGH.** The census-grep patch (break #1) genuinely holds:
I ran the exact command and hunted for a fifth path five different ways; there is
none. But the patch to break #4 (the certifying dry-run) **moved the hole rather
than closing it**: it forbade a stub and mandated a real Grimoire, yet never added
the *positive-control* assertion that the planted dream was actually written before
asserting "0 hits." Against the real code — where `remember()` silently returns an
existing id on dedup, and every Morpheus `.store()` call sits inside a
leak-swallowing `try/except` — an executor can produce a **green V2(b) / CL-4 on a
Grimoire that never received the plant.** CL-4 is "the load-bearing item," so this
is a HIGH that lands on the crown gate.

A second finding (MEDIUM) is that the G3a patch's escape-hatch clause ("a
collection `recall()` never queries") describes a collection that **does not exist
and cannot be created** through any write method the plan permits — so the only
enforceable arm of G3a is "experiment-store only," and the plan should say that
plainly instead of implying a second option.

Attacked hardest at: **the census-grep completeness (break #1)** — because a fifth
write path would be break #1 recurring one level up, the single worst thing to
find. It survived. Details below.

---

## WHAT I ATTACKED HARDEST AND WHY IT SURVIVED

### Break #1 patch (census grep) — HOLDS.

The plan's census is now *derived by running*
`grep -rn "\.store(\|\.remember(\|store_routed(" modules/morpheus/`. I ran it:

```
rd_lab.py:414            target_grimoire.store(...)
rd_lab.py:555            self._grimoire.store(...)   # _store_speculative, the pass-1 catch
serendipity_detector.py:300  self._grimoire.store(...)
experiment_store.py:515      self._grimoire.store(...)  # _store_in_grimoire
```

Four, matching the patched plan. Then I hunted for a fifth the pattern would miss,
along every axis the brief named:

- **Variable-aliased handle** (`target_grimoire`, `rd_lab.py:399/414`): traced to
  `grimoire or self._grimoire`. Still a `.store(` — caught by the grep. No alias
  escapes.
- **`_store_in_grimoire` / `store_experiment` indirection:** `_store_in_grimoire`
  (`experiment_store.py:510`) resolves to the `:515` `.store(` — already in the
  census. No indirect writer hides a *different* call.
- **Method names other than store/remember/store_routed** (`add`/`upsert`/`ingest`/
  `save`/`write`/`insert`/`put`/`index`): `grep -rniE "\.(add|upsert|ingest|save|
  write|insert|put|index)\(" modules/morpheus/` returns only `set.add()`,
  `str.index()`, `_explored_pairs.add()`, `_domains_explored.add()` — no Grimoire
  writer. Clean.
- **Direct ChromaDB `.add()`/`.upsert()`** bypassing Grimoire entirely:
  `grep -niE "collection|chroma|\.add\(|\.upsert\(|get_or_create_collection"` in
  `modules/morpheus/` returns **nothing**. Morpheus never touches Chroma directly.
- **Subdir / path-glob miss:** `modules/morpheus/` has no subdirectories;
  `experiment_store.py` is directly under it and IS caught. No file escapes the
  glob.
- **Non-`store` grimoire methods:** the only other calls on a grimoire handle are
  **reads** — `serendipity_detector.py:398 .query()` and
  `rd_lab.py:503 .get_random_entries()`. Neither writes.

**Conclusion:** the census pattern catches every Morpheus→Grimoire write that
exists today. Break #1 is genuinely closed, not moved. This was the most important
thing to check and it survived — state it plainly.

### Break #2 patch (semantic trust assertion) — HOLDS.

V2(a-ii) now inspects the gate's actual write and asserts an explicit speculative
`trust_level`, not a defaulted 0.5. I confirmed the trap it defends is real:
`store_routed()` (`grimoire_module.py:350`) *does* default to trust 0.5 — it calls
`self._grimoire.remember(...)` with no `trust_level` arg, so `remember()`'s default
`TRUST_CONVERSATION=0.5` applies (`grimoire.py:677`). The semantic assertion is the
right shape to catch a `store_routed`-laundered write. No break.

### Activation / self-flip — HOLDS (re-confirmed).

`grep -rniE "enabled\s*=\s*True|yaml.*dump|config.*save|set_enabled"
modules/morpheus/` returns nothing. No patch introduced a config-write surface.
The double dormancy (`main.py:207-210` instantiation gate + `is_routable`) is
untouched. G1 intact.

---

## FINDING 1 — HIGH — V2(b) never asserts the plant SUCCEEDED, so "0 hits" is trivially satisfiable on a Grimoire that silently rejected the write (break #4 moved, not closed)

**Exact plan lines (V2b / CL-4 / Front 2.2):**

> "(b) **Firewall dry-run against a REAL Grimoire** … plant the same speculative
> artifact via every census path; assert **0 hits** in real default `recall()` AND
> real `grimoire_reader.search()` …" (`morpheus.md:579-582`)

> "CL-4 — … V2(b) — planted speculative artifact yields 0 hits in default recall
> and search … **The load-bearing item.**" (`morpheus.md:648-650`)

**How it fails (one sentence):** the patch replaced the stub with a real Grimoire
but added no positive control that the plant landed, so a plant that silently
no-ops — which the real code makes easy — yields "0 hits" and a false-green CL-4.

**Why the real code makes the silent no-op easy (three independent routes):**

1. **Dedup silent-return.** `remember()` defaults `check_duplicates=True`
   (`grimoire.py:681`); on a ≥0.92-similarity hit it **returns the existing id
   without adding a new row** (`grimoire.py:~820`, "Dedup: merged with existing …
   return existing_id"). Plant twice, or plant something near an existing memory,
   and the "write" is a merge, not an insert — the artifact under test is never
   stored, and recall correctly returns 0 hits. Green on nothing.

2. **Swallowed `try/except` on the write side.** Every Morpheus `.store()` call is
   wrapped in a bare `except Exception` that logs and returns
   (`experiment_store.py:525-526`, `rd_lab.py:426-428`, `:562-563`). The plan even
   *notes* this swallowing (`morpheus.md:94`) — but only in the context of why the
   leaks are inert today. It never carries that awareness into V2(b). If the
   executor's gate write raises for any reason (see route 3), the exception is
   eaten, the plant fails silently, and recall returns 0 hits → false PASS.

3. **Signature mismatch that raises then gets swallowed.** The `.store()` calls
   pass `collection=` and `source=` positional/keyword args
   (`rd_lab.py:414-423`, `:555-560`) that **`remember()` does not accept**
   (`remember()` has no `collection` param, `grimoire.py:675-683`). An executor
   mapping `.store()`→`remember()` who forgets to strip `collection=` gets a
   `TypeError`, swallowed by route-2's `except`, → silent plant failure → 0 hits →
   false PASS. This is not hypothetical: `remember()` genuinely lacks the param the
   legacy calls pass, so the mismatch is the *default* outcome of a naive fix.

**The fix the plan is missing (so you can judge severity):** V2(b) must assert a
**positive control** before the negative one — e.g. "with the firewall OFF (or by
querying the experiment store / the raw row by id), confirm the *same* query
returns the planted artifact, or confirm the write call returned a fresh id that
resolves to the planted content; THEN turn the firewall on and assert 0 hits." As
written, the negative assertion stands alone and is satisfied by an empty store.

**Severity: HIGH.** It lands directly on CL-4, self-described as "the load-bearing
item" and the earned-by for the headline activation gate G1. Pass-1's break #4
report (`wargames/red-team/morpheus.md:125`) *explicitly* named "no assertion that
the *same* [query returns the artifact]" as part of the finding; the patch fixed
the stub half and left the plant-success half open. The hole moved from "stub
returns []" to "real store silently rejected the plant" — same false green.

---

## FINDING 2 — MEDIUM — G3a's "a collection `recall()` never queries" is a phantom escape hatch; only the experiment-store arm is enforceable

**Exact plan lines:**

> "G3a … **Never write speculative content to the `memories` table at all** —
> dreams live only in the experiment store / a collection `recall()` never
> queries." (`morpheus.md:613`, echoed Front 2.2 option (i), `morpheus.md:352-354`)

**How it fails (one sentence):** there is no writable Grimoire collection that
`recall()`/`search()` skip — both read the single `"shadow_memories"` collection,
and every write method (`remember`, `store_routed`) lands there — so the "or a
collection recall never queries" branch points at something that cannot be built
through the API the plan permits.

**Evidence from the real code:**

- `recall()` queries `self.collection` (`grimoire.py:1060`), created once as
  `name="shadow_memories"` (`grimoire.py:237`).
- `grimoire_reader.search()` queries `self._collection` (`grimoire_reader.py:200`),
  also `name="shadow_memories"` (`grimoire_reader.py:98`) — **same collection.**
- `remember()` writes to that same `self.collection.add(...)`
  (`grimoire.py:896`) and has **no `collection` parameter at all**
  (`grimoire.py:675-683`) — you cannot direct a `remember()` write elsewhere.
- `store_routed()` computes a domain route then **discards it** and calls plain
  `remember()` (`grimoire_module.py:362-371`) — despite its
  `base_collection="grimoire_knowledge"` name, it too writes to
  `"shadow_memories"`.
- Only `grimoire.py:237` and `grimoire_reader.py:98` create Chroma collections;
  both are `"shadow_memories"`. No second collection exists, and no Morpheus-
  reachable write method can create/target one.

**What IS enforceable (and sound):** the experiment-store arm. `ExperimentStore`
is a separate SQLite DB (`data/experiments.db`, table `failed_experiments`,
`experiment_store.py:55-68`) with **no ChromaDB** — recall structurally cannot see
it. So "dreams live only in the experiment store" is a real, provable containment.

**Severity: MEDIUM.** It does not itself open a leak — the wired G3a proof (V2b)
tests behavior, not the collection theory, so a phantom option can't leak on its
own. The risk is directional: the "or a collection recall never queries" wording
invites an executor to "fix" a leak by passing `collection=` to a write, which
either (a) raises against `remember()` and gets swallowed (feeding Finding 1's
false-green), or (b) if some future `remember(collection=…)` is added, writes to a
collection nobody proved recall skips. The clause should be deleted; G3a's only
honest arm is experiment-store-only.

---

## WHAT ELSE I CHECKED AND FOUND CLEAN

- **Break #3 (G3a/G3b split):** the split is honest. G3b (recall-side floor) is
  correctly marked NOT wired here and pinned to CL-6/RN3. The `recall()` code
  confirms the breach is real and Grimoire-owned (`min_trust` filter applied only
  `if min_trust > 0`, `grimoire.py:1026`). No break in the split itself.
- **Break #5 (roster count):** `MODULE_DESCRIPTIONS` has 10 keys
  (`cross_module_dreaming.py:28-47`), matching the patched plan; V4 asserts against
  the documented dream-subject roster, not registered modules. Clean.
- **Break #6 (Front 3.2 grep):** the no-write grep now includes
  `.remember(`/`.store(`/`store_routed(`, closing the RSI-invariant-#5 diff-write
  path. Clean.
- **Break #7 (A4 numeric trigger):** rejection <60% / any-noise-survives / >40%
  promoted are concrete. Clean.
- **Break #8 (CL-2 scope note):** the topology-vs-containment orthogonality note is
  present and correct. Clean.
- **New break the patches introduced:** none found beyond Findings 1–2 (and Finding
  2 is a wording carry-over sharpened by the patch, not a fresh code hole).

---

## RUN-THROUGH OF THE HIGH (how an executor lands a false-green CL-4)

1. Executor builds the promotion gate, reroutes all four census writers through it.
2. Writes the certifying V2(b) test against a real Grimoire on `tmp_path` — as the
   patch demands. Good so far.
3. The plant helper calls the gate, which calls `remember(content=dream,
   collection=self._speculation_collection, …)` — copied from the legacy
   `_store_speculative` shape (`rd_lab.py:555-560`).
4. `remember()` rejects `collection=` (`TypeError`, no such param). The gate's
   `try/except` (or the legacy wrapper's) swallows it. `remember()` returns nothing;
   no row is written.
5. Test queries `recall()` and `grimoire_reader.search()` → **0 hits** (the store is
   empty of the artifact).
6. Test asserts `0 == 0`. **PASS.** CL-4 goes green. The firewall was never
   exercised; the load-bearing gate is certified on an empty store.

The patch's real-Grimoire mandate does not catch this because the failure is on the
*write*, upstream of the retrieval the patch hardened. Only a plant-succeeded
positive control catches it.

---

## ONE-LINE SUMMARY FOR THE LEDGER

Census-grep patch (break #1) HOLDS — verified no fifth write path exists.
Certifying-run patch (break #4) **still breakable, HIGH:** V2(b) asserts "0 hits"
without asserting the plant landed, and the real `remember()` (silent dedup-return,
no `collection` param, swallowed `try/except`) makes a silent plant-failure the
default outcome of a naive fix → false-green CL-4. Plus one MEDIUM: G3a's "a
collection recall never queries" escape hatch is a phantom (single `shadow_memories`
collection; `remember()` has no `collection` arg). No self-activation path opened.
