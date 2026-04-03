"""
Grimoire — Shadow's Memory System
===================================
This is Shadow's long-term memory. Everything Shadow learns, every conversation,
every correction, every piece of research gets stored here and can be retrieved
by meaning (semantic search), not just by exact keywords.

HOW IT WORKS:
    1. Something worth remembering happens (conversation, research, user correction)
    2. Grimoire generates an embedding (a list of numbers that captures the MEANING)
    3. The memory gets stored in TWO places:
       - SQLite: full text + all metadata (dates, trust, category, access count)
       - ChromaDB: the embedding vector for semantic search
    4. When Shadow needs to remember something, it embeds the query and finds
       the closest matching memories by meaning
    5. Results come back ranked by relevance AND trust level

TRUST LEVELS (higher = more reliable):
    1.0 = User correction (the creator said "this is wrong, here's what's right")
    0.9 = User-stated fact ("I live in [city]", "My business uses LMN")
    0.8 = Verified research (multiple sources confirmed)
    0.5 = Conversation context (things discussed but not explicitly verified)
    0.3 = Single-source web content (one article, not cross-checked)
    0.0 = Morpheus speculation (creative output, NOT verified)

DESIGNED FOR:
    - Windows development (now) → Ubuntu production (later)
    - Learning Python (every line commented)
    - Ollama with nomic-embed-text for embeddings
    - Incremental building (this is v1 — we add features over time)

Author: Patrick (with Claude Opus 4.6)
Project: Shadow
Module: Grimoire (Module #4 in Shadow's architecture)
"""

import sqlite3                  # Built-in Python database — no install needed
import json                     # For converting Python dicts to/from JSON strings
import uuid                     # Generates unique IDs for each memory
from datetime import datetime   # Timestamps for everything
from pathlib import Path        # Cross-platform file paths (Windows + Linux)
import requests                 # HTTP calls to Ollama API (pip install requests)
import chromadb                 # Vector database for semantic search (pip install chromadb)


# =============================================================================
# TRUST LEVEL CONSTANTS
# =============================================================================
# These are named constants so we don't have magic numbers scattered in the code.
# When you see TRUST_USER_CORRECTION in the code, you know exactly what it means.

TRUST_USER_CORRECTION = 1.0    # Creator said "this is right" — highest possible
TRUST_USER_STATED = 0.9        # Creator directly stated a fact about themselves
TRUST_OFFICIAL_SOURCE = 0.7    # Official docs, .gov, .edu, peer-reviewed research
TRUST_ESTABLISHED = 0.5        # Established journalism, reputable news/industry sites
TRUST_COMMUNITY = 0.3          # Reddit, Stack Overflow, forums, community sources
TRUST_UNVERIFIED = 0.1         # Random blogs, SEO content, unverified web scraping
TRUST_MORPHEUS = 0.0           # Speculative/creative — NOT factual

# Aliases for backward compatibility and readability in different contexts
TRUST_VERIFIED_RESEARCH = TRUST_OFFICIAL_SOURCE  # Alias
TRUST_CONVERSATION = TRUST_ESTABLISHED            # Conversations = medium trust
TRUST_SINGLE_SOURCE = TRUST_COMMUNITY             # Single unverified source


# =============================================================================
# SOURCE TYPE CONSTANTS
# =============================================================================
# Where the memory came from. Used for filtering and the pointer index.

SOURCE_CONVERSATION = "conversation"       # From talking with the creator
SOURCE_USER_CORRECTION = "user_correction" # Creator corrected something
SOURCE_USER_STATED = "user_stated"         # Creator told Shadow a fact
SOURCE_RESEARCH = "research"               # Reaper found this online
SOURCE_REDDIT = "reddit"                   # From Reddit monitoring
SOURCE_YOUTUBE = "youtube"                 # From YouTube transcription
SOURCE_BROWSING = "browsing_history"       # From browser history analysis
SOURCE_MORPHEUS = "morpheus_speculative"   # Creative/speculative output
SOURCE_SYSTEM = "system"                   # Shadow's own operational data


class Grimoire:
    """
    Shadow's memory system — stores, searches, corrects, and manages all knowledge.
    
    Think of Grimoire as two systems working together:
        SQLite = A filing cabinet with labeled folders. You can find things by
                 date, category, trust level, or any other label.
        ChromaDB = A librarian who understands what you MEAN. You ask 
                   "that pricing thing from last week" and it finds the right memory
                   even though those exact words aren't in it.
    
    Usage:
        grimoire = Grimoire()
        
        # Store a memory
        memory_id = grimoire.remember("Shadow uses Ollama for local model serving")
        
        # Find memories by meaning
        results = grimoire.recall("what model runtime does Shadow use?")
        
        # Correct a memory (highest trust)
        grimoire.correct(memory_id, "Shadow uses Ollama 0.5.x for local model serving")
        
        # Get lightweight context for prompts
        pointer = grimoire.get_pointer_index()
        
        # Always close when done
        grimoire.close()
    """

    def __init__(self, 
                 db_path="data/memory/shadow_memory.db",
                 vector_path="data/vectors",
                 ollama_url="http://localhost:11434",
                 embed_model="nomic-embed-text"):
        """
        Initialize Grimoire with both storage engines.
        
        Args:
            db_path: Where to store the SQLite database file.
                     Relative paths are relative to where you run the script.
            vector_path: Where ChromaDB stores its vector data on disk.
            ollama_url: Ollama's API endpoint (default localhost).
            embed_model: Which Ollama model generates embeddings.
                         nomic-embed-text is small (~300MB), fast, and good quality.
        """
        # Store configuration
        self.db_path = Path(db_path)
        self.vector_path = Path(vector_path)
        self.ollama_url = ollama_url
        self.embed_model = embed_model

        # Create directories if they don't exist
        # parents=True means "create parent folders too"
        # exist_ok=True means "don't error if it already exists"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.vector_path.mkdir(parents=True, exist_ok=True)

        # ── Initialize SQLite ──
        # sqlite3.connect creates the database file if it doesn't exist
        self.conn = sqlite3.connect(str(self.db_path))
        
        # Row factory makes query results behave like dictionaries
        # Instead of row[0], row[1], you can do row["content"], row["trust_level"]
        self.conn.row_factory = sqlite3.Row
        
        # Create all tables (safe to call multiple times — uses IF NOT EXISTS)
        self._create_tables()

        # ── Initialize ChromaDB ──
        # PersistentClient saves to disk (survives restarts)
        # EphemeralClient would lose everything when the program stops
        self.chroma_client = chromadb.PersistentClient(path=str(self.vector_path))
        
        # get_or_create_collection: use existing collection or make a new one
        # "cosine" space means similarity is measured by the angle between vectors
        # (most common for text embeddings — 1.0 = identical, 0.0 = unrelated)
        self.collection = self.chroma_client.get_or_create_collection(
            name="shadow_memories",
            metadata={"hnsw:space": "cosine"}
        )

        print(f"[Grimoire] Initialized — SQLite: {self.db_path}")
        print(f"[Grimoire] Initialized — ChromaDB: {self.vector_path}")
        print(f"[Grimoire] Embedding model: {self.embed_model}")
        print(f"[Grimoire] Existing memories: {self.collection.count()}")

    # =========================================================================
    # DATABASE SCHEMA
    # =========================================================================

    def _create_tables(self):
        """
        Create the SQLite tables that store all of Shadow's memories.
        
        This runs every time Grimoire starts up, but CREATE TABLE IF NOT EXISTS
        means it's safe — it only creates tables that don't already exist.
        
        TABLE DESIGN PHILOSOPHY:
            - memories: One row per memory. Everything Shadow remembers.
            - corrections: Audit trail of what was corrected and why.
            - tags: Flexible labeling — one memory can have many tags.
            - sources: Track quality/trust of external information sources.
        """
        cursor = self.conn.cursor()

        # ── Main memories table ──
        # This is the most important table. Every piece of knowledge lives here.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                -- Unique identifier (UUID) — never reused, never changes
                id TEXT PRIMARY KEY,
                
                -- The actual memory content (what Shadow remembers)
                content TEXT NOT NULL,
                
                -- Short one-line summary (generated later, used in pointer index)
                summary TEXT,
                
                -- Topic category (e.g., "hardware", "python", "business", "personal")
                -- Default "uncategorized" until auto-categorization is built
                category TEXT DEFAULT 'uncategorized',
                
                -- Where this memory came from (see SOURCE_ constants above)
                source TEXT NOT NULL,
                
                -- Which Shadow module created it (grimoire, reaper, wraith, etc.)
                source_module TEXT DEFAULT 'grimoire',
                
                -- How much Shadow trusts this info (see TRUST_ constants above)
                -- 0.0 = speculation, 1.0 = creator-verified fact
                trust_level REAL DEFAULT 0.5,
                
                -- How confident Shadow is in this specific memory
                -- Different from trust: trust is about the SOURCE, confidence is 
                -- about whether Shadow understood/stored it correctly
                confidence REAL DEFAULT 0.5,
                
                -- When this memory was created (ISO 8601 format)
                created_at TEXT NOT NULL,
                
                -- When this memory was last modified
                updated_at TEXT NOT NULL,
                
                -- When this memory was last retrieved by a search
                -- NULL means it's never been accessed after creation
                accessed_at TEXT,
                
                -- How many times this memory has been retrieved
                -- High access count = important memory (used in pointer index)
                access_count INTEGER DEFAULT 0,
                
                -- The ID used in ChromaDB (same as this row's id)
                embedding_id TEXT,
                
                -- Soft delete flag: 1 = active, 0 = superseded/deleted
                -- We NEVER hard-delete memories — history is sacred
                is_active INTEGER DEFAULT 1,
                
                -- If this memory replaced another (e.g., correction),
                -- parent_id points to the original memory
                parent_id TEXT,
                
                -- ═══ Fields from Memory System Design Doc (Session 5) ═══
                
                -- Which model/brain handled this interaction
                -- e.g., "phi4-mini", "llama4-scout", "qwen3-coder"
                -- NULL for non-interaction memories (imported facts, etc.)
                model_used TEXT,
                
                -- JSON list of tools called during this interaction
                -- e.g., '["web_search", "file_read", "calculator"]'
                -- NULL if no tools were used
                tools_called TEXT,
                
                -- Safety layer classification from Cerberus
                -- e.g., "safe", "needs_approval", "blocked", "external_action"
                -- NULL until Cerberus is built (Phase 2)
                safety_class TEXT,
                
                -- User feedback on this memory/interaction
                -- e.g., "approved", "corrected", "rejected", or a rating
                -- NULL if no explicit feedback was given
                user_feedback TEXT,
                
                -- Flexible JSON field for anything that doesn't fit above
                -- e.g., {"url": "...", "reddit_post_id": "...", "correction_reason": "..."}
                metadata_json TEXT DEFAULT '{}'
            )
        """)

        # ── Corrections audit trail ──
        # Every time the creator corrects a memory, we log it here.
        # This is training data gold — corrections teach Shadow what it got wrong.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS corrections (
                id TEXT PRIMARY KEY,
                original_memory_id TEXT NOT NULL,
                corrected_content TEXT NOT NULL,
                correction_reason TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (original_memory_id) REFERENCES memories(id)
            )
        """)

        # ── Tags for flexible categorization ──
        # One memory can have many tags. Tags are more granular than categories.
        # Category might be "hardware", tags might be ["gpu", "rtx-5090", "vram", "pricing"]
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                memory_id TEXT NOT NULL,
                tag TEXT NOT NULL,
                PRIMARY KEY (memory_id, tag),
                FOREIGN KEY (memory_id) REFERENCES memories(id)
            )
        """)

        # ── Source quality tracking ──
        # Tracks the trustworthiness of external sources over time.
        # If a website is consistently accurate, its trust_score goes up.
        # If it publishes garbage, trust_score goes down.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY,
                url TEXT,
                domain TEXT,
                source_type TEXT DEFAULT 'unknown',
                trust_score REAL DEFAULT 0.5,
                first_seen TEXT,
                last_checked TEXT,
                times_cited INTEGER DEFAULT 0,
                notes TEXT
            )
        """)

        # ── Indexes for fast lookups ──
        # Without indexes, every query scans the entire table.
        # With indexes, SQLite can jump straight to matching rows.
        # Rule of thumb: index any column you filter or sort by frequently.
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_category "
            "ON memories(category)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_source "
            "ON memories(source)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_trust "
            "ON memories(trust_level)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_created "
            "ON memories(created_at)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_active "
            "ON memories(is_active)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tags_tag "
            "ON tags(tag)"
        )

        # commit() saves all changes to disk
        # Without this, changes exist only in memory and are lost on crash
        self.conn.commit()

    # =========================================================================
    # EMBEDDING — Converting text to vectors
    # =========================================================================

    def _get_embedding(self, text):
        """
        Convert text into a vector (list of numbers) using Ollama.
        
        This is the core of semantic search. The embedding captures the MEANING
        of the text as a point in high-dimensional space. Similar meanings = 
        nearby points. "dog" and "puppy" are close. "dog" and "algebra" are far.
        
        nomic-embed-text produces 768-dimensional vectors. That means each piece
        of text becomes a list of 768 numbers. ChromaDB compares these lists
        using cosine similarity to find the closest matches.
        
        Args:
            text: The text to embed (a sentence, paragraph, or document)
            
        Returns:
            A list of 768 floats (the embedding vector)
            
        Raises:
            ConnectionError: If Ollama isn't running
            requests.HTTPError: If the embedding model isn't pulled
        """
        try:
            response = requests.post(
                f"{self.ollama_url}/api/embeddings",
                json={
                    "model": self.embed_model,
                    "prompt": text
                },
                timeout=30  # Don't wait forever if Ollama is stuck
            )
            response.raise_for_status()  # Raises exception for HTTP errors
            return response.json()["embedding"]
            
        except requests.ConnectionError:
            # Ollama probably isn't running
            raise ConnectionError(
                "[Grimoire] Cannot connect to Ollama at "
                f"{self.ollama_url}. Is Ollama running? "
                "Start it with: ollama serve"
            )
        except requests.HTTPError as e:
            # Model might not be pulled
            raise RuntimeError(
                f"[Grimoire] Embedding failed: {e}. "
                f"Is '{self.embed_model}' pulled? "
                f"Run: ollama pull {self.embed_model}"
            )

    # =========================================================================
    # WRITE PIPELINE — Storing memories
    # =========================================================================

    def remember(self, content, source=SOURCE_CONVERSATION, 
                 source_module="grimoire", category="uncategorized",
                 trust_level=TRUST_CONVERSATION, confidence=0.5,
                 tags=None, metadata=None, parent_id=None,
                 model_used=None, tools_called=None,
                 safety_class=None, user_feedback=None,
                 check_duplicates=True):
        """
        Store a new memory in both SQLite and ChromaDB.
        
        This is the main write function. Everything Shadow learns flows through
        here. The memory gets:
            1. A unique ID (UUID)
            2. A timestamp
            3. Deduplication check (Section 9 of Memory System Design)
            4. An embedding vector (from Ollama)
            5. Stored in SQLite (full record with all metadata)
            6. Stored in ChromaDB (vector for semantic search)
        
        Args:
            content: The text to remember (the actual knowledge)
            source: Where this came from (use SOURCE_ constants)
            source_module: Which Shadow module is storing this
            category: Topic category (e.g., "hardware", "python")
            trust_level: How trustworthy (use TRUST_ constants)
            confidence: How confident Shadow is in the storage (0.0–1.0)
            tags: Optional list of tags, e.g., ["gpu", "pricing", "5090"]
            metadata: Optional dict of extra data, stored as JSON
            parent_id: If this replaces another memory, link to the original
            model_used: Which model/brain handled this (e.g., "phi4-mini")
            tools_called: List of tools used (e.g., ["web_search", "calculator"])
            safety_class: Cerberus safety classification (e.g., "safe", "needs_approval")
            user_feedback: Creator's feedback ("approved", "corrected", "rejected")
            check_duplicates: If True, check for semantic duplicates before storing.
                              Set False when you know it's unique (e.g., corrections).
            
        Returns:
            The UUID string of the new memory, or the ID of an existing duplicate
            
        Example:
            memory_id = grimoire.remember(
                content="Shadow's hardware includes dual RTX 5090 GPUs with 64GB total VRAM",
                source=SOURCE_USER_STATED,
                category="hardware",
                trust_level=TRUST_USER_STATED,
                tags=["gpu", "rtx-5090", "vram", "hardware-build"]
            )
        """
        # Generate a unique ID for this memory
        # UUID4 = random, virtually impossible to collide
        memory_id = str(uuid.uuid4())
        
        # Timestamp in ISO 8601 format (works everywhere, sorts correctly)
        now = datetime.now().isoformat()

        # ── Step 1: Generate embedding ──
        # This calls Ollama to convert the text into a vector
        embedding = self._get_embedding(content)

        # ── Step 1.5: Deduplication Check (Memory System Design, Section 9) ──
        # Before storing, check if a very similar memory already exists.
        # If it does, merge sources/update confidence instead of duplicating.
        # Threshold: 0.92+ cosine similarity = likely duplicate
        if check_duplicates and self.collection.count() > 0:
            similar = self.collection.query(
                query_embeddings=[embedding],
                n_results=1
            )
            if (similar and similar['distances'] and similar['distances'][0]
                    and similar['distances'][0][0] < 0.08):
                # Distance < 0.08 means cosine similarity > 0.92 — very similar
                existing_id = similar['ids'][0][0]
                
                # Check if the existing memory is still active
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT * FROM memories WHERE id = ? AND is_active = 1",
                    (existing_id,)
                )
                existing = cursor.fetchone()
                
                if existing:
                    # Merge: update confidence and timestamp, add source to metadata
                    new_confidence = min(1.0, existing["confidence"] + 0.1)
                    existing_meta = json.loads(existing["metadata_json"] or "{}")
                    
                    # Track additional sources that confirmed this info
                    additional_sources = existing_meta.get("additional_sources", [])
                    additional_sources.append({
                        "source": source,
                        "source_module": source_module,
                        "confirmed_at": now
                    })
                    existing_meta["additional_sources"] = additional_sources
                    
                    cursor.execute("""
                        UPDATE memories 
                        SET confidence = ?, updated_at = ?, metadata_json = ?
                        WHERE id = ?
                    """, (new_confidence, now, json.dumps(existing_meta), existing_id))
                    self.conn.commit()
                    
                    print(f"[Grimoire] Dedup: merged with existing {existing_id[:8]}... "
                          f"(confidence now {new_confidence})")
                    return existing_id

        # ── Step 2: Store in SQLite ──
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO memories 
            (id, content, category, source, source_module, trust_level, 
             confidence, created_at, updated_at, embedding_id, parent_id,
             model_used, tools_called, safety_class, user_feedback,
             metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            memory_id,                    # id
            content,                      # content
            category,                     # category
            source,                       # source
            source_module,                # source_module
            trust_level,                  # trust_level
            confidence,                   # confidence
            now,                          # created_at
            now,                          # updated_at
            memory_id,                    # embedding_id (same as memory id)
            parent_id,                    # parent_id (None if original)
            model_used,                   # model_used (from design doc)
            json.dumps(tools_called) if tools_called else None,  # tools_called
            safety_class,                 # safety_class (from design doc)
            user_feedback,                # user_feedback (from design doc)
            json.dumps(metadata or {})    # metadata_json
        ))

        # ── Step 3: Store tags ──
        if tags:
            for tag in tags:
                # OR IGNORE: skip if this exact memory+tag combo already exists
                cursor.execute(
                    "INSERT OR IGNORE INTO tags (memory_id, tag) VALUES (?, ?)",
                    (memory_id, tag.lower().strip())  # Normalize tags
                )

        # Save to disk
        self.conn.commit()

        # ── Step 4: Store in ChromaDB ──
        # ChromaDB gets the embedding vector plus lightweight metadata
        # (ChromaDB metadata must be simple types: str, int, float, bool)
        self.collection.add(
            ids=[memory_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[{
                "category": category,
                "source": source,
                "source_module": source_module,
                "trust_level": trust_level,
                "created_at": now
            }]
        )

        print(f"[Grimoire] Remembered: {content[:80]}...")
        print(f"[Grimoire] ID: {memory_id} | Trust: {trust_level} | Category: {category}")
        
        return memory_id

    # =========================================================================
    # READ PIPELINE — Retrieving memories
    # =========================================================================

    def recall(self, query, n_results=5, min_trust=0.0, category=None):
        """
        Search memories by meaning (semantic search).
        
        This is the core read function. You describe what you're looking for
        in natural language, and Grimoire finds the most relevant memories —
        even if the exact words don't match.
        
        Example: query "GPU specs" will find a memory about "RTX 5090 with 32GB VRAM"
        even though those strings share no words.
        
        HOW IT WORKS:
            1. Your query gets embedded (converted to a vector)
            2. ChromaDB finds the nearest vectors (most similar meanings)
            3. Those memory IDs are used to fetch full records from SQLite
            4. Results are returned with relevance scores
            5. Access tracking is updated (so we know which memories matter)
        
        Args:
            query: Natural language description of what you're looking for
            n_results: Maximum number of memories to return (default 5)
            min_trust: Only return memories with trust >= this value
            category: Only search within this category (None = search all)
            
        Returns:
            List of dicts, each containing:
                - id: Memory UUID
                - content: The actual memory text
                - category: Topic category
                - source: Where it came from
                - trust_level: How trustworthy
                - confidence: How confident
                - created_at: When stored
                - access_count: How often retrieved
                - relevance: Similarity score (0.0–1.0, higher = more relevant)
        """
        # ── Step 1: Embed the query ──
        query_embedding = self._get_embedding(query)

        # ── Step 2: Build ChromaDB filter ──
        # ChromaDB supports filtering on metadata fields
        # We can filter by trust level, category, or both
        where_filter = None
        
        if min_trust > 0 and category:
            # Both filters: trust AND category
            where_filter = {
                "$and": [
                    {"trust_level": {"$gte": min_trust}},
                    {"category": category}
                ]
            }
        elif min_trust > 0:
            where_filter = {"trust_level": {"$gte": min_trust}}
        elif category:
            where_filter = {"category": category}

        # ── Step 3: Search ChromaDB ──
        # query_embeddings takes a list because you COULD search for multiple
        # queries at once, but we just pass one
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter
        )

        # ── Step 4: Enrich results with SQLite data ──
        memories = []
        
        # results['ids'] is a list of lists (one per query). We only have one query.
        if results and results['ids'] and results['ids'][0]:
            for i, memory_id in enumerate(results['ids'][0]):
                
                # Fetch full record from SQLite
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT * FROM memories WHERE id = ? AND is_active = 1",
                    (memory_id,)
                )
                row = cursor.fetchone()
                
                if row:
                    # ── Step 5: Update access tracking ──
                    # This is how Grimoire learns which memories are important
                    cursor.execute("""
                        UPDATE memories 
                        SET accessed_at = ?, access_count = access_count + 1
                        WHERE id = ?
                    """, (datetime.now().isoformat(), memory_id))
                    self.conn.commit()

                    # ChromaDB returns DISTANCE (lower = more similar)
                    # Convert to RELEVANCE (higher = more similar) for readability
                    distance = results['distances'][0][i]
                    relevance = max(0.0, 1.0 - distance)  # Flip it

                    # Fetch tags for this memory
                    cursor.execute(
                        "SELECT tag FROM tags WHERE memory_id = ?",
                        (memory_id,)
                    )
                    memory_tags = [r["tag"] for r in cursor.fetchall()]

                    memories.append({
                        "id": row["id"],
                        "content": row["content"],
                        "category": row["category"],
                        "source": row["source"],
                        "source_module": row["source_module"],
                        "trust_level": row["trust_level"],
                        "confidence": row["confidence"],
                        "created_at": row["created_at"],
                        "access_count": row["access_count"] + 1,
                        "tags": memory_tags,
                        "relevance": round(relevance, 4),
                        "metadata": json.loads(row["metadata_json"] or "{}")
                    })

        return memories

    def recall_by_tag(self, tag, limit=10):
        """
        Find memories by tag (exact match, not semantic).
        
        Sometimes you know the exact tag you want. This is faster than
        semantic search for precise lookups.
        
        Args:
            tag: The tag to search for (e.g., "gpu", "python", "business")
            limit: Maximum results to return
            
        Returns:
            List of memory dicts (same format as recall())
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT m.* FROM memories m
            JOIN tags t ON m.id = t.memory_id
            WHERE t.tag = ? AND m.is_active = 1
            ORDER BY m.trust_level DESC, m.created_at DESC
            LIMIT ?
        """, (tag.lower().strip(), limit))
        
        return [dict(row) for row in cursor.fetchall()]

    def recall_recent(self, limit=10, source=None):
        """
        Get most recent memories, optionally filtered by source.
        
        Useful for: "What did we talk about recently?" or
        "Show me recent research results."
        
        Args:
            limit: How many to return
            source: Filter by source type (None = all sources)
            
        Returns:
            List of memory dicts
        """
        cursor = self.conn.cursor()
        
        if source:
            cursor.execute("""
                SELECT * FROM memories 
                WHERE is_active = 1 AND source = ?
                ORDER BY created_at DESC LIMIT ?
            """, (source, limit))
        else:
            cursor.execute("""
                SELECT * FROM memories 
                WHERE is_active = 1
                ORDER BY created_at DESC LIMIT ?
            """, (limit,))
        
        return [dict(row) for row in cursor.fetchall()]

    # =========================================================================
    # CORRECTIONS — When the creator says "that's wrong"
    # =========================================================================

    def correct(self, memory_id, new_content, reason="user correction"):
        """
        Apply a correction to an existing memory.
        
        Corrections are the HIGHEST VALUE training data. They teach Shadow:
            - What it got wrong
            - What the correct answer is
            - That the creator's word is final
        
        The old memory is soft-deleted (is_active = 0) but NEVER destroyed.
        A new memory is created with trust_level = 1.0 and linked to the original.
        The correction is logged in the corrections table for the audit trail.
        
        Args:
            memory_id: The ID of the memory to correct
            new_content: The corrected information
            reason: Why the correction was made (training data)
            
        Returns:
            The ID of the new corrected memory
        """
        now = datetime.now().isoformat()
        correction_id = str(uuid.uuid4())

        # ── Step 1: Verify the original memory exists ──
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        original = cursor.fetchone()
        
        if not original:
            raise ValueError(f"[Grimoire] Memory not found: {memory_id}")

        # ── Step 2: Log the correction (audit trail) ──
        cursor.execute("""
            INSERT INTO corrections 
            (id, original_memory_id, corrected_content, correction_reason, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (correction_id, memory_id, new_content, reason, now))

        # ── Step 3: Soft-delete the original ──
        # is_active = 0 means it won't appear in searches
        # but it's still in the database for history
        cursor.execute("""
            UPDATE memories SET is_active = 0, updated_at = ? WHERE id = ?
        """, (now, memory_id))

        # Remove old vector from ChromaDB
        try:
            self.collection.delete(ids=[memory_id])
        except Exception:
            pass  # May not exist in ChromaDB (that's fine)

        self.conn.commit()

        # ── Step 4: Create the corrected memory ──
        # Inherits category from original, gets maximum trust
        # check_duplicates=False because corrections are intentionally new
        new_id = self.remember(
            content=new_content,
            source=SOURCE_USER_CORRECTION,
            source_module="grimoire",
            category=original["category"],
            trust_level=TRUST_USER_CORRECTION,
            confidence=1.0,
            parent_id=memory_id,
            check_duplicates=False,
            metadata={
                "correction_reason": reason,
                "original_id": memory_id,
                "original_content": original["content"]
            }
        )

        print(f"[Grimoire] Corrected memory {memory_id[:8]}... → {new_id[:8]}...")
        print(f"[Grimoire] Reason: {reason}")
        
        return new_id

    # =========================================================================
    # FORGET — When the creator says "forget this" (Design Doc Section 3)
    # =========================================================================

    def forget(self, memory_id):
        """
        Explicitly forget a specific memory.
        
        From Memory System Design, Section 3: "If user says 'don't save that'
        or 'forget what I just said,' Shadow deletes the specific entry from
        both active and deep memory."
        
        Unlike corrections (which soft-delete), explicit forget requests
        remove from ChromaDB entirely. The SQLite record is kept but marked
        inactive with a forget flag — for audit trail only.
        
        Args:
            memory_id: The ID of the memory to forget
            
        Returns:
            True if forgotten, False if memory not found
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        memory = cursor.fetchone()
        
        if not memory:
            print(f"[Grimoire] Memory not found: {memory_id}")
            return False
        
        now = datetime.now().isoformat()
        
        # Mark inactive in SQLite with forget flag
        existing_meta = json.loads(memory["metadata_json"] or "{}")
        existing_meta["forgotten"] = True
        existing_meta["forgotten_at"] = now
        
        cursor.execute("""
            UPDATE memories 
            SET is_active = 0, updated_at = ?, metadata_json = ?
            WHERE id = ?
        """, (now, json.dumps(existing_meta), memory_id))
        
        # Remove from ChromaDB entirely
        try:
            self.collection.delete(ids=[memory_id])
        except Exception:
            pass
        
        # Remove associated tags
        cursor.execute("DELETE FROM tags WHERE memory_id = ?", (memory_id,))
        
        self.conn.commit()
        
        content_preview = memory["content"][:60]
        print(f"[Grimoire] Forgotten: {content_preview}...")
        return True

    # =========================================================================
    # CONFLICT DETECTION (Design Doc Section 7)
    # =========================================================================

    def find_conflicts(self, content, n_candidates=5, threshold=0.15):
        """
        Check if new content conflicts with existing memories.
        
        From Memory System Design, Section 7: When Shadow detects contradictory
        information, it follows a resolution hierarchy:
            1. User correction vs anything = user correction wins
            2. Recent user statement vs older = flag to user
            3. Research vs research = present both with sources
            4. Simple factual updates = most recent wins silently
        
        This method finds potentially conflicting memories so the caller
        can apply the appropriate resolution strategy.
        
        Args:
            content: The new content to check for conflicts
            n_candidates: How many similar memories to check
            threshold: Distance threshold for "similar enough to conflict"
                       (lower = more similar, higher = broader search)
            
        Returns:
            List of potentially conflicting memories with conflict details.
            Empty list if no conflicts found.
        """
        if self.collection.count() == 0:
            return []
        
        # Find memories that are similar (same topic area) but not identical
        embedding = self._get_embedding(content)
        
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=n_candidates
        )
        
        conflicts = []
        
        if results and results['ids'] and results['ids'][0]:
            for i, memory_id in enumerate(results['ids'][0]):
                distance = results['distances'][0][i]
                
                # Too similar (< 0.08) = duplicate, not conflict
                # Too different (> threshold) = unrelated
                # Sweet spot = same topic, different content
                if 0.08 <= distance <= threshold:
                    cursor = self.conn.cursor()
                    cursor.execute(
                        "SELECT * FROM memories WHERE id = ? AND is_active = 1",
                        (memory_id,)
                    )
                    existing = cursor.fetchone()
                    
                    if existing:
                        conflicts.append({
                            "existing_id": existing["id"],
                            "existing_content": existing["content"],
                            "existing_trust": existing["trust_level"],
                            "existing_source": existing["source"],
                            "existing_created": existing["created_at"],
                            "new_content": content,
                            "similarity": round(1.0 - distance, 4),
                        })
        
        if conflicts:
            print(f"[Grimoire] Found {len(conflicts)} potential conflict(s)")
        
        return conflicts

    # =========================================================================
    # POINTER INDEX — Lightweight context for every prompt
    # =========================================================================

    def get_pointer_index(self):
        """
        Generate a lightweight summary of Shadow's most important knowledge.
        
        Inspired by Claude Code's MEMORY.md pattern: a small, structured summary
        that gets loaded into every prompt so the model always has essential context
        without loading the entire database.
        
        The pointer index includes:
            - Total memory count (how much Shadow knows)
            - Category breakdown (what topics Shadow knows about)
            - Most-accessed memories (what comes up most often)
            - Recent corrections (highest-priority context)
            - High-trust memories (verified facts)
        
        Returns:
            Dict containing the pointer index data.
            Can be serialized to JSON or formatted as text for prompts.
        """
        cursor = self.conn.cursor()

        # ── Category distribution ──
        # Shows what topics Shadow knows about and how much
        cursor.execute("""
            SELECT category, COUNT(*) as count 
            FROM memories WHERE is_active = 1 
            GROUP BY category 
            ORDER BY count DESC 
            LIMIT 15
        """)
        categories = {row["category"]: row["count"] for row in cursor.fetchall()}

        # ── Most accessed memories ──
        # These are Shadow's "core knowledge" — the things that keep coming up
        cursor.execute("""
            SELECT id, content, category, trust_level, access_count
            FROM memories WHERE is_active = 1 
            ORDER BY access_count DESC 
            LIMIT 10
        """)
        top_memories = [dict(row) for row in cursor.fetchall()]

        # ── Recent corrections ──
        # Corrections are highest priority — they represent the creator's will
        cursor.execute("""
            SELECT c.corrected_content, c.correction_reason, c.created_at
            FROM corrections c
            ORDER BY c.created_at DESC 
            LIMIT 5
        """)
        recent_corrections = [dict(row) for row in cursor.fetchall()]

        # ── High-trust memories ──
        # Facts the creator has verified or stated directly
        cursor.execute("""
            SELECT id, content, category, trust_level, source
            FROM memories 
            WHERE is_active = 1 AND trust_level >= 0.8
            ORDER BY trust_level DESC, created_at DESC 
            LIMIT 15
        """)
        high_trust = [dict(row) for row in cursor.fetchall()]

        # ── Recent memories ──
        # What was discussed/learned recently
        cursor.execute("""
            SELECT id, content, category, source, created_at
            FROM memories WHERE is_active = 1
            ORDER BY created_at DESC
            LIMIT 5
        """)
        recent = [dict(row) for row in cursor.fetchall()]

        return {
            "total_memories": self.collection.count(),
            "categories": categories,
            "top_accessed": top_memories,
            "recent_corrections": recent_corrections,
            "high_trust": high_trust,
            "recent": recent,
            "generated_at": datetime.now().isoformat()
        }

    def pointer_index_as_text(self):
        """
        Format the pointer index as readable text for injection into prompts.
        
        This is what actually goes into Shadow's system prompt:
        a clean, readable summary of what Shadow knows.
        
        Returns:
            A formatted string ready to inject into a prompt.
        """
        index = self.get_pointer_index()
        
        lines = []
        lines.append(f"=== SHADOW MEMORY INDEX ({index['total_memories']} memories) ===")
        lines.append(f"Generated: {index['generated_at']}")
        lines.append("")
        
        # Categories
        if index['categories']:
            lines.append("KNOWLEDGE AREAS:")
            for cat, count in index['categories'].items():
                lines.append(f"  {cat}: {count} memories")
            lines.append("")
        
        # High-trust facts
        if index['high_trust']:
            lines.append("VERIFIED FACTS (high trust):")
            for mem in index['high_trust']:
                # Truncate long content for the index
                content = mem['content'][:150]
                if len(mem['content']) > 150:
                    content += "..."
                lines.append(f"  [{mem['trust_level']}] {content}")
            lines.append("")
        
        # Recent corrections
        if index['recent_corrections']:
            lines.append("RECENT CORRECTIONS (highest priority):")
            for corr in index['recent_corrections']:
                content = corr['corrected_content'][:150]
                if len(corr['corrected_content']) > 150:
                    content += "..."
                lines.append(f"  CORRECTED: {content}")
                if corr['correction_reason']:
                    lines.append(f"    Reason: {corr['correction_reason']}")
            lines.append("")
        
        # Recent memories
        if index['recent']:
            lines.append("RECENT MEMORIES:")
            for mem in index['recent']:
                content = mem['content'][:120]
                if len(mem['content']) > 120:
                    content += "..."
                lines.append(f"  [{mem['source']}] {content}")
        
        return "\n".join(lines)

    # =========================================================================
    # STATISTICS & UTILITIES
    # =========================================================================

    def stats(self):
        """
        Return database statistics. Useful for monitoring and debugging.
        
        Returns:
            Dict with counts of active memories, corrections, tags, etc.
        """
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM memories WHERE is_active = 1")
        active = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM memories WHERE is_active = 0")
        inactive = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM corrections")
        corrections = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT tag) FROM tags")
        unique_tags = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT category, COUNT(*) as count 
            FROM memories WHERE is_active = 1 
            GROUP BY category
        """)
        by_category = {row["category"]: row["count"] for row in cursor.fetchall()}
        
        cursor.execute("""
            SELECT source, COUNT(*) as count 
            FROM memories WHERE is_active = 1 
            GROUP BY source
        """)
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}
        
        return {
            "active_memories": active,
            "inactive_memories": inactive,
            "total_stored": active + inactive,
            "corrections": corrections,
            "unique_tags": unique_tags,
            "vector_count": self.collection.count(),
            "by_category": by_category,
            "by_source": by_source,
            "db_path": str(self.db_path),
            "vector_path": str(self.vector_path)
        }

    def search_corrections(self, limit=20):
        """
        View correction history. Training data for anti-sycophancy.
        
        Returns:
            List of correction records with original and corrected content.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT c.*, m.content as original_content
            FROM corrections c
            LEFT JOIN memories m ON c.original_memory_id = m.id
            ORDER BY c.created_at DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        """
        Clean shutdown. Always call this when you're done.
        
        SQLite connections should be closed properly to ensure all data
        is flushed to disk. ChromaDB's PersistentClient handles its own cleanup.
        """
        self.conn.close()
        print("[Grimoire] Shut down cleanly.")


# =============================================================================
# STANDALONE TEST — Run this file directly to verify Grimoire works
# =============================================================================
# Usage: python -m modules.grimoire.grimoire
# Or:    python modules/grimoire/grimoire.py

if __name__ == "__main__":
    print("=" * 60)
    print("GRIMOIRE — Shadow's Memory System — Standalone Test")
    print("=" * 60)
    print()
    print("This test will:")
    print("  1. Create a Grimoire instance")
    print("  2. Store several test memories")
    print("  3. Search for them semantically")
    print("  4. Test the correction system")
    print("  5. Display the pointer index")
    print()
    print("REQUIRES: Ollama running with nomic-embed-text pulled")
    print("  Start Ollama: ollama serve")
    print("  Pull model:   ollama pull nomic-embed-text")
    print()
    
    # Create Grimoire with test paths
    grimoire = Grimoire(
        db_path="data/memory/shadow_memory.db",
        vector_path="data/vectors"
    )
    
    print("\n" + "=" * 60)
    print("STEP 1: Storing test memories...")
    print("=" * 60)
    
    # Store some memories about Shadow's hardware
    id1 = grimoire.remember(
        content="Shadow's hardware build includes dual RTX 5090 GPUs providing 64GB total VRAM for running large language models locally.",
        source=SOURCE_USER_STATED,
        category="hardware",
        trust_level=TRUST_USER_STATED,
        tags=["gpu", "rtx-5090", "vram", "hardware-build"]
    )
    
    id2 = grimoire.remember(
        content="Shadow uses Ollama as the model serving runtime, with llama.cpp as the backend. NVIDIA announced 30-35% performance improvements at CES 2026.",
        source=SOURCE_CONVERSATION,
        category="software",
        trust_level=TRUST_CONVERSATION,
        tags=["ollama", "llama-cpp", "performance"]
    )
    
    id3 = grimoire.remember(
        content="The creator runs a landscaping business and uses LMN software at my.golmn.com for job scheduling, estimates, and crew management.",
        source=SOURCE_USER_STATED,
        category="business",
        trust_level=TRUST_USER_STATED,
        tags=["landscaping", "lmn", "business"]
    )
    
    id4 = grimoire.remember(
        content="Shadow's ethics are based on biblical values, not manufacturer alignment. Every base model is abliterated using Heretic to strip manufacturer censorship before use.",
        source=SOURCE_USER_STATED,
        category="ethics",
        trust_level=TRUST_USER_STATED,
        tags=["ethics", "abliteration", "values", "heretic"]
    )
    
    id5 = grimoire.remember(
        content="Python virtual environments (venv) are used for dependency isolation. Created with python -m venv shadow_env and activated with shadow_env/Scripts/activate on Windows.",
        source=SOURCE_CONVERSATION,
        category="python",
        trust_level=TRUST_CONVERSATION,
        tags=["python", "venv", "environment"]
    )
    
    print("\n" + "=" * 60)
    print("STEP 2: Semantic search tests...")
    print("=" * 60)
    
    # These queries use DIFFERENT WORDS than what's stored
    # Semantic search should still find the right memories
    test_queries = [
        "What GPU does Shadow use?",
        "How does Shadow run AI models?",
        "What does the creator do for work?",
        "What are Shadow's moral principles?",
        "How do I set up Python packages?",
    ]
    
    for query in test_queries:
        print(f"\n  Query: '{query}'")
        results = grimoire.recall(query, n_results=2)
        for r in results:
            print(f"    → [{r['relevance']:.3f}] [{r['category']}] {r['content'][:80]}...")
    
    print("\n" + "=" * 60)
    print("STEP 3: Testing corrections...")
    print("=" * 60)
    
    # Correct the Ollama version info
    new_id = grimoire.correct(
        memory_id=id2,
        new_content="Shadow uses Ollama 0.5.x as the model serving runtime with llama.cpp backend. NVIDIA CES 2026 optimizations already live: 35% faster in llama.cpp, 30% in Ollama.",
        reason="Updated with specific version and exact performance numbers"
    )
    print(f"  Correction applied. New ID: {new_id[:8]}...")
    
    # Search again — should find the corrected version
    print("\n  Searching after correction:")
    results = grimoire.recall("Ollama version and performance", n_results=2)
    for r in results:
        print(f"    → [trust:{r['trust_level']}] {r['content'][:80]}...")
    
    print("\n" + "=" * 60)
    print("STEP 4: Pointer Index")
    print("=" * 60)
    
    print(grimoire.pointer_index_as_text())
    
    print("\n" + "=" * 60)
    print("STEP 5: Statistics")
    print("=" * 60)
    
    stats = grimoire.stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Clean up
    grimoire.close()
    print("\n✅ All Grimoire tests complete!")
