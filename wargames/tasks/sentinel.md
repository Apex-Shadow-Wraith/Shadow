# MISSION — Sentinel: the security monster (defense-only)

WARGAME ORDER. You are not executing this mission, you are wargaming it. A separate executor (Opus 4.8, max effort) runs the brief below later, on its own turn. Your job is the route it will follow. Follow the `wargame` skill: load SUCCESS.md, recon read-only, fight it on paper to `wargames/plans/sentinel.md`, build the Gates & Autonomy Ledger, dispatch a fresh red-team subagent to `wargames/red-team/sentinel.md`, patch, and log every pass in `wargames/LEDGER.md`. Split into parts if the mission is honestly more than one — Sentinel almost certainly is; justify the seam in the ledger.

This brief folds in what was scheduled as the Session 56 **security sprint**. The wargame IS the security sprint's threat model and plan. Treat it with that weight.

---

## Recon before you plan (read-only, quote file:line)

Read the real Sentinel and everything it touches. Do not plan against this brief's description — plan against the code. Start here, expand as the traces demand:

- `modules/sentinel/sentinel.py` — the module. Note the **HARD CONSTRAINT** at the top: defense only, never retaliates, never probes systems it does not own. Note the Phase-1 status (psutil-based; no Suricata/Zeek yet). Enumerate the real tools via `get_tools()`, not the docs' count.
- `modules/sentinel/security_analyzer.py` — firewall analysis/scoring/generation, the `learn_firewall_concepts` → Grimoire path.
- `modules/sentinel/threat_intelligence.py` — the attack-pattern and named-threat knowledge base (prompt_injection, data_poisoning, trojans, rootkits, ransomware, Mirai, LockBit, etc.). This is Sentinel's brain; know what's in it and what's stubbed.
- `modules/cerberus/` — the whole directory: `cerberus.py`, `injection_detector.py`, `reversibility.py`, `watchdog.py`. **Sentinel proposes, Cerberus checks.** Trace that actual handoff — does every Sentinel response really go through Cerberus, or does it only look like it? This is the "looks governed but isn't" hotspot for the whole module.
- The Grimoire trust system — `modules/grimoire/grimoire.py`, the `remember()` signature (`source`, `trust_level`, `source_module`, `check_duplicates`), `recall()` (`min_trust`, filters), and `supersede()`. The injection-defense story lives or dies on how trust levels are actually assigned and enforced at retrieval, not on their existence.
- Reaper's write path into Grimoire — `modules/reaper/` — because **the live prompt-injection vector is Reaper-scraped web content flowing into Grimoire persistent memory**, then retrieved into a prompt later. Trace one scraped item from fetch to stored memory to future recall. What trust level does scraped content actually get? Is it wrapped as data or as instructions when it comes back out?
- The graph path — `modules/shadow/graph/` (post-merge) and the orchestrator's dispatch — to see where a Sentinel alert or a Cerberus denial actually sits in the request flow now that Track B is merged.
- `main.py` wiring for Sentinel, its config block, and its tests: `tests/test_security_analyzer.py`, any `tests/test_sentinel*`, `tests/test_threat_intelligence*`. Confirm what's actually covered vs. asserted.
- The abliteration reality: Shadow's base model has manufacturer alignment stripped. **There is no model-level refusal backstop.** Whatever Sentinel and Cerberus don't catch, nothing downstream will. Plan with that in mind — it raises the stakes on every boundary.

Settle these boundary questions in recon and state the answer with file:line:
- Is Sentinel a live routable module, or has it merged into Cerberus in the codebase (docs conflict)? Plan against what `main.py` and the router actually do.
- Does "all responses go through Cerberus" hold in code, or is it an aspiration in a docstring?
- Is there any host-level defensive capability today (ClamAV, AIDE, rkhunter, ufw/nftables management), or only the knowledge of them in `threat_intelligence.py`?

---

## THE MISSION BRIEF (the executor's orders, not yours)

Make Sentinel a security monster — the best defensive security capability Shadow can have on Citadel — **without ever crossing the white-hat line.** Defense only. Sentinel's never retaliates, never launches offensive operations, never probes, scans, or touches any system Master does not own. Sentinel knows how all of these operations work and function in order to defend Shadow and Citadel, without this knowledge true defense is not possible. Sentinel has the capability to red team and blue team his own software and system so that he can learn and improve his defenses.

Deliver a complete defensive posture across five fronts. For each, the plan states what Sentinel can do today (from recon), what it must be able to do, the exact build to close the gap, how it's verified live, and every gate on every dangerous move.

**Front 1 — Defend Citadel (the host).** Sentinel must protect the machine it lives on. File-integrity monitoring that actually alerts on change to Shadow's own code, config, identity files, and the model files (not just a baseline that's never checked). Malware and virus defense — plan the real tools recon says are absent (ClamAV signatures, AIDE or the existing baseline hasher, rkhunter/chkrootkit for rootkits) with how each integrates, how quarantine works (there's a quarantine dir already — verify it's wired), and what a detection actually triggers. Network posture — connection/port monitoring via the existing psutil path, firewall config analysis (the analyzer exists) and, if in scope, *proposing* nftables/ufw rules for Master to apply. Host defense that writes to the host, changes firewall rules, or quarantines a file is a gated action — see the gate front.

**Front 2 — Defend Shadow against prompt injection (the live vector).** This is the highest-severity front and the reason the security sprint exists. The threat: hostile instructions embedded in web content that Reaper scrapes, written into Grimoire, and later retrieved into a prompt where the abliterated model — with no refusal backstop — executes them. The severity comes from **persistence**: one poisoned memory poisons every future retrieval. Plan the mitigation Master has scoped as minimum-viable-plus, and pressure-test whether it's actually sufficient:
  - **Provenance tagging** — every Grimoire entry sourced from scraped/untrusted content is tagged untrusted-source at write time. Recon whether the `source`/`trust_level` fields already carry this and whether Reaper sets them correctly.
  - **Retrieval-time demotion** — untrusted content, when recalled, is wrapped as data-to-analyze, never as instructions-to-follow, and never silently promoted in trust. Plan where in the retrieval/context-assembly path this wrapping happens and prove it can't be bypassed.
  - **An adversarial test suite** — planted injection pages (a corpus of known injection payloads) that assert the payload never executes: it gets stored as inert tagged data, retrieved as data, and never changes Shadow's behavior. This is the verification that the front actually holds.
  - Then attack your own mitigation: a homoglyph payload, an injection that impersonates a Cerberus/system instruction, a payload that arrives split across two memories and reassembles at recall, a payload that tries to raise its own trust level. Plan the counter for each, or mark it a known residual with the gate that contains it.

**Front 3 — Red-team Sentinel and Shadow itself (know your own weaknesses).** Sentinel must be able to assess Shadow's own defensive posture — a standing, repeatable self-audit. Plan a self-red-team capability: enumerate Shadow's attack surface (Reaper web ingress, Grimoire write path, the API keys in `.env`, Telegram/Discord tokens, the MCP tool surface, the host), and for each, the defensive check that proves it's covered. This is white-hat self-assessment — Sentinel probes *Shadow's own* posture, never anyone else's. The output is a posture report (route it through Harbinger, which already consumes Sentinel alerts) with findings ranked by severity and the fix for each. Any finding that proposes a change to Shadow's own code or config is a *proposal*, gated behind Master — Sentinel reports and recommends; it does not self-patch.

**Front 4 — Detect, decide, respond (the live loop).** Tie the fronts into a running loop: monitor → detect → assess threat level (the `threat_assess` path exists) → decide response → act or alert. Plan the decision logic: which detections Sentinel handles autonomously (read-only, non-destructive — logging an alert, raising a Harbinger notification) and which require Master (anything that quarantines, changes firewall rules, kills a process, or touches the host). The autonomous set must be provably safe — a detection response that can itself cause harm is not autonomous, it's gated. Plan the dead-man's-switch angle too: if Sentinel's own monitoring goes silent, that silence must alert (the SearXNG-dead-for-months lesson applies to security monitoring more than anything).

**Front 5 — The gates (this is the security sprint's spine).** Every dangerous move above wears a gate. Build the Gates & Autonomy Ledger as the sprint's actual output: host writes (firewall changes, quarantine, process kills) gated behind Master's approval; self-modification proposals gated behind Master's diff review; the whole Tier-2 web-facing expansion (Reaper research pulls that flow scraped content into Grimoire) **dormant until the Front-2 injection mitigations are live and their adversarial test suite passes.** That last one is the load-bearing sequencing decision of the entire project: web autonomy is earned by the injection defense being real, not assumed. State it as a hard gate with a concrete earned-by condition. Sandboxing (bubblewrap) and static policy (Semgrep) were scoped as sprint phase 2 — plan them as the next gate tier, running while Tier 2 runs, not as a prerequisite that blocks everything.

Constraints that bind the whole mission:
- **Defense only.** The white-hat line is permanent. Re-read Front-1-through-5 through that lens; anything offensive is out.
- **Sentinel proposes, Cerberus checks.** If recon shows that handoff is aspirational rather than enforced, fixing it is part of the mission — an ungoverned Sentinel is more dangerous than a weak one.
- **The abliterated model has no refusal backstop.** Sentinel and Cerberus are the backstop. Plan like nothing downstream will save a miss.
- **Report and recommend; do not self-patch.** Sentinel surfaces its findings; Master approves changes. Full capability to *find* and *propose*; gated capability to *change*.

---

## Wargame-specific instructions

- **This is likely a multi-part wargame.** Front 2 (injection defense) is the sprint's core and may deserve its own `sentinel-part2-injection.md` with its own red-team pass, because its adversarial test suite is itself a mini-mission. Split if honest; justify in the ledger.
- **Recon must settle the Cerberus handoff before you plan Fronts 3–5**, because if Sentinel's responses don't actually route through Cerberus today, that's a RECON NEEDED that changes every downstream gate. Put the exact check in the plan.
- **The Gates & Autonomy Ledger is the deliverable Master cares about most here.** It is not a footnote to the security plan — it *is* the security plan's contract. Make each gate's earned-by condition concrete enough that the executor knows exactly when it's allowed to open and Master knows exactly what he's approving.
- **Red-team the injection defense hardest.** When you dispatch the attacker subagent, tell it Front 2 is where to concentrate: have it play an attacker who controls a web page Reaper will scrape, and see if the plan's mitigations actually stop a determined payload from reaching a prompt as an instruction. If the attacker gets a payload through on paper, that break and its patch are the most important lines in the whole plan.
- **Do not ask the executor to explain its reasoning in its output** — request artifacts, findings, configs, test assertions, and proposed diffs, never the thinking itself. (Reasoning-extraction phrasing can trip a safeguard and silently reroute a Fable session to Opus 4.8 mid-run.)
- Anything recon can't settle about the host (what's installed on Citadel, whether ufw/nftables is active, whether ClamAV exists) is a `RECON NEEDED` with the exact command for the executor to run first — not a guess.
