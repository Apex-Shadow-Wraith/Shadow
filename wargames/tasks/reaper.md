# MISSION — Reaper: undetectable, threat-aware, professional information gathering

WARGAME ORDER. You are not executing this mission, you are wargaming it. A separate executor (Opus 4.8, max effort) runs the brief below later, on its own turn. Your job is the route it will follow. Follow the `wargame` skill: load SUCCESS.md, recon read-only, fight it on paper to `wargames/plans/reaper.md`, build the Gates & Autonomy Ledger, dispatch a fresh red-team subagent to `wargames/red-team/reaper.md`, patch, and log every pass in `wargames/LEDGER.md`. If run in RECON mode, write `wargames/recon/reaper.md` and stop. Split if honest; justify in the ledger.

**Framing that binds the whole mission:** Reaper *gathers*, it never *attacks*. Stealth here means "reads the public web without being fingerprinted, throttled, or served poison" — not intrusion, not evasion of authentication, not accessing anything Master isn't entitled to read. It is the research analyst who doesn't get rate-limited, not an intruder. Every capability below lives inside that line, the same way Sentinel's power lives inside defense-only. And Reaper is the origin of the project's highest-severity risk: its scraped content flows into Grimoire's permanent memory and can carry prompt-injection payloads. So this mission has two obligations that pull against each other — be excellent at reading the web, and be the disciplined source that never lets what it reads become an instruction Shadow follows. Plan both.

---

## Recon before you plan (read-only, quote file:line)

Read the real Reaper and its stealth layer. Plan against the code.

- `modules/reaper/` — the module and its real tool set (docs say 5 tools: research, web scraping, Reddit .json, YouTube transcription — verify). The source-evaluation hierarchy, the summarization path, the write into Grimoire.
- The stealth layer as it actually exists post-S48 (Master Plan §12): SearXNG as first cascade rung (Docker, boot-race fixed, three config flags), user-agent rotation (8 signatures), request-timing randomization, referrer-chain spoofing, clean sessions, DNT header. Confirm each in code, not just in the doc.
- The search cascade / priority chain: Reddit .json (permanent primary for Reddit) → SearXNG → DuckDuckGo → Bing → PRAW fallback. Trace the fallback logic — and note the SearXNG lesson: it was dead-on-arrival for months, silently served by DuckDuckGo, because a boot-time health probe made the failure invisible. Any silent-fallback path in the cascade is a repeat of that failure class.
- What's built vs. pending (Master Plan §12 "Pending on Citadel"): Canvas/WebGL fingerprint spoofing, residential proxies, DNS-over-HTTPS + TLS-fingerprint randomization, full browser-context isolation — these are named as *not yet built*. The stealth front is largely a build, not a polish; recon confirms exactly how much exists.
- The dependencies: `playwright` (stealth browser automation), `beautifulsoup4`, `requests`, `ddgs`, `yt-dlp`, `praw` (`requirements.txt`). Confirm Playwright stealth is actually wired, not just installed.
- The CAPTCHA strategy (Master Plan §12): avoid, don't solve — APIs/authenticated access → SearXNG → Playwright full stealth + residential proxies → alternative sources → last resort solving service. "Never waste local compute solving CAPTCHAs." Confirm the cascade honors this.
- The injection seam: exactly what `trust_level`/`source` Reaper assigns when it writes scraped content to Grimoire (`remember()` call sites in Reaper), and whether that content is tagged untrusted. This is the shared boundary with the Grimoire and Sentinel missions.
- The security posture from Master Plan §12, verbatim in spirit: Reaper's scraping into Grimoire is a **live prompt-injection vector**; combined with the abliterated model and no sandboxing, it is the project's highest-severity open risk and the target of the security sprint. **"The path exists" is not "the path is safe."**
- Tests: `tests/test_reaper*`. Verify coverage by collection.

Settle in recon, with file:line:
- How much of the stealth layer is actually built vs. pending? (Determines whether Front 1 is a build or a hardening pass.)
- Does any cascade rung fail silently to a fallback? (The SearXNG failure class.)
- What trust level does scraped content get on the way into Grimoire, and is it tagged untrusted?
- Is there residential-proxy / DoH / TLS-fingerprint infrastructure on Citadel yet, or is that a RECON NEEDED for the host?

---

## THE MISSION BRIEF (the executor's orders, not yours)

Make Reaper a professional-grade, undetectable, threat-aware information-gatherer — the research analyst who reads the whole public web without being fingerprinted, throttled, or fed poison, and who never crosses from gathering into attacking or into accessing what Master isn't entitled to. Five fronts. For each: what exists today (from recon), what it must become, the exact build, live verification, and every gate.

**Front 1 — Truly undetectable (stealth as it reads the public web).** Reaper should leave no distinguishing fingerprint when it reads public pages. Plan the full stealth stack, closing the gap recon finds between built and pending: user-agent rotation (exists) → request-timing randomization and referrer spoofing (exist) → the pending layers that make it real: Canvas/WebGL fingerprint spoofing, TLS-fingerprint randomization, DNS-over-HTTPS, full browser-context isolation, and residential proxies. Plan Playwright full-stealth as the heavy-page path. The bar: a page Reaper reads cannot cheaply distinguish it from an ordinary browser. Verification is concrete — a fingerprinting test page (e.g. a self-hosted or public fingerprint reflector) returns a plausible, rotating, non-headless signature; requests don't cluster in a detectable timing pattern. Keep this strictly reading-side: stealth is for not-being-throttled while reading public content, never for defeating authentication or access controls.

**Front 2 — Threat-aware (recognize warning signs and back off).** A professional notices when a source is hostile and stops. Plan detection-and-response for: rate-limit signals (429s, slowdowns, soft-blocks) → exponential backoff and rung-switch; CAPTCHA walls → the avoid-don't-solve cascade, never burning local compute solving them; bot-detection / honeypot pages (hidden links, trap forms, content that only appears to bots) → recognize and disengage; and — the subtle one — **content that looks like it's trying to instruct the reader** (a page whose text is a prompt-injection payload aimed at an AI scraper). Reaper recognizing "this page is trying to talk to me, not inform me" is a first line of the injection defense, before Grimoire's trust demotion is the second. Plan how Reaper flags such content on the way in.

**Front 3 — Professional information gathering (be excellent at the actual job).** The stealth is in service of the work: getting good information reliably. Plan the source-evaluation hierarchy (favor original sources — company blogs, filings, primary docs — over aggregators; skip low-quality unless specifically relevant), the extraction quality (clean content out of messy pages), the cascade that always returns *something* useful and never silently degrades (no repeat of the SearXNG silent-failure — every rung switch is logged and observable), and the specialized paths (Reddit .json as permanent primary, YouTube transcription via yt-dlp/Whisper). The investment-research use case rides on this front: portfolio monitoring, financial data via free APIs, earnings and news sentiment — research-analyst role, explicitly not day-trading, folded into the morning briefing later. Verification: a real research query returns cited, deduplicated, correctly-attributed results with conflicts flagged rather than averaged.

**Front 4 — The injection-source discipline (Reaper's obligation to the rest of Shadow).** Reaper is where poison enters. Its discipline: everything it writes to Grimoire is tagged untrusted-source at the write, never labeled higher-trust than it earned, and flagged if Front 2 spotted instruction-like content. This is the seam with the Grimoire and Sentinel missions — Reaper tags at the source, Grimoire demotes at retrieval, Sentinel's adversarial suite proves the payload never executes. Plan Reaper's half: the exact write-time tagging, and the "this page tried to instruct me" flag riding along with flagged content. A plan where Reaper writes scraped content at anything above untrusted has failed this front.

**Front 5 — The gates (Tier-2 is earned, not assumed).** This is the load-bearing sequencing decision. Reaper's web-facing autonomy — the weekly research pulls that flow scraped content into Grimoire (Tier 2 dogfooding) — is **dormant until the injection mitigations are live and their adversarial test suite passes.** State it as a hard gate with a concrete earned-by condition: Grimoire's trust demotion enforced (Grimoire Front 2), Sentinel's adversarial suite green (Sentinel Front 2), Reaper's source-tagging verified (Front 4). Until then, Reaper runs supervised on demand, not autonomously on a schedule. Other gates in the ledger: CAPTCHA-solving-service is last-resort and gated (never a default, never autonomous — it costs money and signals); residential proxies and any paid infrastructure are Master-approved; and the permanent line — Reaper never authenticates as Master into an account, never accesses non-public content, never crosses from reading into acting. External-facing actions (posting, submitting, purchasing) require explicit Master approval, per standing policy.

Constraints that bind the whole mission:
- **Gather, never attack. Read public content, never defeat access controls.** The stealth line is permanent.
- **Every rung switch is observable** — no silent fallback (the SearXNG failure class).
- **Everything written to Grimoire is untrusted-tagged at the source.** Reaper is the origin of the injection risk and owns the first mitigation.
- **Tier-2 autonomy is earned by the injection defense being real**, not assumed. Web autonomy waits on the mitigations.
- **The abliterated model has no refusal backstop** — Reaper's threat-flagging and Grimoire's trust demotion are the backstop for scraped content.

---

## Wargame-specific instructions

- **This mission WILL likely route to Opus** during the wargame phase — the stealth/evasion content sits in the Fable safeguard zone, same as Sentinel and Omen. That's expected and fine; Opus is the executor these plans target. If run in two phases, the RECON digest is still worth writing on whatever model does recon so the wargame starts from settled facts.
- **Front 5's Tier-2 gate is the deliverable Master cares about most** — the earned-by condition must be concrete enough that the executor knows exactly what must be true before Reaper is allowed to run autonomous web pulls, and Master knows exactly what he's approving when he opens it.
- **Fronts 2 and 4 are the injection seam.** Settle them against the Grimoire and Sentinel missions with file:line so the three plans compose into one coherent injection defense rather than three partial ones.
- **Red-team the stealth-vs-line boundary and the injection seam.** Tell the attacker subagent to (a) find any move where "stealth" quietly becomes "defeating an access control" — that's a mission failure, not a feature — and (b) play a hostile page that Reaper scrapes and see whether its content reaches Grimoire tagged as anything other than untrusted. Either break is among the plan's most important lines.
- **Do not ask the executor to explain its reasoning in its output** — request artifacts, configs, findings, and test assertions, never the thinking itself. (Reasoning-extraction phrasing can trip a safeguard and silently reroute a Fable session to Opus 4.8 mid-run.)
- Host-infrastructure unknowns (residential proxies, DoH, TLS randomization on Citadel) are `RECON NEEDED` with the exact check — never a guess.
