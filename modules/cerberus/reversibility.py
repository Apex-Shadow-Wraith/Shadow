"""
Reversibility Engine — Pre-Action Snapshots
=============================================
Before Shadow modifies anything, Cerberus takes a snapshot.
If something goes wrong, we can roll back. Every snapshot is
tracked in SQLite with its risk level and action context.

Supports four action types:
- file: Full copy before modification, automatic rollback
- config: JSON state dump, automatic rollback
- database: Transaction log of affected rows, automatic rollback
- external: Record-only (emails, notifications cannot be undone)
"""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger("shadow.cerberus.reversibility")


class ReversibilityEngine:
    """Manages pre-action snapshots for rollback capability.

    Every file modification, config change, or database write gets
    snapshotted before execution. Snapshots are tracked in SQLite
    with status tracking and metadata.
    """

    SNAPSHOTS_DDL = """\
    CREATE TABLE IF NOT EXISTS snapshots (
        snapshot_id         TEXT PRIMARY KEY,
        timestamp           TEXT NOT NULL,
        action_type         TEXT NOT NULL,
        target              TEXT NOT NULL,
        original_state_path TEXT,
        metadata            TEXT,
        status              TEXT NOT NULL DEFAULT 'active',
        risk_level          TEXT NOT NULL DEFAULT 'low'
    )
    """

    def __init__(
        self,
        snapshot_dir: Path | None = None,
        db_path: Path | None = None,
    ) -> None:
        self._snapshot_dir = snapshot_dir or Path("C:/Shadow/data/snapshots")
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)

        self._db_path = db_path or (self._snapshot_dir / "cerberus_snapshots.db")
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.row_factory = sqlite3.Row
        self._init_db()

        logger.info("ReversibilityEngine initialized. Dir: %s", self._snapshot_dir)

    def _init_db(self) -> None:
        """Create the snapshots tracking table if it doesn't exist."""
        self._conn.execute(self.SNAPSHOTS_DDL)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_snapshots_action_type "
            "ON snapshots(action_type)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_snapshots_status "
            "ON snapshots(status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp "
            "ON snapshots(timestamp)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Unified entry point
    # ------------------------------------------------------------------

    def snapshot_before_action(
        self,
        action_type: str,
        target_path_or_key: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Take a snapshot before any write operation.

        Args:
            action_type: One of 'file', 'config', 'database', 'external'.
            target_path_or_key: File path, config key, db table, or description.
            metadata: Optional dict with extra context (risk_level, db_path,
                      where_clause, content sent, etc.).

        Returns:
            snapshot_id (uuid hex) for later rollback.

        Raises:
            FileNotFoundError: If action_type is 'file' and target doesn't exist.
            ValueError: If action_type is unknown.
        """
        metadata = metadata or {}
        risk_level = metadata.get("risk_level", "low")

        if action_type == "file":
            return self._snapshot_file(target_path_or_key, metadata, risk_level)
        elif action_type == "config":
            return self._snapshot_config(target_path_or_key, metadata, risk_level)
        elif action_type == "database":
            return self._snapshot_database(target_path_or_key, metadata, risk_level)
        elif action_type == "external":
            return self._snapshot_external(target_path_or_key, metadata, risk_level)
        else:
            raise ValueError(f"Unknown action_type: {action_type}")

    # ------------------------------------------------------------------
    # Snapshot implementations
    # ------------------------------------------------------------------

    def _snapshot_file(
        self, target: str, metadata: dict[str, Any], risk_level: str
    ) -> str:
        """Copy a file before modification."""
        filepath = Path(target)
        if not filepath.exists():
            raise FileNotFoundError(f"Cannot snapshot missing file: {filepath}")

        snapshot_id = uuid.uuid4().hex
        dest_dir = self._snapshot_dir / snapshot_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / filepath.name
        shutil.copy2(filepath, dest)

        self._record_snapshot(
            snapshot_id=snapshot_id,
            action_type="file",
            target=str(filepath),
            original_state_path=str(dest),
            metadata=metadata,
            risk_level=risk_level,
        )
        logger.info("File snapshot %s: %s", snapshot_id[:8], filepath)
        return snapshot_id

    def _snapshot_config(
        self, config_key: str, metadata: dict[str, Any], risk_level: str
    ) -> str:
        """Save config state as JSON before modification."""
        snapshot_id = uuid.uuid4().hex
        dest_dir = self._snapshot_dir / snapshot_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / "config_state.json"

        config_state = metadata.get("config_state", {})
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(config_state, f, indent=2, default=str)

        self._record_snapshot(
            snapshot_id=snapshot_id,
            action_type="config",
            target=config_key,
            original_state_path=str(dest),
            metadata=metadata,
            risk_level=risk_level,
        )
        logger.info("Config snapshot %s: %s", snapshot_id[:8], config_key)
        return snapshot_id

    def _snapshot_database(
        self, target: str, metadata: dict[str, Any], risk_level: str
    ) -> str:
        """Save affected database rows before modification.

        Metadata must include 'db_path', 'table', and 'where_clause'.
        """
        snapshot_id = uuid.uuid4().hex
        dest_dir = self._snapshot_dir / snapshot_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / "db_transaction_log.json"

        db_path = metadata.get("db_path", "")
        table = metadata.get("table", target)
        where_clause = metadata.get("where_clause", "1=1")

        rows: list[dict[str, Any]] = []
        if db_path and Path(db_path).exists():
            target_conn = sqlite3.connect(str(db_path))
            target_conn.row_factory = sqlite3.Row
            try:
                cursor = target_conn.execute(
                    f"SELECT * FROM {table} WHERE {where_clause}"
                )
                rows = [dict(row) for row in cursor.fetchall()]
            finally:
                target_conn.close()

        transaction_log = {
            "table": table,
            "where_clause": where_clause,
            "db_path": str(db_path),
            "rows": rows,
            "row_count": len(rows),
        }
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(transaction_log, f, indent=2, default=str)

        self._record_snapshot(
            snapshot_id=snapshot_id,
            action_type="database",
            target=f"{db_path}:{table}",
            original_state_path=str(dest),
            metadata=metadata,
            risk_level=risk_level,
        )
        logger.info(
            "DB snapshot %s: %s.%s (%d rows)",
            snapshot_id[:8], db_path, table, len(rows),
        )
        return snapshot_id

    def _snapshot_external(
        self, target: str, metadata: dict[str, Any], risk_level: str
    ) -> str:
        """Record an external action (cannot undo, stored for reference).

        Used for emails, notifications, API calls, etc.
        """
        snapshot_id = uuid.uuid4().hex
        dest_dir = self._snapshot_dir / snapshot_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / "external_record.json"

        record = {
            "target": target,
            "action_details": metadata.get("action_details", {}),
            "content_sent": metadata.get("content_sent", ""),
            "recipients": metadata.get("recipients", []),
            "note": "External action — cannot be reversed. Stored for reference.",
        }
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, default=str)

        self._record_snapshot(
            snapshot_id=snapshot_id,
            action_type="external",
            target=target,
            original_state_path=str(dest),
            metadata=metadata,
            risk_level=risk_level,
        )
        logger.info("External snapshot %s: %s (record-only)", snapshot_id[:8], target)
        return snapshot_id

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    def rollback(self, snapshot_id: str) -> bool:
        """Restore from a snapshot.

        - file: copies snapshot back to original location
        - config: restores previous config JSON to original path
        - database: re-inserts saved rows into the original table
        - external: returns False (cannot reverse external actions)

        Args:
            snapshot_id: The snapshot to restore.

        Returns:
            True if rollback succeeded, False otherwise.
        """
        row = self._conn.execute(
            "SELECT * FROM snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()

        if row is None:
            logger.error("Rollback failed: snapshot %s not found", snapshot_id)
            return False

        if row["status"] == "rolled_back":
            logger.warning("Snapshot %s already rolled back", snapshot_id[:8])
            return False

        action_type = row["action_type"]
        target = row["target"]
        state_path = Path(row["original_state_path"])

        if not state_path.exists():
            logger.error("Rollback failed: snapshot data missing at %s", state_path)
            return False

        success = False

        if action_type == "file":
            target_path = Path(target)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(state_path, target_path)
            logger.info("Rolled back file: %s from snapshot %s", target, snapshot_id[:8])
            success = True

        elif action_type == "config":
            # Restore config state — write JSON back to the config target path
            with open(state_path, "r", encoding="utf-8") as f:
                config_state = json.load(f)
            # If target is a file path, write it back
            target_path = Path(target)
            if target_path.suffix in (".json", ".yaml", ".yml"):
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with open(target_path, "w", encoding="utf-8") as f:
                    json.dump(config_state, f, indent=2, default=str)
                logger.info("Rolled back config: %s", target)
                success = True
            else:
                # Target is a key name — caller must handle restoration
                logger.info(
                    "Config snapshot %s restored to memory. "
                    "Caller should apply state from: %s",
                    snapshot_id[:8], state_path,
                )
                success = True

        elif action_type == "database":
            with open(state_path, "r", encoding="utf-8") as f:
                transaction_log = json.load(f)
            db_path = transaction_log.get("db_path", "")
            table = transaction_log.get("table", "")
            rows = transaction_log.get("rows", [])
            if db_path and table and rows:
                try:
                    target_conn = sqlite3.connect(str(db_path))
                    try:
                        for row_data in rows:
                            columns = ", ".join(row_data.keys())
                            placeholders = ", ".join(["?"] * len(row_data))
                            target_conn.execute(
                                f"INSERT OR REPLACE INTO {table} ({columns}) "
                                f"VALUES ({placeholders})",
                                list(row_data.values()),
                            )
                        target_conn.commit()
                    finally:
                        target_conn.close()
                    logger.info(
                        "Rolled back DB: %s.%s (%d rows)",
                        db_path, table, len(rows),
                    )
                    success = True
                except Exception as e:
                    logger.error("DB rollback failed: %s", e)
                    success = False
            else:
                logger.warning("DB rollback: no rows to restore for %s", snapshot_id[:8])
                success = True

        elif action_type == "external":
            logger.warning(
                "Cannot rollback external action %s: %s. "
                "Record preserved at: %s",
                snapshot_id[:8], target, state_path,
            )
            return False

        if success:
            self._conn.execute(
                "UPDATE snapshots SET status = 'rolled_back' WHERE snapshot_id = ?",
                (snapshot_id,),
            )
            self._conn.commit()

        return success

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def list_snapshots(
        self,
        limit: int = 20,
        action_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """List snapshot metadata, newest first.

        Args:
            limit: Max number of snapshots to return.
            action_type: Filter by action type (file/config/database/external).

        Returns:
            List of snapshot metadata dicts.
        """
        if action_type:
            rows = self._conn.execute(
                "SELECT * FROM snapshots WHERE action_type = ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (action_type, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM snapshots ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()

        return [
            {
                "snapshot_id": row["snapshot_id"],
                "timestamp": row["timestamp"],
                "action_type": row["action_type"],
                "target": row["target"],
                "original_state_path": row["original_state_path"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                "status": row["status"],
                "risk_level": row["risk_level"],
            }
            for row in rows
        ]

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        """Get a single snapshot's metadata."""
        row = self._conn.execute(
            "SELECT * FROM snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "snapshot_id": row["snapshot_id"],
            "timestamp": row["timestamp"],
            "action_type": row["action_type"],
            "target": row["target"],
            "original_state_path": row["original_state_path"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            "status": row["status"],
            "risk_level": row["risk_level"],
        }

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup_expired(
        self,
        retention_days: int = 30,
        keep_high_risk: bool = True,
    ) -> int:
        """Delete snapshots older than retention_days.

        Args:
            retention_days: Delete snapshots older than this.
            keep_high_risk: If True, never delete high/critical risk snapshots.

        Returns:
            Number of snapshots deleted.
        """
        cutoff = (datetime.now() - timedelta(days=retention_days)).isoformat()
        protected_levels = {"high", "critical"} if keep_high_risk else set()

        rows = self._conn.execute(
            "SELECT snapshot_id, original_state_path, risk_level "
            "FROM snapshots WHERE timestamp < ?",
            (cutoff,),
        ).fetchall()

        deleted = 0
        for row in rows:
            if row["risk_level"] in protected_levels:
                continue

            # Delete the snapshot directory
            state_path = Path(row["original_state_path"])
            snapshot_dir = state_path.parent
            if snapshot_dir.exists() and snapshot_dir.parent == self._snapshot_dir:
                shutil.rmtree(snapshot_dir, ignore_errors=True)
            elif state_path.exists():
                state_path.unlink()

            # Mark as expired then delete record
            self._conn.execute(
                "DELETE FROM snapshots WHERE snapshot_id = ?",
                (row["snapshot_id"],),
            )
            deleted += 1

        self._conn.commit()
        logger.info("Cleanup: deleted %d snapshots (cutoff: %s)", deleted, cutoff)
        return deleted

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _record_snapshot(
        self,
        snapshot_id: str,
        action_type: str,
        target: str,
        original_state_path: str,
        metadata: dict[str, Any],
        risk_level: str,
    ) -> None:
        """Insert a snapshot record into the tracking database."""
        self._conn.execute(
            "INSERT INTO snapshots "
            "(snapshot_id, timestamp, action_type, target, original_state_path, "
            "metadata, status, risk_level) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                snapshot_id,
                datetime.now().isoformat(),
                action_type,
                target,
                original_state_path,
                json.dumps(metadata, default=str),
                "active",
                risk_level,
            ),
        )
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
