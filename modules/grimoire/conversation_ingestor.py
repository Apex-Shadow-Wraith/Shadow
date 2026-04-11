"""Conversation Ingestor — mines Claude Code transcripts into Grimoire.

Scans ~/.claude/ for JSONL session transcripts, extracts knowledge-worthy
exchanges (bug fixes, architecture decisions, config changes, etc.), and
stores them as permanent Grimoire memories.

No LLM calls — uses fast keyword heuristics for categorization.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Categories for extracted knowledge
CATEGORY_BUG_FIX = "bug_fix"
CATEGORY_CONFIGURATION = "configuration"
CATEGORY_ARCHITECTURE = "architecture"
CATEGORY_TESTING = "testing"
CATEGORY_IMPLEMENTATION = "implementation"
CATEGORY_GENERAL = "general_knowledge"

# Keyword sets for heuristic categorization
_BUG_KEYWORDS = {"bug", "fix", "error", "broken", "crash", "fail", "exception",
                 "traceback", "stacktrace", "issue", "regression", "patch"}
_CONFIG_KEYWORDS = {"config", "configuration", "setting", "env", ".env", "yaml",
                    "toml", "ini", ".json config", "environment variable"}
_ARCH_KEYWORDS = {"should we", "approach", "design", "architecture", "pattern",
                  "refactor", "restructure", "trade-off", "tradeoff", "migrate"}
_TEST_KEYWORDS = {"test", "pytest", "assert", "coverage", "spec", "passing",
                  "failing", "test suite", "test_"}
_IMPL_KEYWORDS = {"create", "implement", "new file", "scaffold", "feature",
                  "add support", "build"}

# Secrets to strip before ingestion
_SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_-]+"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"key-[A-Za-z0-9_-]{20,}"),
    re.compile(
        r"(ANTHROPIC_API_KEY|OPENAI_API_KEY|API_KEY|SECRET_KEY|ACCESS_TOKEN)"
        r"\s*=\s*\S+"
    ),
    re.compile(r"config/\.env\b"),
]

# Minimum content length to consider an exchange meaningful
_MIN_CONTENT_LENGTH = 100


class ConversationIngestor:
    """Mines Claude Code session transcripts and ingests knowledge into Grimoire.

    Workflow: scan_transcripts → parse_transcript → extract_knowledge → ingest
    """

    def __init__(self, grimoire, config: dict | None = None):
        """Initialize the ingestor.

        Args:
            grimoire: A Grimoire instance for storing extracted knowledge.
            config: Optional dict with keys:
                - transcript_dir: Path to scan (default ~/.claude/projects/)
                - manifest_path: Tracking file (default data/ingestor_manifest.json)
        """
        config = config or {}
        self._grimoire = grimoire
        self._transcript_dir = Path(
            config.get("transcript_dir", Path.home() / ".claude" / "projects")
        )
        self._manifest_path = Path(
            config.get("manifest_path", "data/ingestor_manifest.json")
        )
        self._manifest = self._load_manifest()

    # ------------------------------------------------------------------
    # Manifest (processed-file tracking)
    # ------------------------------------------------------------------

    def _load_manifest(self) -> dict:
        """Load the processed-file manifest from disk."""
        if self._manifest_path.exists():
            try:
                return json.loads(self._manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Corrupt manifest, starting fresh: %s", exc)
        return {"processed_files": [], "stats": {"total_files": 0,
                                                  "total_entries": 0,
                                                  "last_run": None}}

    def _save_manifest(self) -> None:
        """Persist the manifest to disk (append-only semantics)."""
        self._manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self._manifest_path.write_text(
            json.dumps(self._manifest, indent=2, default=str),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Step 1 — Scan for unprocessed transcripts
    # ------------------------------------------------------------------

    # File extensions per source type
    _SOURCE_EXTENSIONS = {
        "claude_code": "*.jsonl",
        "claude_ai": "*.json",
        "chatgpt": "*.json",
    }

    def scan_transcripts(
        self, directory: str | None = None, source: str = "claude_code"
    ) -> list[str]:
        """Find all unprocessed transcript/export files.

        Args:
            directory: Override scan directory (default: self._transcript_dir).
            source: One of "claude_code", "claude_ai", "chatgpt".

        Returns:
            List of absolute file paths that haven't been ingested yet.
        """
        scan_dir = Path(directory) if directory else self._transcript_dir
        if not scan_dir.exists():
            logger.info("Transcript directory does not exist: %s", scan_dir)
            return []

        glob_pattern = self._SOURCE_EXTENSIONS.get(source, "*.jsonl")
        processed = set(self._manifest.get("processed_files", []))
        found: list[str] = []
        for path in scan_dir.rglob(glob_pattern):
            abs_path = str(path.resolve())
            if abs_path not in processed:
                found.append(abs_path)

        logger.info("Scanned %s — %d new %s file(s)", scan_dir, len(found), source)
        return sorted(found)

    # ------------------------------------------------------------------
    # Step 2 — Parse a single transcript
    # ------------------------------------------------------------------

    def parse_transcript(self, filepath: str) -> list[dict]:
        """Parse a Claude Code JSONL transcript into structured exchanges.

        Each line in a Claude Code transcript is a JSON object. We extract
        the role, content, timestamp, any tool calls, and file changes.

        Args:
            filepath: Absolute path to a .jsonl transcript.

        Returns:
            List of exchange dicts:
                {role, content, timestamp, tool_calls, file_changes}
        """
        exchanges: list[dict] = []
        path = Path(filepath)
        if not path.exists():
            logger.warning("Transcript file not found: %s", filepath)
            return exchanges

        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            logger.error("Failed to read transcript %s: %s", filepath, exc)
            return exchanges

        for line_num, raw_line in enumerate(lines, 1):
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                entry = json.loads(raw_line)
            except json.JSONDecodeError:
                logger.debug("Skipping non-JSON line %d in %s", line_num, filepath)
                continue

            exchange = self._normalize_entry(entry)
            if exchange:
                exchanges.append(exchange)

        logger.info("Parsed %d exchange(s) from %s", len(exchanges), filepath)
        return exchanges

    # ------------------------------------------------------------------
    # Step 2b — Parse Claude.ai export
    # ------------------------------------------------------------------

    def parse_claude_export(self, filepath: str) -> list[dict]:
        """Parse a Claude.ai conversation export (JSON format).

        Claude.ai exports as JSON with structure:
        {"uuid": "...", "name": "...", "created_at": "...", "updated_at": "...",
         "chat_messages": [{"sender": "human"/"assistant", "text": "...",
                            "created_at": "..."}]}

        Args:
            filepath: Absolute path to a .json export file.

        Returns:
            List of exchange dicts matching parse_transcript output format.
        """
        exchanges: list[dict] = []
        path = Path(filepath)
        if not path.exists():
            logger.warning("Claude.ai export not found: %s", filepath)
            return exchanges

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to read Claude.ai export %s: %s", filepath, exc)
            return exchanges

        if not isinstance(raw, dict):
            logger.warning("Unexpected Claude.ai export format in %s", filepath)
            return exchanges

        conversation_title = raw.get("name", "")
        messages = raw.get("chat_messages", [])

        for msg in messages:
            if not isinstance(msg, dict):
                continue
            sender = msg.get("sender", "unknown")
            # Normalize sender to role
            role = "user" if sender == "human" else sender
            text = msg.get("text", "")
            timestamp = msg.get("created_at", raw.get("created_at"))

            exchange = {
                "role": role,
                "content": text if isinstance(text, str) else str(text),
                "timestamp": timestamp,
                "tool_calls": [],
                "file_changes": [],
                "source": "claude_ai_export",
                "conversation_title": conversation_title,
            }
            exchanges.append(exchange)

        logger.info(
            "Parsed %d exchange(s) from Claude.ai export %s",
            len(exchanges), filepath,
        )
        return exchanges

    # ------------------------------------------------------------------
    # Step 2c — Parse ChatGPT export
    # ------------------------------------------------------------------

    def parse_chatgpt_export(self, filepath: str) -> list[dict]:
        """Parse a ChatGPT conversation export (conversations.json).

        ChatGPT exports via Settings > Data Controls > Export as:
        [{"title": "...", "mapping": {"node_id": {"message":
          {"role": "...", "content": {"parts": ["..."]}},
          "create_time": float}}}]

        Args:
            filepath: Absolute path to conversations.json.

        Returns:
            List of exchange dicts matching parse_transcript output format.
        """
        exchanges: list[dict] = []
        path = Path(filepath)
        if not path.exists():
            logger.warning("ChatGPT export not found: %s", filepath)
            return exchanges

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to read ChatGPT export %s: %s", filepath, exc)
            return exchanges

        # ChatGPT export is a list of conversations
        conversations = raw if isinstance(raw, list) else [raw]

        for convo in conversations:
            if not isinstance(convo, dict):
                continue
            title = convo.get("title", "")
            mapping = convo.get("mapping", {})
            if not isinstance(mapping, dict):
                continue

            # Collect nodes with messages, then sort by create_time
            nodes = []
            for node_id, node in mapping.items():
                if not isinstance(node, dict):
                    continue
                message = node.get("message")
                if not isinstance(message, dict):
                    continue
                role = message.get("role", "")
                if role not in ("user", "assistant", "system"):
                    continue
                # Extract text from content.parts
                content_obj = message.get("content", {})
                if isinstance(content_obj, dict):
                    parts = content_obj.get("parts", [])
                    text_parts = [
                        p for p in parts if isinstance(p, str)
                    ]
                    text = "\n".join(text_parts)
                elif isinstance(content_obj, str):
                    text = content_obj
                else:
                    text = ""

                create_time = message.get("create_time") or node.get("create_time")
                timestamp = None
                if create_time is not None:
                    try:
                        timestamp = datetime.fromtimestamp(
                            float(create_time), tz=timezone.utc
                        ).isoformat()
                    except (ValueError, TypeError, OSError):
                        pass

                nodes.append({
                    "role": role,
                    "content": text,
                    "timestamp": timestamp,
                    "tool_calls": [],
                    "file_changes": [],
                    "source": "chatgpt_export",
                    "conversation_title": title,
                    "create_time": create_time,
                })

            # Sort by create_time to preserve conversation order
            nodes.sort(key=lambda n: n.get("create_time") or 0)
            for node in nodes:
                node.pop("create_time", None)
                exchanges.append(node)

        logger.info(
            "Parsed %d exchange(s) from ChatGPT export %s",
            len(exchanges), filepath,
        )
        return exchanges

    # ------------------------------------------------------------------
    # Auto-detection
    # ------------------------------------------------------------------

    @staticmethod
    def detect_format(filepath: str) -> str:
        """Auto-detect export format from file content.

        Returns:
            "claude_code", "claude_ai", or "chatgpt".
        """
        path = Path(filepath)
        if not path.exists():
            return "claude_code"

        # JSONL files are always Claude Code transcripts
        if path.suffix == ".jsonl":
            return "claude_code"

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return "claude_code"

        # Claude.ai: dict with "chat_messages" key
        if isinstance(raw, dict) and "chat_messages" in raw:
            return "claude_ai"

        # ChatGPT: list of dicts with "mapping" keys
        if isinstance(raw, list) and raw:
            if isinstance(raw[0], dict) and "mapping" in raw[0]:
                return "chatgpt"

        # Single ChatGPT conversation wrapped as dict
        if isinstance(raw, dict) and "mapping" in raw:
            return "chatgpt"

        return "claude_code"

    def _normalize_entry(self, entry: dict) -> dict | None:
        """Convert a raw JSONL entry into a normalized exchange dict."""
        if not isinstance(entry, dict):
            return None

        # Claude Code transcripts use "type" or "role" fields
        role = entry.get("role", entry.get("type", "unknown"))

        # Content can be a string or a list of content blocks
        raw_content = entry.get("content", entry.get("message", ""))
        if isinstance(raw_content, list):
            # Concatenate text blocks
            parts = []
            for block in raw_content:
                if isinstance(block, dict):
                    parts.append(block.get("text", block.get("content", "")))
                elif isinstance(block, str):
                    parts.append(block)
            content = "\n".join(parts)
        elif isinstance(raw_content, str):
            content = raw_content
        else:
            content = str(raw_content) if raw_content else ""

        # Extract tool calls
        tool_calls = []
        if "tool_calls" in entry:
            tool_calls = entry["tool_calls"]
        elif isinstance(raw_content, list):
            for block in raw_content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_calls.append({
                        "name": block.get("name", "unknown"),
                        "input": block.get("input", {}),
                    })

        # Detect file changes from tool calls
        file_changes = self._extract_file_changes(tool_calls, entry)

        timestamp = entry.get("timestamp", entry.get("created_at", None))

        return {
            "role": role,
            "content": content,
            "timestamp": timestamp,
            "tool_calls": tool_calls,
            "file_changes": file_changes,
        }

    def _extract_file_changes(self, tool_calls: list, entry: dict) -> list[str]:
        """Pull file paths from tool calls that modify files."""
        changes: list[str] = []
        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue
            name = tc.get("name", "")
            inp = tc.get("input", {})
            if name in ("Edit", "Write", "NotebookEdit") and isinstance(inp, dict):
                fp = inp.get("file_path", inp.get("path", ""))
                if fp:
                    changes.append(fp)
        # Also check top-level entry for file_path
        if entry.get("file_path"):
            changes.append(entry["file_path"])
        return changes

    # ------------------------------------------------------------------
    # Step 3 — Extract knowledge from parsed exchanges
    # ------------------------------------------------------------------

    def extract_knowledge(self, exchanges: list[dict]) -> list[dict]:
        """Extract Grimoire-worthy knowledge entries from exchanges.

        Filters noise (short messages, pure tool output) and categorizes
        each meaningful exchange using keyword heuristics.

        Args:
            exchanges: Output of parse_transcript().

        Returns:
            List of knowledge entries:
                {content, category, metadata: {source_file, timestamp, type}}
        """
        entries: list[dict] = []

        for i, ex in enumerate(exchanges):
            content = ex.get("content", "")
            if not content or len(content) < _MIN_CONTENT_LENGTH:
                continue

            # Skip pure tool output without analysis
            if self._is_noise(ex):
                continue

            # Sanitize before storing
            clean_content = self._sanitize(content)
            category = self._categorize(clean_content, ex)

            metadata = {
                "source_file": "",  # filled by caller
                "timestamp": ex.get("timestamp"),
                "type": category,
                "role": ex.get("role", "unknown"),
                "exchange_index": i,
                "file_changes": ex.get("file_changes", []),
                "has_tool_calls": bool(ex.get("tool_calls")),
            }
            # Propagate export source metadata if present
            if ex.get("source"):
                metadata["source"] = ex["source"]
            if ex.get("conversation_title"):
                metadata["conversation_title"] = ex["conversation_title"]
            if ex.get("timestamp"):
                metadata["original_date"] = ex["timestamp"]

            entry = {
                "content": clean_content,
                "category": category,
                "metadata": metadata,
            }
            entries.append(entry)

        return entries

    def _is_noise(self, exchange: dict) -> bool:
        """Return True if the exchange is pure noise (tool output, listings)."""
        content = exchange.get("content", "")
        role = exchange.get("role", "")

        # Tool results without substantial text are noise
        if role in ("tool_result", "tool"):
            # Unless the result is paired with analysis (long text)
            if len(content) < 300:
                return True

        # Pure file listings
        lines = content.strip().splitlines()
        if lines and all(self._looks_like_path(l.strip()) for l in lines if l.strip()):
            return True

        return False

    @staticmethod
    def _looks_like_path(line: str) -> bool:
        """Heuristic: does this line look like a bare file path or ls output?"""
        # Matches lines like "  src/foo.py" or "d--- dir/"
        stripped = line.lstrip()
        if not stripped:
            return False
        # Very short lines that look like paths
        if "/" in stripped and " " not in stripped and len(stripped) < 200:
            return True
        if "\\" in stripped and " " not in stripped and len(stripped) < 200:
            return True
        return False

    def _categorize(self, content: str, exchange: dict) -> str:
        """Categorize an exchange using keyword heuristics."""
        lower = content.lower()

        # Check categories by priority
        if any(kw in lower for kw in _BUG_KEYWORDS):
            return CATEGORY_BUG_FIX
        if any(kw in lower for kw in _ARCH_KEYWORDS):
            return CATEGORY_ARCHITECTURE
        if any(kw in lower for kw in _CONFIG_KEYWORDS):
            return CATEGORY_CONFIGURATION
        if any(kw in lower for kw in _TEST_KEYWORDS):
            return CATEGORY_TESTING

        # Check for new file creation
        file_changes = exchange.get("file_changes", [])
        tool_calls = exchange.get("tool_calls", [])
        if file_changes or any(
            isinstance(tc, dict) and tc.get("name") == "Write"
            for tc in tool_calls
        ):
            if any(kw in lower for kw in _IMPL_KEYWORDS):
                return CATEGORY_IMPLEMENTATION

        return CATEGORY_GENERAL

    @staticmethod
    def _sanitize(text: str) -> str:
        """Strip secrets, API keys, and env references from text."""
        if not text:
            return text
        result = text
        for pattern in _SECRET_PATTERNS:
            result = pattern.sub("[REDACTED]", result)
        return result

    # ------------------------------------------------------------------
    # Format dispatch helpers
    # ------------------------------------------------------------------

    def _parse_by_format(self, filepath: str, fmt: str) -> list[dict]:
        """Dispatch to the correct parser based on format."""
        if fmt == "claude_ai":
            return self.parse_claude_export(filepath)
        elif fmt == "chatgpt":
            return self.parse_chatgpt_export(filepath)
        else:
            return self.parse_transcript(filepath)

    @staticmethod
    def _source_tag(fmt: str) -> str:
        """Return the Grimoire tag for a given source format."""
        return {
            "claude_ai": "claude_ai",
            "chatgpt": "chatgpt",
        }.get(fmt, "claude_code")

    # ------------------------------------------------------------------
    # Step 4 — Full pipeline
    # ------------------------------------------------------------------

    def ingest(
        self, directory: str | None = None, source: str | None = None
    ) -> dict:
        """Run the full pipeline: scan → parse → extract → store in Grimoire.

        Args:
            directory: Override scan directory.
            source: "claude_code", "claude_ai", "chatgpt", or None for auto-detect.

        Returns:
            {files_processed: int, entries_created: int, errors: list[str]}
        """
        from .grimoire import SOURCE_SYSTEM, TRUST_COMMUNITY

        result = {"files_processed": 0, "entries_created": 0, "errors": []}

        # Determine which source(s) to scan
        scan_source = source or "claude_code"
        files = self.scan_transcripts(directory, source=scan_source)
        if not files:
            logger.info("No new transcripts to ingest.")
            return result

        for filepath in files:
            try:
                # Auto-detect or use explicit source
                file_format = source or self.detect_format(filepath)
                exchanges = self._parse_by_format(filepath, file_format)
                knowledge = self.extract_knowledge(exchanges)

                # Tag each entry with its source file and export metadata
                for entry in knowledge:
                    entry["metadata"]["source_file"] = filepath
                    # Propagate source metadata from exchange-level tags
                    if exchanges:
                        sample = exchanges[0]
                        if "source" in sample:
                            entry["metadata"]["source"] = sample["source"]
                        if "conversation_title" in sample:
                            entry["metadata"]["conversation_title"] = sample[
                                "conversation_title"
                            ]

                stored = 0
                for entry in knowledge:
                    try:
                        source_tag = self._source_tag(file_format)
                        tags = ["transcript", source_tag, entry["category"]]
                        self._grimoire.remember(
                            content=entry["content"],
                            source=SOURCE_SYSTEM,
                            source_module="conversation_ingestor",
                            category=entry["category"],
                            trust_level=TRUST_COMMUNITY,
                            confidence=0.6,
                            tags=tags,
                            metadata=entry["metadata"],
                        )
                        stored += 1
                    except Exception as exc:
                        msg = f"Failed to store entry from {filepath}: {exc}"
                        logger.error(msg)
                        result["errors"].append(msg)

                result["entries_created"] += stored
                result["files_processed"] += 1

                # Mark as processed (append-only)
                self._manifest["processed_files"].append(filepath)

            except Exception as exc:
                msg = f"Failed to process {filepath}: {exc}"
                logger.error(msg)
                result["errors"].append(msg)

        # Update stats
        self._manifest["stats"]["total_files"] += result["files_processed"]
        self._manifest["stats"]["total_entries"] += result["entries_created"]
        self._manifest["stats"]["last_run"] = datetime.now(timezone.utc).isoformat()
        self._save_manifest()

        logger.info(
            "Ingestion complete: %d file(s), %d entries, %d error(s)",
            result["files_processed"],
            result["entries_created"],
            len(result["errors"]),
        )
        return result

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return ingestion history stats.

        Returns:
            {total_files, total_entries, last_run, processed_files_count}
        """
        stats = self._manifest.get("stats", {})
        return {
            "total_files": stats.get("total_files", 0),
            "total_entries": stats.get("total_entries", 0),
            "last_run": stats.get("last_run"),
            "processed_files_count": len(
                self._manifest.get("processed_files", [])
            ),
        }
