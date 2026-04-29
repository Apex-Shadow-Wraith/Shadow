"""Cerberus security surface — absorbed Sentinel logic.

White hat security: detection, analysis, defensive response.

HARD CONSTRAINT: Defensive only. Never retaliates, never launches
offensive attacks, never probes systems it does not own. That is the
permanent, non-negotiable line between white hat and illegal.

Phase 1: psutil-based network monitoring, file integrity hashing,
threat assessment stubs. No Suricata/Zeek yet (Ubuntu).

Absorbed from modules/sentinel/sentinel.py during Phase A
consolidation. Behavior preserved verbatim. Differences from the
old Sentinel module:

- No longer a BaseModule. SecuritySurface is a plain helper held
  by Cerberus; lifecycle (initialize/shutdown) is driven from
  Cerberus's own async methods. No registry presence, no
  independent status tracking.
- async execute() lifted to synchronous handle(tool_name, params)
  -> ToolResult. Cerberus's existing execute() branch awaits
  nothing here; the handler bodies were already pure-sync.
- ToolResult.module is stamped "cerberus" (the absorbing module)
  rather than "sentinel" so the registry sees the surface as
  part of Cerberus.
- get_tools() removed; the 24 tool schemas now live in
  Cerberus.get_tools() (see commit 5).
- _record_call removed; Cerberus's own BaseModule call-tracking
  records the dispatch.
- Watchdog lockfile contract: SecuritySurface holds none. Per
  addendum 1 decision (a), CerberusWatchdog retains sole
  ownership of the lockfile.
- Grimoire writes inside SecurityAnalyzer / ThreatIntelligence
  tag source_module="cerberus.security" per addendum 2 (b).
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from modules.base import ToolResult
from modules.cerberus.security.analyzer import SecurityAnalyzer
from modules.cerberus.security.threat_intelligence import ThreatIntelligence

logger = logging.getLogger("shadow.cerberus.security")


# Tools dispatched by SecuritySurface.handle(). Mirrors the schemas
# that Cerberus.get_tools() exposes for the absorbed surface.
SECURITY_TOOLS: frozenset[str] = frozenset({
    "network_scan",
    "file_integrity_check",
    "breach_check",
    "firewall_status",
    "threat_scan",
    "network_monitor",
    "vulnerability_scan",
    "log_analysis",
    "security_alert",
    "threat_assess",
    "quarantine_file",
    "firewall_analyze",
    "firewall_evaluate",
    "firewall_compare",
    "firewall_explain_rule",
    "firewall_generate",
    "security_learn",
    "threat_analyze",
    "threat_log_analyze",
    "threat_defense_profile",
    "threat_malware_study",
    "threat_detection_rule",
    "threat_shadow_assessment",
    "threat_knowledge_store",
})


class SecuritySurface:
    """Cerberus's absorbed security surface.

    Holds the integrity baseline, quarantine directory, firewall
    analyzer, and threat intelligence engine. Cerberus delegates the
    24 absorbed tool calls to handle().
    """

    # ToolResult.module value stamped on every result returned by this
    # surface. Set to "cerberus" because the absorbing module owns the
    # surface post-merge; the registry indexes by this name.
    MODULE_NAME: str = "cerberus"

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        grimoire: Any | None = None,
    ) -> None:
        """Initialize SecuritySurface.

        Args:
            config: Configuration dict. Recognized keys:
                baseline_file: path for file-integrity baseline JSON
                    (default "data/sentinel_baseline.json" — kept as-is
                    to preserve any existing baseline data; the
                    "sentinel" filename is a historical provenance
                    marker, not a scope indicator).
                quarantine_dir: directory for quarantined files
                    (default "data/research/quarantine").
                grimoire: optional Grimoire instance (also accepted as
                    a separate kwarg for symmetry with the Reaper
                    wiring pattern; either route works).
            grimoire: Optional Grimoire instance for the analyzer +
                threat intelligence engines. May be None — both
                store_*_knowledge methods no-op gracefully when
                Grimoire is unavailable, matching the pre-merge
                Sentinel behavior on this codebase.
        """
        self._config = config or {}
        self._baseline_file = Path(
            self._config.get("baseline_file", "data/sentinel_baseline.json")
        )
        self._quarantine_dir = Path(
            self._config.get("quarantine_dir", "data/research/quarantine")
        )
        self._baseline: dict[str, str] = {}
        self._alerts: list[dict[str, Any]] = []

        # Grimoire wiring: prefer explicit kwarg over config-dict slot.
        grim = grimoire if grimoire is not None else self._config.get("grimoire")
        self._analyzer = SecurityAnalyzer(grimoire=grim)
        self._threat_intel = ThreatIntelligence(grimoire=grim)

    def initialize(self) -> None:
        """Load file integrity baseline and ensure quarantine dir exists.

        Synchronous — Cerberus calls this from its own async initialize().
        Raises on filesystem errors so Cerberus can fail loud.
        """
        self._load_baseline()
        self._quarantine_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            "SecuritySurface online. %d files in integrity baseline.",
            len(self._baseline),
        )

    def shutdown(self) -> None:
        """Persist the integrity baseline to disk.

        Synchronous — Cerberus calls this from its own async shutdown().
        """
        self._save_baseline()
        logger.info("SecuritySurface offline.")

    def handle(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        """Dispatch one of the 24 absorbed security tools.

        Synchronous; all handler bodies are pure-sync and were already
        called synchronously inside the old async Sentinel.execute()
        wrapper. Cerberus's own execute() branch awaits nothing here.
        """
        start = time.time()
        try:
            handlers = {
                "network_scan": self._network_scan,
                "file_integrity_check": self._file_integrity_check,
                "breach_check": self._breach_check,
                "firewall_status": self._firewall_status,
                "threat_scan": self._threat_scan,
                "network_monitor": self._network_monitor,
                "vulnerability_scan": self._vulnerability_scan,
                "log_analysis": self._log_analysis,
                "security_alert": self._security_alert,
                "threat_assess": self._threat_assess,
                "quarantine_file": self._quarantine_file,
                "firewall_analyze": self._firewall_analyze,
                "firewall_evaluate": self._firewall_evaluate,
                "firewall_compare": self._firewall_compare,
                "firewall_explain_rule": self._firewall_explain_rule,
                "firewall_generate": self._firewall_generate,
                "security_learn": self._security_learn,
                "threat_analyze": self._threat_analyze,
                "threat_log_analyze": self._threat_log_analyze,
                "threat_defense_profile": self._threat_defense_profile,
                "threat_malware_study": self._threat_malware_study,
                "threat_detection_rule": self._threat_detection_rule,
                "threat_shadow_assessment": self._threat_shadow_assessment,
                "threat_knowledge_store": self._threat_knowledge_store,
            }

            handler = handlers.get(tool_name)
            if handler is None:
                result = ToolResult(
                    success=False, content=None, tool_name=tool_name,
                    module=self.MODULE_NAME, error=f"Unknown security tool: {tool_name}",
                )
            else:
                result = handler(params)

            result.execution_time_ms = (time.time() - start) * 1000
            return result

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            logger.error("Security tool '%s' failed: %s", tool_name, e)
            return ToolResult(
                success=False, content=None, tool_name=tool_name,
                module=self.MODULE_NAME, error=str(e), execution_time_ms=elapsed,
            )

    # --- Tool implementations ---

    def _network_scan(self, params: dict[str, Any]) -> ToolResult:
        """List current network connections using psutil.

        Args:
            params: No required parameters.
        """
        try:
            import psutil
        except ImportError:
            return ToolResult(
                success=False, content=None, tool_name="network_scan",
                module=self.MODULE_NAME, error="psutil not installed",
            )

        connections = []
        for conn in psutil.net_connections(kind="inet"):
            connections.append({
                "fd": conn.fd,
                "family": str(conn.family),
                "type": str(conn.type),
                "laddr": f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else None,
                "raddr": f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else None,
                "status": conn.status,
                "pid": conn.pid,
            })

        return ToolResult(
            success=True,
            content={
                "connection_count": len(connections),
                "connections": connections[:50],  # Limit output
                "scanned_at": datetime.now().isoformat(),
            },
            tool_name="network_scan",
            module=self.MODULE_NAME,
        )

    def _file_integrity_check(self, params: dict[str, Any]) -> ToolResult:
        """Check file hashes against baseline.

        If no baseline exists for a file, creates one. If baseline exists,
        compares and reports changes.

        Args:
            params: 'file_paths' (list of str).
        """
        file_paths = params.get("file_paths", [])
        if not file_paths:
            return ToolResult(
                success=False, content=None, tool_name="file_integrity_check",
                module=self.MODULE_NAME, error="file_paths list is required",
            )

        results: list[dict[str, Any]] = []
        for fp in file_paths:
            path = Path(fp)
            if not path.exists():
                results.append({"file": fp, "status": "missing", "changed": None})
                continue

            current_hash = self._hash_file(path)
            stored_hash = self._baseline.get(str(path.resolve()))

            if stored_hash is None:
                # New file — add to baseline
                self._baseline[str(path.resolve())] = current_hash
                results.append({
                    "file": fp, "status": "baselined", "hash": current_hash,
                    "changed": False,
                })
            elif stored_hash == current_hash:
                results.append({
                    "file": fp, "status": "intact", "hash": current_hash,
                    "changed": False,
                })
            else:
                results.append({
                    "file": fp, "status": "MODIFIED",
                    "expected_hash": stored_hash,
                    "current_hash": current_hash,
                    "changed": True,
                })

        self._save_baseline()
        modified_count = sum(1 for r in results if r.get("changed") is True)

        return ToolResult(
            success=True,
            content={
                "files_checked": len(results),
                "modified": modified_count,
                "results": results,
            },
            tool_name="file_integrity_check",
            module=self.MODULE_NAME,
        )

    def _breach_check(self, params: dict[str, Any]) -> ToolResult:
        """Check if an email has been in known data breaches.

        Phase 1: Stub. HaveIBeenPwned API integration deferred.

        Args:
            params: 'email' (str).
        """
        email = params.get("email", "")
        if not email:
            return ToolResult(
                success=False, content="Email address is required", tool_name="breach_check",
                module=self.MODULE_NAME, error="Email address is required",
            )

        return ToolResult(
            success=True,
            content={
                "email": email,
                "status": "stub",
                "message": "HaveIBeenPwned integration deferred to Ubuntu Phase 1. "
                           "No actual breach check performed.",
                "breaches_found": 0,
            },
            tool_name="breach_check",
            module=self.MODULE_NAME,
        )

    def _firewall_status(self, params: dict[str, Any]) -> ToolResult:
        """Check host firewall status and active rules.

        Not yet operational — requires Ubuntu deployment with iptables/nftables.

        Args:
            params: No required parameters.
        """
        return ToolResult(
            success=True,
            content={
                "status": "not_operational",
                "message": "Tool not yet operational — requires Ubuntu deployment "
                           "with iptables/nftables for host firewall inspection.",
            },
            tool_name="firewall_status",
            module=self.MODULE_NAME,
        )

    def _threat_scan(self, params: dict[str, Any]) -> ToolResult:
        """Run active threat detection scan.

        Not yet operational — requires Ubuntu deployment with Suricata IDS.

        Args:
            params: Optional 'scan_type' (str).
        """
        return ToolResult(
            success=True,
            content={
                "status": "not_operational",
                "message": "Tool not yet operational — requires Ubuntu deployment "
                           "with Suricata IDS for active threat detection.",
            },
            tool_name="threat_scan",
            module=self.MODULE_NAME,
        )

    def _network_monitor(self, params: dict[str, Any]) -> ToolResult:
        """Monitor network traffic for anomalies.

        Not yet operational — requires Ubuntu deployment with Zeek network analyzer.

        Args:
            params: Optional 'duration_seconds' (int).
        """
        return ToolResult(
            success=True,
            content={
                "status": "not_operational",
                "message": "Tool not yet operational — requires Ubuntu deployment "
                           "with Zeek network analyzer for traffic monitoring.",
            },
            tool_name="network_monitor",
            module=self.MODULE_NAME,
        )

    def _vulnerability_scan(self, params: dict[str, Any]) -> ToolResult:
        """Scan system for known vulnerabilities.

        Not yet operational — requires Ubuntu deployment with OpenVAS/GVM scanner.

        Args:
            params: Optional 'target' (str).
        """
        return ToolResult(
            success=True,
            content={
                "status": "not_operational",
                "message": "Tool not yet operational — requires Ubuntu deployment "
                           "with OpenVAS/GVM for vulnerability scanning.",
            },
            tool_name="vulnerability_scan",
            module=self.MODULE_NAME,
        )

    def _log_analysis(self, params: dict[str, Any]) -> ToolResult:
        """Analyze system and security logs for suspicious patterns.

        Not yet operational — requires Ubuntu deployment with auditd log framework.

        Args:
            params: Optional 'log_source' (str).
        """
        return ToolResult(
            success=True,
            content={
                "status": "not_operational",
                "message": "Tool not yet operational — requires Ubuntu deployment "
                           "with auditd for system log analysis.",
            },
            tool_name="log_analysis",
            module=self.MODULE_NAME,
        )

    def _security_alert(self, params: dict[str, Any]) -> ToolResult:
        """Generate a security alert for Harbinger.

        Args:
            params: 'message', 'severity' (low/medium/high/critical), 'source'.
        """
        message = params.get("message", "")
        if not message:
            return ToolResult(
                success=False, content=None, tool_name="security_alert",
                module=self.MODULE_NAME, error="Alert message is required",
            )

        severity = params.get("severity", "medium")
        valid_severities = ("low", "medium", "high", "critical")
        if severity not in valid_severities:
            return ToolResult(
                success=False, content=None, tool_name="security_alert",
                module=self.MODULE_NAME,
                error=f"Severity must be one of: {', '.join(valid_severities)}",
            )

        alert = {
            "message": message,
            "severity": severity,
            "source": params.get("source", "cerberus.security"),
            "timestamp": datetime.now().isoformat(),
            "status": "active",
        }
        self._alerts.append(alert)
        logger.warning("SECURITY ALERT [%s]: %s", severity.upper(), message)

        return ToolResult(
            success=True,
            content=alert,
            tool_name="security_alert",
            module=self.MODULE_NAME,
        )

    def _threat_assess(self, params: dict[str, Any]) -> ToolResult:
        """Assess the threat level of an event.

        Phase 1: Rule-based scoring.

        Args:
            params: 'event' (str), optional 'indicators' (list).
        """
        event = params.get("event", "")
        indicators = params.get("indicators", [])

        if not event:
            return ToolResult(
                success=False, content=None, tool_name="threat_assess",
                module=self.MODULE_NAME, error="Event description is required",
            )

        lower = event.lower()
        score = 0
        reasons = []

        # Rule-based scoring
        high_threat = ["breach", "ransomware", "rootkit", "exploit", "backdoor", "c2"]
        medium_threat = ["scan", "brute", "unauthorized", "suspicious", "anomaly"]
        low_threat = ["update", "patch", "warning", "audit"]

        for kw in high_threat:
            if kw in lower:
                score += 30
                reasons.append(f"High-threat keyword: {kw}")
        for kw in medium_threat:
            if kw in lower:
                score += 15
                reasons.append(f"Medium-threat keyword: {kw}")
        for kw in low_threat:
            if kw in lower:
                score += 5
                reasons.append(f"Low-threat keyword: {kw}")

        # Indicator bonus
        score += len(indicators) * 10

        # Cap at 100
        score = min(score, 100)

        if score >= 70:
            level = "critical"
        elif score >= 40:
            level = "high"
        elif score >= 20:
            level = "medium"
        else:
            level = "low"

        return ToolResult(
            success=True,
            content={
                "event": event,
                "threat_score": score,
                "threat_level": level,
                "reasons": reasons,
                "indicators_count": len(indicators),
            },
            tool_name="threat_assess",
            module=self.MODULE_NAME,
        )

    def _quarantine_file(self, params: dict[str, Any]) -> ToolResult:
        """Move a suspicious file to the quarantine directory.

        Args:
            params: 'file_path' (str), 'reason' (str).
        """
        file_path = params.get("file_path", "")
        reason = params.get("reason", "unspecified")

        if not file_path:
            return ToolResult(
                success=False, content=None, tool_name="quarantine_file",
                module=self.MODULE_NAME, error="file_path is required",
            )

        source = Path(file_path)
        if not source.exists():
            return ToolResult(
                success=False, content=None, tool_name="quarantine_file",
                module=self.MODULE_NAME, error=f"File not found: {file_path}",
            )

        # Move to quarantine with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = self._quarantine_dir / f"{timestamp}_{source.name}"
        self._quarantine_dir.mkdir(parents=True, exist_ok=True)

        try:
            shutil.move(str(source), str(dest))

            # Log quarantine action
            meta = {
                "original_path": str(source),
                "quarantine_path": str(dest),
                "reason": reason,
                "timestamp": datetime.now().isoformat(),
                "hash": self._hash_file(dest),
            }
            meta_file = dest.with_suffix(dest.suffix + ".meta.json")
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)

            logger.warning("File quarantined: %s → %s (reason: %s)", source, dest, reason)

            return ToolResult(
                success=True,
                content=meta,
                tool_name="quarantine_file",
                module=self.MODULE_NAME,
            )

        except OSError as e:
            return ToolResult(
                success=False, content=None, tool_name="quarantine_file",
                module=self.MODULE_NAME, error=f"Failed to quarantine: {e}",
            )

    # --- Security Analyzer tool handlers ---

    def _firewall_analyze(self, params: dict[str, Any]) -> ToolResult:
        """Analyze a firewall configuration."""
        config_text = params.get("config_text", "")
        if not config_text:
            return ToolResult(
                success=False, content=None, tool_name="firewall_analyze",
                module=self.MODULE_NAME, error="config_text is required",
            )
        firewall_type = params.get("firewall_type", "auto")
        result = self._analyzer.analyze_firewall_config(config_text, firewall_type)
        return ToolResult(
            success="error" not in result, content=result,
            tool_name="firewall_analyze", module=self.MODULE_NAME,
            error=result.get("error"),
        )

    def _firewall_evaluate(self, params: dict[str, Any]) -> ToolResult:
        """Evaluate a firewall analysis for security best practices."""
        analysis = params.get("analysis", {})
        if not analysis:
            return ToolResult(
                success=False, content=None, tool_name="firewall_evaluate",
                module=self.MODULE_NAME, error="analysis dict is required",
            )
        result = self._analyzer.evaluate_firewall(analysis)
        return ToolResult(
            success="error" not in result, content=result,
            tool_name="firewall_evaluate", module=self.MODULE_NAME,
            error=result.get("error"),
        )

    def _firewall_compare(self, params: dict[str, Any]) -> ToolResult:
        """Compare multiple firewall configs."""
        configs = params.get("configs", [])
        if len(configs) < 2:
            return ToolResult(
                success=False, content=None, tool_name="firewall_compare",
                module=self.MODULE_NAME, error="Need at least 2 configs to compare",
            )
        result = self._analyzer.compare_firewalls(configs)
        return ToolResult(
            success="error" not in result, content=result,
            tool_name="firewall_compare", module=self.MODULE_NAME,
            error=result.get("error"),
        )

    def _firewall_explain_rule(self, params: dict[str, Any]) -> ToolResult:
        """Explain a single firewall rule."""
        rule_text = params.get("rule_text", "")
        firewall_type = params.get("firewall_type", "")
        if not rule_text or not firewall_type:
            return ToolResult(
                success=False, content=None, tool_name="firewall_explain_rule",
                module=self.MODULE_NAME, error="rule_text and firewall_type are required",
            )
        result = self._analyzer.explain_rule(rule_text, firewall_type)
        return ToolResult(
            success=True, content=result,
            tool_name="firewall_explain_rule", module=self.MODULE_NAME,
        )

    def _firewall_generate(self, params: dict[str, Any]) -> ToolResult:
        """Generate a firewall config from requirements."""
        requirements = params.get("requirements", {})
        if not requirements:
            return ToolResult(
                success=False, content=None, tool_name="firewall_generate",
                module=self.MODULE_NAME, error="requirements dict is required",
            )
        result = self._analyzer.generate_firewall(requirements)
        return ToolResult(
            success=True, content=result,
            tool_name="firewall_generate", module=self.MODULE_NAME,
        )

    def _security_learn(self, params: dict[str, Any]) -> ToolResult:
        """Learn a firewall concept and optionally store in Grimoire."""
        topic = params.get("topic", "")
        if not topic:
            return ToolResult(
                success=False, content=None, tool_name="security_learn",
                module=self.MODULE_NAME, error="topic is required",
            )
        knowledge = self._analyzer.learn_firewall_concepts(topic)
        if "error" in knowledge:
            return ToolResult(
                success=False, content=knowledge,
                tool_name="security_learn", module=self.MODULE_NAME,
                error=knowledge["error"],
            )
        stored = self._analyzer.store_security_knowledge(knowledge, source="security_analyzer")
        knowledge["stored_in_grimoire"] = stored > 0
        return ToolResult(
            success=True, content=knowledge,
            tool_name="security_learn", module=self.MODULE_NAME,
        )

    # --- Threat Intelligence tool handlers ---

    def _threat_analyze(self, params: dict[str, Any]) -> ToolResult:
        """Analyze a known attack pattern."""
        pattern_name = params.get("pattern_name", "")
        if not pattern_name:
            return ToolResult(
                success=False, content=None, tool_name="threat_analyze",
                module=self.MODULE_NAME, error="pattern_name is required",
            )
        result = self._threat_intel.analyze_attack_pattern(pattern_name)
        return ToolResult(
            success="error" not in result, content=result,
            tool_name="threat_analyze", module=self.MODULE_NAME,
            error=result.get("error"),
        )

    def _threat_log_analyze(self, params: dict[str, Any]) -> ToolResult:
        """Analyze log entries for threats."""
        log_text = params.get("log_text", "")
        if not log_text:
            return ToolResult(
                success=False, content=None, tool_name="threat_log_analyze",
                module=self.MODULE_NAME, error="log_text is required",
            )
        log_type = params.get("log_type", "auto")
        result = self._threat_intel.analyze_log_pattern(log_text, log_type)
        return ToolResult(
            success=True, content=result,
            tool_name="threat_log_analyze", module=self.MODULE_NAME,
        )

    def _threat_defense_profile(self, params: dict[str, Any]) -> ToolResult:
        """Build a defense profile for given threats."""
        threat_list = params.get("threat_list", [])
        if not threat_list:
            return ToolResult(
                success=False, content=None, tool_name="threat_defense_profile",
                module=self.MODULE_NAME, error="threat_list is required",
            )
        result = self._threat_intel.build_defense_profile(threat_list)
        return ToolResult(
            success="error" not in result, content=result,
            tool_name="threat_defense_profile", module=self.MODULE_NAME,
            error=result.get("error"),
        )

    def _threat_malware_study(self, params: dict[str, Any]) -> ToolResult:
        """Study a malware family for defensive understanding."""
        family_name = params.get("family_name", "")
        if not family_name:
            return ToolResult(
                success=False, content=None, tool_name="threat_malware_study",
                module=self.MODULE_NAME, error="family_name is required",
            )
        result = self._threat_intel.study_malware_family(family_name)
        return ToolResult(
            success="error" not in result, content=result,
            tool_name="threat_malware_study", module=self.MODULE_NAME,
            error=result.get("error"),
        )

    def _threat_detection_rule(self, params: dict[str, Any]) -> ToolResult:
        """Generate a detection rule for a threat."""
        threat_type = params.get("threat_type", "")
        if not threat_type:
            return ToolResult(
                success=False, content=None, tool_name="threat_detection_rule",
                module=self.MODULE_NAME, error="threat_type is required",
            )
        rule_format = params.get("rule_format", "suricata")
        result = self._threat_intel.generate_detection_rule(threat_type, rule_format)
        return ToolResult(
            success="error" not in result, content=result,
            tool_name="threat_detection_rule", module=self.MODULE_NAME,
            error=result.get("error"),
        )

    def _threat_shadow_assessment(self, params: dict[str, Any]) -> ToolResult:
        """Assess Shadow's threat surface."""
        result = self._threat_intel.assess_shadow_threat_surface()
        return ToolResult(
            success=True, content=result,
            tool_name="threat_shadow_assessment", module=self.MODULE_NAME,
        )

    def _threat_knowledge_store(self, params: dict[str, Any]) -> ToolResult:
        """Store threat intelligence in Grimoire."""
        knowledge = params.get("knowledge", {})
        source = params.get("source", "")
        if not knowledge or not source:
            return ToolResult(
                success=False, content=None, tool_name="threat_knowledge_store",
                module=self.MODULE_NAME, error="knowledge dict and source are required",
            )
        count = self._threat_intel.store_threat_knowledge(knowledge, source)
        return ToolResult(
            success=True, content={"stored_count": count},
            tool_name="threat_knowledge_store", module=self.MODULE_NAME,
        )

    # --- Internal helpers ---

    @staticmethod
    def _hash_file(path: Path) -> str:
        """Compute SHA-256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _load_baseline(self) -> None:
        """Load integrity baseline from disk."""
        if self._baseline_file.exists():
            try:
                with open(self._baseline_file, "r", encoding="utf-8") as f:
                    self._baseline = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._baseline = {}

    def _save_baseline(self) -> None:
        """Persist integrity baseline to disk."""
        self._baseline_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._baseline_file, "w", encoding="utf-8") as f:
                json.dump(self._baseline, f, indent=2)
        except OSError as e:
            logger.error("Failed to save baseline: %s", e)
