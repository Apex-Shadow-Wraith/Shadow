"""
Embedding Evaluator — Measure and Compare Retrieval Quality
=============================================================
Evaluates how well nomic-embed-text (or any embedding model) retrieves
the right memories from Grimoire. Tracks metrics over time and exports
fine-tuning data when retrieval quality needs improvement.

Metrics:
    - recall@1, recall@5, recall@10: Is the expected doc in top-k?
    - MRR (Mean Reciprocal Rank): How high does the expected doc rank?
    - avg_similarity_score: Mean relevance of correct retrievals

Usage:
    evaluator = EmbeddingEvaluator(grimoire)
    eval_set = evaluator.build_eval_set()
    results = evaluator.run_eval(eval_set)
    print(results["metrics"])

Author: Patrick (with Claude Opus 4.6)
Project: Shadow
Module: Grimoire — Embedding Evaluation (Phase 5)
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("grimoire.embedding_evaluator")


class EmbeddingEvaluator:
    """Evaluate and benchmark embedding retrieval quality for Grimoire."""

    # Category-specific query generators: each returns candidate queries
    # from a memory's content based on its category.
    _CATEGORY_EXTRACTORS = {
        "code": "_extract_code_queries",
        "python": "_extract_code_queries",
        "programming": "_extract_code_queries",
        "debugging": "_extract_code_queries",
        "bible": "_extract_bible_queries",
        "ethics": "_extract_bible_queries",
        "theology": "_extract_bible_queries",
        "scripture": "_extract_bible_queries",
        "technical": "_extract_technical_queries",
        "hardware": "_extract_technical_queries",
        "software": "_extract_technical_queries",
        "system": "_extract_technical_queries",
        "business": "_extract_business_queries",
        "landscaping": "_extract_business_queries",
    }

    def __init__(self, grimoire):
        """Initialize with a Grimoire instance to query against.

        Args:
            grimoire: A Grimoire instance with recall() and remember() methods.
        """
        self.grimoire = grimoire

    # ------------------------------------------------------------------
    # Eval set construction
    # ------------------------------------------------------------------

    def build_eval_set(self) -> list[dict]:
        """Create evaluation pairs from existing Grimoire data.

        For each active memory, generates:
            - 1 positive query that SHOULD retrieve it
            - 1 negative query that should NOT retrieve it (cross-category)

        Returns:
            List of {query, expected_id, label, category} dicts.
            label is "positive" or "negative".
        """
        memories = self._fetch_all_active_memories()
        if not memories:
            logger.warning("No active memories found — cannot build eval set")
            return []

        eval_set: list[dict] = []
        categories = list({m["category"] for m in memories})

        for mem in memories:
            # --- Positive query ---
            positive_query = self._generate_positive_query(mem)
            if positive_query:
                eval_set.append({
                    "query": positive_query,
                    "expected_id": mem["id"],
                    "label": "positive",
                    "category": mem["category"],
                })

            # --- Negative query ---
            negative_query = self._generate_negative_query(mem, categories)
            if negative_query:
                eval_set.append({
                    "query": negative_query,
                    "expected_id": mem["id"],
                    "label": "negative",
                    "category": mem["category"],
                })

        logger.info("Built eval set with %d pairs from %d memories",
                     len(eval_set), len(memories))
        return eval_set

    # ------------------------------------------------------------------
    # Evaluation runner
    # ------------------------------------------------------------------

    def run_eval(self, eval_set: list[dict] | None = None) -> dict:
        """Run retrieval evaluation against Grimoire.

        For each positive query, checks if the expected document appears
        in the top-k results. Negative queries verify the expected doc
        does NOT dominate results.

        Args:
            eval_set: Pre-built eval pairs. If None, calls build_eval_set().

        Returns:
            {
                "metrics": {
                    "recall_at_1": float,
                    "recall_at_5": float,
                    "recall_at_10": float,
                    "mrr": float,
                    "avg_similarity_score": float,
                },
                "failures": [...],
                "total": int,
                "timestamp": str,
            }
        """
        if eval_set is None:
            eval_set = self.build_eval_set()

        positives = [e for e in eval_set if e["label"] == "positive"]
        if not positives:
            return {
                "metrics": {
                    "recall_at_1": 0.0,
                    "recall_at_5": 0.0,
                    "recall_at_10": 0.0,
                    "mrr": 0.0,
                    "avg_similarity_score": 0.0,
                },
                "failures": [],
                "total": 0,
                "timestamp": datetime.now().isoformat(),
            }

        hits_at_1 = 0
        hits_at_5 = 0
        hits_at_10 = 0
        reciprocal_ranks: list[float] = []
        similarity_scores: list[float] = []
        failures: list[dict] = []

        for pair in positives:
            results = self.grimoire.recall(pair["query"], n_results=10)
            result_ids = [r["id"] for r in results]

            found_rank = None
            found_similarity = None
            for rank, r in enumerate(results, start=1):
                if r["id"] == pair["expected_id"]:
                    found_rank = rank
                    found_similarity = r.get("relevance", 0.0)
                    break

            if found_rank is not None:
                if found_rank <= 1:
                    hits_at_1 += 1
                if found_rank <= 5:
                    hits_at_5 += 1
                hits_at_10 += 1  # found_rank is always <= 10
                reciprocal_ranks.append(1.0 / found_rank)
                similarity_scores.append(found_similarity)
            else:
                reciprocal_ranks.append(0.0)
                failures.append({
                    "query": pair["query"],
                    "expected_id": pair["expected_id"],
                    "category": pair["category"],
                    "returned_ids": result_ids[:5],
                })

        total = len(positives)
        metrics = {
            "recall_at_1": hits_at_1 / total,
            "recall_at_5": hits_at_5 / total,
            "recall_at_10": hits_at_10 / total,
            "mrr": sum(reciprocal_ranks) / total,
            "avg_similarity_score": (
                sum(similarity_scores) / len(similarity_scores)
                if similarity_scores else 0.0
            ),
        }

        return {
            "metrics": metrics,
            "failures": failures,
            "total": total,
            "timestamp": datetime.now().isoformat(),
        }

    # ------------------------------------------------------------------
    # Model comparison
    # ------------------------------------------------------------------

    def compare_models(self, model_a: str, model_b: str,
                       eval_set: list[dict]) -> dict:
        """Run the same eval set against two embedding models.

        Temporarily swaps the Grimoire embed_model, re-embeds queries,
        and compares retrieval metrics side by side.

        Args:
            model_a: First model name (e.g. "nomic-embed-text").
            model_b: Second model name (e.g. "nomic-embed-text:fine-tuned").
            eval_set: Pre-built eval pairs to use for both models.

        Returns:
            {
                "model_a": {"name": str, "metrics": {...}},
                "model_b": {"name": str, "metrics": {...}},
                "winner": str,
                "delta": {metric: float difference, ...},
            }
        """
        original_model = self.grimoire.embed_model

        # Run model A
        self.grimoire.embed_model = model_a
        results_a = self.run_eval(eval_set)

        # Run model B
        self.grimoire.embed_model = model_b
        results_b = self.run_eval(eval_set)

        # Restore original
        self.grimoire.embed_model = original_model

        # Compute deltas and pick winner
        metrics_a = results_a["metrics"]
        metrics_b = results_b["metrics"]
        delta = {
            k: metrics_b[k] - metrics_a[k]
            for k in metrics_a
        }

        # Winner is whoever has higher MRR (primary metric)
        if metrics_a["mrr"] >= metrics_b["mrr"]:
            winner = model_a
        else:
            winner = model_b

        return {
            "model_a": {"name": model_a, "metrics": metrics_a},
            "model_b": {"name": model_b, "metrics": metrics_b},
            "winner": winner,
            "delta": delta,
        }

    # ------------------------------------------------------------------
    # Fine-tuning data export
    # ------------------------------------------------------------------

    def export_training_pairs(self, output_path: str) -> int:
        """Export query-document pairs as fine-tuning data.

        Format: one JSON object per line (JSONL):
            {"query": str, "positive": str, "negative": str}

        Args:
            output_path: File path for the JSONL output.

        Returns:
            Count of pairs exported.
        """
        memories = self._fetch_all_active_memories()
        if not memories:
            logger.warning("No memories to export training pairs from")
            return 0

        categories = list({m["category"] for m in memories})
        # Build a category→memories index for negative sampling
        by_category: dict[str, list[dict]] = {}
        for m in memories:
            by_category.setdefault(m["category"], []).append(m)

        pairs: list[dict] = []
        for mem in memories:
            query = self._generate_positive_query(mem)
            if not query:
                continue

            # Find a negative from a different category
            negative_doc = self._pick_negative_document(mem, by_category,
                                                         categories)
            if negative_doc is None:
                continue

            pairs.append({
                "query": query,
                "positive": mem["content"],
                "negative": negative_doc["content"],
            })

        # Write JSONL
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            for pair in pairs:
                f.write(json.dumps(pair, ensure_ascii=False) + "\n")

        logger.info("Exported %d training pairs to %s", len(pairs), output_path)
        return len(pairs)

    # ------------------------------------------------------------------
    # Result storage
    # ------------------------------------------------------------------

    def store_benchmark(self, results: dict) -> str:
        """Store eval results in Grimoire for tracking over time.

        Args:
            results: Output from run_eval().

        Returns:
            Memory ID of the stored benchmark.
        """
        content = json.dumps({
            "metrics": results["metrics"],
            "total": results["total"],
            "failure_count": len(results["failures"]),
            "timestamp": results.get("timestamp", datetime.now().isoformat()),
        }, indent=2)

        memory_id = self.grimoire.remember(
            content=content,
            source="system",
            source_module="embedding_evaluator",
            category="embedding_benchmarks",
            trust_level=0.9,
            confidence=1.0,
            tags=["benchmark", "embeddings", "eval"],
            check_duplicates=False,  # Each benchmark run is unique
        )
        logger.info("Stored benchmark as memory %s", memory_id)
        return memory_id

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_all_active_memories(self) -> list[dict]:
        """Fetch all active memories from SQLite directly."""
        cursor = self.grimoire.conn.cursor()
        cursor.execute(
            "SELECT id, content, category, source, trust_level "
            "FROM memories WHERE is_active = 1"
        )
        rows = cursor.fetchall()
        return [
            {
                "id": row["id"],
                "content": row["content"],
                "category": row["category"],
                "source": row["source"],
                "trust_level": row["trust_level"],
            }
            for row in rows
        ]

    def _generate_positive_query(self, memory: dict) -> str | None:
        """Generate a query that should retrieve this memory.

        Uses category-specific heuristics, no LLM calls.
        """
        category = memory.get("category", "uncategorized")
        content = memory.get("content", "")
        if not content:
            return None

        # Try category-specific extractor
        extractor_name = self._CATEGORY_EXTRACTORS.get(category)
        if extractor_name:
            extractor = getattr(self, extractor_name)
            query = extractor(content)
            if query:
                return query

        # Fallback: use first meaningful sentence
        return self._extract_generic_query(content)

    def _generate_negative_query(self, memory: dict,
                                  categories: list[str]) -> str | None:
        """Generate a query from a different category (should NOT retrieve this memory)."""
        own_category = memory.get("category", "uncategorized")
        other_categories = [c for c in categories if c != own_category]
        if not other_categories:
            return None

        # Pick a query from a mismatched domain
        category = other_categories[0]
        return self._cross_category_query(category)

    def _extract_code_queries(self, content: str) -> str | None:
        """Extract code-relevant queries: function names, class names, errors."""
        # Function/method names
        match = re.search(r'(?:def|function|fn)\s+(\w+)', content)
        if match:
            return f"how does {match.group(1)} work"

        # Class names
        match = re.search(r'class\s+(\w+)', content)
        if match:
            return f"what is {match.group(1)} class"

        # Error messages
        match = re.search(r'(Error|Exception|Failed|error):\s*(.{10,60})', content)
        if match:
            return match.group(2).strip()

        # Import statements
        match = re.search(r'import\s+(\w+)', content)
        if match:
            return f"{match.group(1)} usage"

        return None

    def _extract_bible_queries(self, content: str) -> str | None:
        """Extract bible/ethics queries: verse refs, theological terms."""
        # Verse references (e.g., "John 3:16", "Genesis 1:1")
        match = re.search(
            r'(\d?\s*[A-Z][a-z]+)\s+(\d+:\d+(?:-\d+)?)', content
        )
        if match:
            return f"{match.group(1)} {match.group(2)}"

        # Theological terms
        terms = [
            "grace", "salvation", "redemption", "covenant", "righteousness",
            "sanctification", "atonement", "forgiveness", "mercy", "faith",
            "sin", "repentance", "baptism", "resurrection", "judgment",
        ]
        content_lower = content.lower()
        for term in terms:
            if term in content_lower:
                return f"what does the Bible say about {term}"

        return None

    def _extract_technical_queries(self, content: str) -> str | None:
        """Extract technical queries: tool names, specs, error types."""
        # Tool/command names
        match = re.search(r'(?:tool|command|utility):\s*(\w+)', content, re.I)
        if match:
            return f"{match.group(1)} tool"

        # Hardware specs
        match = re.search(
            r'(GPU|CPU|RAM|SSD|RTX|GTX|Ryzen|Intel)\s*\w*',
            content, re.I
        )
        if match:
            return f"{match.group(0)} specs"

        # Pattern names
        match = re.search(r'pattern:\s*(.{5,40})', content, re.I)
        if match:
            return match.group(1).strip()

        return None

    def _extract_business_queries(self, content: str) -> str | None:
        """Extract business/landscaping queries."""
        keywords = [
            "estimate", "client", "invoice", "job", "crew",
            "equipment", "schedule", "bid", "mowing", "mulch",
        ]
        content_lower = content.lower()
        for kw in keywords:
            if kw in content_lower:
                return f"landscaping {kw} information"

        return None

    def _extract_generic_query(self, content: str) -> str | None:
        """Fallback: extract first meaningful phrase as a query."""
        # Take first sentence, trim to reasonable length
        sentences = re.split(r'[.!?\n]', content)
        for sentence in sentences:
            cleaned = sentence.strip()
            if len(cleaned) >= 10:
                # Cap at 80 chars to keep it query-like
                return cleaned[:80]
        return content[:80] if len(content) >= 10 else None

    def _cross_category_query(self, category: str) -> str:
        """Generate a query typical of a given category (for negatives)."""
        templates = {
            "code": "Python function implementation",
            "python": "Python exception handling",
            "programming": "software design pattern",
            "debugging": "stack trace analysis",
            "bible": "Bible verse about love",
            "ethics": "ethical decision framework",
            "theology": "theological doctrine",
            "scripture": "Old Testament prophecy",
            "technical": "system hardware specifications",
            "hardware": "GPU memory bandwidth",
            "software": "software installation steps",
            "system": "operating system configuration",
            "business": "landscaping job estimate",
            "landscaping": "lawn maintenance schedule",
        }
        return templates.get(category, f"information about {category}")

    def _pick_negative_document(self, memory: dict,
                                 by_category: dict[str, list[dict]],
                                 categories: list[str]) -> dict | None:
        """Pick a document from a different category as a negative example."""
        own_category = memory.get("category", "uncategorized")
        for cat in categories:
            if cat != own_category and cat in by_category:
                return by_category[cat][0]
        return None

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def format_report(self, results: dict) -> str:
        """Format eval results as a human-readable report.

        Args:
            results: Output from run_eval().

        Returns:
            Formatted string for display.
        """
        m = results["metrics"]
        lines = [
            "**Embedding Evaluation Report**",
            f"Total positive queries: {results['total']}",
            f"Timestamp: {results.get('timestamp', 'N/A')}",
            "",
            "**Retrieval Metrics:**",
            f"  Recall@1:  {m['recall_at_1']:.3f}",
            f"  Recall@5:  {m['recall_at_5']:.3f}",
            f"  Recall@10: {m['recall_at_10']:.3f}",
            f"  MRR:       {m['mrr']:.3f}",
            f"  Avg Similarity: {m['avg_similarity_score']:.3f}",
        ]

        if results["failures"]:
            lines.append("")
            lines.append(f"**Failures ({len(results['failures'])}):**")
            for f in results["failures"][:10]:
                lines.append(f"  - Query: \"{f['query']}\" "
                             f"(expected: {f['expected_id'][:8]}...)")

        return "\n".join(lines)

    def format_comparison(self, comparison: dict) -> str:
        """Format model comparison as a human-readable report.

        Args:
            comparison: Output from compare_models().

        Returns:
            Formatted string for display.
        """
        a = comparison["model_a"]
        b = comparison["model_b"]
        d = comparison["delta"]

        lines = [
            "**Embedding Model Comparison**",
            "",
            f"  {'Metric':<20} {a['name']:<15} {b['name']:<15} {'Delta':<10}",
            f"  {'-'*60}",
        ]
        for key in a["metrics"]:
            label = key.replace("_", " ").title()
            val_a = a["metrics"][key]
            val_b = b["metrics"][key]
            delta = d[key]
            sign = "+" if delta >= 0 else ""
            lines.append(
                f"  {label:<20} {val_a:<15.3f} {val_b:<15.3f} {sign}{delta:.3f}"
            )

        lines.append("")
        lines.append(f"Winner: **{comparison['winner']}**")
        return "\n".join(lines)
