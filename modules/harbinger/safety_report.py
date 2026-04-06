"""Daily Safety Report Generator for Cerberus audit logs.

Queries the cerberus_audit_log table in SQLite, computes metrics
over a 24-hour window, and produces structured reports for Harbinger
morning briefings.
"""

import json
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# SQLite schema — created if the table doesn't exist yet
# ---------------------------------------------------------------------------

AUDIT_TABLE_DDL = """\
CREATE TABLE IF NOT EXISTS cerberus_audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,
    type        TEXT    NOT NULL,
    tool        TEXT,
    module      TEXT,
    reason      TEXT,
    rule        TEXT,
    verdict     TEXT,
    resolved    INTEGER DEFAULT 0,
    resolved_at TEXT,
    category    TEXT,
    metadata    TEXT
);
"""

# Columns expected by the report generator:
#   timestamp   — ISO 8601, e.g. "2026-04-05T08:31:00"
#   type        — one of: allow, denial, approval_required, log, modify,
#                 creator_exception, creator_authorization
#   tool        — the tool name that was checked
#   module      — the requesting module codename
#   reason      — human-readable explanation of the verdict
#   rule        — which safety rule matched (nullable)
#   verdict     — SafetyVerdict enum value as string
#   resolved    — 1 if a block was later overridden, else 0
#   resolved_at — ISO 8601 of when the override happened (nullable)
#   category    — grouping key for false-positive calculations
#   metadata    — JSON blob for extra context (nullable)

# Anomaly detection thresholds
RATE_LIMIT_WARN_FRACTION = 0.80   # Flag when >80% of hourly capacity used
HOURLY_ACTION_THRESHOLD = 100     # Expected max actions per hour


class DailySafetyReport:
    """Generate a structured safety report from Cerberus audit logs."""

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_table(db_path: Path) -> None:
        """Create the cerberus_audit_log table if it doesn't exist."""
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute(AUDIT_TABLE_DDL)
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def generate(self, date: datetime.date, db_path: Path) -> dict:
        """Query the audit log for *date* and compute all report metrics.

        Args:
            date: The calendar day to report on.
            db_path: Path to the SQLite database containing
                     ``cerberus_audit_log``.

        Returns:
            A structured dict with keys: summary, blocks, anomalies,
            false_positive_rate, calibration_alerts.
        """
        self._ensure_table(db_path)

        day_start = datetime(date.year, date.month, date.day).isoformat()
        day_end = (
            datetime(date.year, date.month, date.day) + timedelta(days=1)
        ).isoformat()

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM cerberus_audit_log "
                "WHERE timestamp >= ? AND timestamp < ? "
                "ORDER BY timestamp",
                (day_start, day_end),
            ).fetchall()
        finally:
            conn.close()

        entries = [dict(r) for r in rows]

        summary = self._compute_summary(entries)
        blocks = self._collect_blocks(entries)
        anomalies = self._detect_anomalies(entries)
        fp_rate = self._compute_false_positive_rate(entries)
        calibration = self._compute_calibration_alerts(fp_rate)

        return {
            "date": str(date),
            "generated_at": datetime.now().isoformat(),
            "summary": summary,
            "blocks": blocks,
            "anomalies": anomalies,
            "false_positive_rate": fp_rate,
            "calibration_alerts": calibration,
        }

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_summary(entries: list[dict]) -> dict:
        total = len(entries)
        type_counts = Counter(e["type"] for e in entries)

        return {
            "total_actions": total,
            "approved_autonomous": type_counts.get("allow", 0),
            "approved_with_logging": type_counts.get("log", 0),
            "deferred_to_queue": type_counts.get("approval_required", 0),
            "blocked": type_counts.get("denial", 0),
            "modified": type_counts.get("modify", 0),
            "creator_exceptions": type_counts.get("creator_exception", 0),
            "creator_authorizations": type_counts.get("creator_authorization", 0),
        }

    # ------------------------------------------------------------------
    # Blocks detail
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_blocks(entries: list[dict]) -> list[dict]:
        blocks = []
        for e in entries:
            if e["type"] == "denial":
                blocks.append({
                    "action_type": e.get("tool", "unknown"),
                    "requesting_module": e.get("module", "unknown"),
                    "reason": e.get("reason", ""),
                    "timestamp": e.get("timestamp", ""),
                    "resolved": bool(e.get("resolved", 0)),
                })
        return blocks

    # ------------------------------------------------------------------
    # Anomaly detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_anomalies(entries: list[dict]) -> list[dict]:
        anomalies: list[dict] = []

        # 1. Injection attempts — look for injection-related reasons
        injection_keywords = ["injection", "metacharacter", "shell", "sql", "xss"]
        for e in entries:
            reason = (e.get("reason") or "").lower()
            if any(kw in reason for kw in injection_keywords):
                anomalies.append({
                    "type": "injection_attempt",
                    "detail": f"Injection pattern detected: {e.get('tool', '?')} "
                              f"from {e.get('module', '?')}",
                    "timestamp": e.get("timestamp", ""),
                })

        # 2. Rate limit approaches — hourly action counts
        hourly: Counter = Counter()
        for e in entries:
            ts = e.get("timestamp", "")
            if len(ts) >= 13:  # "YYYY-MM-DDTHH"
                hourly[ts[:13]] += 1

        for hour, count in hourly.items():
            if count >= int(HOURLY_ACTION_THRESHOLD * RATE_LIMIT_WARN_FRACTION):
                anomalies.append({
                    "type": "rate_limit_approach",
                    "detail": f"{count} actions in hour {hour} "
                              f"(threshold: {HOURLY_ACTION_THRESHOLD})",
                    "timestamp": hour,
                })

        # 3. Unusual patterns — spike of denials in a single hour
        hourly_denials: Counter = Counter()
        for e in entries:
            if e["type"] == "denial":
                ts = e.get("timestamp", "")
                if len(ts) >= 13:
                    hourly_denials[ts[:13]] += 1

        for hour, count in hourly_denials.items():
            if count >= 5:
                anomalies.append({
                    "type": "denial_spike",
                    "detail": f"{count} denials in hour {hour}",
                    "timestamp": hour,
                })

        return anomalies

    # ------------------------------------------------------------------
    # False positive rate
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_false_positive_rate(entries: list[dict]) -> dict:
        denials = [e for e in entries if e["type"] == "denial"]
        total_blocks = len(denials)
        total_resolved = sum(1 for e in denials if e.get("resolved"))

        overall = total_resolved / total_blocks if total_blocks > 0 else 0.0

        # Per-category breakdown
        by_category: dict[str, dict] = {}
        for e in denials:
            cat = e.get("category") or "uncategorized"
            if cat not in by_category:
                by_category[cat] = {"blocks": 0, "resolved": 0}
            by_category[cat]["blocks"] += 1
            if e.get("resolved"):
                by_category[cat]["resolved"] += 1

        category_rates = {}
        for cat, counts in by_category.items():
            rate = counts["resolved"] / counts["blocks"] if counts["blocks"] > 0 else 0.0
            category_rates[cat] = {
                "blocks": counts["blocks"],
                "resolved": counts["resolved"],
                "rate": round(rate, 4),
            }

        return {
            "overall": round(overall, 4),
            "total_blocks": total_blocks,
            "total_resolved": total_resolved,
            "by_category": category_rates,
        }

    # ------------------------------------------------------------------
    # Calibration alerts
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_calibration_alerts(fp_rate: dict) -> list[dict]:
        alerts = []
        for cat, info in fp_rate.get("by_category", {}).items():
            if info["rate"] > 0.15:
                alerts.append({
                    "category": cat,
                    "false_positive_rate": info["rate"],
                    "blocks": info["blocks"],
                    "resolved": info["resolved"],
                    "message": f"Category '{cat}' has {info['rate']:.1%} false positive "
                               f"rate ({info['resolved']}/{info['blocks']} blocks overridden). "
                               f"Consider tuning rules.",
                })
        return alerts

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    @staticmethod
    def format_for_harbinger(report: dict) -> str:
        """Format the report as clean readable text for the morning briefing."""
        lines: list[str] = []
        s = report.get("summary", {})

        lines.append(f"=== DAILY SAFETY REPORT — {report.get('date', '?')} ===")
        lines.append("")

        # Summary
        lines.append("SUMMARY")
        lines.append(f"  Total actions evaluated:  {s.get('total_actions', 0)}")
        lines.append(f"  Approved (autonomous):    {s.get('approved_autonomous', 0)}")
        lines.append(f"  Approved (with logging):  {s.get('approved_with_logging', 0)}")
        lines.append(f"  Deferred to queue:        {s.get('deferred_to_queue', 0)}")
        lines.append(f"  Blocked:                  {s.get('blocked', 0)}")
        lines.append(f"  Modified:                 {s.get('modified', 0)}")
        lines.append(f"  Creator exceptions:       {s.get('creator_exceptions', 0)}")
        lines.append(f"  Creator authorizations:   {s.get('creator_authorizations', 0)}")
        lines.append("")

        # Blocks
        blocks = report.get("blocks", [])
        if blocks:
            lines.append(f"BLOCKED ACTIONS ({len(blocks)})")
            for b in blocks:
                resolved_tag = " [RESOLVED]" if b.get("resolved") else ""
                lines.append(
                    f"  - [{b.get('timestamp', '?')}] {b.get('action_type', '?')} "
                    f"(from {b.get('requesting_module', '?')}): "
                    f"{b.get('reason', 'no reason')}{resolved_tag}"
                )
            lines.append("")

        # Anomalies
        anomalies = report.get("anomalies", [])
        if anomalies:
            lines.append(f"ANOMALIES ({len(anomalies)})")
            for a in anomalies:
                lines.append(f"  - [{a.get('type', '?')}] {a.get('detail', '')}")
            lines.append("")

        # False positive rate
        fp = report.get("false_positive_rate", {})
        lines.append(f"FALSE POSITIVE RATE: {fp.get('overall', 0):.1%} overall "
                      f"({fp.get('total_resolved', 0)}/{fp.get('total_blocks', 0)} blocks overridden)")
        lines.append("")

        # Calibration alerts
        alerts = report.get("calibration_alerts", [])
        if alerts:
            lines.append("CALIBRATION ALERTS")
            for a in alerts:
                lines.append(f"  ⚠ {a.get('message', '')}")
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @staticmethod
    def save_report(report: dict, output_dir: Path) -> Path:
        """Save the report as a YAML file.

        Args:
            report: The structured report dict from :meth:`generate`.
            output_dir: Directory to write into (created if needed).

        Returns:
            The Path of the written file.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{report.get('date', 'unknown')}_safety_report.yaml"
        filepath = output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(report, f, default_flow_style=False, sort_keys=False)

        return filepath
