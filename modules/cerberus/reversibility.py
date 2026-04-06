"""
Reversibility Engine — Pre-Action Snapshots
=============================================
Before Shadow modifies anything, Cerberus takes a snapshot.
If something goes wrong, we can roll back. Every snapshot is
tracked in SQLite with its risk level and action context.

Phase 1: file snapshots with full rollback. Config and DB
snapshots are stored but rollback is manual (Phase 2).
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

import yaml

logger = logging.getLogger("shadow.cerberus.reversibility")


class ReversibilityEngine:
    """Manages pre-action snapshots for rollback capability.

    Every file modification, config change, or database write gets
    snapshotted before execution. Snapshots are tracked in SQLite
    with risk levels from Cerberus classification.
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
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS cerberus_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                target TEXT NOT NULL,
                action_id TEXT NOT NULL,
                risk_level TEXT NOT NULL DEFAULT 'low',
                created_at TEXT NOT NULL,
                data_path TEXT NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_snapshots_action_id "
            "ON cerberus_snapshots(action_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_snapshots_type "
            "ON cerberus_snapshots(type)"
        )
        self._conn.commit()

    def snapshot_file(
        self,
        filepath: Path,
        action_id: str,
        risk_level: str = "low",
    ) -> str:
        """Copy a file before modification.

        Args:
            filepath: Path to the file to snapshot.
            action_id: Identifier for the action triggering this snapshot.
            risk_level: Risk classification from Cerberus.

        Returns:
            snapshot_id for later rollback.

        Raises:
            FileNotFoundError: If the source file doesn't exist.
        """
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"Cannot snapshot missing file: {filepath}")

        snapshot_id = uuid.uuid4().hex
        dest = self._snapshot_dir / f"{snapshot_id}{filepath.suffix}"
        shutil.copy2(filepath, dest)

        self._record_snapshot(
            snapshot_id=snapshot_id,
            snapshot_type="file",
            target=str(filepath),
            action_id=action_id,
            risk_level=risk_level,
            data_path=str(dest),
        )
        logger.info("File snapshot %s: %s", snapshot_id[:8], filepath)
        return snapshot_id

    def snapshot_config(
        self,
        config_key: str,
        current_value: dict[str, Any],
        action_id: str,
        risk_level: str = "medium",
    ) -> str:
        """Save a config value before modification.

        Args:
            config_key: Identifier for the config being changed.
            current_value: Current config dict to preserve.
            action_id: Identifier for the action triggering this snapshot.
            risk_level: Risk classification from Cerberus.

        Returns:
            snapshot_id for later rollback.
        """
        snapshot_id = uuid.uuid4().hex
        dest = self._snapshot_dir / f"{snapshot_id}.yaml"

        with open(dest, "w", encoding="utf-8") as f:
            yaml.dump(current_value, f, default_flow_style=False)

        self._record_snapshot(
            snapshot_id=snapshot_id,
            snapshot_type="config",
            target=config_key,
            action_id=action_id,
            risk_level=risk_level,
            data_path=str(dest),
        )
        logger.info("Config snapshot %s: %s", snapshot_id[:8], config_key)
        return snapshot_id

    def snapshot_db(
        self,
        table: str,
        where_clause: str,
        db_path: Path,
        action_id: str,
        risk_level: str = "medium",
    ) -> str:
        """Save affected database rows before modification.

        Args:
            table: Table name to snapshot rows from.
            where_clause: SQL WHERE clause to select affected rows.
            db_path: Path to the database file.
            action_id: Identifier for the action triggering this snapshot.
            risk_level: Risk classification from Cerberus.

        Returns:
            snapshot_id for later rollback.
        """
        snapshot_id = uuid.uuid4().hex
        dest = self._snapshot_dir / f"{snapshot_id}.json"

        # Connect to the target database and extract rows
        target_conn = sqlite3.connect(str(db_path))
        target_conn.row_factory = sqlite3.Row
        try:
            cursor = target_conn.execute(
                f"SELECT * FROM {table} WHERE {where_clause}"
            )
            rows = [dict(row) for row in cursor.fetchall()]
        finally:
            target_conn.close()

        with open(dest, "w", encoding="utf-8") as f:
            json.dump({"table": table, "where": where_clause, "rows": rows}, f, indent=2)

        self._record_snapshot(
            snapshot_id=snapshot_id,
            snapshot_type="db",
            target=f"{db_path}:{table}",
            action_id=action_id,
            risk_level=risk_level,
            data_path=str(dest),
        )
        logger.info("DB snapshot %s: %s.%s (%d rows)", snapshot_id[:8], db_path, table, len(rows))
        return snapshot_id

    def rollback(self, snapshot_id: str) -> bool:
        """Restore from a snapshot.

        Phase 1: Only file snapshots support automatic rollback.
        Config and DB rollback log a warning and return False.

        Args:
            snapshot_id: The snapshot to restore.

        Returns:
            True if rollback succeeded, False otherwise.
        """
        row = self._conn.execute(
            "SELECT * FROM cerberus_snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()

        if row is None:
            logger.error("Rollback failed: snapshot %s not found", snapshot_id)
            return False

        snapshot_type = row["type"]
        target = row["target"]
        data_path = Path(row["data_path"])

        if not data_path.exists():
            logger.error("Rollback failed: snapshot data missing at %s", data_path)
            return False

        if snapshot_type == "file":
            target_path = Path(target)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(data_path, target_path)
            logger.info("Rolled back file: %s from snapshot %s", target, snapshot_id[:8])
            return True

        elif snapshot_type == "config":
            logger.warning(
                "Config rollback not yet automated (Phase 2). "
                "Snapshot data at: %s", data_path,
            )
            return False

        elif snapshot_type == "db":
            logger.warning(
                "DB rollback not yet automated (Phase 2). "
                "Snapshot data at: %s", data_path,
            )
            return False

        logger.error("Unknown snapshot type: %s", snapshot_type)
        return False

    def cleanup(
        self,
        max_age_days: int = 30,
        keep_high_risk: bool = True,
    ) -> int:
        """Prune old snapshots.

        Args:
            max_age_days: Delete snapshots older than this.
            keep_high_risk: If True, never delete high/critical risk snapshots.

        Returns:
            Number of snapshots deleted.
        """
        cutoff = (datetime.now() - timedelta(days=max_age_days)).isoformat()
        protected_levels = {"high", "critical"} if keep_high_risk else set()

        rows = self._conn.execute(
            "SELECT snapshot_id, data_path, risk_level FROM cerberus_snapshots "
            "WHERE created_at < ?",
            (cutoff,),
        ).fetchall()

        deleted = 0
        for row in rows:
            if row["risk_level"] in protected_levels:
                continue

            # Delete the snapshot file
            data_path = Path(row["data_path"])
            if data_path.exists():
                data_path.unlink()

            # Delete the record
            self._conn.execute(
                "DELETE FROM cerberus_snapshots WHERE snapshot_id = ?",
                (row["snapshot_id"],),
            )
            deleted += 1

        self._conn.commit()
        logger.info("Cleanup: deleted %d snapshots (cutoff: %s)", deleted, cutoff)
        return deleted

    def _record_snapshot(
        self,
        snapshot_id: str,
        snapshot_type: str,
        target: str,
        action_id: str,
        risk_level: str,
        data_path: str,
    ) -> None:
        """Insert a snapshot record into the tracking database."""
        self._conn.execute(
            "INSERT INTO cerberus_snapshots "
            "(snapshot_id, type, target, action_id, risk_level, created_at, data_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (snapshot_id, snapshot_type, target, action_id, risk_level,
             datetime.now().isoformat(), data_path),
        )
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
