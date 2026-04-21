"""
EntityExtractor — Rule-Based Entity & Relationship Extraction
================================================================
Extracts entities and relationships from text for graph storage.
Uses rule-based extraction (no LLM calls) for speed.

Phase 1: pattern matching against known entity lists + simple NER heuristics.
Phase 2 (future): optional LLM-based extraction for higher recall.

Author: Patrick (with Claude Opus 4.6)
Module: Grimoire sub-component
"""

from __future__ import annotations

import re
import logging

logger = logging.getLogger("grimoire.extractor")

# =============================================================================
# Known entity lists — hardcoded for speed
# =============================================================================

# Shadow's 13 modules
_KNOWN_MODULES: dict[str, str] = {
    "shadow": "module",
    "wraith": "module",
    "cerberus": "module",
    "apex": "module",
    "grimoire": "module",
    "sentinel": "module",
    "harbinger": "module",
    "reaper": "module",
    "cipher": "module",
    "omen": "module",
    "nova": "module",
    "morpheus": "module",
}

# Technologies Shadow uses or might reference
_KNOWN_TECHNOLOGIES: dict[str, str] = {
    "python": "technology",
    "ollama": "technology",
    "chromadb": "technology",
    "kuzu": "technology",
    "sqlite": "technology",
    "langchain": "technology",
    "langgraph": "technology",
    "pytorch": "technology",
    "cuda": "technology",
    "gemma": "technology",
    "qwen": "technology",
    "playwright": "technology",
    "fastapi": "technology",
    "react": "technology",
    "tailwind": "technology",
    "electron": "technology",
    "langfuse": "technology",
    "docker": "technology",
    "linux": "technology",
    "ubuntu": "technology",
    "windows": "technology",
}

# Known people — always entity_type=person
_KNOWN_PEOPLE: dict[str, str] = {
    "master morstad": "person",
}

# Merge all known entities into one lookup (lowercase key → type)
_ALL_KNOWN: dict[str, str] = {}
_ALL_KNOWN.update(_KNOWN_MODULES)
_ALL_KNOWN.update(_KNOWN_TECHNOLOGIES)
_ALL_KNOWN.update(_KNOWN_PEOPLE)

# =============================================================================
# Relationship patterns — regex-based extraction
# =============================================================================
# Each pattern: (compiled_regex, relation_type, source_group, target_group)
# Groups are named 'src' and 'tgt' in the regex.

_RELATIONSHIP_PATTERNS: list[tuple[re.Pattern, str]] = [
    # "X uses Y", "X is using Y"
    (re.compile(
        r'\b(?P<src>[A-Za-z_][\w]*)\s+(?:uses|is\s+using|utilizes)\s+(?P<tgt>[A-Za-z_][\w]*)\b',
        re.IGNORECASE,
    ), "uses"),

    # "X depends on Y", "X requires Y"
    (re.compile(
        r'\b(?P<src>[A-Za-z_][\w]*)\s+(?:depends\s+on|requires|needs)\s+(?P<tgt>[A-Za-z_][\w]*)\b',
        re.IGNORECASE,
    ), "depends_on"),

    # "X created by Y"
    (re.compile(
        r'\b(?P<tgt>[A-Za-z_][\w]*)\s+(?:created|built|made|written)\s+by\s+(?P<src>[A-Za-z_][\w]*)\b',
        re.IGNORECASE,
    ), "created_by"),

    # "X replaces Y", "X supersedes Y"
    (re.compile(
        r'\b(?P<src>[A-Za-z_][\w]*)\s+(?:replaces|supersedes|succeeds)\s+(?P<tgt>[A-Za-z_][\w]*)\b',
        re.IGNORECASE,
    ), "supersedes"),

    # "X contradicts Y", "X conflicts with Y"
    (re.compile(
        r'\b(?P<src>[A-Za-z_][\w]*)\s+(?:contradicts|conflicts?\s+with)\s+(?P<tgt>[A-Za-z_][\w]*)\b',
        re.IGNORECASE,
    ), "contradicts"),

    # "X part of Y", "X belongs to Y"
    (re.compile(
        r'\b(?P<src>[A-Za-z_][\w]*)\s+(?:(?:is\s+)?part\s+of|belongs?\s+to)\s+(?P<tgt>[A-Za-z_][\w]*)\b',
        re.IGNORECASE,
    ), "part_of"),

    # "X implements Y"
    (re.compile(
        r'\b(?P<src>[A-Za-z_][\w]*)\s+implements\s+(?P<tgt>[A-Za-z_][\w]*)\b',
        re.IGNORECASE,
    ), "implements"),

    # "X improves Y", "X enhances Y"
    (re.compile(
        r'\b(?P<src>[A-Za-z_][\w]*)\s+(?:improves|enhances|upgrades)\s+(?P<tgt>[A-Za-z_][\w]*)\b',
        re.IGNORECASE,
    ), "improves"),

    # "X related to Y"
    (re.compile(
        r'\b(?P<src>[A-Za-z_][\w]*)\s+(?:is\s+)?related\s+to\s+(?P<tgt>[A-Za-z_][\w]*)\b',
        re.IGNORECASE,
    ), "related_to"),

    # "X learned from Y"
    (re.compile(
        r'\b(?P<src>[A-Za-z_][\w]*)\s+(?:learned|learnt)\s+from\s+(?P<tgt>[A-Za-z_][\w]*)\b',
        re.IGNORECASE,
    ), "learned_from"),
]

# Sentence splitter — split on . ! ? followed by space or end
_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+')

# Capitalized proper noun pattern — 2+ consecutive capitalized words
_PROPER_NOUN = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b')

# Common words that shouldn't start a proper noun entity name
_LEADING_ARTICLES = {"the", "a", "an", "this", "that", "these", "those"}


class EntityExtractor:
    """Extracts entities and relationships from text for graph storage.

    Uses rule-based extraction (no LLM calls) for speed.
    LLM-based extraction available as optional upgrade path.
    """

    def extract_entities(
        self,
        text: str,
        source_memory_id: str,
    ) -> list[dict]:
        """Extract entities from text using known lists + heuristics.

        Scans for:
        1. Known Shadow module names (case-insensitive)
        2. Known technology names (case-insensitive)
        3. Known people (case-insensitive)
        4. Capitalized proper nouns (2+ consecutive capitalized words)

        Args:
            text: The text to extract entities from.
            source_memory_id: UUID of the memory being processed.

        Returns:
            List of dicts with keys: name, entity_type, confidence,
            source_memory_id. Deduplicated by name.
        """
        if not text or not text.strip():
            return []

        found: dict[str, dict] = {}  # name -> entity dict (dedup)
        text_lower = text.lower()

        # --- Pass 1: Known entities (high confidence) ---
        for known_name, entity_type in _ALL_KNOWN.items():
            # Use word boundary check for single-word entities
            # For multi-word (e.g., "master morstad"), just check substring
            if " " in known_name:
                if known_name in text_lower:
                    found[known_name] = {
                        "name": known_name,
                        "entity_type": entity_type,
                        "confidence": 0.9,
                        "source_memory_id": source_memory_id,
                    }
            else:
                # Word boundary match to avoid "react" matching "reactive"
                pattern = rf'\b{re.escape(known_name)}\b'
                if re.search(pattern, text_lower):
                    found[known_name] = {
                        "name": known_name,
                        "entity_type": entity_type,
                        "confidence": 0.9,
                        "source_memory_id": source_memory_id,
                    }

        # --- Pass 2: Capitalized proper nouns (lower confidence) ---
        for match in _PROPER_NOUN.finditer(text):
            name = match.group(1)
            # Strip leading articles ("The Quick Fox" → "Quick Fox")
            words = name.split()
            while words and words[0].lower() in _LEADING_ARTICLES:
                words.pop(0)
            if len(words) < 2:
                continue  # Need at least 2 words after stripping
            name = " ".join(words)
            name_lower = name.lower()
            # Skip if already found as a known entity
            if name_lower in found:
                continue
            found[name_lower] = {
                "name": name_lower,
                "entity_type": "concept",
                "confidence": 0.5,
                "source_memory_id": source_memory_id,
            }

        return list(found.values())

    def extract_relationships(
        self,
        text: str,
        entities: list[dict],
    ) -> list[dict]:
        """Extract relationships between entities from text.

        Uses two strategies:
        1. Pattern matching for explicit relationship keywords
        2. Proximity: entities in the same sentence → related_to (low conf)

        Args:
            text: The text to analyze.
            entities: List of entity dicts (from extract_entities).

        Returns:
            List of dicts with keys: source, target, relation_type,
            confidence. Deduplicated by (source, target, relation_type).
        """
        if not text or not entities or len(entities) < 2:
            return []

        entity_names = {e["name"] for e in entities}
        found: dict[tuple, dict] = {}  # (src, tgt, type) -> relationship dict

        # --- Pass 1: Pattern-based relationships ---
        for pattern, rel_type in _RELATIONSHIP_PATTERNS:
            for match in pattern.finditer(text):
                src = match.group("src").lower()
                tgt = match.group("tgt").lower()
                # Only keep if both endpoints are known entities
                if src in entity_names and tgt in entity_names and src != tgt:
                    key = (src, tgt, rel_type)
                    if key not in found:
                        found[key] = {
                            "source": src,
                            "target": tgt,
                            "relation_type": rel_type,
                            "confidence": 0.7,
                        }

        # --- Pass 2: Proximity-based (same sentence → related_to) ---
        sentences = _SENTENCE_SPLIT.split(text)
        for sentence in sentences:
            sentence_lower = sentence.lower()
            entities_in_sentence = [
                e["name"] for e in entities
                if e["name"] in sentence_lower
            ]
            # Create related_to edges between all pairs in the sentence
            for i, src in enumerate(entities_in_sentence):
                for tgt in entities_in_sentence[i + 1:]:
                    if src == tgt:
                        continue
                    key = (src, tgt, "related_to")
                    rev_key = (tgt, src, "related_to")
                    # Don't overwrite a stronger relationship or duplicate
                    if key not in found and rev_key not in found:
                        # Don't add proximity if a pattern match already
                        # exists between these two entities
                        has_explicit = any(
                            k[0] == src and k[1] == tgt or
                            k[0] == tgt and k[1] == src
                            for k in found
                        )
                        if not has_explicit:
                            found[key] = {
                                "source": src,
                                "target": tgt,
                                "relation_type": "related_to",
                                "confidence": 0.3,
                            }

        return list(found.values())

    def extract_from_memory(
        self,
        memory_content: str,
        memory_id: str,
        collection: str,
    ) -> tuple[list[dict], list[dict]]:
        """Convenience: extract both entities and relationships.

        Args:
            memory_content: The text content of the memory.
            memory_id: UUID of the memory.
            collection: Collection/category name (unused in Phase 1,
                        reserved for future collection-specific rules).

        Returns:
            Tuple of (entities, relationships).
        """
        entities = self.extract_entities(memory_content, memory_id)
        relationships = self.extract_relationships(memory_content, entities)
        return entities, relationships
