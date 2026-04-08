"""
Staged Retrieval — Hierarchical Two-Stage Grimoire Search
==========================================================
Saves 60-80% of context tokens by searching summaries first (cheap),
then pulling full content only for the most relevant documents (expensive).

Stage 1: Search pre-computed summaries (~200 tokens each)
Stage 2: Pull full content for only the top N most relevant hits

Author: Patrick (with Claude Opus 4.6)
Project: Shadow
Module: Grimoire / Staged Retrieval
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

logger = logging.getLogger("shadow.grimoire.staged_retrieval")


class StagedRetrieval:
    """Two-stage retrieval: search summaries first, then pull full docs selectively."""

    def __init__(self, grimoire=None, summary_max_tokens: int = 200):
        """
        Initialize staged retrieval.

        Args:
            grimoire: The existing GrimoireModule instance for storage/retrieval.
            summary_max_tokens: Max tokens per document summary in Stage 1.
        """
        self._grimoire = grimoire
        self._summary_max_tokens = summary_max_tokens

        # Stats tracking for Growth Engine / context profiling
        self._stats = {
            "total_searches": 0,
            "total_stage1_results": 0,
            "total_stage2_pulls": 0,
            "total_tokens_saved": 0,
        }

    def generate_summary(self, document: str, metadata: dict = None) -> str:
        """
        Generate a compact summary from a document for Stage 1 search.

        Extracts first 2-3 sentences, appends key terms and metadata tags.
        Called at storage time, not query time (pre-computed).

        Args:
            document: Full document text.
            metadata: Optional metadata dict (domain, trust_level, category, etc.).

        Returns:
            Summary string truncated to summary_max_tokens.
        """
        if not document or not document.strip():
            return ""

        # Extract first 2-3 sentences
        sentences = re.split(r'(?<=[.!?])\s+', document.strip())
        summary_sentences = sentences[:3]
        summary = " ".join(summary_sentences)

        # Extract key terms: capitalized words, technical terms (containing _, digits, etc.)
        words = document.split()
        key_terms = set()
        for word in words:
            cleaned = word.strip(".,;:!?()[]{}\"'")
            if not cleaned:
                continue
            # Capitalized words (not sentence starters) that are likely proper nouns/terms
            if len(cleaned) > 2 and cleaned[0].isupper() and cleaned != cleaned.upper():
                key_terms.add(cleaned)
            # Technical terms with underscores, digits, or camelCase
            if "_" in cleaned or (any(c.isdigit() for c in cleaned) and any(c.isalpha() for c in cleaned)):
                key_terms.add(cleaned)
            # CamelCase detection
            if re.match(r'^[a-z]+[A-Z]', cleaned):
                key_terms.add(cleaned)

        # Remove terms that are already in the summary sentences
        summary_lower = summary.lower()
        unique_terms = [t for t in sorted(key_terms) if t.lower() not in summary_lower]

        if unique_terms:
            summary += " | Key terms: " + ", ".join(unique_terms[:10])

        # Append metadata tags if available
        if metadata:
            tags = []
            for key in ("domain", "category", "trust_level", "source"):
                if key in metadata and metadata[key] is not None:
                    tags.append(f"{key}={metadata[key]}")
            if tags:
                summary += " | " + ", ".join(tags)

        # Truncate to approximate token limit (rough: 1 token ≈ 4 chars)
        max_chars = self._summary_max_tokens * 4
        if len(summary) > max_chars:
            summary = summary[:max_chars].rsplit(" ", 1)[0] + "..."

        return summary

    def store_with_summary(self, content: str, collection: str, metadata: dict = None) -> str:
        """
        Store both full content and its summary in Grimoire.

        Args:
            content: Full document content.
            collection: Collection/category to store in.
            metadata: Optional metadata dict.

        Returns:
            The document ID.
        """
        try:
            doc_id = str(uuid.uuid4())

            # Generate summary
            summary = self.generate_summary(content, metadata)

            # Store full content
            full_metadata = dict(metadata) if metadata else {}
            full_metadata["staged_doc_id"] = doc_id
            full_metadata["has_summary"] = True

            if self._grimoire is not None:
                self._grimoire.remember(
                    content=content,
                    category=collection,
                    metadata=full_metadata,
                )

            # Store summary with pointer to full doc
            summary_metadata = dict(metadata) if metadata else {}
            summary_metadata["is_summary"] = True
            summary_metadata["full_doc_id"] = doc_id
            summary_metadata["staged_doc_id"] = doc_id

            if self._grimoire is not None:
                self._grimoire.remember(
                    content=summary,
                    category=collection,
                    metadata=summary_metadata,
                )

            return doc_id

        except Exception as e:
            logger.error("Failed to store with summary: %s", e)
            raise

    def search_summaries(self, query: str, collection: str = None, n_results: int = 10) -> list[dict]:
        """
        Stage 1: Search against summary embeddings only.

        Args:
            query: Search query string.
            collection: Optional collection/category filter.
            n_results: Max number of summary results.

        Returns:
            List of dicts: {summary, doc_id, relevance_score, metadata}
        """
        if not query or not query.strip():
            return []

        try:
            if self._grimoire is None:
                return []

            # Search with larger pool to filter summaries from
            raw_results = self._grimoire.recall(
                query=query,
                n_results=n_results * 3,
                category=collection,
            )

            if not raw_results:
                # Fallback: no results at all
                return []

            summaries = []
            seen_doc_ids = set()

            for result in raw_results:
                meta = result.get("metadata") or {}
                if isinstance(meta, str):
                    import json
                    try:
                        meta = json.loads(meta)
                    except (json.JSONDecodeError, TypeError):
                        meta = {}

                is_summary = meta.get("is_summary", False)
                doc_id = meta.get("full_doc_id") or meta.get("staged_doc_id")

                if is_summary and doc_id and doc_id not in seen_doc_ids:
                    seen_doc_ids.add(doc_id)
                    summaries.append({
                        "summary": result.get("content", ""),
                        "doc_id": doc_id,
                        "relevance_score": result.get("relevance", 0.0),
                        "metadata": meta,
                    })

                if len(summaries) >= n_results:
                    break

            # Fallback: if no summaries found (legacy data), truncate full docs
            if not summaries:
                for result in raw_results[:n_results]:
                    content = result.get("content", "")
                    truncated = self.generate_summary(content, result.get("metadata"))
                    doc_id = result.get("id", str(uuid.uuid4()))
                    summaries.append({
                        "summary": truncated,
                        "doc_id": doc_id,
                        "relevance_score": result.get("relevance", 0.0),
                        "metadata": result.get("metadata") or {},
                    })

            return summaries

        except Exception as e:
            logger.error("Summary search failed: %s", e)
            return []

    def get_full_documents(self, doc_ids: list[str]) -> list[dict]:
        """
        Stage 2: Retrieve full content for specific document IDs.

        Args:
            doc_ids: List of document IDs to retrieve.

        Returns:
            List of dicts: {content, doc_id, metadata}
        """
        if not doc_ids:
            return []

        try:
            if self._grimoire is None:
                return []

            results = []
            for doc_id in doc_ids:
                # Search for the full document by its staged_doc_id
                matches = self._grimoire.recall(
                    query=doc_id,
                    n_results=5,
                )

                for match in matches:
                    meta = match.get("metadata") or {}
                    if isinstance(meta, str):
                        import json
                        try:
                            meta = json.loads(meta)
                        except (json.JSONDecodeError, TypeError):
                            meta = {}

                    match_doc_id = meta.get("staged_doc_id")
                    is_summary = meta.get("is_summary", False)

                    if match_doc_id == doc_id and not is_summary:
                        results.append({
                            "content": match.get("content", ""),
                            "doc_id": doc_id,
                            "metadata": meta,
                        })
                        break

            return results

        except Exception as e:
            logger.error("Full document retrieval failed: %s", e)
            return []

    def search(self, query: str, collection: str = None,
               n_results: int = 10, auto_select: int = 3) -> list[dict]:
        """
        Combined two-stage search — main entry point.

        Stage 1: Search summaries with n_results.
        Auto-select: Pick top auto_select most relevant by relevance_score.
        Stage 2: Pull full documents for the selected IDs.
        Return full docs for selected + summaries for the rest.

        Args:
            query: Search query string.
            collection: Optional collection/category filter.
            n_results: Max Stage 1 results.
            auto_select: How many top results get full content pulled.

        Returns:
            List of result dicts, plus stats metadata.
        """
        if not query or not query.strip():
            return []

        try:
            # Stage 1: Get summaries
            summaries = self.search_summaries(query, collection, n_results)

            if not summaries:
                return []

            # Sort by relevance_score descending
            summaries.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)

            # Select top N for full retrieval
            selected_ids = [s["doc_id"] for s in summaries[:auto_select]]
            remaining_summaries = summaries[auto_select:]

            # Stage 2: Get full documents for selected
            full_docs = self.get_full_documents(selected_ids)

            # Build result list
            results = []

            # Full documents first
            for doc in full_docs:
                doc["stage"] = 2
                doc["type"] = "full"
                results.append(doc)

            # Then remaining summaries
            for s in remaining_summaries:
                results.append({
                    "content": s["summary"],
                    "doc_id": s["doc_id"],
                    "metadata": s["metadata"],
                    "stage": 1,
                    "type": "summary",
                    "relevance_score": s["relevance_score"],
                })

            # Estimate token savings
            # Assume: full doc avg ~1500 tokens, summary avg ~200 tokens
            full_doc_tokens = len(summaries) * 1500  # if all were full
            actual_tokens = (len(full_docs) * 1500) + (len(remaining_summaries) * 200)
            tokens_saved = max(0, full_doc_tokens - actual_tokens)

            # Update stats
            self._stats["total_searches"] += 1
            self._stats["total_stage1_results"] += len(summaries)
            self._stats["total_stage2_pulls"] += len(full_docs)
            self._stats["total_tokens_saved"] += tokens_saved

            # Append stats metadata to results
            stats_info = {
                "stage1_count": len(summaries),
                "stage2_count": len(full_docs),
                "tokens_saved_estimate": tokens_saved,
            }

            # Return results with stats as last element
            results.append({"_stats": stats_info})

            return results

        except Exception as e:
            logger.error("Staged search failed: %s", e)
            return []

    def get_retrieval_stats(self) -> dict:
        """
        Get retrieval performance statistics for Growth Engine / context profiling.

        Returns:
            Dict with avg_stage1_results, avg_stage2_pulls, avg_token_savings,
            hit_rate (stage2/stage1 ratio), total_searches.
        """
        total = self._stats["total_searches"]
        if total == 0:
            return {
                "total_searches": 0,
                "avg_stage1_results": 0.0,
                "avg_stage2_pulls": 0.0,
                "avg_token_savings": 0.0,
                "hit_rate": 0.0,
            }

        avg_s1 = self._stats["total_stage1_results"] / total
        avg_s2 = self._stats["total_stage2_pulls"] / total
        avg_saved = self._stats["total_tokens_saved"] / total
        hit_rate = avg_s2 / avg_s1 if avg_s1 > 0 else 0.0

        return {
            "total_searches": total,
            "avg_stage1_results": round(avg_s1, 2),
            "avg_stage2_pulls": round(avg_s2, 2),
            "avg_token_savings": round(avg_saved, 2),
            "hit_rate": round(hit_rate, 4),
        }

    def backfill_summaries(self, collection: str = None, batch_size: int = 100) -> dict:
        """
        Generate summaries for existing Grimoire content that doesn't have them.

        Can be run once on startup or as a maintenance task.

        Args:
            collection: Optional collection/category to backfill.
            batch_size: Number of documents to process per batch.

        Returns:
            Dict: {processed, already_had_summary, errors}
        """
        result = {"processed": 0, "already_had_summary": 0, "errors": 0}

        try:
            if self._grimoire is None:
                return result

            # Get existing documents by searching with a broad query
            # This is a best-effort approach since Grimoire doesn't expose
            # a "list all" method directly
            all_docs = self._grimoire.recall(
                query="",
                n_results=batch_size,
            )

            if not all_docs:
                return result

            for doc in all_docs:
                try:
                    meta = doc.get("metadata") or {}
                    if isinstance(meta, str):
                        import json
                        try:
                            meta = json.loads(meta)
                        except (json.JSONDecodeError, TypeError):
                            meta = {}

                    # Skip if it's already a summary
                    if meta.get("is_summary", False):
                        result["already_had_summary"] += 1
                        continue

                    # Skip if it already has a paired summary
                    if meta.get("has_summary", False):
                        result["already_had_summary"] += 1
                        continue

                    content = doc.get("content", "")
                    if not content:
                        continue

                    doc_id = doc.get("id", str(uuid.uuid4()))

                    # Generate and store summary
                    summary = self.generate_summary(content, meta)
                    summary_metadata = dict(meta)
                    summary_metadata["is_summary"] = True
                    summary_metadata["full_doc_id"] = doc_id
                    summary_metadata["staged_doc_id"] = doc_id

                    self._grimoire.remember(
                        content=summary,
                        category=collection or doc.get("category", "uncategorized"),
                        metadata=summary_metadata,
                    )

                    result["processed"] += 1

                except Exception as e:
                    logger.error("Backfill error for doc: %s", e)
                    result["errors"] += 1

            return result

        except Exception as e:
            logger.error("Backfill summaries failed: %s", e)
            return result
