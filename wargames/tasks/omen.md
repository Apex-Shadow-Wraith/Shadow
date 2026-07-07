# MISSION — Omen: the code brain that can rebuild itself (gated)

WARGAME ORDER. You are not executing this mission, you are wargaming it. A separate executor (Opus 4.8, max effort) runs the brief below later, on its own turn. Your job is the route it will follow. Follow the `wargame` skill: load SUCCESS.md, recon read-only, fight it on paper to `wargames/plans/omen.md`, build the Gates & Autonomy Ledger, dispatch a fresh red-team subagent to `wargames/red-team/omen.md`, patch, and log every pass in `wargames/LEDGER.md`. Split into parts if honest — Omen is large (21 tools) and the self-modification front deserves its own part with its own red-team. Justify the seam in the ledger.

**Read this before anything else:** the self-modification front of this mission plans the single most dangerous capability in the entire project — Omen writing to, testing, and committing changes to Shadow's own code, including Omen's own. Plan it in full; Master wants the capability real, not neutered. But every write to Shadow's code is a gated move, and the gate is the point. A plan that lets Omen self-modify without Master in the loop has failed the mission. A plan that makes Omen too timid to analyze and propose has also failed it. Full capability, hard gates, both present.

---

## Recon before you plan (read-only, quote file:line)

Read the real Omen and everything it touches. Plan against the code, not this brief.

- `modules/omen/omen.py` — the module. Enumerate the **real** tool set from the `handlers` dict, not the docs' "21" (docs already disagree: CLAUDE.md says 21, README says 21 but a different capability list). Note which tools are real and which are stubs. Critically: `code_review` is a Phase-1 **stub** — structural analysis only, with the note "Full code review requires LLM (Phase 2+)." That gap is central to this mission.
- The write-and-ship surface, because it already exists: `code_edit`, `code_read`, `git_commit`, `git_status`, and the sandbox tools `sandbox_execute` / `sandbox_validate` / `sandbox_to_production` / `sandbox_cleanup`. **Trace `sandbox_to_production` line by line** — this is the promotion path from scratch code to real code, and it is the crown jewel and the crown risk. What exactly does it move, where, and what (if anything) gates it today?
- `modules/omen/sandbox.py` — the `CodeSandbox`. Is it a real sandbox (process isolation, resource limits, no filesystem/network escape) or a subprocess with a timeout? Recon settles this with file:line; the honesty of every downstream gate depends on it. The abliterated model has no refusal backstop, so if the sandbox is thin, that's the first finding.
- `modules/omen/code_analyzer.py` — `CodeAnalyzer`, powering `code_analyze_file/dir/url`, `code_learn`, `code_compare`, `code_generate`. This is Omen's ability to read and understand code. How deep is it — AST-level structure, or real semantic analysis? Does it call the local model, Apex, or neither?
- `modules/omen/model_evaluator.py` — `ModelEvaluator`, the `model_list/pull/benchmark/evaluate/compare` tools. Relevant because "recreate himself better" means Omen must be able to evaluate the models it runs on.
- The pattern DB and failure-learning path — `pattern_store/search/apply`, `failure_log/search/stats`, `SEED_PATTERNS`, `VALID_PATTERN_CATEGORIES`. This is Omen learning from its own mistakes; recon whether it's wired into the execution path or a side store nobody reads.
- The intelligence source: what model actually drives Omen's judgment? The local abliterated Gemma, Apex (Claude API) escalation, or is code generation template-only? "Intelligent enough to fully recreate himself" is bounded by this, and the wargame must be honest about the ceiling. Trace whether Omen can escalate hard reasoning to Apex and under what conditions.
- Cerberus and the graph: does Omen's code-write/commit path route through Cerberus and the reversibility/snapshot system (`modules/cerberus/reversibility.py`)? Trace it. If commits or `sandbox_to_production` bypass Cerberus, that's the "looks governed but isn't" finding for this module, and it changes every gate.
- Standing policy already in `CLAUDE.md`: **never push** (Master pushes manually), don't commit if tests fail, no architecture decisions in Claude Code sessions, don't bypass Cerberus, don't edit `.env`, all merges are Master's manual `--no-ff`. There is also a live auto-commit-after-tests-pass git workflow — find it and confirm whether it's active, because that is an existing autonomous write surface.
- Tests: `tests/test_omen.py` and any `tests/test_code_analyzer`, `tests/test_sandbox`, `tests/test_model_evaluator`. Confirm coverage vs. claims; verify counts by collection, not grep.

Settle in recon, with file:line:
- What actually gates a write to Shadow's own code today — Cerberus, a snapshot, a test-pass requirement, or nothing?
- Is `sandbox_to_production` reachable autonomously (via a task the router can dispatch), or only by explicit human tool call?
- Does Omen's judgment come from a real model or from structural heuristics? (Determines whether "self-analysis" is real or aspirational.)

---

## THE MISSION BRIEF (the executor's orders, not yours)

Make Omen Shadow's full coding brain: able to write production code, analyze code deeply, find and fix flaws — including its own — and, under hard gates, rebuild itself and help repair Master's machine. Five fronts. For each: what exists today (from recon), what it must become, the exact build to close the gap, live verification, and every gate on every dangerous move.

**Front 1 — Full coding capability (the daily brain).** Omen must be a complete developer: execute code in a real sandbox, lint, test, and — the gap — perform *real* code review, not the current structural stub. Plan the upgrade of `code_review` from string-matching (`"try:" in code`) to genuine analysis: what drives it (local model, Apex escalation for hard reviews), what it produces (findings with file:line, severity, and a proposed fix), and how it's verified against known-bad code. Plan `code_generate` and the scaffolding tools to produce code that matches Shadow's own conventions (the `SEED_PATTERNS` exist for this — verify they're used). The bar: Omen writes code Master would accept, catches bugs a good reviewer would catch, and explains its work when Master is learning (the dual mandate — build fast when told "just do it," teach when Master is learning — is in the module's design; preserve it).

**Front 2 — Self-analysis (know your own code).** Omen must be able to read Shadow's entire codebase — including Omen's own — and find real flaws: logic errors, dead code, the "looks governed but isn't" pattern, delegation-vs-duplication violations, silent-failure paths, missing error handling. This is self-directed and repeatable: a standing capability to audit Shadow's code and produce a ranked findings report with file:line evidence and a proposed fix per finding. It overlaps the bug-hunt mission but from the inside and continuously — plan how they compose rather than duplicate (self-analysis is Omen auditing itself on demand; the bug-hunt is a whole-system sweep). Every finding is a *proposal*. Omen reports and recommends; it does not fix in this front. The output feeds Front 3, gated.

**Front 3 — Self-repair and self-recreation (the crown, gated).** This is the capability Master wants real and the one that must never run ungated. Omen proposes a change to Shadow's own code (a bug fix, a refactor, a new capability, an improvement to Omen itself), and the plan carries it through a gated pipeline:
  1. **Snapshot first** — a verified rollback point exists before any write (recon the reversibility/snapshot system; if it doesn't cover code files, that's part of the build). No write without a proven path back.
  2. **Sandbox** — the change is written and tested in the sandbox, never directly to production. `sandbox_to_production` is the only promotion path, and it is gated.
  3. **Test gate** — the full relevant test suite runs and passes on the change before promotion is even offered. Green tests on the *new* path, not a bypassed one (a suite that passes while guarding the old code certifies nothing).
  4. **Master's approval** — the diff is presented to Master for review; promotion to production and the commit happen only on Master's explicit approval. Never pushed — Master's manual `--no-ff` and push stand.
  5. **Rollback on any failure** — if promotion breaks something, the verified snapshot restores it, and the failure is logged to the failure DB so Omen learns from it.
  Plan this pipeline in full, including the hard case: Omen modifying Omen. When Omen rewrites its own code, the running instance must not corrupt itself mid-edit — plan how the change is validated and promoted without the editor sawing off the branch it sits on. "Intelligent enough to fully recreate himself" is the aspiration; be honest in the plan that recreation quality is bounded by the model driving Omen, with Apex escalation for changes beyond the local model's reliable reach, and Master's review as the backstop that catches what both miss.

**Front 4 — Repair Master's machine (conservative default, gated).** Omen should be able to help fix Citadel when Master wants it. Default scope is deliberately narrow: **read-only host diagnostics** (disk, memory, service status, logs, package state, the kind of thing that diagnosed the 8TB-drive-link-down and the EXPO-freeze) plus **proposed fixes that Master approves before any host write**. Plan the diagnostic capability fully — it's low-risk and high-value. Plan host writes (installing a package, changing a service, editing a config, touching firmware/BIOS-adjacent settings) as gated proposals only: Omen presents the exact command and what it does; Master runs it or approves it. The machine Omen runs on is the machine it could brick — start narrow, widen only as trust is earned, and say so in the gates. No `sudo`, no destructive `systemctl`, no `.env` edits autonomously — these are already denied in `CLAUDE.md`; the plan honors and extends that.

**Front 5 — The gates (the contract).** Build the Gates & Autonomy Ledger as the mission's most important deliverable. Every write to Shadow's code, every `sandbox_to_production`, every `git_commit`, every host write is listed with: what goes wrong ungated, the gate (snapshot-first / test-pass / Cerberus / Master's diff approval), and the earned-by condition. The load-bearing gates:
  - **No production write without a verified rollback snapshot.** Earned-by: the snapshot exists and was confirmed restorable.
  - **No promotion without the relevant test suite green on the new path.** Earned-by: collection-verified test run passes.
  - **No self-modification commit without Master's diff review.** Earned-by: Master has seen and approved the exact diff. Never pushed.
  - **No autonomous host write.** Earned-by: never, in the default scope — host writes are always Master-approved proposals until Master explicitly widens scope.
  - **Omen-modifying-Omen** gets an extra gate: the change is validated by a *separate* run, not by the instance being modified.

Constraints that bind the whole mission:
- **Full capability, hard gates, both present.** Never neuter Omen's ability to analyze and propose; never let it write to itself ungated.
- **Report and propose; Master approves changes.** The line between "find/recommend" (ungated) and "change" (gated) is the spine of the whole plan.
- **Green tests on a bypassed path certify nothing.** Every verification runs against the new code, not the old.
- **No push, ever, by Omen.** Master merges `--no-ff` and pushes manually. This is not negotiable and predates this mission.
- **The abliterated model has no refusal backstop.** Cerberus, the sandbox, the test gate, and Master's review are the backstop. Plan like nothing downstream saves a miss.

---

## Wargame-specific instructions

- **Split this.** Front 3 (self-repair/recreation) should almost certainly be its own `wargames/plans/omen-part3-selfmod.md` with its own red-team pass, because the self-modification pipeline is a mission in itself and its gates are the highest-stakes lines in the whole kit. Justify in the ledger.
- **Recon must settle the sandbox's real strength and what gates `sandbox_to_production` today before you plan Front 3.** If the sandbox is a subprocess-with-timeout and promotion is ungated, that is the finding that reshapes the entire self-mod plan — put the exact check in the plan as a RECON NEEDED with its settling command.
- **Red-team Front 3 hardest.** Tell the attacker subagent to play an executor that follows the self-mod plan and tries to reach a production write without a snapshot, without green tests, or without Master's approval — and to try the Omen-modifying-Omen corruption case where the running instance breaks itself mid-edit. If the attacker reaches an ungated or unrecoverable write on paper, that break and its patch are the most important lines in the plan.
- **Be honest about the intelligence ceiling.** "Fully recreate himself" is bounded by the local model's capability. The plan must state where Apex escalation is required and where Master's review is the real safety net, rather than implying Omen can autonomously out-engineer its own base model.
- **Do not ask the executor to explain its reasoning in its output** — request artifacts, diffs, findings, test assertions, and proposed commands, never the thinking itself. (Reasoning-extraction phrasing can trip a safeguard and silently reroute a Fable session to Opus 4.8 mid-run.)
- Anything recon can't settle about the host or the sandbox is a `RECON NEEDED` with the exact command for the executor to run first — never a guess.
