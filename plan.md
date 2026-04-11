# Plan: Routing & Module Targeting Fixes (Batch 2)

## Files to Modify
1. **`modules/shadow/orchestrator.py`** — `_fast_path_classify()` (lines 1728-1827) and `_step2_classify()` LLM prompt (lines 1448-1468), plus `_fallback_classify()` (lines 1500-1538)
2. **`tests/test_orchestrator.py`** — Add tests for all new routing rules

## Changes

### Step 1: Restructure fast-path keyword section with priority order and new modules

The current keyword section (lines 1728-1827) checks: Omen → Cipher → Wraith → Reaper → Cerberus. We need to:

**a) Add code-detection helper set** (used by Nova vs Omen conflict resolution):
```python
code_indicators = {"code", "function", "script", "program", "class", "module", "debug",
                   "compile", "api", "endpoint", "database", "sql", "python", "javascript",
                   "typescript", "rust", "java", "html", "css", "react", "django", "flask",
                   "bot", "parser", "handler", "decorator", "lambda", "variable", "method",
                   "lint", "refactor", "syntax", "algorithm", "snippet", "coding"}
```

**b) Reorder keyword checks to match priority spec:**

1. **Cipher math patterns** (digits + operators) — FIRST priority
   - Keep existing `has_math_symbol` and `has_numeric_expr` checks
   - Move them BEFORE Omen keywords
   
2. **Omen** (code keywords) — add `"compile"` to keywords, keep existing context matching
   
3. **Wraith** (reminders) — keep existing, add `"reminder"`, `"calendar"`, `"task"`, `"todo"`

4. **Sentinel** (security) — NEW
   - Keywords: `security`, `scan`, `vulnerability`, `threat`, `intrusion`, `firewall`, `integrity`, `breach`, `audit`
   - Phrases: `"security check"`, `"security scan"`, `"threat assessment"`
   
5. **Cipher word keywords** — existing math word keywords (calculate, compute, etc.) checked AFTER Sentinel
   - Split Cipher into two checks: pattern-first (priority 1), words-second (priority 5)

6. **Nova** (content creation) — NEW
   - Keywords: `draft`, `compose`, `blog`, `article`, `essay`, `paragraph`, `story`, `creative`, `content`, `post`, `copywriting`, `newsletter`
   - Context words (only route when NOT code): `write`, `generate`, `create`
   - Rule: if `code_indicators` present → skip Nova (Omen will catch it or already did)

7. **Morpheus** (discovery/exploration) — NEW
   - Keywords: `discover`, `explore`, `experiment`, `brainstorm`, `imagine`, `speculate`, `serendipity`, `unconventional`
   - Phrases: `"what if"`, `"cross-pollinate"`, `"creative connection"`

8. **Reaper** (research) — keep existing but AFTER Morpheus
   - Remove `"find"` as sole keyword (too generic, conflicts with Nova/Morpheus)
   - Keep phrases: `"look up"`, `"what is"`, `"who is"`

9. **Void** (metrics/monitoring) — NEW
   - Keywords: `metrics`, `monitoring`, `uptime`, `diagnostics`
   - Phrases: `"system status"`, `"system health"`, `"performance"`, `"health check"`, `"resource usage"`, `"cpu usage"`, `"memory usage"`, `"gpu usage"`, `"disk usage"`

10. **Harbinger** (briefings/reports) — NEW
    - Keywords: `briefing`, `alert`, `notification`
    - Phrases: `"daily briefing"`, `"morning briefing"`, `"status report"`, `"safety report"`

11. **Grimoire** (memory keywords) — keep `"remember"`, `"forget"`, `"recall"` but move LAST in keyword section

12. **Cerberus** (ethics) — keep existing position

### Step 2: Fix the × symbol bug (BUG 10)
The `has_numeric_expr` regex already handles `×` in the character class `[+\-*/×÷xX^%]`. But the problem is that `x` and `X` in the regex match normal letters. The fix: require digits on both sides (already done). The actual bug is that Cipher math patterns are checked AFTER Omen, so if any Omen keyword matches first, Cipher never runs. Moving Cipher pattern detection to position 1 fixes this.

Also: the `"x"` in the regex pattern could match words like "text". We should keep the digit-boundary requirement strict. The current regex `\d+\s*[...xX...]\s*\d+` already requires digits on both sides, so "text" won't match. The `×` symbol is fine.

### Step 3: Update LLM router prompt (BUG 11)
Replace the limited 5-module capabilities list with all 13 modules. Add clear, actionable descriptions for each.

### Step 4: Update `_fallback_classify()` 
Add fallback entries for the new modules (Sentinel, Void, Nova, Morpheus, Harbinger) so they're reachable even when LLM routing fails.

### Step 5: Add tests
Add test cases in `tests/test_orchestrator.py`:
- BUG 6: "Run a security check on your system" → sentinel
- BUG 7: "Show me your system metrics" → void  
- BUG 8: "Write me a short paragraph about why landscaping is rewarding" → nova
- BUG 8 conflict: "Write a Python function to sort a list" → omen (not nova)
- BUG 9: "Discover something interesting about neural network architecture" → morpheus
- BUG 10: "What is 347 × 892?" → cipher
- BUG 10: "347 * 892" → cipher (not reaper)
- Conflict: "calculate 15% of 2400" → cipher (not reaper)
- Sentinel phrases: "threat assessment of my network" → sentinel
- Void phrases: "how is my system health" → void
- Nova vs Omen: "write a blog post about landscaping" → nova
- Morpheus: "what if we combined neural networks with landscaping scheduling" → morpheus
- Priority: math pattern before everything: "5 + 3" → cipher
