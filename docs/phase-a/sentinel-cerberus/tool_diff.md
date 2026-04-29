# Sentinel → Cerberus Tool Inventory Diff

**Phase A merge.** Branch: `phase-a/sentinel-into-cerberus`.
**Invariant:** zero capability loss — every Sentinel tool must have a
preserved equivalent in post-merge Cerberus, with feature parity.

Companion artifacts in this directory:
- `tool_inventory_pre.json` — pre-merge: all 24 Sentinel tools + 15
  original Cerberus tools (39 entries).
- `tool_inventory_post.json` — post-merge: Cerberus.get_tools() (39
  entries: 15 original + 24 absorbed).
- Generator: [`scripts/phase_a_sentinel_cerberus_inventory.py`](../../../scripts/phase_a_sentinel_cerberus_inventory.py).

## Summary

| Metric | Value |
| --- | ---: |
| Pre-merge Sentinel tools | 24 |
| Pre-merge Cerberus tools | 15 |
| Post-merge Cerberus tools | **39** (15 + 24) |
| Sentinel tools missing in Cerberus post-merge | **0** |
| Tool names changed | **0** |
| Tools deduplicated | **0** |
| Schema-byte mismatches (description / parameters / permission_level) | **0** |

**Result:** zero-tool-loss invariant satisfied without any rename or
dedup. Every Sentinel tool name appears in Cerberus.get_tools() with
byte-identical schema.

## Per-tool fate (all 24 Sentinel tools)

Every entry below has fate **"preserved as-is"** — same tool name,
same description, same parameters, same permission_level. Dispatch
moves from `Sentinel.execute()` (async) to `Cerberus.execute()` →
`SecuritySurface.handle()` (sync helper); the user-visible behavior,
inputs, and outputs are unchanged.

| Sentinel tool | Cerberus post-merge equivalent | Fate |
| --- | --- | --- |
| `network_scan` | `network_scan` | preserved as-is |
| `file_integrity_check` | `file_integrity_check` | preserved as-is |
| `breach_check` | `breach_check` | preserved as-is |
| `firewall_status` | `firewall_status` | preserved as-is |
| `threat_scan` | `threat_scan` | preserved as-is |
| `network_monitor` | `network_monitor` | preserved as-is |
| `vulnerability_scan` | `vulnerability_scan` | preserved as-is |
| `log_analysis` | `log_analysis` | preserved as-is |
| `security_alert` | `security_alert` | preserved as-is |
| `threat_assess` | `threat_assess` | preserved as-is |
| `quarantine_file` | `quarantine_file` | preserved as-is |
| `firewall_analyze` | `firewall_analyze` | preserved as-is |
| `firewall_evaluate` | `firewall_evaluate` | preserved as-is |
| `firewall_compare` | `firewall_compare` | preserved as-is |
| `firewall_explain_rule` | `firewall_explain_rule` | preserved as-is |
| `firewall_generate` | `firewall_generate` | preserved as-is |
| `security_learn` | `security_learn` | preserved as-is |
| `threat_analyze` | `threat_analyze` | preserved as-is |
| `threat_log_analyze` | `threat_log_analyze` | preserved as-is |
| `threat_defense_profile` | `threat_defense_profile` | preserved as-is |
| `threat_malware_study` | `threat_malware_study` | preserved as-is |
| `threat_detection_rule` | `threat_detection_rule` | preserved as-is |
| `threat_shadow_assessment` | `threat_shadow_assessment` | preserved as-is |
| `threat_knowledge_store` | `threat_knowledge_store` | preserved as-is |

## Dedup decisions

**No dedup performed.** The merge plan considered one near-collision
candidate and explicitly chose to keep both tools:

| Sentinel tool | Cerberus tool | Decision |
| --- | --- | --- |
| `file_integrity_check` | `config_integrity_check` | **NO dedup.** Different scope. `config_integrity_check` SHA-256-hashes one specific YAML (`config/cerberus_limits.yaml`) for tamper detection. `file_integrity_check` hashes arbitrary file lists against a persisted baseline (`data/sentinel_baseline.json`). Orthogonal capabilities; both retained as separate tools. |

Per the planning addenda, no `tests/test_cerberus_dedup.py` is
required because zero dedup decisions were made. This document is
the dedup record.

## Cross-cutting changes (out of name-level scope)

These don't affect tool identity but accompany the merge:

1. **`ToolResult.module` stamp** — every absorbed tool now stamps
   `module="cerberus"` (was `"sentinel"`) so the registry indexes
   the surface as part of Cerberus. The tool name, parameters, and
   return shape are unchanged; only the owning-module identifier
   differs.

2. **`source_module` provenance for Grimoire writes** — per
   addendum 2 decision (b), the two Grimoire write sites
   (`SecurityAnalyzer.store_security_knowledge`,
   `ThreatIntelligence.store_threat_knowledge`) now tag new
   memories `source_module="cerberus.security"`. Historical
   `"sentinel"`-tagged entries remain queryable via the writer-side
   validator allowlist; both strings are accepted by
   `modules/grimoire/grimoire.py:VALID_SOURCE_MODULES`.

3. **`security_alert` default `source` field** — changed from
   `"sentinel"` to `"cerberus.security"`. This is alert-payload
   metadata consumed by Harbinger; verified that no Harbinger code
   does string-equality dispatch on the literal `"sentinel"` and no
   test asserts on this field.

4. **Grimoire wiring caveat** — `SecurityAnalyzer` and
   `ThreatIntelligence` accept an optional `grimoire=` argument
   that `main.py` has never wired in (unlike Reaper's explicit
   post-construction Grimoire attachment). Both
   `store_*_knowledge` methods continue to no-op gracefully when
   Grimoire is `None`. Post-merge behavior is preserved: writes
   no-op today; if Cerberus chooses to wire Grimoire later, writes
   land with the new tag.

5. **Watchdog lockfile** — per addendum 1 decision (a),
   `CerberusWatchdog` retains sole ownership of the watchdog
   lockfile. `SecuritySurface` introduces no new lockfile, no
   heartbeat, no in-process concurrency primitive. Sentinel had
   none of these pre-merge so there was nothing to migrate.

## Verification

End-to-end smoke (commit 5 message and pause-2 report):

- Cerberus instantiates with the security surface loaded.
- `Cerberus.get_tools()` returns 39 tools, zero duplicates.
- `Cerberus.execute("file_integrity_check", {...})` routes to
  `SecuritySurface.handle()` and returns
  `ToolResult(module="cerberus", success=True)`.
- Pre-existing Cerberus tools (e.g. `config_integrity_check`,
  `safety_check`) still work and still report `module="cerberus"`.
- 201 targeted tests pass across `test_cerberus*.py` (commit 9).

The `tool_inventory_pre.json` ↔ `tool_inventory_post.json` diff
script asserts zero missing names and zero schema-byte changes for
the absorbed entries.
