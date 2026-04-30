#!/usr/bin/env bash
# B2 verification harness — one-shot followup to commit 4d53206
# (fix(retry_engine): add DETERMINISTIC failure classification, break retry death spiral)
#
# Runs 14 days post-fix to confirm the deterministic-failure short-circuit
# is firing in production logs. Writes a plain-text report; takes no other action.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="$REPO_ROOT/data/reports"
REPORT_DATE="$(date +%Y-%m-%d)"
REPORT_FILE="$REPORT_DIR/b2_followup_${REPORT_DATE}.txt"

mkdir -p "$REPORT_DIR"

# Window: last 14 days. Adjust SINCE if rerun manually with different scope.
SINCE="14 days ago"

# Read the user journal (Shadow's daemons run as user units — shadow-void,
# shadow-cerberus-watchdog, etc.). Fall back to whatever the user journal
# contains if Shadow itself isn't a unit yet.
JOURNAL_CMD="journalctl --user --since \"$SINCE\""

# `grep -c` exits 1 on zero matches but still prints "0" — exactly the value
# we want.  Trailing `|| true` keeps `set -e` happy without re-emitting "0"
# (which would corrupt the integer comparisons below).
SHORT_CIRCUITS=$(eval "$JOURNAL_CMD" 2>/dev/null | grep -ic 'deterministic failure on first attempt' || true)
DEEP_RETRIES=$(eval "$JOURNAL_CMD" 2>/dev/null | grep -icE 'retry attempt ([4-9]|1[0-9])' || true)
TOTAL_RETRY_LINES=$(eval "$JOURNAL_CMD" 2>/dev/null | grep -ic 'retry attempt' || true)

# Sample deep retries (up to 5) for triage
DEEP_RETRY_SAMPLES=$(eval "$JOURNAL_CMD" 2>/dev/null | grep -iE 'retry attempt ([4-9]|1[0-9])' | head -5 || true)

{
  echo "B2 Verification Report"
  echo "======================"
  echo
  echo "Generated: $(date -Iseconds)"
  echo "Window:    last 14 days (since $SINCE)"
  echo "Source:    journalctl --user"
  echo "Fix ref:   commit 4d53206 (retry_engine deterministic-failure short-circuit)"
  echo
  echo "Counts"
  echo "------"
  echo "Deterministic short-circuits fired:  $SHORT_CIRCUITS"
  echo "Retry attempts >= 4 (suspicious):    $DEEP_RETRIES"
  echo "Total 'retry attempt' log lines:     $TOTAL_RETRY_LINES"
  echo
  echo "Interpretation"
  echo "--------------"
  if [ "$SHORT_CIRCUITS" -eq 0 ] && [ "$TOTAL_RETRY_LINES" -eq 0 ]; then
    echo "AMBIGUOUS: No retry activity logged at all in the window."
    echo "Either Shadow had no failures (unusual over 14 days) or logging is not"
    echo "reaching the user journal. Check Shadow's logging configuration."
  elif [ "$SHORT_CIRCUITS" -eq 0 ] && [ "$TOTAL_RETRY_LINES" -gt 0 ]; then
    echo "PROBLEM: Retries are happening but no deterministic short-circuits fired."
    echo "Either no deterministic failures occurred (possible), or the classifier"
    echo "is not firing when it should. Review the retry samples below to triage."
  elif [ "$DEEP_RETRIES" -gt 0 ]; then
    echo "PARTIAL: Short-circuits firing ($SHORT_CIRCUITS) but deep retries also"
    echo "occurring ($DEEP_RETRIES). The classifier may be missing some"
    echo "deterministic failure modes. Review samples below."
  else
    echo "HEALTHY: Short-circuits firing ($SHORT_CIRCUITS) and no retry attempts"
    echo "reached >= 4. Classifier appears to be catching deterministic failures"
    echo "before the retry loop burns budget."
  fi
  echo
  echo "Deep retry samples (up to 5)"
  echo "----------------------------"
  if [ -z "$DEEP_RETRY_SAMPLES" ]; then
    echo "(none)"
  else
    echo "$DEEP_RETRY_SAMPLES"
  fi
  echo
  echo "Next steps"
  echo "----------"
  echo "Master triages. If PROBLEM or PARTIAL, extend FailureType.DETERMINISTIC"
  echo "markers in modules/shadow/retry_engine.py and add regression tests."
  echo "If HEALTHY, file is informational only — no action needed."
} > "$REPORT_FILE"

# Print the report path so the systemd journal records what was generated
echo "B2 verification report written: $REPORT_FILE"
