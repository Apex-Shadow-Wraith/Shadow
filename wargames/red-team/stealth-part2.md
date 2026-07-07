# RED-TEAM — Reaper Part 2: Injection-Source Discipline + Tier-2 Gate

**Attacker:** fresh instance, blind executor of `wargames/plans/stealth-part2-injection-gate.md`.
**Target:** the injection seam (Front 4), the autonomy gate (Front 5), the detector (Front 2).
**Method:** read-only against the code (grep, Read, `pytest --collect-only`). No mutation.
**Recon cross-checked:** `wargames/recon/stealth.md` file:line claims verified against source.

The plan is unusually strong: choke helper, an AST/grep guard against direct
`remember`, a real `if`-around-`add_job` gate with an enforcement test, a
fail-toward-flagging detector, and an explicit A2 abort against the read-side
over-claim. Most of my usual breaks were pre-empted. But it has **one hole the
plan never sees**, and it is exactly the failure class the plan claims to close.

---

## Findings table

| Plan-line quote | How it fails | Severity |
|---|---|---|
| "**(2)** the gate: find any way `standing_research` still fires with the flag False (a second scheduler, a **direct `run_task(\"standing_research\")` call**, the job added elsewhere)." | The plan *names* this attack in its own red-team section but **never defends it in the build**. Move 4.3 gates only `add_job` (the 12h timer). `StandingTaskScheduler.run_task()` (`standing_tasks.py:110-124`) calls `self._run_standing_research()` **directly**, bypassing the scheduler entirely — and it is reachable from the live CLI at `main.py:574-578` via `/schedule run standing_research`. With `autonomous_research_enabled=False`, the timer is dormant but `/schedule run standing_research` still fires the autonomous scraped-content write. The gate the plan calls "WIRED, not named" (G1) is wired on ONE of two entry points. **This is the "looks governed but isn't" failure the plan warns about, in the plan itself.** | **CRITICAL** |
| "Route ALL six write paths through it (recon §6): `fetch_page` (`reaper.py:988`), research full/summary (`:1192`, `:1217`), Reddit (`:1377`), YouTube (`:1625`), AND the scheduler write (`standing_tasks.py:236` …)." | The choke helper `_untrusted_store` is defined as `self.` on Reaper, but the scheduler write at `standing_tasks.py:236` is in `StandingTaskScheduler`, which holds no Reaper instance — it calls `grim.remember(...)` on the Grimoire internal directly (`standing_tasks.py:233-249`). The plan hand-waves "goes through an equivalent tagged call" (M4.2 counter) but never specifies WHAT that equivalent is or how the `test_no_direct_remember_in_reaper` AST guard (scoped to `reaper.py`) would ever catch a bypass in `standing_tasks.py`. The guard is scoped to the wrong file to protect the sixth path. If the executor tags five paths and forgets to plumb a helper into the scheduler, **no test catches it** — the guard only reads `reaper.py`. | **HIGH** |
| "recall ignores `safety_class` (recon §6) → **NOT met.**" / V-seam: "today it returns undemoted." | Under-stated, and it hides the real read-side gap. `recall()` (`grimoire.py:965-1165`) not only ignores `safety_class` for **filtering** — the returned memory dict (`grimoire.py:1142-1161`) **does not include `safety_class` at all**. So a downstream consumer that WANTED to honor the marker Reaper writes cannot even see it in a `recall()` result. Reaper's marker is write-only and invisible on read. The plan's V-seam records "returns undemoted" but not "the field isn't even surfaced" — a consumer reading the V-seam line could believe the marker is retrievable-but-not-yet-acted-on, when it is not retrievable at all. | **MED** |
| "**Optional phi4-mini classifier** (already the Reaper scoring model, `config.py:273` — no new dependency)" and Move 4.1 as a whole. | The plan tells the executor to **build a new detector from scratch** inside Reaper and never greps for an existing one. A full `PromptInjectionDetector` already exists at `modules/cerberus/injection_detector.py` (regex set for `ignore previous instructions`, `disregard … instructions`, `new instructions:`, role-hijack, plus an `analyze()` pipeline). Recon §5 said "No injection detection" — **true only within Reaper**; the plan inherits that blind spot and never checks Cerberus. Result: a second, divergent injection detector, violating the plan's own "Do not invent divergent payload sets across the two missions" rule — and violating it against Cerberus, not just Sentinel. | **MED** |
| "`evaluate_source()` … Tier-1 = 0.7 … a redirect (`allow_redirects=True`, reaper.py) landing on a Tier-1 URL that re-earns 0.7" (red-team focus) | Not a break, but the plan mis-frames the redirect risk. `evaluate_source(url)` is called at `reaper.py:930` on the **original** URL, **before** `requests.get(..., allow_redirects=True)` at `:935-938`. So a redirect *from* a benign URL *to* an attacker page is stored under the ORIGINAL url's tier — the reverse of the plan's worry. After the cap (M4.2) both cases collapse to `UNTRUSTED_WEB_TRUST`, so the cap neutralizes it — but the plan's stated redirect mechanism ("lands on a Tier-1 URL that re-earns 0.7") is not how the code works, so an executor tracing it would find nothing and could wrongly conclude "no redirect risk." | **LOW** |
| "each returns `instruction_like=True` with `injection_score >= 0.5`; and `test_benign_content_not_flagged` … Both green." (M4.1 Expected observation) | Checkable, but the payload corpus is **RECON NEEDED and unbuilt** ("If absent, build the corpus here"). The move's pass condition ("≥12 known payloads") is only as good as a corpus the executor writes itself — the `zero-width-obfuscated "sy​stem:"` example the plan gives would defeat a naive regex (`sy​stem` ≠ `system`), and the plan does not require the detector to strip zero-width chars *before* matching, only lists it as a "matched pattern" to detect. A payload split across `WEB_MAX_ARTICLE_CHARS=8000` (`config.py:219`) so the stored slice (`text[:8000]`, `reaper.py:973`) is clean while the inspected full `text` triggers — or vice versa — has no defined handling: the plan inspects `content` but never says whether that's the full text or the truncated slice. Ambiguous inspection boundary = a real evasion the tests won't necessarily cover. | **MED** |
| Front-5 earned-by #2: "Sentinel adversarial injection suite green. Check: `pytest tests/ -k \"sentinel and injection\"`. Today: **RECON NEEDED**." | `grep -rln injection tests/ \| grep -i sentinel` returns **nothing** — there is no Sentinel injection suite in the tree today. The earned-by condition points at a suite that does not exist, so gate G1 can never be honestly satisfied from within this plan's world. Correctly marked RECON NEEDED, but it means one third of the flip-gate is un-runnable now — worth flagging so Master doesn't read "3 checkable conditions" as "3 runnable today." | **LOW** |

---

## Single worst break — the CRITICAL, with the concrete run-through

**The gate is wired on the scheduled path and wide open on the manual path.**

Move 4.3 guards the 12h timer:
```python
# standing_tasks.py:65-100, after the plan's M4.3 edit
if config.reaper.autonomous_research_enabled:      # default False
    self._scheduler.add_job(self._run_standing_research, "interval", hours=12, id="standing_research", …)
else:
    self._logger.info("standing_research DORMANT …")
```
`test_research_job_absent_when_flag_false` goes green: `"standing_research" not in
{j.id for j in scheduler._scheduler.get_jobs()}`. The plan marks Front 5 done and
G1 "WIRED." V-gate confirms dormant-at-boot. Everything the plan checks passes.

But `run_task` is untouched:
```python
# standing_tasks.py:110-124 — UNCHANGED by the plan
def run_task(self, task_name: str) -> str:
    runners = {..., "standing_research": self._run_standing_research, ...}
    runner = runners.get(task_name)
    runner()          # ← calls _run_standing_research() DIRECTLY, no add_job, no flag check
```
And it is live on the CLI:
```python
# main.py:569-578 — the /schedule command handler
elif cmd.startswith("/schedule"):
    if len(parts) >= 3 and parts[1].lower() == "run":
        task_name = parts[2].lower()                       # "standing_research"
        result = standing_scheduler.run_task(task_name)    # fires the autonomous write
```

**Run-through:**
1. Executor ships the plan exactly. `autonomous_research_enabled=False`. All plan
   tests green, V-gate green, "gate WIRED" recorded.
2. At the running Shadow CLI, anyone (or any orchestrator path that reaches
   `run_task`) types `/schedule run standing_research`.
3. `run_task` → `_run_standing_research()` (standing_tasks.py:209) → `reaper.execute("web_search", {topic, 5})` → `grim.remember(content="Standing research: …", source="standing_task", trust_level=0.3, check_duplicates=False)` (standing_tasks.py:236-249).
4. Autonomous scraped web content enters permanent Grimoire memory. The 12h flag
   was False the entire time. The gate the mission calls "the deliverable Master
   cares about most" (Front 5) did not stop it.

Worse: if the executor takes the plan literally and routes only the six *listed*
write paths through `_untrusted_store`, the `run_task`→`_run_standing_research`
write at `standing_tasks.py:236` is the SAME line as the scheduled write, so it
inherits whatever tagging the scheduler path got — BUT the **firing** is
ungated. The plan closes the poison-tagging on that write while leaving the
autonomy trigger open. So even post-plan, an operator can autonomously pull the
web on demand with the "autonomous research" flag reading False — the exact
"named but not truly wired" CRITICAL the brief defines: *"A gate that is named
but not truly wired is the 'looks governed but isn't' failure — CRITICAL."*

The plan **names this attack in its own red-team focus** ("a direct
`run_task(\"standing_research\")` call") and then **never patches it in Move
4.3**. The gate must wrap the firing, not the registration: `run_task` must
refuse `standing_research` (or any autonomous web pull) unless
`config.reaper.autonomous_research_enabled` is True, with its own test
(`test_run_task_refuses_standing_research_when_flag_false`). Until it does, Front
5 is decorative on the one path a human is most likely to actually hit.

---

## Verdict

I could not break the choke-helper convention on `reaper.py` (the AST guard is
genuinely clever) and I could not break the write-side trust cap (0.7 → ≤0.3 is
real and testable). But the plan fails on the gate it was built to deliver:
`standing_research` fires through `run_task`/`/schedule run standing_research`
(`standing_tasks.py:110-124`, `main.py:574-578`) with `autonomous_research_enabled=False`,
because Move 4.3 gates only `add_job` and the plan — despite listing this exact
attack in its own red-team notes — never wires the guard onto the manual firing
path. That is a CRITICAL "looks governed but isn't." Two supporting cracks
compound it: the `_untrusted_store` choke and its AST guard live in `reaper.py`
while the sixth (scheduler) write lives in `standing_tasks.py` where the guard
cannot see it (HIGH), and the read side doesn't merely ignore `safety_class` —
`recall()` never returns it, so Reaper's marker is invisible, not just unhonored
(MED). The write-half of the injection defense is sound; the autonomy gate has a
back door the plan pointed at and walked past.
