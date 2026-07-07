# Red Team — Sentinel Part 2, Pass 3

**Target:** `wargames/plans/sentinel-part2-injection.md` (twice-patched: pass-1 trust-0.7
laundering host, pass-2 GrimoireReader parallel-reader bypass). The author's pass-2 patch
moved enforcement to a shared `_sanitize_recalled(rows)` helper called by "every read path,"
keyed on `provenance="scraped"`, with provenance stamped at "every web-origin write."

**Role:** hostile web page Reaper scrapes. **Scope:** attack the ROUTE as-if-implemented,
not the unbuilt tree. READ-ONLY; nothing changed.

**Verdict: BREAKS FOUND.** The provenance key is NOT structurally complete, and the "single
shared sanitizer" is not a single real seam. Three concrete unfenced payloads reach a
prompt/egress on paper, plus a design flaw that makes the "one helper, every reader" claim
false as written. Ordered by severity.

---

## BREAK 1 (CRITICAL) — Apex re-store of scraped content has NO web provenance, so the fence never keys on it

This is the cleanest kill and it defeats the load-bearing control directly.

**The plan's completeness argument** (P2-0, plan lines 113-117): provenance is stamped
per-caller, and to stop a caller forgetting it, the counter is to *auto-derive structurally*:

> "derive `provenance="scraped"` structurally (any write whose `source_module=="reaper"` or
> `source=="research"/"reddit"/"youtube"` is auto-tagged in `remember()` itself)" — plan:116

**The path that misses it.** Apex is Shadow's Claude/GPT fallback. When Apex answers a task,
it stores the API response as a teaching signal:

- `modules/apex/apex.py:1072` — `self._grimoire.remember(content=f"Apex teaching signal…",
  source="system", source_module="apex", trust_level=0.5, …)`
- `modules/apex/teaching_extractor.py:203` — `grimoire.remember(content=content,
  source="system", source_module="apex", trust_level=0.5, …)`
- `modules/apex/apex.py:868` — Apex transaction record, `source="apex_transaction",
  source_module="apex", trust_level=1.0`, whose content embeds `Response: {response_summary}`.

**Why the content is attacker-influenced.** Reaper scrapes a page → stores it in Grimoire →
the orchestrator recalls it into the prompt → the task escalates to Apex → the Claude/GPT
response *quotes or paraphrases the scraped instruction* (the model is summarizing the very
research Reaper pulled) → Apex writes that response back into Grimoire. The scraped payload
is now laundered through Apex into a NEW memory whose `source_module=="apex"` and
`source=="system"`/`"apex_transaction"`. It matches **none** of the auto-derive keys
(`reaper` / `research` / `reddit` / `youtube`). **`provenance` is never set.** The
`_sanitize_recalled` fence keys on `provenance=="scraped"` — this row does not carry it, so on
the next recall the Apex-laundered payload is served **unfenced** to the prompt.

Worse: apex.py:868 stores at **trust_level=1.0** and teaching_extractor.py:203 at 0.5 — both
at or above the 0.3 float floor, so P2-1's numeric floor also misses it. This is the pass-1
laundering vector reincarnated *through a legitimate module*: attacker-influenced content, HIGH
trust, NOT `provenance="scraped"`. It trips **Abort condition 4** ("A scraped write enters
Grimoire without `provenance="scraped"`") — except the plan never contemplates Apex as a
"scraped write" at all, so RP5's writer enumeration
(`grep … "\.remember(" modules/`) will list apex.py:1072/868 and the author must decide they
are NOT web-origin — which is exactly the misclassification that opens the hole. This is a
direct hit on the third attack directive: *"Apex/LLM-generated content that quotes scraped
material."*

**Exact unfenced read path:** `apex.py:1072` (write, no provenance) → later
`orchestrator`/`context_orchestrator.py:376` staged recall or `grimoire.py:965 recall()` →
prompt. Fence absent because `provenance != "scraped"`.

---

## BREAK 2 (HIGH) — The plan enumerates FOUR Reaper write sites; there are FIVE. Site 1217 is omitted from every list.

Every place the plan counts Reaper writers it says **four** and lists the same four IDs:

- truth table, plan:25 — "consistent at all four store sites … web [reaper.py:988-999],
  research [reaper.py:1192-1203], reddit [reaper.py:1377-1389], youtube [reaper.py:1625-1634]"
- P2-0, plan:102 — "the four Reaper store sites ([reaper.py:988,1192,1377,1625])"
- P2-3, plan:177 — "all FOUR Reaper write sites ([reaper.py:988,1192,1377,1625])"

**The code has five scraped-content `remember()` calls in reaper.py:**

- `reaper.py:988` — fetch_page full store ✓ listed
- `reaper.py:1192` — research, `score >= STORE_FULL_THRESHOLD` ✓ listed
- **`reaper.py:1217` — research, `score >= STORE_SUMMARY_THRESHOLD` (summary store) ✗ NOT LISTED**
- `reaper.py:1377` — reddit ✓ listed
- `reaper.py:1625` — youtube ✓ listed

Verified: `grep -n "\.remember(" modules/reaper/reaper.py` → 988, 1192, **1217**, 1377, 1625.
Site 1217 stores a summarized scraped page (`source="research", source_module="reaper",
trust_level=page["source_evaluation"]["trust_score"]`) — a genuine web-origin write on the
mainline research path (it fires for every page scoring 4-6 on relevance).

**Why it matters to THIS plan.** If provenance is stamped *per-write-site* (the plan's literal
"stamp at the four Reaper store sites" instruction, plan:101-102), the executor patches four
call sites and **1217 is left untagged** — a scraped summary that is invisible to the
`provenance="scraped"` fence. This is Abort condition 4 again, on the mainline Reaper path, not
some exotic corner. The structural auto-derive counter (Break-1's `source_module=="reaper"`
rule) *would* catch 1217 — but the plan presents the auto-derive as an optional
"where feasible" fallback (plan:115-117), and P2-3's detector scan is explicitly wired to
"all FOUR" sites (plan:177), so the injection scan skips 1217 regardless of how provenance is
stamped. A summary-tier scraped page therefore bypasses the P2-3 write-time detector by
enumeration error.

---

## BREAK 3 (HIGH) — "A single shared `_sanitize_recalled(rows)`" is a fiction: the read paths build three incompatible row shapes, and the plan's reader list omits at least seven readers.

The plan's central pass-2 claim (plan:87-89, 119-124): one helper `_sanitize_recalled(rows)`
that BOTH `recall()` AND GrimoireReader's methods AND MCP call "before returning any row."
Attacking the seam as directed:

### 3a. There is no single shape for the helper to key on.

- `grimoire.recall()` (grimoire.py:1142-1161) returns hand-built dicts with 15 keys
  (`content`, `trust_level`, `source`, `relevance`, `faceted_tags`, `content_blocks`,
  `temporal_status`, …). A provenance field would live in `metadata`.
- `GrimoireReader.search()` (grimoire_reader.py:227-239) returns a DIFFERENT dict —
  `relevance_score` (not `relevance`), `timestamp` (not `created_at`), no `tags`, no
  `content_blocks`, no `temporal_status`. Provenance again would be inside `metadata`.
- `recall_by_tag` (grimoire.py:1190) and `recall_recent` (grimoire.py:1221) return
  **raw `dict(row)`** straight off SQLite — no `metadata` parsing at all; the row's
  `metadata_json` is still a JSON *string*, not a dict. `recall_operational` (grimoire.py:1258)
  and `search_corrections` (grimoire.py:1836) are the same raw-row shape.

A "shared `_sanitize_recalled(rows)`" that reads `row["provenance"]` or `row["metadata"]
["provenance"]` cannot work uniformly across a parsed-dict path, a differently-parsed-dict
path, and a raw-`dict(row)` path where `metadata_json` is an unparsed string. The plan treats
these as "one integration"; they are **at least three** distinct integrations. That is exactly
the attack-directive question — *"would they need two different sanitizer integrations the plan
treats as one?"* — answered **yes, three**, and the plan names none of the shape mismatch.

### 3b. The reader inventory the plan's sanitizer list still omits.

Enumerating EVERY method that returns stored memory content toward a caller:

**grimoire.py (Family A):**
| Method | Line | In plan's P2-1 sanitizer list? |
|---|---|---|
| `recall` | 965 | ✓ |
| `recall_by_tag` | 1167 | ✓ |
| `recall_recent` | 1192 | ✓ |
| `recall_operational` | 1223 | **✗ OMITTED** |
| `memory_block_search` | 1264 | **✗ OMITTED** |
| `find_conflicts` | 1555 | **✗ OMITTED** (returns `existing_content`) |
| `get_pointer_index` | 1627 | **✗ OMITTED** (returns top-accessed/high-trust content) |
| `pointer_index_as_text` | 1710 | **✗ OMITTED — injected into the SYSTEM PROMPT (see below)** |
| `search_corrections` | 1821 | **✗ OMITTED** (returns `corrected_content`) |
| `recall_graph` | 1961 | **✗ OMITTED** (returns full `dict(row)`) |
| `recall_enriched` | 2013 | **✗ OMITTED** (wraps recall + graph rows) |

**grimoire_reader.py (Family B):**
| Method | Line | In plan's list? |
|---|---|---|
| `search` | 160 | ✓ |
| `search_by_category` | 249 | ✓ |
| `search_related` | 301 | ✓ |
| `get_module_knowledge` | 387 | ✓ |
| `get_recent` | 482 | **✗ OMITTED** (reachable? see below) |

The plan (plan:122-124, abort-cond-3 plan:281) names `recall`/`recall_recent`/`recall_by_tag`
+ the four GrimoireReader methods + MCP. It misses **eight** content-returning readers. Two are
load-bearing:

### 3c. `pointer_index_as_text()` is the worst omission — it goes straight into the system prompt, un-fenced, by design.

`grimoire.py:1710 pointer_index_as_text()` formats high-trust + recent + correction content and
its docstring says (grimoire.py:1712-1714): *"This is what actually goes into Shadow's system
prompt."* It calls `get_pointer_index()` (1627), which pulls `content` from `high_trust`
(trust ≥ 0.8, grimoire.py:1684) and `recent` (grimoire.py:1692) rows and renders them raw at
1742/1764. **Nothing in this path calls `recall()` or any GrimoireReader method**, so no
version of `_sanitize_recalled` on the plan's list touches it. A `provenance="scraped"` page
that reaches trust ≥ 0.8 — e.g. via the **Break-1 Apex laundering (trust 1.0)** or the
**pass-1 supersede laundering the plan patches only inside `supersede`/`remember`** — lands in
`high_trust`, is rendered into the system prompt by `pointer_index_as_text`, and is
**never fenced**. This is a scraped/laundered payload reaching a prompt un-fenced via a reader
the plan does not list: **Abort condition 3**, uncaught.

Note the plan's own test-time greps only look for `_collection.query`/`SELECT * FROM memories`
call sites (plan:170, 407). `get_pointer_index` uses `SELECT id, content, … FROM memories`
(grimoire.py:1662, 1681, 1692) — it WOULD match `SELECT … FROM memories` if the grep were
`SELECT .* FROM memories`, but the plan's literal pattern is `SELECT \* FROM memories` (star),
and these queries select **named columns, not `*`**. So the plan's own future-reader-catch
test misses `get_pointer_index`, `search_by_category` (grimoire_reader.py:271 selects named
cols), `get_module_knowledge` (409, named cols), and `get_recent` (505, named cols). The
guard-grep is under-inclusive against the exact readers that don't use `SELECT *`.

---

## BREAK 4 (MEDIUM) — MCP `grimoire_remember` writes with no provenance and no source_module, and the MCP `recall`/`search` egress dicts have no provenance to key on.

`modules/grimoire/mcp_server.py:116` `grimoire_remember` calls `remember(content=…,
category=…, metadata=…)` — no `source`, no `source_module`, no `trust_level`. An external MCP
client (Claude Code during a coding session, per the module docstring) can paste **web-quoted
content** into Grimoire; it defaults to `source="conversation"`, `source_module="grimoire"`,
`trust_level=0.5` (grimoire.py:675-677). Attacker-influenced (user pasted a web quote), above
the 0.3 floor, and `provenance` unset → fence misses it. This is the attack directive's
*"a user-pasted web quote (trust from user = high, provenance not scraped)"* case, realized
through the MCP write surface the plan lists only as a *read* egress (plan:124, GP3 plan:321),
never as an unguarded *write*.

On the read side, `grimoire_recall`/`grimoire_search` (mcp_server.py:96,138) return
`json.dumps(results)` where `results` are `recall()` dicts. If `_sanitize_recalled` fences the
`content` string in place inside `recall()`, the MCP egress inherits it — *provided* the MCP
path actually routes through the sanitized `recall()`. It does (both call `_grimoire().recall`).
So MCP read egress is OK **iff** `recall()` itself is sanitized — but that is Family A only;
MCP never exposes GrimoireReader, so this one is not an independent read break. The write break
above stands.

---

## What I attacked hardest and could NOT break

- **The nonce fence escape-safety (P2-2 / B6).** As designed — per-request nonce unknown to the
  attacker, delimiter-stripping, entire payload rendered inside the boundary — I found no lever
  to break OUT of a correctly-applied nonce fence. My breaks are all about content that never
  *reaches* the fence (missing provenance, un-listed reader), not content that escapes it.
- **Corpus fixture isolation (GP8).** No lever, same as pass-1/pass-2.
- **The supersede/remember trust ceiling (P2-5 / B3) as a mechanism.** The ceiling logic is
  sound *for scraped-derived writes it can identify*; my Break-1 defeats it by making the write
  NOT scraped-derived (it is Apex-derived), so the ceiling never engages — that is a provenance
  completeness failure, not a ceiling-logic failure.
- **The homoglyph normalization (P2-5 / GP6).** No new break; pass-1's analysis holds.

---

## The precise findings (quote-and-line, for the executor)

1. **BREAK 1 (CRITICAL):** Apex re-stores scraped-derived content with `source_module="apex"`,
   `source="system"`/`"apex_transaction"`, `trust_level=0.5`–`1.0`
   (`modules/apex/apex.py:1072`, `apex.py:868`, `modules/apex/teaching_extractor.py:203`).
   Plan auto-derive keys on `source_module=="reaper"` or `source in {research,reddit,youtube}`
   (plan:116) → Apex misses → `provenance` unset → served un-fenced on next recall. Attacker
   content + HIGH trust + not-scraped = the exact fence gap the third directive names.

2. **BREAK 2 (HIGH):** Five Reaper write sites, plan lists four. Missing
   `reaper.py:1217` (summary-store, mainline research path) from plan:25, plan:102, plan:177.
   Untagged scraped summary + skipped by the P2-3 write-site detector.

3. **BREAK 3 (HIGH):** "One shared `_sanitize_recalled(rows)`" is three incompatible
   integrations (parsed `recall()` dict vs `GrimoireReader` dict vs raw `dict(row)` with
   unparsed `metadata_json`). Plan's sanitizer list (plan:122-124) omits eight content-returning
   readers, including **`pointer_index_as_text()` (grimoire.py:1710) which is injected directly
   into the system prompt** (grimoire.py:1712-1714) and reaches no `recall()`/GrimoireReader
   method — a laundered/high-trust scraped payload lands in `high_trust` (grimoire.py:1684) and
   renders un-fenced. Abort condition 3, uncaught. The plan's future-reader-catch grep
   (`SELECT \* FROM memories`, plan:170) misses every named-column reader
   (`get_pointer_index`, `search_by_category`, `get_module_knowledge`, `get_recent`).

4. **BREAK 4 (MEDIUM):** `mcp_server.py:116 grimoire_remember` is an un-guarded WRITE surface
   (no source/source_module/trust) — a user-pasted web quote enters at trust 0.5, provenance
   unset. The plan lists MCP only as a read egress, never as a write to guard.

**Bottom line for the author:** provenance-keying is the right idea, but "provenance
completeness at write" (RP5) is asserted, not achieved by the route as written — it enumerates
Reaper writers only (and even miscounts those), while the real web-origin surface includes
**Apex re-store** and the **MCP write endpoint**, neither of which the auto-derive rule covers.
And "one shared sanitizer at every read path" cannot be literally one function given three row
shapes and eight un-listed readers — most damningly the system-prompt pointer index. Fix order:
(a) make provenance structural in `remember()` itself and treat *any* write whose content is
derived from a recall as provenance-inheriting (so Apex laundering inherits `scraped`);
(b) enumerate ALL 16 content-returning readers, not 7; (c) fence `pointer_index_as_text`
explicitly or exclude scraped/laundered rows from the pointer index entirely.
