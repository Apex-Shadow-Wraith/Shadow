# SUCCESS.md · the definition of properly wargamed

A wargame passes only when ALL NINE hold. Points 1–8 are the standard.
Point 9 is the Project Shadow addendum, and it is not optional.

1. **Expected observation on every move.** Exactly what you should see if the move worked — the actual string, exit code, file state, test name, row count, or log line. Not "it should work."

2. **Failure branch on every move.** Its most likely failure, the cause that failure signals, and the counter-move that fixes it.

3. **A trigger on every fork.** If you observe X, take route B. No judgment calls left to the executor — the trigger decides the branch.

4. **RECON NEEDED where recon couldn't settle it.** Every unsettled assumption is marked, with the exact check that settles it (the command, the file, or the question to Master). No assumption is smuggled into a confident move.

5. **Abort conditions exist.** The moments to stop and flag rather than improvise — data-loss risk, an unsatisfiable gate, a plan-vs-reality divergence too large to continue through.

6. **Verification is spelled out.** Which runs the executor performs, when, and what pass looks like for each. Built is not done; live-verified is done.

7. **It has survived a red-team pass.** The plan records the attack that failed against it, and the patch born from the attack that landed. A fresh attacker — not the author — ran an honest attempt to break the route.

8. **It is executable blind.** A competent operator could run the mission end to end without asking a single question. Every hidden judgment call has been forced out into a trigger.

---

## 9. The Shadow addendum — the Gates & Autonomy Ledger

**No plan passes with an ungated write to Shadow's own code, memory, config, identity, or training data; an ungated autonomous action; or an ungated touch of the network, an external account, the host OS, or another machine.**

The plan must contain a **Gates & Autonomy Ledger** listing every such move. For each: what could go wrong if it ran ungated, the gate that guards it, and the earned-by condition that must be true before that gate is allowed to open.

Two things must both be true, or point 9 fails:

- **The capability is planned in full.** Nothing dangerous is amputated in the name of caution. A self-repairing Omen, a stealth Reaper, an autonomously-defending Sentinel are each planned to their full intended power. A neutered capability is not a safe plan — it is an incomplete one.
- **Every dangerous move arrives wearing its gate.** The gate is real: the plan wires the check that enforces it, not merely names it. A ledger that lists a gate the plan never enforces is the "looks governed but isn't" failure, and it fails point 9 exactly as an ungated write would.

Security before autonomy is a column in the plan, not a phase that comes afterward.

---

### How the loop uses this file

Grade every draft point by point against all nine. Log the grades in `LEDGER.md`, honestly — a softened grade to finish faster hides the plan that dies at first contact, which is the one failure this whole method exists to prevent. A wargame is DONE when it passes all nine **and** one honest red-team attempt to break it fails. Be stricter here and everything downstream gets better.
