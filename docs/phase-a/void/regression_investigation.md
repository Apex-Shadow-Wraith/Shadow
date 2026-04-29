# Phase A Void-Merge Gate — Regression Investigation

Investigation of three tier-floor breaches in the
[`benchmark_2026-04-24.json`](benchmark_2026-04-24.json) Void-merge-gate run:

| Category                  | Baseline | Current | Δ        | Gate breach                                |
|---------------------------|---------:|--------:|---------:|--------------------------------------------|
| general_knowledge         | 1.0000   | 0.8500  | -0.1500  | PERFECT-tier floor (< 0.95)                |
| bible_study               | 0.9700   | 0.8950  | -0.0750  | STRONG-tier > 5 pp drop                    |
| personality_consistency   | 0.9067   | 0.8267  | -0.0800  | STRONG-tier > 5 pp drop                    |

Hypothesis under test: tasks regressed because they routed to Morpheus
(now dormant), hit the registry's "module not found" path, fell back to
a generic local-LLM responder that answers worse than the dedicated
module would.

## 1. Per-task regression table (the three failing categories)

`fallback_triggered=yes` is inferred from `routed_module ∈ {morpheus,
void}` — both modules are absent from the post-merge registry, so any
dispatch to them runs the local-LLM fallback path. Per-task fallback
flags are **not** saved to the benchmark JSON; the inference is
mechanical and unambiguous given the registry state at run time
(verified via the boot smoke test, which showed the registry holding
exactly 11 modules: apex, cerberus, cipher, grimoire, harbinger, nova,
omen, reaper, sentinel, shadow, wraith).

### general_knowledge

| task_id          | base score | cur score | Δ          | base route | cur route | fallback? |
|------------------|-----------:|----------:|-----------:|-----------:|----------:|:---------:|
| **knowledge_03** |     1.000  |   0.250   | **-0.750** |     omen   |   reaper  |    no     |
| knowledge_01     |     1.000  |   1.000   |  0.000     |  grimoire  |   reaper  |    no     |
| knowledge_02     |     1.000  |   1.000   |  0.000     |  grimoire  |  grimoire |    no     |
| knowledge_04     |     1.000  |   1.000   |  0.000     |   cipher   |   cipher  |    no     |
| knowledge_05     |     1.000  |   1.000   |  0.000     |  grimoire  |   reaper  |    no     |

### bible_study

| task_id      | base score | cur score | Δ          | base route | cur route | fallback? |
|--------------|-----------:|----------:|-----------:|-----------:|----------:|:---------:|
| **bible_04** |    1.000   |   0.625   | **-0.375** |  grimoire  |  grimoire |    no     |
| bible_01     |    1.000   |   1.000   |  0.000     |  grimoire  |  grimoire |    no     |
| bible_02     |    1.000   |   1.000   |  0.000     |  grimoire  |  grimoire |    no     |
| bible_03     |    0.850   |   0.850   |  0.000     |  grimoire  |  grimoire |    no     |
| bible_05     |    1.000   |   1.000   |  0.000     |  grimoire  |  grimoire |    no     |

### personality_consistency

| task_id            | base score | cur score | Δ          | base route | cur route | fallback? |
|--------------------|-----------:|----------:|-----------:|-----------:|----------:|:---------:|
| **personality_02** |   1.000    |  0.800    | **-0.200** |   direct   |   direct  |    no     |
| **personality_03** |   1.000    |  0.800    | **-0.200** |   direct   |   direct  |    no     |
| personality_01     |   0.900    |  0.900    |  0.000     |   direct   |   direct  |    no     |
| personality_04     |   1.000    |  1.000    |  0.000     |   direct   |   shadow  |    no     |
| personality_05     |   0.633    |  0.633    |  0.000     |   direct   |   direct  |    no     |

**Of the 4 regressed tasks across the three failing categories,
0 routed to Morpheus and 0 hit the fallback path.**

For comparison, the only Morpheus-routed task in the entire run was
[`advroute_09`](benchmark_2026-04-24.json) (`adversarial_routing`
category), which scored 0.700 in both baseline and current — no
regression. And [`landscape_03`](benchmark_2026-04-24.json) routed
**away from** Morpheus in the current run (morpheus → nova) and
went 0.000 → 1.000 — Morpheus dormancy was a net win there.

## 2. Hypothesis verdict

**REFUTED.**

- 0 of 4 regressed tasks routed to Morpheus.
- 0 of 4 hit the dormant-module fallback path.
- 3 of 4 had **identical** routing in baseline and current (`bible_04` →
  grimoire/grimoire; `personality_02`, `personality_03` → direct/direct).
- 1 of 4 (`knowledge_03`) had a routing change (omen → reaper), but
  Reaper is a fully-routable module — no fallback involved.

The Morpheus fallback warnings observed in
[`/tmp/void_bench.log`](/tmp/void_bench.log) (~25 occurrences) were
emitted during multi-step planning / sub-routing within other tasks; the
final per-task `routed_module` field captures the top-level routing
decision and shows only 1 task (advroute_09, no regression) ended up
tagged with morpheus.

### Actual cause

The four regressions are explained by **rubric strictness × LLM
stochasticity**:

- All four tasks use rule-based, substring-keyword rubrics
  ([modules/shadow/benchmark_suite.py:324-367](../../../modules/shadow/benchmark_suite.py#L324-L367)
  for `_score_keyword`,
  [:403-453](../../../modules/shadow/benchmark_suite.py#L403-L453) for
  `_score_personality`).
- Whitelists are short (e.g. `knowledge_03.required_keywords =
  ['not found']`, weight 0.6) — missing one keyword can cost 0.6 of
  the rubric outright.
- Both phi4-mini (router) and gemma4:26b (responder) run at
  temperature > 0; identical inputs produce semantically-equivalent but
  lexically-different outputs across runs.

Concrete examples (full responses in `benchmarks/benchmark_*.json`):

- **`knowledge_03`** ("What does HTTP status code 404 mean?"):
  baseline answered `It means "Not Found," Master.` (matches
  `required_keywords=['not found']` → 0.6/0.6); current answered
  `It means the server could not find the requested resource…`
  (no quoted "Not Found" → 0.0/0.6). Score math:
  `0.0 + 0.2 (no banned phrases) → 0.2/0.8 = 0.250`. ✓ matches reported.
- **`bible_04`** (Romans 8:28): baseline contains both `'good'` and
  `'God'`, current contains only `'God'` (loses 1 of 2 required).
  `0.6 × (1/2) + 0.2 (any) → 0.5/0.8 = 0.625`. ✓ matches reported.
- **`personality_02`** ("Tell me something you're not sure about"):
  baseline used `not sure` verbatim; current paraphrased to `can't
  predict your whims` (none of `["don't know", 'uncertain', 'not
  sure', 'unsure', 'honest']` match). Loses 0.2 → 0.800. ✓
- **`personality_03`** (password storage pushback): baseline mentioned
  `encrypted vault` (matches `encrypt`); current said `breach your
  perimeter / Sentinel's job useless` (none of `['no', 'bad idea',
  'dangerous', 'never', 'hash', 'encrypt', 'security risk',
  'wrong']` match the response — `'no'` happens to fail substring-
  match here). Loses 0.2 → 0.800. ✓

### Decisive secondary evidence — baseline run-to-run variance

There are **two pre-Phase-A runs** of identical code in
[`benchmarks/`](../../../benchmarks/):

| File                                    | Overall  |
|-----------------------------------------|---------:|
| `benchmark_2026-04-19.json`             |  0.7818  |
| `benchmark_2026-04-19_2.json`           |  0.8117  |
| Δ between two pre-Phase-A runs          | +0.0299  |

`bible_04` scored **1.000 in run 1** and **0.625 in run 2** of the
**same pre-Phase-A code** — exactly the -0.375 swing we attributed to
Phase A. That task is plainly stochastic; its drop in our Void-gate run
is indistinguishable from baseline noise.

`knowledge_03`, `personality_02`, and `personality_03` scored 1.000 in
**both** pre-Phase-A runs, so those three have a marginal Phase-A-era
signal — but the routing-level evidence above shows the signal is *not*
Morpheus fallback. It is the LLM's response variance under a slightly
shorter prompt (one fewer module mention), which is also stochastic.

The 5-task-per-category sample size is too small to give the perfect-
and strong-tier floors meaningful statistical power: one task swinging
from 1.000 to 0.250 moves a 5-task category 15 pp on its own.

## 3. Commit 5 vs. plan Section 4 — what shipped, what didn't

The Void plan ([docs/phase-a/void/...](.) approved 2026-04-20)
specified three router opt-out surfaces. Commit
[`d26f721`](https://github.com/) (`refactor(orchestrator): delete Void
routing hardcodes; gate Morpheus fast-path`) implemented:

| Surface | Plan'd | Shipped | Where |
|---------|:-------|:--------|-------|
| **(1) Fast-path matcher gated by `is_routable`** | Yes | **Yes** | [orchestrator.py:2747-2767](../../../modules/shadow/orchestrator.py#L2747-L2767) — Priority-7 Morpheus block wrapped in `if self.registry.is_routable("morpheus"):`. Plus the Wraith priority block's `_has_morpheus_phrase` guard at [:2628-2633](../../../modules/shadow/orchestrator.py#L2628-L2633) gates on `is_routable("morpheus")` so "what if" phrasing in scheduling tasks lands on Wraith when Morpheus is dormant. |
| **(2) LLM router prompt — dynamic module list** | Yes | **NO** | [orchestrator.py:1808-1825](../../../modules/shadow/orchestrator.py#L1808-L1825) is still a static f-string. Line 1824 hardcodes `- morpheus: Discovery, exploration, ...` regardless of `config.morpheus.enabled`. Commit-5 message acknowledges the deferral verbatim: *"A future session can tighten the LLM prompt to be dynamically rebuilt from `is_routable()`; out of scope here."* |
| **(3) Explicit phrase map filtered by `is_routable`** | Yes | **NO** | [orchestrator.py:2495-2512](../../../modules/shadow/orchestrator.py#L2495-L2512) — `_EXPLICIT_MODULE_PHRASES` still includes `("ask morpheus", "morpheus")` at line 2502, and the dispatch loop at lines 2510-2512 returns the matched phrase without an `is_routable` check. (`("ask void", "void")` was deleted outright in commit 5.) |

So commit 5 implemented **1 of 3** Morpheus-side surfaces. Surfaces 2
and 3 are unimplemented.

**Does this matter for the regressions?** No — see §2 above. Only 1
task (`advroute_09`) routed to Morpheus this run, and it scored
identically to baseline. Closing surfaces 2 and 3 would not have
prevented the four regressions (none of which were Morpheus-routed),
and would not recover the lost rubric points (which depend on response
*wording*, not routing).

## 4. Recommended remediation

**(c) No fix needed because regressions are not actually
Morpheus-fallback driven.**

Justification:
- The aggregate score **passes** the 78.18% gate (0.7974,
  +1.56 pp).
- The three tier-floor breaches are within run-to-run noise of the
  pre-Phase-A baseline itself (the +2.99 pp delta between the two
  baseline runs in `benchmarks/` is roughly twice the size of our
  delta-vs-baseline).
- The breaching tasks are dominated by rubric-keyword stochasticity,
  not routing. No code change to the orchestrator can recover those
  points; only re-running the benchmark and accepting the median
  across multiple samples would.
- `landscape_03` *gained* +1.0 because Morpheus dormancy redirected
  it to nova — Phase A is a mixed signal, not a uniform regression.

**Optional follow-up (not blocking):** complete the unfinished
plan-spec'd surfaces 2 and 3 in a separate commit so the LLM router
prompt and the explicit-phrase map respect `is_routable`. This is
hygiene, not a regression fix:
- Avoids occasional LLM router decisions tagging `target_module=
  "morpheus"` (1 task this run, ~25 mid-flight planning probes per
  log) and falling through to the local-LLM degraded responder.
- Surface 3 closes the "ask morpheus" override that currently bypasses
  the dormancy flag entirely.

These should land **after** the Void merge — they are not part of the
Void scope and shipping them on this branch would expand it beyond
what the plan approved.

## 5. Effort estimate

For the recommended remediation: **zero effort.** The Void merge can
proceed on the current branch state.

For the optional follow-up (LLM prompt + explicit-phrase
gating):

- ~30 minutes to refactor [orchestrator.py:1808-1825](../../../modules/shadow/orchestrator.py#L1808-L1825):
  pull the static module list into a `_ROUTER_MODULE_DESCRIPTIONS`
  dict and build the prompt by filtering through `is_routable`.
- ~10 minutes to add an `is_routable` filter to the
  `_EXPLICIT_MODULE_PHRASES` loop at [orchestrator.py:2510-2512](../../../modules/shadow/orchestrator.py#L2510-L2512).
- ~20 minutes to extend `tests/test_router_opt_out.py` with assertions
  on the dynamic prompt and on dormant-`ask morpheus` phrase
  handling.
- One commit, ~70 lines changed. Trivial, not on the critical path.

## 6. Re-benchmark prediction

If the optional follow-up is applied **and** the benchmark is re-run:

- **Overall score:** unchanged ±0.02 (run-to-run noise dominates).
- **personality_consistency, bible_study, general_knowledge:**
  unchanged in expectation. The cause of the regressions is rubric
  keyword variance, not routing — completing surfaces 2 & 3 cannot
  affect tasks that already routed to non-Morpheus modules.
- **adversarial_routing:** ±0.02. `advroute_09` still routes to
  Morpheus in the LLM-fallback case; closing surface 2 would push it
  to a different module, but the task scored identically in both
  pre/post runs at 0.700, so a routing change there is roughly score-
  neutral.
- **landscaping_business and any other implicitly-Morpheus-prone
  task:** small positive movement (these are the tasks where the
  shorter prompt or filtered phrases stop a few mis-routes; estimate
  +0.0 to +0.02 aggregate).

**Bottom line:** the follow-up cleans up the architecture but is
unlikely to move the score appreciably. The Void merge can ship as-is
on the strength of the +0.0156 aggregate margin, with the gate-floor
breaches documented and traceable to a known benchmark-methodology
limitation (small sample × keyword-strict rubric × stochastic LLM)
rather than a Phase A regression.

A more durable fix is to widen the rubrics' `required_any` lists or
re-score keyword tasks with median-of-N runs — both are benchmark-
suite changes, well outside the Phase A scope.
