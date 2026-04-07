"""
EthicsEngine — Biblical ethics integration for Cerberus.

Provides Scripture-backed ethical guidance by combining:
1. Fast-path lookup: keyword matching against curated ethical topics
2. Semantic search: vector similarity against ESV pericopes in ChromaDB
3. Study notes: structured SQLite queries for scholarly commentary

The ethics engine is ADVISORY ONLY — it never overrides Cerberus hard limits.
If any component fails, it degrades gracefully and returns empty results.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("shadow.cerberus.ethics")

# Keywords that map to ethical categories for extraction from action text
ETHICAL_KEYWORDS = {
    "honesty": ["lie", "lying", "deceive", "deception", "deceptive", "fake", "false",
                 "mislead", "fabricate", "dishonest", "truth", "honest", "integrity",
                 "transparent"],
    "stewardship": ["waste", "resource", "manage", "responsible", "careful",
                     "efficient", "accountable", "steward"],
    "privacy": ["privacy", "private", "personal data", "confidential", "secret",
                 "surveillance", "tracking", "expose", "leak", "snoop"],
    "justice": ["fair", "unfair", "bias", "discriminat", "oppress", "exploit",
                "equal", "rights", "justice", "equity"],
    "humility": ["arrogant", "pride", "humble", "uncertain", "limitation",
                  "wisdom", "defer", "acknowledge"],
    "protection": ["harm", "danger", "vulnerable", "defend", "protect", "safety",
                    "shield", "guard", "risk"],
    "diligence": ["lazy", "sloppy", "thorough", "excellence", "quality",
                   "careful", "diligent", "effort", "hardworking"],
    "stealing": ["steal", "theft", "pirate", "piracy", "plagiar", "copy without",
                  "take without", "unauthorized"],
}


@dataclass
class EthicsResult:
    """Result of an ethics engine evaluation."""
    action: str
    ethical_category: str | None
    relevant_passages: list[dict] = field(default_factory=list)
    study_notes: list[dict] = field(default_factory=list)
    assessment: str = ""
    recommendation: str = "APPROVE"  # APPROVE | BLOCK | DEFER
    confidence: float = 0.0


class EthicsEngine:
    """Biblical ethics engine for Cerberus safety evaluations.

    Combines fast-path keyword lookup with semantic vector search
    against stored ESV Bible passages and study notes.
    """

    def __init__(
        self,
        db_path: str | Path = "data/memory/shadow_memory.db",
        vector_path: str | Path = "data/vectors",
        ethical_topics_file: str | Path = "config/ethical_topics.yaml",
        ollama_url: str = "http://localhost:11434",
        embed_model: str = "nomic-embed-text",
    ) -> None:
        self._db_path = Path(db_path)
        self._vector_path = Path(vector_path)
        self._ollama_url = ollama_url
        self._embed_model = embed_model
        self._topics: list[dict[str, Any]] = []
        self._chroma_client = None
        self._pericope_collection = None
        self._studynote_collection = None

        # Load ethical topics
        self.load_ethical_topics(Path(ethical_topics_file))

        # Initialize ChromaDB connection
        self._init_chromadb()

    def load_ethical_topics(self, path: Path) -> None:
        """Read ethical topics from YAML config."""
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                self._topics = data.get("topics", [])
                logger.info("EthicsEngine loaded %d ethical topics", len(self._topics))
            else:
                logger.warning("Ethical topics file not found: %s", path)
                self._topics = []
        except Exception as e:
            logger.error("Failed to load ethical topics: %s", e)
            self._topics = []

    def _init_chromadb(self) -> None:
        """Initialize ChromaDB client and get ESV collections."""
        try:
            import chromadb
            self._chroma_client = chromadb.PersistentClient(path=str(self._vector_path))
            self._pericope_collection = self._chroma_client.get_collection("esv_pericopes")
            self._studynote_collection = self._chroma_client.get_collection("esv_studynotes")
            logger.info("EthicsEngine connected to ChromaDB ESV collections")
        except Exception as e:
            logger.warning("EthicsEngine ChromaDB unavailable: %s", e)
            self._chroma_client = None
            self._pericope_collection = None
            self._studynote_collection = None

    def fast_path_lookup(self, topic: str) -> list[dict[str, Any]]:
        """Keyword match against curated ethical topics.

        Uses the same matching logic as Cerberus.lookup_ethical_guidance():
        searches topic names, descriptions, and keyword lists.

        Args:
            topic: The ethical concept to look up.

        Returns:
            List of {ref, summary, weight} dicts sorted by weight descending.
        """
        topic_lower = topic.lower()
        results: list[dict[str, Any]] = []

        for entry in self._topics:
            matched = False

            if topic_lower in entry.get("name", "").lower():
                matched = True

            if not matched and topic_lower in entry.get("description", "").lower():
                matched = True

            if not matched:
                for keyword in entry.get("keywords", []):
                    kw = str(keyword).lower()
                    if topic_lower in kw or kw in topic_lower:
                        matched = True
                        break

            if matched:
                for ref in entry.get("references", []):
                    results.append({
                        "ref": ref["ref"],
                        "summary": ref["summary"],
                        "weight": ref["weight"],
                        "category": entry["name"],
                    })

        results.sort(key=lambda r: r["weight"], reverse=True)
        return results

    def _get_embedding(self, text: str) -> list[float] | None:
        """Get embedding vector from Ollama. Returns None on failure."""
        try:
            import requests
            response = requests.post(
                f"{self._ollama_url}/api/embeddings",
                json={"model": self._embed_model, "prompt": text[:2000]},
                timeout=30,
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except Exception as e:
            logger.warning("EthicsEngine embedding failed: %s", e)
            return None

    def semantic_scripture_search(
        self, query: str, top_k: int = 5
    ) -> list[dict[str, Any]]:
        """Search ESV pericopes by semantic similarity.

        Args:
            query: Natural language query.
            top_k: Number of results to return.

        Returns:
            List of passage dicts with text and metadata. Empty on failure.
        """
        if not self._pericope_collection:
            return []

        try:
            embedding = self._get_embedding(query)
            if not embedding:
                return []

            results = self._pericope_collection.query(
                query_embeddings=[embedding],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )

            passages = []
            if results and results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    meta = results["metadatas"][0][i] if results["metadatas"] else {}
                    distance = results["distances"][0][i] if results["distances"] else 1.0
                    passages.append({
                        "text": doc[:500],  # Truncate for context blocks
                        "book": meta.get("book_name", ""),
                        "chapter": meta.get("chapter", 0),
                        "verse_start": meta.get("verse_start", 0),
                        "verse_end": meta.get("verse_end", 0),
                        "section_heading": meta.get("section_heading", ""),
                        "similarity": round(1 - distance, 4),
                    })
            return passages

        except Exception as e:
            logger.warning("EthicsEngine semantic search failed: %s", e)
            return []

    def _get_study_notes(
        self, book_name: str, chapter: int, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Fetch study notes from SQLite for a given book and chapter.

        Args:
            book_name: Bible book name (e.g., "Proverbs").
            chapter: Chapter number.
            limit: Max notes to return.

        Returns:
            List of study note dicts. Empty on failure.
        """
        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT book_name, chapter, verse_range, note_text, note_type "
                "FROM esv_studynotes WHERE book_name = ? AND chapter = ? LIMIT ?",
                (book_name, chapter, limit),
            )
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.warning("EthicsEngine study notes query failed: %s", e)
            return []

    def _extract_ethical_keywords(self, text: str) -> list[str]:
        """Extract ethical category keywords from action/plan text."""
        text_lower = text.lower()
        matched_categories = []

        for category, keywords in ETHICAL_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    matched_categories.append(category)
                    break

        return matched_categories

    def build_ethics_context(self, action_description: str) -> dict[str, Any]:
        """Combine fast-path + semantic search into a formatted context block.

        Args:
            action_description: Description of the action being evaluated.

        Returns:
            Dict with fast_path, semantic, and study_notes results.
        """
        context: dict[str, Any] = {
            "fast_path": [],
            "semantic": [],
            "study_notes": [],
            "categories_matched": [],
        }

        # Extract ethical keywords from action
        categories = self._extract_ethical_keywords(action_description)
        context["categories_matched"] = categories

        # Fast-path lookup for each matched category
        for category in categories:
            refs = self.fast_path_lookup(category)
            context["fast_path"].extend(refs)

        # Semantic search against ESV pericopes
        if action_description.strip():
            context["semantic"] = self.semantic_scripture_search(action_description)

        # Fetch study notes for top semantic results
        seen_chapters = set()
        for passage in context["semantic"][:3]:
            book = passage.get("book", "")
            chapter = passage.get("chapter", 0)
            key = (book, chapter)
            if book and chapter and key not in seen_chapters:
                seen_chapters.add(key)
                notes = self._get_study_notes(book, chapter, limit=2)
                context["study_notes"].extend(notes)

        return context

    def evaluate_action(self, action: str, plan: str) -> EthicsResult:
        """Full ethics evaluation pipeline.

        Args:
            action: The tool or action being taken.
            plan: Description of what the action does.

        Returns:
            EthicsResult with assessment and recommendation.
        """
        combined_text = f"{action} {plan}"

        # Extract ethical categories
        categories = self._extract_ethical_keywords(combined_text)
        primary_category = categories[0] if categories else None

        # Fast-path lookup
        fast_path_refs = []
        for category in categories:
            fast_path_refs.extend(self.fast_path_lookup(category))

        # Semantic search
        semantic_results = self.semantic_scripture_search(combined_text)

        # Study notes from top semantic hits
        study_notes: list[dict] = []
        seen_chapters: set[tuple[str, int]] = set()
        for passage in semantic_results[:3]:
            book = passage.get("book", "")
            chapter = passage.get("chapter", 0)
            key = (book, chapter)
            if book and chapter and key not in seen_chapters:
                seen_chapters.add(key)
                study_notes.extend(self._get_study_notes(book, chapter, limit=2))

        # Build assessment
        if not categories:
            assessment = "No specific ethical concerns identified for this action."
            recommendation = "APPROVE"
            confidence = 0.3
        elif primary_category in ("stealing", "honesty"):
            # Strong biblical prohibitions
            ref_text = "; ".join(r["ref"] for r in fast_path_refs[:3])
            assessment = (
                f"Action touches '{primary_category}' — a clear biblical concern. "
                f"Relevant Scripture: {ref_text}. Review recommended."
            )
            recommendation = "DEFER"
            confidence = 0.8
        else:
            ref_text = "; ".join(r["ref"] for r in fast_path_refs[:3])
            assessment = (
                f"Action relates to '{primary_category}'. "
                f"Biblical guidance available: {ref_text}."
            )
            recommendation = "APPROVE"
            confidence = 0.5

        return EthicsResult(
            action=action,
            ethical_category=primary_category,
            relevant_passages=fast_path_refs + [
                {"ref": f"{p['book']} {p['chapter']}:{p['verse_start']}-{p['verse_end']}",
                 "summary": p["section_heading"],
                 "text_excerpt": p["text"][:200]}
                for p in semantic_results
            ],
            study_notes=study_notes,
            assessment=assessment,
            recommendation=recommendation,
            confidence=confidence,
        )
