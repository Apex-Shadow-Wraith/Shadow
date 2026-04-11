"""Grimoire Snapshot Exporter — dump key memories to markdown for Claude project knowledge.

Exports Grimoire memories into well-structured markdown files that can be
uploaded as project knowledge to Claude Opus sessions.
"""

import os
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("shadow.grimoire.snapshot_exporter")


class SnapshotExporter:
    """Export Grimoire memories to markdown files for external use."""

    DEFAULT_CATEGORIES = ["architecture", "bug_fixes", "decisions", "patterns"]

    def __init__(self, grimoire):
        """Initialize with a Grimoire instance.

        Args:
            grimoire: A Grimoire instance (modules.grimoire.grimoire.Grimoire).
        """
        self.grimoire = grimoire

    def export_collection(self, collection: str, output_path: str, max_entries: int = 100) -> str:
        """Export a Grimoire collection (category) to a markdown file.

        Args:
            collection: The category name to export.
            output_path: File path for the output markdown.
            max_entries: Maximum number of entries to include.

        Returns:
            The filepath of the created file.
        """
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        cursor = self.grimoire.conn.cursor()
        cursor.execute(
            """SELECT id, content, trust_level, confidence, source, source_module,
                      created_at, access_count, metadata_json
               FROM memories
               WHERE is_active = 1 AND category = ?
               ORDER BY trust_level DESC, access_count DESC
               LIMIT ?""",
            (collection, max_entries),
        )
        rows = cursor.fetchall()

        lines = [f"# Collection: {collection}", ""]

        if not rows:
            lines.append("_No entries in this collection._")
        else:
            for i, row in enumerate(rows, 1):
                mid, content, trust, conf, source, src_mod, created, access_ct, meta = row
                lines.append(f"## Entry {i}")
                lines.append("")
                lines.append(content)
                lines.append("")
                lines.append(
                    f"_Trust: {trust} | Source: {source} | Module: {src_mod} "
                    f"| Accessed: {access_ct}x | Created: {created}_"
                )
                lines.append("")
                lines.append("---")
                lines.append("")

        output.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Exported %d entries from '%s' to %s", len(rows), collection, output)
        return str(output)

    def export_key_memories(self, output_dir: str, categories: list[str] | None = None) -> list[str]:
        """Export the most important memories across categories.

        Importance is determined by high trust_level + high access_count.

        Args:
            output_dir: Directory to write markdown files into.
            categories: List of categories to export. Defaults to
                        architecture, bug_fixes, decisions, patterns.

        Returns:
            List of filepaths created.
        """
        if categories is None:
            categories = self.DEFAULT_CATEGORIES

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        created_files = []
        for cat in categories:
            filepath = out / f"{cat}.md"
            self.export_collection(cat, str(filepath))
            created_files.append(str(filepath))

        return created_files

    def export_for_project_knowledge(self, output_dir: str) -> dict:
        """Full export formatted for Claude project knowledge upload.

        Creates one .md file per active category, plus an index.md.

        Args:
            output_dir: Directory to write files into.

        Returns:
            Dict with files_created, total_entries, total_size_bytes.
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        # Discover all active categories
        cursor = self.grimoire.conn.cursor()
        cursor.execute(
            "SELECT DISTINCT category FROM memories WHERE is_active = 1 ORDER BY category"
        )
        categories = [row[0] for row in cursor.fetchall()]

        files_created = []
        total_entries = 0
        total_size = 0

        # Export each category
        for cat in categories:
            filepath = out / f"{cat}.md"
            self.export_collection(cat, str(filepath))
            files_created.append(str(filepath))

            # Count entries for this category
            cursor.execute(
                "SELECT COUNT(*) FROM memories WHERE is_active = 1 AND category = ?",
                (cat,),
            )
            total_entries += cursor.fetchone()[0]
            total_size += filepath.stat().st_size

        # Build index
        index_path = out / "index.md"
        index_lines = [
            "# Grimoire Snapshot Index",
            "",
            f"_Exported: {datetime.now().isoformat(timespec='seconds')}_",
            "",
            f"**Total entries:** {total_entries}  ",
            f"**Categories:** {len(categories)}  ",
            "",
            "## Categories",
            "",
        ]
        for cat in categories:
            cursor.execute(
                "SELECT COUNT(*) FROM memories WHERE is_active = 1 AND category = ?",
                (cat,),
            )
            count = cursor.fetchone()[0]
            index_lines.append(f"- [{cat}]({cat}.md) — {count} entries")

        index_path.write_text("\n".join(index_lines), encoding="utf-8")
        files_created.append(str(index_path))
        total_size += index_path.stat().st_size

        logger.info(
            "Project knowledge export: %d files, %d entries, %d bytes",
            len(files_created), total_entries, total_size,
        )

        return {
            "files_created": files_created,
            "total_entries": total_entries,
            "total_size_bytes": total_size,
        }
