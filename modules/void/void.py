"""
Void — 24/7 Passive Monitoring
================================
System health, trends, and alerts. Watches everything, acts on nothing.

Design Principle: Void detects and reports. When Void sees something
wrong, he sends the alert to the appropriate module. Void is the
sensor array, not the response team.

Phase 1: psutil-based health checks, trend snapshots, service
watchdog, alert thresholds.
"""

import json
import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from modules.base import BaseModule, ModuleStatus, ToolResult

logger = logging.getLogger("shadow.void")


class Void(BaseModule):
    """24/7 passive monitoring. Detects and reports only.

    Void never takes corrective action. He watches system health,
    tracks trends, and escalates anomalies to Harbinger.
    """

    # Alert thresholds (percent)
    THRESHOLDS = {
        "cpu_percent": 90.0,
        "ram_percent": 85.0,
        "disk_percent": 90.0,
        "gpu_temp_c": 80.0,
    }

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize Void.

        Args:
            config: Module configuration.
        """
        super().__init__(
            name="void",
            description="24/7 passive monitoring — system health, trends, alerts",
        )
        self._config = config or {}
        self._trends_file = Path(
            self._config.get("trends_file", "data/void_trends.json")
        )
        self._trends: list[dict[str, Any]] = []

    async def initialize(self) -> None:
        """Start Void."""
        self.status = ModuleStatus.STARTING
        try:
            self._load_trends()
            self.status = ModuleStatus.ONLINE
            logger.info("Void online. %d trend snapshots loaded.", len(self._trends))
        except Exception as e:
            self.status = ModuleStatus.ERROR
            logger.error("Void failed to initialize: %s", e)
            raise

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        """Execute a Void tool."""
        start = time.time()
        try:
            handlers = {
                "system_health": self._system_health,
                "gpu_status": self._gpu_status,
                "process_list": self._process_list,
                "service_status": self._service_status,
                "disk_usage": self._disk_usage,
                "backup_status": self._backup_status,
                "trend_snapshot": self._trend_snapshot,
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
            logger.error("Void tool '%s' failed: %s", tool_name, e)
            return ToolResult(
                success=False, content=None, tool_name=tool_name,
                module=self.name, error=str(e), execution_time_ms=elapsed,
            )

    async def shutdown(self) -> None:
        """Shut down Void. Save trends."""
        self._save_trends()
        self.status = ModuleStatus.OFFLINE
        logger.info("Void offline. Trends saved.")

    def get_tools(self) -> list[dict[str, Any]]:
        """Return Void's tool definitions."""
        return [
            {
                "name": "system_health",
                "description": "Get CPU/RAM/disk/network stats",
                "parameters": {},
                "permission_level": "autonomous",
            },
            {
                "name": "gpu_status",
                "description": "GPU utilization and temperature",
                "parameters": {},
                "permission_level": "autonomous",
            },
            {
                "name": "process_list",
                "description": "Running processes with resource usage",
                "parameters": {"top_n": "int"},
                "permission_level": "autonomous",
            },
            {
                "name": "service_status",
                "description": "Check if specific services are running",
                "parameters": {"services": "list"},
                "permission_level": "autonomous",
            },
            {
                "name": "disk_usage",
                "description": "Storage usage across all drives",
                "parameters": {},
                "permission_level": "autonomous",
            },
            {
                "name": "backup_status",
                "description": "Check backup integrity and recency",
                "parameters": {"backup_dir": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "trend_snapshot",
                "description": "Save current metrics for trend tracking",
                "parameters": {},
                "permission_level": "autonomous",
            },
        ]

    # --- Tool implementations ---

    def _system_health(self, params: dict[str, Any]) -> ToolResult:
        """Get overall system health metrics."""
        try:
            import psutil
        except ImportError:
            return ToolResult(
                success=False, content=None, tool_name="system_health",
                module=self.name, error="psutil not installed",
            )

        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        alerts = []
        if cpu > self.THRESHOLDS["cpu_percent"]:
            alerts.append(f"CPU at {cpu}% (threshold: {self.THRESHOLDS['cpu_percent']}%)")
        if ram.percent > self.THRESHOLDS["ram_percent"]:
            alerts.append(f"RAM at {ram.percent}% (threshold: {self.THRESHOLDS['ram_percent']}%)")
        if disk.percent > self.THRESHOLDS["disk_percent"]:
            alerts.append(f"Disk at {disk.percent}% (threshold: {self.THRESHOLDS['disk_percent']}%)")

        return ToolResult(
            success=True,
            content={
                "cpu_percent": cpu,
                "ram_total_gb": round(ram.total / (1024**3), 2),
                "ram_used_gb": round(ram.used / (1024**3), 2),
                "ram_percent": ram.percent,
                "disk_total_gb": round(disk.total / (1024**3), 2),
                "disk_used_gb": round(disk.used / (1024**3), 2),
                "disk_percent": disk.percent,
                "alerts": alerts,
                "timestamp": datetime.now().isoformat(),
            },
            tool_name="system_health",
            module=self.name,
        )

    def _gpu_status(self, params: dict[str, Any]) -> ToolResult:
        """Get GPU status via nvidia-smi.

        Gracefully handles absence of GPU or nvidia-smi.
        """
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True, text=True, timeout=10,
            )

            if result.returncode != 0:
                return ToolResult(
                    success=True,
                    content={"available": False, "reason": "nvidia-smi returned error"},
                    tool_name="gpu_status",
                    module=self.name,
                )

            gpus = []
            for line in result.stdout.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 5:
                    temp = float(parts[1])
                    alerts = []
                    if temp > self.THRESHOLDS["gpu_temp_c"]:
                        alerts.append(f"GPU temp {temp}C exceeds threshold")
                    gpus.append({
                        "name": parts[0],
                        "temperature_c": temp,
                        "utilization_percent": float(parts[2]),
                        "memory_used_mb": float(parts[3]),
                        "memory_total_mb": float(parts[4]),
                        "alerts": alerts,
                    })

            return ToolResult(
                success=True,
                content={"available": True, "gpus": gpus},
                tool_name="gpu_status",
                module=self.name,
            )

        except FileNotFoundError:
            return ToolResult(
                success=True,
                content={"available": False, "reason": "nvidia-smi not found"},
                tool_name="gpu_status",
                module=self.name,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=True,
                content={"available": False, "reason": "nvidia-smi timed out"},
                tool_name="gpu_status",
                module=self.name,
            )

    def _process_list(self, params: dict[str, Any]) -> ToolResult:
        """List top processes by CPU usage."""
        try:
            import psutil
        except ImportError:
            return ToolResult(
                success=False, content=None, tool_name="process_list",
                module=self.name, error="psutil not installed",
            )

        top_n = params.get("top_n", 10)
        processes = []

        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                info = proc.info
                processes.append({
                    "pid": info["pid"],
                    "name": info["name"],
                    "cpu_percent": info["cpu_percent"] or 0.0,
                    "memory_percent": round(info["memory_percent"] or 0.0, 2),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        processes.sort(key=lambda p: p["cpu_percent"], reverse=True)

        return ToolResult(
            success=True,
            content={"processes": processes[:top_n], "total": len(processes)},
            tool_name="process_list",
            module=self.name,
        )

    def _service_status(self, params: dict[str, Any]) -> ToolResult:
        """Check if specific services are running.

        Args:
            params: 'services' (list of process names to check).
        """
        try:
            import psutil
        except ImportError:
            return ToolResult(
                success=False, content=None, tool_name="service_status",
                module=self.name, error="psutil not installed",
            )

        services = params.get("services", ["ollama", "docker"])
        running_names = set()
        for proc in psutil.process_iter(["name"]):
            try:
                running_names.add(proc.info["name"].lower())
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        results = {}
        for svc in services:
            results[svc] = any(svc.lower() in name for name in running_names)

        return ToolResult(
            success=True,
            content={"services": results, "checked_at": datetime.now().isoformat()},
            tool_name="service_status",
            module=self.name,
        )

    def _disk_usage(self, params: dict[str, Any]) -> ToolResult:
        """Get disk usage for all mounted partitions."""
        try:
            import psutil
        except ImportError:
            return ToolResult(
                success=False, content=None, tool_name="disk_usage",
                module=self.name, error="psutil not installed",
            )

        partitions = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                partitions.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "total_gb": round(usage.total / (1024**3), 2),
                    "used_gb": round(usage.used / (1024**3), 2),
                    "free_gb": round(usage.free / (1024**3), 2),
                    "percent": usage.percent,
                })
            except (PermissionError, OSError):
                continue

        return ToolResult(
            success=True,
            content={"partitions": partitions, "count": len(partitions)},
            tool_name="disk_usage",
            module=self.name,
        )

    def _backup_status(self, params: dict[str, Any]) -> ToolResult:
        """Check backup directory for recency and integrity.

        Args:
            params: 'backup_dir' (str) — path to backup directory.
        """
        backup_dir = Path(params.get("backup_dir", "data/backups"))

        if not backup_dir.exists():
            return ToolResult(
                success=True,
                content={
                    "exists": False,
                    "message": f"Backup directory not found: {backup_dir}",
                },
                tool_name="backup_status",
                module=self.name,
            )

        files = sorted(backup_dir.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
        backup_files = [f for f in files if f.is_file()]

        latest = None
        if backup_files:
            newest = backup_files[0]
            latest = {
                "name": newest.name,
                "size_mb": round(newest.stat().st_size / (1024**2), 2),
                "modified": datetime.fromtimestamp(newest.stat().st_mtime).isoformat(),
            }

        return ToolResult(
            success=True,
            content={
                "exists": True,
                "file_count": len(backup_files),
                "latest": latest,
                "directory": str(backup_dir),
            },
            tool_name="backup_status",
            module=self.name,
        )

    def _trend_snapshot(self, params: dict[str, Any]) -> ToolResult:
        """Save current system metrics for trend tracking."""
        try:
            import psutil
        except ImportError:
            return ToolResult(
                success=False, content=None, tool_name="trend_snapshot",
                module=self.name, error="psutil not installed",
            )

        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "ram_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent,
        }

        self._trends.append(snapshot)
        # Keep last 1440 snapshots (1 per minute = 24 hours)
        if len(self._trends) > 1440:
            self._trends = self._trends[-1440:]
        self._save_trends()

        return ToolResult(
            success=True,
            content={
                "snapshot": snapshot,
                "total_snapshots": len(self._trends),
            },
            tool_name="trend_snapshot",
            module=self.name,
        )

    # --- Internal helpers ---

    def _load_trends(self) -> None:
        """Load trend data from disk."""
        if self._trends_file.exists():
            try:
                with open(self._trends_file, "r", encoding="utf-8") as f:
                    self._trends = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._trends = []

    def _save_trends(self) -> None:
        """Persist trend data to disk."""
        self._trends_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._trends_file, "w", encoding="utf-8") as f:
                json.dump(self._trends, f)
        except OSError as e:
            logger.error("Failed to save trends: %s", e)
