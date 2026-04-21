# Dual Tool-Registration Pattern Investigation

**Status:** Read-only investigation, no code changed.
**Author:** Claude Code (Opus 4.7), session 2026-04-20.
**Scope:** Answer how Shadow's module registry handles the "two tool-registration patterns" flagged in `CLAUDE.md`.

---

## TL;DR — The premise is wrong

There is **no dual tool-registration pattern** inside Shadow's module registry.

Every one of the 13 modules — including Grimoire and Reaper — registers its internal tools exclusively through `get_tools()`. The `mcp_manifest.json` files in [modules/grimoire/](modules/grimoire/) and [modules/reaper/](modules/reaper/) describe a **separate, orthogonal surface**: standalone FastAPI HTTP servers exposed to external MCP clients (Claude Code itself, other tools). The internal `ModuleRegistry` never reads those manifest files. They declare different tools with different names, and live behind a different lifecycle.

Accordingly, the `CLAUDE.md` "Dual Pattern Advisory" and the tool-count split (`145 via get_tools() + 8 via mcp_manifest.json`) are factually incorrect and should be corrected. See §7.

The remainder of this doc walks the code to prove it.

---

## 1. Module Registry Architecture

The live registry is **`ModuleRegistry`** in [modules/base.py:349-518](modules/base.py#L349).

(Note: `ModuleStateManager` in [modules/shadow/module_state.py:90](modules/shadow/module_state.py#L90) also has a `register_module()` method at [:108](modules/shadow/module_state.py#L108), but it is a **state tracker** — it stores status/capabilities for monitoring and does not build a tool index. It is populated by modules at runtime, not at boot, and is not consulted by the tool loader.)

Interface (from `base.py`):

| Method | Line | Purpose |
| --- | --- | --- |
| `register(module)` | [:372](modules/base.py#L372) | Validate tools, add module, extend `_tool_index` (tool_name → module_name) |
| `unregister(name)` | [:406](modules/base.py#L406) | Remove module and its tool_index entries |
| `get_module(name)` | [:418](modules/base.py#L418) | Phonebook lookup |
| `get_module_for_tool(tool)` | [:424](modules/base.py#L424) | Reverse lookup: tool → owning module |
| `list_tools()` | [:431](modules/base.py#L431) | Return every tool from every **ONLINE** module; used by LLM context build |
| `list_modules()` | [:454](modules/base.py#L454) | Status snapshot for monitoring |
| `find_tools(...)` | [:469](modules/base.py#L469) | Filtered query |
| `tool_stats()` | [:495](modules/base.py#L495) | Counts |

Registration flow (atomic — [:372-404](modules/base.py#L372-L404)):

1. `module.get_tools()` is called (line 382).
2. Every tool name is pre-validated against `_tool_index` for collisions. If any collision, `ValueError` and the registry is unchanged.
3. Only then is `_modules[name] = module` assigned and the tool index extended.
4. If Cerberus is wired, each tool is auto-classified via `Cerberus.auto_register_tool(...)` ([:399](modules/base.py#L399)).

`list_tools()` ([:431-452](modules/base.py#L431)) iterates `_modules.values()`, skips non-`ONLINE` modules, calls `module.get_tools()`, and stamps each tool with `module` and `status` keys. It is isolated per module: a raised exception in one module's `get_tools()` is caught and logged, and the loop continues ([:442-447](modules/base.py#L442-L447)).

---

## 2. `get_tools()` Pattern — How It Flows

End-to-end trace:

1. **Module construction.** `main.py` constructs module instances and calls `module.initialize()` ([main.py:207-212](main.py#L207-L212)).
2. **Registration.** After all modules are initialized, `main.py` registers them one-by-one:
   - `orchestrator.registry.register(module)` at [main.py:218](main.py#L218) in the main module loop, and
   - `orchestrator.registry.register(shadow_mod)` at [main.py:234](main.py#L234) for `ShadowModule`.
3. **Registry validation.** `ModuleRegistry.register` at [modules/base.py:382](modules/base.py#L382) calls `module.get_tools()` and populates `_tool_index`.
4. **DynamicToolLoader wiring.** `Orchestrator.__init__` constructs `DynamicToolLoader(module_registry=self.registry)` at [modules/shadow/orchestrator.py:356-357](modules/shadow/orchestrator.py#L356-L357). The loader calls `self._build_index()` in its constructor ([modules/shadow/tool_loader.py:44-45](modules/shadow/tool_loader.py#L44-L45)) — but at this point modules are not yet `ONLINE`, so the first build yields nothing.
5. **Post-online refresh.** `Orchestrator.start()` at [modules/shadow/orchestrator.py:627-628](modules/shadow/orchestrator.py#L627-L628) calls `self._tool_loader.refresh()` **after** all `module.initialize()` calls, when modules are actually `ONLINE`. This is the real index build.
6. **Index build.** `DynamicToolLoader._build_index()` at [modules/shadow/tool_loader.py:51-98](modules/shadow/tool_loader.py#L51-L98) calls `self._registry.list_tools()` ([:58](modules/shadow/tool_loader.py#L58)), which walks each module and calls `module.get_tools()` at [modules/base.py:441](modules/base.py#L441). Each returned tool dict has `"module"` stamped on it ([:449](modules/base.py#L449)), then the loader buckets them by module_name ([tool_loader.py:73-75](modules/shadow/tool_loader.py#L73-L75)).
7. **Per-request dispatch.** The decision loop calls `self._tool_loader.get_tools_for_task(module_name=target)` at [modules/shadow/orchestrator.py:3501](modules/shadow/orchestrator.py#L3501) and [:3715](modules/shadow/orchestrator.py#L3715) to get only the routed module's tools plus the core set, trimming prompt size by 2–4k tokens per call.

**Canonical line where tools actually leave a module and enter the router:** [modules/base.py:441](modules/base.py#L441) (`module_tools = module.get_tools()` inside `list_tools()`).

Secondary call sites where the registry invokes `get_tools()` directly:
- Registration validation: [modules/base.py:382](modules/base.py#L382)
- Unregister cleanup: [modules/base.py:413](modules/base.py#L413)
- Filtered query: [modules/base.py:484](modules/base.py#L484)
- Stats: [modules/base.py:501](modules/base.py#L501)

All 13 modules implement `get_tools()` on their class (or a parent class). `BaseModule.get_tools` is `@abstractmethod` at [modules/base.py:117-124](modules/base.py#L117-L124), so a module that omitted it could not be instantiated.

AST-verified tool counts per module (April 2026):

| Module | Tools via `get_tools()` | First three tool names |
| --- | ---: | --- |
| shadow | 4 | task_create, task_status, task_list |
| wraith | 12 | quick_answer, reminder_create, reminder_list |
| cerberus | 15 | safety_check, hook_pre_tool, hook_post_tool |
| apex | 10 | apex_query, apex_teach, apex_log |
| **grimoire** | **9** | memory_store, memory_search, memory_recall |
| sentinel | 24 | network_scan, file_integrity_check, breach_check |
| harbinger | 12 | briefing_compile, notification_send, notification_severity_assign |
| **reaper** | **5** | web_search, web_fetch, youtube_transcribe |
| cipher | 7 | calculate, unit_convert, date_math |
| omen | 40 | code_execute, code_lint, code_test |
| nova | 6 | format_document, format_report, format_email |
| void | 6 | system_snapshot, health_check, metric_history |
| morpheus | 11 | experiment_propose, experiment_start, experiment_complete |
| **TOTAL** | **161** | — |

(CLAUDE.md's "~153 tools, 145 + 8 manifest" is stale; the correct current figure is **161, all via `get_tools()`**. See §7.)

---

## 3. `mcp_manifest.json` Pattern — How It Flows

**The registry does not read the manifest files at all.**

Exhaustive grep for `mcp_manifest` and `manifest.json` across the repo returns only:

- [modules/grimoire/mcp_manifest.json](modules/grimoire/mcp_manifest.json) — the file itself
- [modules/reaper/mcp_manifest.json](modules/reaper/mcp_manifest.json) — the file itself
- [tests/test_grimoire_mcp.py:354-369](tests/test_grimoire_mcp.py#L354-L369) — test that validates the manifest schema
- [modules/grimoire/conversation_ingestor.py:67, :75](modules/grimoire/conversation_ingestor.py#L67) — unrelated; this reads `data/ingestor_manifest.json`, a separate tracking file

No source file under `modules/shadow/`, no `tool_loader.py`, no `orchestrator.py`, no `base.py` opens, parses, imports, or otherwise references `mcp_manifest.json`.

The manifests are actually consumed by standalone HTTP servers:

- [modules/grimoire/mcp_server.py](modules/grimoire/mcp_server.py) — FastAPI app, run via `python -m modules.grimoire.mcp_server` ([:8](modules/grimoire/mcp_server.py#L8)). Declares endpoints `/tools/grimoire_recall`, `/tools/grimoire_remember`, etc. that match the manifest verbatim.
- [modules/reaper/mcp_server.py](modules/reaper/mcp_server.py) — FastAPI app, run standalone on `127.0.0.1:8101` per [modules/reaper/mcp_manifest.json:6-11](modules/reaper/mcp_manifest.json#L6-L11).

These servers exist so **external** MCP clients (Claude Code extensions, other agents) can call a curated subset of Grimoire/Reaper over HTTP. They are not invoked by Shadow's orchestrator or decision loop.

**Critical: the manifest tools are not the same tools as the registered tools.** Tool-name comparison:

| Manifest (external MCP HTTP) | `get_tools()` (internal router) |
| --- | --- |
| grimoire_recall, grimoire_remember, grimoire_search, grimoire_collections, grimoire_stats | memory_store, memory_search, memory_recall, memory_forget, memory_compact, memory_block_search, store_failure_pattern, get_common_failures, get_failure_trend |
| reaper_search, reaper_fetch, reaper_summarize | web_search, web_fetch, youtube_transcribe, reddit_search_json, reddit_monitor |

Every internal tool dispatched through Shadow's router has its *internal* name (`memory_search`, `web_search`, …). A request that says "call `grimoire_recall`" to the router would not resolve — `grimoire_recall` is not in `ModuleRegistry._tool_index`. You'd have to issue an HTTP POST to the standalone Grimoire MCP server.

### Answering the three possibilities posed

- **(a) Grimoire/Reaper also have `get_tools()` on the module class.** **YES — this is the actual reality.** [modules/grimoire/grimoire_module.py:387-470](modules/grimoire/grimoire_module.py#L387) registers 9 tools; [modules/reaper/reaper_module.py:198-246](modules/reaper/reaper_module.py#L198) registers 5 tools. They went through the registry the same way every other module does.
- **(b) Registry reads manifest as a fallback.** **No.** No code path does this.
- **(c) Tools unreachable via router.** **No for the `get_tools()` tools; yes for the manifest tools.** The manifest tools are reachable only via the standalone HTTP MCP servers, not via the orchestrator's decision loop.

---

## 4. Reconciliation

The two surfaces are cleanly separated **by virtue of not overlapping at all**. There is no reconciliation code because there is no conflict to reconcile.

Test coverage:

- `get_tools()` pattern: covered by [tests/test_orchestrator.py](tests/test_orchestrator.py) (many sites like [:765](tests/test_orchestrator.py#L765), [:829](tests/test_orchestrator.py#L829)), [tests/test_decision_loop.py](tests/test_decision_loop.py) (many sites like [:335](tests/test_decision_loop.py#L335), [:402](tests/test_decision_loop.py#L402), [:410](tests/test_decision_loop.py#L410), [:452](tests/test_decision_loop.py#L452)), [tests/test_cerberus_auto_registration.py](tests/test_cerberus_auto_registration.py), and [tests/test_shadow_module.py](tests/test_shadow_module.py).
- External MCP servers: covered by [tests/test_grimoire_mcp.py](tests/test_grimoire_mcp.py) (including a manifest-shape assertion at [:351-373](tests/test_grimoire_mcp.py#L351-L373)) and [tests/test_reaper_mcp.py](tests/test_reaper_mcp.py).

No test bridges the two — they don't need to.

**Low-severity risks worth noting** (none is a live bug):

1. **Drift between internal and external surfaces.** The Grimoire MCP server exposes `grimoire_recall` which maps to `Grimoire.recall(...)` ([modules/grimoire/mcp_server.py:96-100](modules/grimoire/mcp_server.py#L96-L100)). The internal `memory_recall` tool routes through the same underlying object. If someone refactors internal method names, only the internal `get_tools()` test catches it; the external MCP server will raise 500 at runtime.
2. **Misleading count in `Orchestrator.list_tools()` vs. what external clients see.** An external MCP client connecting to port 8101 sees three Reaper tools; an internal trace says five. If a tool-count sanity check is ever added across the two surfaces, it must distinguish them.
3. **CLAUDE.md documentation drift.** The "dual-pattern advisory" block misleads any future session into thinking normalization work is required. This is the highest-impact risk because it already has downstream scope implications (see §5/6).

No file:line warrants a code change here.

---

## 5. Normalization Options

Reframed, given the finding above:

### Option A — Migrate Grimoire/Reaper manifests to `get_tools()`; delete manifest files

**Misunderstands the problem.** Deleting the manifests would break [tests/test_grimoire_mcp.py](tests/test_grimoire_mcp.py) and [tests/test_reaper_mcp.py](tests/test_reaper_mcp.py) and, more seriously, disable the external MCP HTTP server surface — which is a feature, not a wart. These servers exist so Claude Code and other MCP clients can reach Grimoire/Reaper directly during coding sessions. Not recommended.

- **Effort:** 1–2 hours to delete + fix tests.
- **Risk:** High. Loses external-client integration capability.
- **Phase fit:** Don't.

### Option B — Migrate all 11 other modules to `mcp_manifest.json`

Category error — the manifest is an HTTP-server description, not a registry format. The internal registry needs runtime Python objects (methods, state managers) that a static JSON manifest cannot carry. Adopting this pattern system-wide would require standing up 11 new FastAPI servers. That's a rebuild of the orchestrator, not a normalization.

- **Effort:** Weeks.
- **Risk:** Reshapes the entire runtime architecture.
- **Phase fit:** Don't.

### Option C — Keep both surfaces, document them clearly

The two surfaces already serve different purposes and neither is broken. The work is documentation, not code.

- **Effort:** 30 minutes.
- **Risk:** Near zero.
- **Phase fit:** Between Phase A and Phase B (or inline with Phase A if the author is touching CLAUDE.md anyway).

### Option D — (added) Improve the sync contract between internal and external surfaces

If the external MCP servers are becoming more important (which the manifest declaring port 8101 suggests), consider:

- Adding a contract test that exercises each manifest endpoint against the real Grimoire/Reaper instance, not just a schema check.
- Documenting which *internal* tool each *external* endpoint delegates to, so refactors can update both.

This is a real, small improvement — not a normalization.

- **Effort:** Half a day.
- **Risk:** Low.
- **Phase fit:** Interstitial work between Phase A and Phase B, alongside Option C.

---

## 6. Recommendation

**Do Option C (documentation correction) in the Phase A → Phase B interstitial, as part of a ~30-minute CLAUDE.md edit.** The investigation the dual-pattern advisory asked for has already been paid; the resolution is to update CLAUDE.md to describe the two surfaces correctly — internal `get_tools()`-based registry (161 tools across 13 modules) versus optional external MCP HTTP servers (Grimoire + Reaper, fully orthogonal) — delete the "dual-pattern investigation scheduled before Phase B" item, and update the registered-tool count (153 → 161) and the per-module counts for Grimoire (5 → 9) and Reaper (3 → 5). If Option D is also taken, add it as a small standalone task; do **not** bundle it with Phase B's LangGraph cutover, which is already load-bearing enough.

No Phase A scope change is warranted. The Sentinel → Cerberus merge does not touch either surface's plumbing and is unaffected by this finding.

---

## 7. Other Findings

### 7.1 CLAUDE.md has incorrect tool counts and a miscategorized advisory

- **"~153 tools, 145 via `get_tools()` + 8 via `mcp_manifest.json`"** — wrong. The correct picture is 161 tools, all via `get_tools()`. The 8 manifest tools are a separate external-MCP surface, not registry entries.
- **"Grimoire: 5 tools"** — the module registers 9, not 5. The number 5 is the manifest's external-surface count.
- **"Reaper: 3 tools"** — the module registers 5, not 3. The number 3 is the manifest's external-surface count.
- **"Sentinel: 24 tools (+24 from Sentinel in Phase A)"** — the "+24 from Sentinel in Phase A" is implying Cerberus gains 24 from Sentinel. AST-verified Sentinel count is indeed 24 (the CLAUDE.md body says 22+ elsewhere; the actual number is exactly 24). Bring the Phase-A zero-tool-loss invariant to bear against this exact number when writing the pre-/post-merge diff.
- **"Cerberus (15 tools)"** — AST-verified at 15 (matches).
- **"Omen (42 tools)"** — AST-verified at 40 (not 42). Minor, but `omen/omen.py:385` returns a different tool list than the CLAUDE.md claim. Worth verifying with a manual eye before the Phase A Cipher → Omen merge so the post-merge invariant diff is clean.

### 7.2 Shadow itself is a 14th registered module, not 13

[main.py:228-235](main.py#L228-L235) constructs and registers a `ShadowModule` (separate from the `Orchestrator`) with 4 tools (task_create, task_status, task_list, module_health). CLAUDE.md's module list numbers 13; this 14th module is real and its tools are routable. This does not affect any Phase A merge.

### 7.3 Registry enforces global tool-name uniqueness

[modules/base.py:385-389](modules/base.py#L385-L389) raises `ValueError` if any two modules claim the same tool name. This is a hidden constraint for every Phase A merge:

- **Cipher → Omen:** any name collision between Cipher's 7 tools and Omen's 40 tools will hard-fail at boot. Run a quick name-intersection check pre-merge. (`calculate`, `unit_convert`, `date_math`, `financial`, `statistics`, `percentage`, `rounding` vs Omen's `code_*`, `git_*`, etc. — looks clean on a skim, but verify.)
- **Sentinel → Cerberus:** same concern. 24 + 15 = 39 names must all be globally unique post-merge.

### 7.4 The `DynamicToolLoader` has a first-build race that's already handled

On `Orchestrator.__init__`, the tool loader's initial `_build_index()` runs against modules that are registered but not yet `ONLINE`, so the first index is empty. This is intentional: [modules/shadow/orchestrator.py:627-628](modules/shadow/orchestrator.py#L627-L628) explicitly calls `.refresh()` in `start()` after `initialize()`, and the loader additionally auto-refreshes if a request arrives while the index is empty ([modules/shadow/tool_loader.py:133-145](modules/shadow/tool_loader.py#L133-L145)). Not a bug. Worth knowing if you ever see an "index empty" warning right after boot — give the registry one more tick before diagnosing.

### 7.5 `list_tools()` mutates tool dicts in place

[modules/base.py:449-451](modules/base.py#L449-L451) sets `tool["module"]` and `tool["status"]` on the dict returned by `module.get_tools()`. If a module returns a cached list literal (most do, by returning a fresh list of fresh dicts each call), this is harmless. If any module ever returns a cached, shared dict, repeated `list_tools()` calls will trample status values under race conditions. Not a present bug, but fragile — any future refactor that caches tool schemas should return deep copies. Low priority; no action needed now.

