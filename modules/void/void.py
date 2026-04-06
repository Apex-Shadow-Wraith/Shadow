"""
Void — 24/7 Passive Monitoring
================================
System health, trends, and alerts. Watches everything, acts on nothing.

Design Principle: Void detects and reports. When Void sees something
wrong, he sends the alert to the appropriate module. Void is the
sensor array, not the response team.

Phase 1: psutil-based health checks, SQLite metric storage, threshold
alerts, service watchdog, structured reports for Harbinger.
"""

import logging
import os
import sqlite3
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from modules.base import BaseModule, ModuleStatus, ToolResult

logger = logging.getLogger("shadow.void")


class Void(BaseModule):
    """24/7 passive monitoring. Detects and reports only.

    Void never takes corrective action. He watches system health,
    tracks trends, and escalates anomalies to Harbinger.
    """

    DEFAULT_THRESHOLDS = {
        "cpu_warning": 80.0,
        "cpu_critical": 95.0,
        "ram_warning": 85.0,
        "ram_critical": 95.0,
        "disk_warning": 90.0,
        "disk_critical": 95.0,
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
        self._db_path = Path(
            self._config.get("db_path", "data/void_metrics.db")
        )
        self._thresholds = dict(self.DEFAULT_THRESHOLDS)
        # Override defaults with any thresholds from config
        if "thresholds" in self._config:
            self._thresholds.update(self._config["thresholds"])
        self._conn: sqlite3.Connection | None = None

    async def initialize(self) -> None:
        """Start Void. Create DB and metrics table."""
        self.status = ModuleStatus.STARTING
        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS void_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL,
                    value REAL NOT NULL,
                    unit TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_metric_time
                ON void_metrics(metric_name, timestamp)
            """)
            self._conn.commit()
            self.status = ModuleStatus.ONLINE
            self._initialized_at = datetime.now()
            logger.info("Void online. Metrics DB at %s", self._db_path)
        except Exception as e:
            self.status = ModuleStatus.ERROR
            logger.error("Void failed to initialize: %s", e)
            raise

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        """Execute a Void tool."""
        start = time.time()
        try:
            handlers = {
                "system_snapshot": self._system_snapshot,
                "health_check": self._health_check,
                "metric_history": self._metric_history,
                "service_check": self._service_check,
                "set_threshold": self._set_threshold,
                "void_report": self._void_report,
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
        """Shut down Void. Close DB connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
        self.status = ModuleStatus.OFFLINE
        logger.info("Void offline. DB connection closed.")

    def get_tools(self) -> list[dict[str, Any]]:
        """Return Void's tool definitions."""
        return [
            {
                "name": "system_snapshot",
                "description": "Collect all system metrics (CPU, RAM, disk, GPU, process memory) and store to DB",
                "parameters": {},
                "permission_level": "autonomous",
            },
            {
                "name": "health_check",
                "description": "Compare current metrics against warning/critical thresholds",
                "parameters": {},
                "permission_level": "autonomous",
            },
            {
                "name": "metric_history",
                "description": "Query stored metrics by name and time range",
                "parameters": {
                    "metric_name": "str — metric to query (e.g., cpu_percent)",
                    "hours": "int — how many hours back to query (default 24)",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "service_check",
                "description": "Check if Ollama and Shadow process are healthy",
                "parameters": {},
                "permission_level": "autonomous",
            },
            {
                "name": "set_threshold",
                "description": "Update warning/critical thresholds for a metric",
                "parameters": {
                    "metric": "str — threshold key (e.g., cpu_warning, ram_critical)",
                    "value": "float — new threshold value (percent)",
                },
                "permission_level": "approval_required",
            },
            {
                "name": "void_report",
                "description": "Compile full system report with metrics, alerts, and history for Harbinger",
                "parameters": {},
                "permission_level": "autonomous",
            },
        ]

    # --- Tool implementations ---

    def _system_snapshot(self, params: dict[str, Any]) -> ToolResult:
        """Collect all system metrics and store to DB."""
        try:
            import psutil
        except ImportError:
            return ToolResult(
                success=False, content=None, tool_name="system_snapshot",
                module=self.name, error="psutil not installed",
            )

        now = datetime.now().isoformat()

        # CPU
        cpu = psutil.cpu_percent(interval=0.1)
        # RAM
        ram = psutil.virtual_memory()
        # Disk
        disk = psutil.disk_usage("/")
        # Python process memory
        process = psutil.Process(os.getpid())
        proc_mem = process.memory_info()
        proc_mem_mb = proc_mem.rss / (1024 ** 2)

        # GPU (graceful failure)
        gpu_data = self._query_gpu()

        # Store metrics to DB
        metrics = [
            ("cpu_percent", cpu, "percent", now),
            ("ram_percent", ram.percent, "percent", now),
            ("ram_used_gb", round(ram.used / (1024 ** 3), 2), "GB", now),
            ("disk_percent", disk.percent, "percent", now),
            ("disk_used_gb", round(disk.used / (1024 ** 3), 2), "GB", now),
            ("process_memory_mb", round(proc_mem_mb, 2), "MB", now),
        ]

        if gpu_data.get("available"):
            for i, gpu in enumerate(gpu_data["gpus"]):
                metrics.append((f"gpu_{i}_temp_c", gpu["temperature_c"], "celsius", now))
                metrics.append((f"gpu_{i}_util_percent", gpu["utilization_percent"], "percent", now))

        self._store_metrics(metrics)

        snapshot = {
            "cpu_percent": cpu,
            "ram_percent": ram.percent,
            "ram_total_gb": round(ram.total / (1024 ** 3), 2),
            "ram_used_gb": round(ram.used / (1024 ** 3), 2),
            "disk_percent": disk.percent,
            "disk_total_gb": round(disk.total / (1024 ** 3), 2),
            "disk_used_gb": round(disk.used / (1024 ** 3), 2),
            "process_memory_mb": round(proc_mem_mb, 2),
            "gpu": gpu_data,
            "timestamp": now,
        }

        return ToolResult(
            success=True, content=snapshot,
            tool_name="system_snapshot", module=self.name,
        )

    def _health_check(self, params: dict[str, Any]) -> ToolResult:
        """Compare current metrics against thresholds."""
        try:
            import psutil
        except ImportError:
            return ToolResult(
                success=False, content=None, tool_name="health_check",
                module=self.name, error="psutil not installed",
            )

        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        alerts = []
        checks = [
            ("cpu", cpu, self._thresholds["cpu_warning"], self._thresholds["cpu_critical"]),
            ("ram", ram.percent, self._thresholds["ram_warning"], self._thresholds["ram_critical"]),
            ("disk", disk.percent, self._thresholds["disk_warning"], self._thresholds["disk_critical"]),
        ]

        for metric, value, warning, critical in checks:
            if value >= critical:
                alerts.append({
                    "metric": metric,
                    "value": value,
                    "threshold": critical,
                    "severity": "critical",
                })
            elif value >= warning:
                alerts.append({
                    "metric": metric,
                    "value": value,
                    "threshold": warning,
                    "severity": "warning",
                })

        status = "healthy"
        if any(a["severity"] == "critical" for a in alerts):
            status = "critical"
        elif alerts:
            status = "warning"

        return ToolResult(
            success=True,
            content={
                "status": status,
                "alerts": alerts,
                "current": {
                    "cpu_percent": cpu,
                    "ram_percent": ram.percent,
                    "disk_percent": disk.percent,
                },
                "thresholds": dict(self._thresholds),
                "timestamp": datetime.now().isoformat(),
            },
            tool_name="health_check", module=self.name,
        )

    def _metric_history(self, params: dict[str, Any]) -> ToolResult:
        """Query stored metrics by name and time range."""
        metric_name = params.get("metric_name")
        if not metric_name:
            return ToolResult(
                success=False, content=None, tool_name="metric_history",
                module=self.name, error="metric_name is required",
            )

        hours = params.get("hours", 24)
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

        if not self._conn:
            return ToolResult(
                success=False, content=None, tool_name="metric_history",
                module=self.name, error="Database not connected",
            )

        rows = self._conn.execute(
            """SELECT timestamp, value FROM void_metrics
               WHERE metric_name = ? AND timestamp >= ?
               ORDER BY timestamp ASC""",
            (metric_name, cutoff),
        ).fetchall()

        history = [{"timestamp": row["timestamp"], "value": row["value"]} for row in rows]

        return ToolResult(
            success=True,
            content={
                "metric_name": metric_name,
                "hours": hours,
                "data_points": len(history),
                "history": history,
            },
            tool_name="metric_history", module=self.name,
        )

    def _service_check(self, params: dict[str, Any]) -> ToolResult:
        """Check if key services are running."""
        services = {}

        # Check Ollama
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True, text=True, timeout=5,
            )
            services["ollama"] = {
                "running": result.returncode == 0,
                "detail": "responding" if result.returncode == 0 else "error",
            }
        except FileNotFoundError:
            services["ollama"] = {"running": False, "detail": "not installed"}
        except subprocess.TimeoutExpired:
            services["ollama"] = {"running": False, "detail": "timed out"}

        # Check Shadow process health
        try:
            import psutil
            process = psutil.Process(os.getpid())
            proc_mem = process.memory_info()
            services["shadow_process"] = {
                "running": True,
                "detail": "healthy",
                "pid": os.getpid(),
                "memory_mb": round(proc_mem.rss / (1024 ** 2), 2),
            }
        except ImportError:
            services["shadow_process"] = {
                "running": True,
                "detail": "psutil unavailable — limited info",
                "pid": os.getpid(),
            }
        except Exception as e:
            services["shadow_process"] = {
                "running": True,
                "detail": f"error reading process info: {e}",
                "pid": os.getpid(),
            }

        return ToolResult(
            success=True,
            content={
                "services": services,
                "checked_at": datetime.now().isoformat(),
            },
            tool_name="service_check", module=self.name,
        )

    def _set_threshold(self, params: dict[str, Any]) -> ToolResult:
        """Update a threshold value."""
        metric = params.get("metric")
        value = params.get("value")

        if not metric or value is None:
            return ToolResult(
                success=False, content=None, tool_name="set_threshold",
                module=self.name, error="Both 'metric' and 'value' are required",
            )

        if metric not in self._thresholds:
            valid_keys = ", ".join(sorted(self._thresholds.keys()))
            return ToolResult(
                success=False, content=None, tool_name="set_threshold",
                module=self.name,
                error=f"Unknown threshold '{metric}'. Valid keys: {valid_keys}",
            )

        try:
            value = float(value)
        except (TypeError, ValueError):
            return ToolResult(
                success=False, content=None, tool_name="set_threshold",
                module=self.name, error=f"Value must be a number, got: {value}",
            )

        old_value = self._thresholds[metric]
        self._thresholds[metric] = value

        return ToolResult(
            success=True,
            content={
                "metric": metric,
                "old_value": old_value,
                "new_value": value,
                "thresholds": dict(self._thresholds),
            },
            tool_name="set_threshold", module=self.name,
        )

    def _void_report(self, params: dict[str, Any]) -> ToolResult:
        """Compile full system report for Harbinger."""
        # Get current health check
        health = self._health_check({})
        if not health.success:
            return ToolResult(
                success=False, content=None, tool_name="void_report",
                module=self.name, error=f"Health check failed: {health.error}",
            )

        # Get snapshot
        snapshot = self._system_snapshot({})

        # Count stored metrics
        metric_count = 0
        if self._conn:
            row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM void_metrics"
            ).fetchone()
            metric_count = row["cnt"] if row else 0

        report = {
            "generated_at": datetime.now().isoformat(),
            "system_status": health.content["status"],
            "alerts": health.content["alerts"],
            "snapshot": snapshot.content if snapshot.success else {"error": snapshot.error},
            "stored_metrics_count": metric_count,
            "thresholds": dict(self._thresholds),
        }

        return ToolResult(
            success=True, content=report,
            tool_name="void_report", module=self.name,
        )

    # --- Internal helpers ---

    def _query_gpu(self) -> dict[str, Any]:
        """Query GPU status via nvidia-smi. Graceful failure if unavailable."""
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
                return {"available": False, "reason": "nvidia-smi returned error"}

            gpus = []
            for line in result.stdout.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 5:
                    gpus.append({
                        "name": parts[0],
                        "temperature_c": float(parts[1]),
                        "utilization_percent": float(parts[2]),
                        "memory_used_mb": float(parts[3]),
                        "memory_total_mb": float(parts[4]),
                    })

            return {"available": True, "gpus": gpus}

        except FileNotFoundError:
            return {"available": False, "reason": "nvidia-smi not found"}
        except subprocess.TimeoutExpired:
            return {"available": False, "reason": "nvidia-smi timed out"}

    def _store_metrics(self, metrics: list[tuple[str, float, str, str]]) -> None:
        """Store a batch of metrics to the DB."""
        if not self._conn:
            logger.warning("Cannot store metrics — DB not connected")
            return
        self._conn.executemany(
            "INSERT INTO void_metrics (metric_name, value, unit, timestamp) VALUES (?, ?, ?, ?)",
            metrics,
        )
        self._conn.commit()
