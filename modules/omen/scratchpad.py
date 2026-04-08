"""
Omen Scratchpad — File-Based Working Memory
=============================================
Persistent scratchpad for intermediate thoughts during complex tasks.
Externalizes working memory so the model doesn't hold intermediates
in context.

Each active task gets its own JSON file under data/scratchpads/.
Completed scratchpads are optionally archived to Grimoire, then deleted.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("shadow.omen.scratchpad")

VALID_ENTRY_TYPES = {
    "thought",
    "intermediate_result",
    "decision",
    "open_question",
    "code_draft",
}


class Scratchpad:
    """File-based working memory for complex tasks."""

    def __init__(
        self,
        base_dir: str = "data/scratchpads",
        grimoire: Any = None,
    ) -> None:
        """Initialize scratchpad system.

        Args:
            base_dir: Directory for scratchpad files.
            grimoire: Optional Grimoire instance for archiving.
        """
        self._base_dir = Path(base_dir)
        self._grimoire = grimoire
        try:
            self._base_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error("Failed to create scratchpad dir %s: %s", self._base_dir, e)

    def _path(self, task_id: str) -> Path:
        """Return the file path for a task's scratchpad."""
        return self._base_dir / f"{task_id}.json"

    def create(self, task_id: str, task_description: str = "") -> str:
        """Create a new scratchpad for a task.

        Args:
            task_id: Unique task identifier.
            task_description: Human-readable description.

        Returns:
            File path of the created scratchpad.
        """
        path = self._path(task_id)
        data = {
            "task_id": task_id,
            "task_description": task_description,
            "created_at": time.time(),
            "entries": [],
            "status": "active",
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            logger.info("Created scratchpad for task '%s' at %s", task_id, path)
            return str(path)
        except Exception as e:
            logger.error("Failed to create scratchpad for '%s': %s", task_id, e)
            return ""

    def write(self, task_id: str, entry: dict) -> bool:
        """Append an entry to a task's scratchpad.

        Args:
            task_id: Task identifier.
            entry: Dict with keys: step, content, entry_type.
                   Timestamp is added automatically.

        Returns:
            True on success, False if scratchpad doesn't exist or on error.
        """
        path = self._path(task_id)
        try:
            if not path.exists():
                logger.warning("Scratchpad not found for task '%s'", task_id)
                return False

            data = json.loads(path.read_text(encoding="utf-8"))

            enriched = {
                "step": entry.get("step", ""),
                "content": entry.get("content", ""),
                "timestamp": time.time(),
                "entry_type": entry.get("entry_type", "thought"),
            }
            data["entries"].append(enriched)
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return True
        except Exception as e:
            logger.error("Failed to write to scratchpad '%s': %s", task_id, e)
            return False

    def read(self, task_id: str) -> dict | None:
        """Read entire scratchpad contents.

        Args:
            task_id: Task identifier.

        Returns:
            Full scratchpad dict, or None if not found.
        """
        path = self._path(task_id)
        try:
            if not path.exists():
                return None
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error("Failed to read scratchpad '%s': %s", task_id, e)
            return None

    def read_latest(self, task_id: str, n: int = 3) -> list[dict]:
        """Return only the last N entries from a scratchpad.

        Args:
            task_id: Task identifier.
            n: Number of recent entries to return.

        Returns:
            List of the last N entries, or empty list if not found.
        """
        data = self.read(task_id)
        if data is None:
            return []
        return data["entries"][-n:]

    def format_for_context(self, task_id: str, max_tokens: int = 1000) -> str:
        """Format scratchpad entries as a readable string for context injection.

        Truncates oldest entries first if over max_tokens (estimated as chars).

        Args:
            task_id: Task identifier.
            max_tokens: Approximate max length of output string.

        Returns:
            Formatted string, or empty string if scratchpad not found/empty.
        """
        data = self.read(task_id)
        if data is None or not data["entries"]:
            return ""

        lines = []
        for i, entry in enumerate(data["entries"], 1):
            step = entry.get("step", "unknown")
            content = entry.get("content", "")
            lines.append(f"- [Step {i}: {step}] {content}")

        # Truncate oldest entries first to fit within max_tokens
        result = "Working memory:\n" + "\n".join(lines)
        while len(result) > max_tokens and len(lines) > 1:
            lines.pop(0)
            result = "Working memory:\n" + "\n".join(lines)

        return result

    def close(self, task_id: str, archive: bool = True) -> bool:
        """Close a scratchpad, optionally archiving to Grimoire.

        Args:
            task_id: Task identifier.
            archive: If True and Grimoire available, archive before deleting.

        Returns:
            True on success, False on error.
        """
        path = self._path(task_id)
        try:
            if not path.exists():
                logger.warning("Scratchpad not found for close: '%s'", task_id)
                return False

            data = json.loads(path.read_text(encoding="utf-8"))
            data["status"] = "completed"

            # Archive to Grimoire if available
            if archive and self._grimoire is not None:
                try:
                    self._grimoire.store(
                        content=json.dumps(data, indent=2),
                        category="scratchpad_archive",
                        metadata={"task_id": task_id},
                    )
                    logger.info("Archived scratchpad '%s' to Grimoire", task_id)
                except Exception as e:
                    logger.warning(
                        "Failed to archive scratchpad '%s' to Grimoire: %s",
                        task_id, e,
                    )

            # Delete the file
            path.unlink()
            logger.info("Closed and deleted scratchpad '%s'", task_id)
            return True
        except Exception as e:
            logger.error("Failed to close scratchpad '%s': %s", task_id, e)
            return False

    def cleanup_stale(self, max_age_hours: int = 24) -> int:
        """Find and close scratchpads older than max_age_hours.

        Args:
            max_age_hours: Maximum age in hours before a scratchpad is stale.

        Returns:
            Number of stale scratchpads cleaned up.
        """
        cutoff = time.time() - (max_age_hours * 3600)
        cleaned = 0
        try:
            for path in self._base_dir.glob("*.json"):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    if (
                        data.get("status") == "active"
                        and data.get("created_at", 0) < cutoff
                    ):
                        task_id = data.get("task_id", path.stem)
                        self.close(task_id, archive=True)
                        cleaned += 1
                except Exception as e:
                    logger.warning("Error checking scratchpad %s: %s", path, e)
            return cleaned
        except Exception as e:
            logger.error("Failed during stale cleanup: %s", e)
            return cleaned

    def list_active(self) -> list[dict]:
        """Return summary info for all active scratchpads.

        Returns:
            List of dicts with task_id, task_description, created_at, entry_count.
        """
        active = []
        try:
            for path in self._base_dir.glob("*.json"):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    if data.get("status") == "active":
                        active.append({
                            "task_id": data.get("task_id", path.stem),
                            "task_description": data.get("task_description", ""),
                            "created_at": data.get("created_at", 0),
                            "entry_count": len(data.get("entries", [])),
                        })
                except Exception as e:
                    logger.warning("Error reading scratchpad %s: %s", path, e)
            return active
        except Exception as e:
            logger.error("Failed to list active scratchpads: %s", e)
            return []
