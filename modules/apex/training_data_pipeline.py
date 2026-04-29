"""
Training Data Pipeline — LoRA-Ready Dataset from Apex Escalations
===================================================================
Every time Shadow escalates to a frontier model and learns something,
that exchange is captured as a clean training example in JSONL format.

Output format is ChatML-compatible (Unsloth/Axolotl ready):
    {"conversations": [...], "metadata": {...}}

Design: append-only daily files, never overwrite, never store secrets.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("shadow.apex.training_pipeline")

# Patterns that must never appear in training data
_SECRET_PATTERNS = [
    # API key values
    re.compile(r"sk-ant-[A-Za-z0-9_-]+"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"key-[A-Za-z0-9_-]{20,}"),
    # Environment variable assignments containing secrets
    re.compile(r"(ANTHROPIC_API_KEY|OPENAI_API_KEY|API_KEY|SECRET_KEY|ACCESS_TOKEN)\s*=\s*\S+"),
    # config/.env file references with content
    re.compile(r"config/\.env\b"),
]


class TrainingDataPipeline:
    """Capture Apex escalation exchanges as LoRA-ready training data.

    Each successful escalation produces a JSONL entry with the original
    user input, the correct response from the frontier model, and
    metadata about the escalation context.

    Files are organized by date: apex_training_YYYY-MM-DD.jsonl
    """

    def __init__(self, output_dir: str = "training_data/apex_sessions") -> None:
        """Initialize the training data pipeline.

        Args:
            output_dir: Directory for JSONL output files.
                        Created automatically if it doesn't exist.
        """
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def capture(
        self,
        user_input: str,
        shadow_failed_response: str,
        apex_response: str,
        module: str,
        category: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Capture one training example from an escalation.

        Args:
            user_input: The original user input that triggered escalation.
            shadow_failed_response: Shadow's failed attempt (may be empty).
            apex_response: The correct response from the frontier model.
            module: Which module was involved (e.g. "omen", "reaper").
            category: Task category (e.g. "code_generation", "research").
            metadata: Optional extra metadata (model names, confidence, etc).

        Returns:
            The training entry dict ready for save().
        """
        extra = metadata or {}

        entry = {
            "conversations": [
                {"role": "system", "content": "You are Shadow."},
                {"role": "user", "content": self._sanitize(user_input)},
                {"role": "assistant", "content": self._sanitize(apex_response)},
            ],
            "metadata": {
                "source": "apex_escalation",
                "module": module,
                "category": category,
                "timestamp": datetime.now().isoformat(),
                "model_that_failed": extra.get("model_that_failed", ""),
                "model_that_answered": extra.get("model_that_answered", ""),
                "confidence_before": extra.get("confidence_before", 0.0),
                "confidence_after": extra.get("confidence_after", 0.0),
            },
        }

        # Include shadow's failed response in metadata if provided
        if shadow_failed_response:
            entry["metadata"]["shadow_failed_response"] = self._sanitize(
                shadow_failed_response
            )

        return entry

    def save(self, entry: dict[str, Any]) -> str:
        """Append entry to today's JSONL file.

        Args:
            entry: A training entry dict (from capture()).

        Returns:
            Filepath of the JSONL file written to.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        filepath = self._output_dir / f"apex_training_{today}.jsonl"
        line = json.dumps(entry, ensure_ascii=False)

        with open(filepath, "a", encoding="utf-8") as f:
            f.write(line + "\n")

        logger.info("Training example saved to %s", filepath)
        return str(filepath)

    def get_stats(self) -> dict[str, Any]:
        """Return counts: total examples, examples today, by category, by module.

        Returns:
            Dict with total_examples, examples_today, by_category, by_module.
        """
        total = 0
        today_count = 0
        by_category: dict[str, int] = {}
        by_module: dict[str, int] = {}

        today_str = datetime.now().strftime("%Y-%m-%d")
        today_file = f"apex_training_{today_str}.jsonl"

        for jsonl_file in self._output_dir.glob("apex_training_*.jsonl"):
            is_today = jsonl_file.name == today_file
            with open(jsonl_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    total += 1
                    if is_today:
                        today_count += 1

                    meta = entry.get("metadata", {})
                    cat = meta.get("category", "unknown")
                    mod = meta.get("module", "unknown")
                    by_category[cat] = by_category.get(cat, 0) + 1
                    by_module[mod] = by_module.get(mod, 0) + 1

        return {
            "total_examples": total,
            "examples_today": today_count,
            "by_category": by_category,
            "by_module": by_module,
        }

    def export_for_lora(
        self, output_path: str, format: str = "chatml"
    ) -> int:
        """Export all JSONL files as a single merged LoRA-ready dataset.

        Args:
            output_path: Path for the merged output file.
            format: Output format. "chatml" (default) is compatible
                    with Unsloth/Axolotl.

        Returns:
            Number of examples exported.
        """
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = output.with_suffix(".jsonl.tmp")

        count = 0
        with open(tmp_path, "w", encoding="utf-8") as out:
            for jsonl_file in sorted(
                self._output_dir.glob("apex_training_*.jsonl")
            ):
                with open(jsonl_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        out.write(json.dumps(entry, ensure_ascii=False) + "\n")
                        count += 1

        # Atomic rename
        tmp_path.replace(output)
        logger.info("Exported %d examples to %s", count, output)
        return count

    def _sanitize(self, text: str) -> str:
        """Strip secrets, API keys, and env references from text.

        Args:
            text: Raw text that may contain sensitive data.

        Returns:
            Sanitized text with secrets replaced by [REDACTED].
        """
        if not text:
            return text

        result = text
        for pattern in _SECRET_PATTERNS:
            result = pattern.sub("[REDACTED]", result)

        return result
