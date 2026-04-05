"""
Sentinel — White Hat Security Architecture
=============================================
Detection, analysis, and defensive response.

HARD CONSTRAINT: Sentinel defends only. Never retaliates, never
launches offensive attacks, never probes systems it does not own.
That is the permanent, non-negotiable line between white hat and illegal.

Phase 1: psutil-based network monitoring, file integrity hashing,
threat assessment stubs. No Suricata/Zeek yet (Ubuntu).
"""

import hashlib
import json
import logging
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from modules.base import BaseModule, ModuleStatus, ToolResult

logger = logging.getLogger("shadow.sentinel")


class Sentinel(BaseModule):
    """White hat security module. Detect, analyze, defend.

    All responses go through Cerberus. Sentinel proposes, Cerberus checks.
    Defense only — never retaliates or probes external systems.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize Sentinel.

        Args:
            config: Module configuration.
        """
        super().__init__(
            name="sentinel",
            description="White hat security — detection, analysis, defense",
        )
        self._config = config or {}
        self._baseline_file = Path(
            self._config.get("baseline_file", "data/sentinel_baseline.json")
        )
        self._quarantine_dir = Path(
            self._config.get("quarantine_dir", "data/research/quarantine")
        )
        self._baseline: dict[str, str] = {}
        self._alerts: list[dict[str, Any]] = []

    async def initialize(self) -> None:
        """Start Sentinel. Load file integrity baseline."""
        self.status = ModuleStatus.STARTING
        try:
            self._load_baseline()
            self._quarantine_dir.mkdir(parents=True, exist_ok=True)
            self.status = ModuleStatus.ONLINE
            logger.info(
                "Sentinel online. %d files in integrity baseline.",
                len(self._baseline),
            )
        except Exception as e:
            self.status = ModuleStatus.ERROR
            logger.error("Sentinel failed to initialize: %s", e)
            raise

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        """Execute a Sentinel tool."""
        start = time.time()
        try:
            handlers = {
                "network_scan": self._network_scan,
                "file_integrity_check": self._file_integrity_check,
                "breach_check": self._breach_check,
                "security_alert": self._security_alert,
                "threat_assess": self._threat_assess,
                "quarantine_file": self._quarantine_file,
            }

            handler = handlers.get(tool_name)
            if handler is None:
                result = ToolResult(
                    success=False, content=None, tool_name=tool_name,
                    module=self.name, error=f"Unknown tool: {tool_name}",
                )
            else:
                result = handler(params)

            result.execution_time_ms = (time.time() - start) * 1000
            self._record_call(result.success)
            return result

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            self._record_call(False)
            logger.error("Sentinel tool '%s' failed: %s", tool_name, e)
            return ToolResult(
                success=False, content=None, tool_name=tool_name,
                module=self.name, error=str(e), execution_time_ms=elapsed,
            )

    async def shutdown(self) -> None:
        """Shut down Sentinel. Save baseline."""
        self._save_baseline()
        self.status = ModuleStatus.OFFLINE
        logger.info("Sentinel offline.")

    def get_tools(self) -> list[dict[str, Any]]:
        """Return Sentinel's tool definitions."""
        return [
            {
                "name": "network_scan",
                "description": "Check current network connections and open ports",
                "parameters": {},
                "permission_level": "autonomous",
            },
            {
                "name": "file_integrity_check",
                "description": "Hash comparison on critical files against baseline",
                "parameters": {"file_paths": "list"},
                "permission_level": "autonomous",
            },
            {
                "name": "breach_check",
                "description": "Check email against known breaches (stub)",
                "parameters": {"email": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "security_alert",
                "description": "Generate a security alert for Harbinger",
                "parameters": {"message": "str", "severity": "str", "source": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "threat_assess",
                "description": "Assess threat level of an event",
                "parameters": {"event": "str", "indicators": "list"},
                "permission_level": "autonomous",
            },
            {
                "name": "quarantine_file",
                "description": "Move suspicious file to quarantine directory",
                "parameters": {"file_path": "str", "reason": "str"},
                "permission_level": "autonomous",
            },
        ]

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
                module=self.name, error="psutil not installed",
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
            module=self.name,
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
                module=self.name, error="file_paths list is required",
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
            module=self.name,
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
                success=False, content=None, tool_name="breach_check",
                module=self.name, error="Email address is required",
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
            module=self.name,
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
                module=self.name, error="Alert message is required",
            )

        severity = params.get("severity", "medium")
        valid_severities = ("low", "medium", "high", "critical")
        if severity not in valid_severities:
            return ToolResult(
                success=False, content=None, tool_name="security_alert",
                module=self.name,
                error=f"Severity must be one of: {', '.join(valid_severities)}",
            )

        alert = {
            "message": message,
            "severity": severity,
            "source": params.get("source", "sentinel"),
            "timestamp": datetime.now().isoformat(),
            "status": "active",
        }
        self._alerts.append(alert)
        logger.warning("SECURITY ALERT [%s]: %s", severity.upper(), message)

        return ToolResult(
            success=True,
            content=alert,
            tool_name="security_alert",
            module=self.name,
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
                module=self.name, error="Event description is required",
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
            module=self.name,
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
                module=self.name, error="file_path is required",
            )

        source = Path(file_path)
        if not source.exists():
            return ToolResult(
                success=False, content=None, tool_name="quarantine_file",
                module=self.name, error=f"File not found: {file_path}",
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
                module=self.name,
            )

        except OSError as e:
            return ToolResult(
                success=False, content=None, tool_name="quarantine_file",
                module=self.name, error=f"Failed to quarantine: {e}",
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
