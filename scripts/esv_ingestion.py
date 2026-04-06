"""
ESV Study Bible Ingestion Script
Loads parsed ESV JSON files into Grimoire's SQLite and ChromaDB storage.

Prerequisites:
    - Run esv_processor.py first to generate the JSON files
    - Ollama must be running with nomic-embed-text pulled
    - ChromaDB data dir at C:/Shadow/data/vectors/ must exist

Usage:
    python scripts/esv_ingestion.py
"""

import json
import sqlite3
import time
from pathlib import Path

import chromadb
import requests

# ── Paths ──
JSON_DIR = Path(r"C:\Shadow\training_data\esv")
PERICOPES_JSON = JSON_DIR / "esv_pericopes.json"
STUDYNOTES_JSON = JSON_DIR / "esv_studynotes.json"
SQLITE_DB = Path(r"C:\Shadow\data\memory\shadow_memory.db")
VECTOR_DIR = Path(r"C:\Shadow\data\vectors")

# ── Ollama config (matches Grimoire) ──
OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
EMBED_TRUNCATE = 2000  # chars, matching Grimoire's limit
MAX_RETRIES = 3


def get_embedding(text):
    """
    Get embedding vector from Ollama, matching Grimoire's pattern.
    Truncates to 2000 chars, retries with exponential backoff.
    """
    truncated = text[:EMBED_TRUNCATE]

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": EMBED_MODEL, "prompt": truncated},
                timeout=30,
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except requests.ConnectionError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {OLLAMA_URL}. "
                "Is Ollama running? Start it with: ollama serve"
            )
        except requests.HTTPError as e:
            if attempt < MAX_RETRIES - 1:
                wait = 2 * (attempt + 1)
                print(f"  Embedding retry {attempt + 1}/{MAX_RETRIES} in {wait}s...")
                time.sleep(wait)
            else:
                raise RuntimeError(
                    f"Embedding failed after {MAX_RETRIES} attempts: {e}. "
                    f"Is '{EMBED_MODEL}' pulled? Run: ollama pull {EMBED_MODEL}"
                )


def setup_sqlite():
    """Create SQLite tables and return connection."""
    SQLITE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(SQLITE_DB))
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS esv_pericopes (
            id INTEGER PRIMARY KEY,
            book_number INTEGER,
            book_name TEXT,
            chapter INTEGER,
            verse_start INTEGER,
            verse_end INTEGER,
            section_heading TEXT,
            text TEXT,
            testament TEXT,
            genre TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS esv_studynotes (
            id INTEGER PRIMARY KEY,
            book_name TEXT,
            chapter INTEGER,
            verse_range TEXT,
            note_text TEXT
        )
    """)

    # Clear for idempotent re-runs
    cursor.execute("DELETE FROM esv_pericopes")
    cursor.execute("DELETE FROM esv_studynotes")
    conn.commit()

    return conn


def ingest_sqlite(conn, pericopes, studynotes):
    """Insert all records into SQLite tables."""
    cursor = conn.cursor()

    print("\n[SQLite] Inserting pericopes...")
    for i, p in enumerate(pericopes):
        cursor.execute(
            "INSERT INTO esv_pericopes (book_number, book_name, chapter, verse_start, verse_end, section_heading, text, testament, genre) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (p["book_number"], p["book_name"], p["chapter"], p["verse_start"],
             p["verse_end"], p["section_heading"], p["text"], p["testament"], p["genre"]),
        )
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(pericopes)} pericopes inserted")
    conn.commit()
    print(f"  {len(pericopes)} pericopes inserted into esv_pericopes")

    print("\n[SQLite] Inserting study notes...")
    for i, n in enumerate(studynotes):
        cursor.execute(
            "INSERT INTO esv_studynotes (book_name, chapter, verse_range, note_text) VALUES (?, ?, ?, ?)",
            (n["book_name"], n["chapter"], n["verse_range"], n["note_text"]),
        )
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(studynotes)} study notes inserted")
    conn.commit()
    print(f"  {len(studynotes)} study notes inserted into esv_studynotes")


def setup_chromadb():
    """Initialize ChromaDB client and create/recreate collections."""
    VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(VECTOR_DIR))

    # Delete existing collections for idempotent re-runs
    try:
        client.delete_collection("esv_pericopes")
    except Exception:
        pass
    try:
        client.delete_collection("esv_studynotes")
    except Exception:
        pass

    pericope_collection = client.get_or_create_collection(
        name="esv_pericopes",
        metadata={"hnsw:space": "cosine"},
    )
    studynote_collection = client.get_or_create_collection(
        name="esv_studynotes",
        metadata={"hnsw:space": "cosine"},
    )

    return pericope_collection, studynote_collection


def ingest_chromadb_pericopes(collection, pericopes):
    """Embed and insert pericopes into ChromaDB."""
    print(f"\n[ChromaDB] Embedding and inserting {len(pericopes)} pericopes...")

    for i, p in enumerate(pericopes):
        text = p["text"]
        if not text:
            continue

        embedding = get_embedding(text)

        collection.add(
            ids=[f"pericope_{i}"],
            embeddings=[embedding],
            documents=[text],
            metadatas=[{
                "book_name": p["book_name"],
                "book_number": p["book_number"],
                "chapter": p["chapter"],
                "verse_start": p["verse_start"],
                "verse_end": p["verse_end"],
                "testament": p["testament"],
                "genre": p["genre"],
                "section_heading": p["section_heading"],
            }],
        )

        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(pericopes)} pericopes embedded")

    print(f"  {collection.count()} pericopes in ChromaDB collection")


def ingest_chromadb_studynotes(collection, studynotes):
    """Embed and insert study notes into ChromaDB."""
    print(f"\n[ChromaDB] Embedding and inserting {len(studynotes)} study notes...")

    for i, n in enumerate(studynotes):
        text = n["note_text"]
        if not text:
            continue

        embedding = get_embedding(text)

        collection.add(
            ids=[f"studynote_{i}"],
            embeddings=[embedding],
            documents=[text],
            metadatas=[{
                "book_name": n["book_name"],
                "chapter": n["chapter"],
                "verse_range": n["verse_range"],
            }],
        )

        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(studynotes)} study notes embedded")

    print(f"  {collection.count()} study notes in ChromaDB collection")


def main():
    # Load JSON files
    print(f"Loading {PERICOPES_JSON}...")
    if not PERICOPES_JSON.exists():
        print(f"ERROR: {PERICOPES_JSON} not found. Run esv_processor.py first.")
        return
    with open(PERICOPES_JSON, "r", encoding="utf-8") as f:
        pericopes = json.load(f)
    print(f"  Loaded {len(pericopes)} pericopes")

    print(f"Loading {STUDYNOTES_JSON}...")
    if not STUDYNOTES_JSON.exists():
        print(f"ERROR: {STUDYNOTES_JSON} not found. Run esv_processor.py first.")
        return
    with open(STUDYNOTES_JSON, "r", encoding="utf-8") as f:
        studynotes = json.load(f)
    print(f"  Loaded {len(studynotes)} study notes")

    # SQLite ingestion
    print("\n" + "=" * 50)
    print("SQLite Ingestion")
    print("=" * 50)
    conn = setup_sqlite()
    ingest_sqlite(conn, pericopes, studynotes)
    conn.close()

    # ChromaDB ingestion
    print("\n" + "=" * 50)
    print("ChromaDB Ingestion")
    print("=" * 50)
    pericope_col, studynote_col = setup_chromadb()
    ingest_chromadb_pericopes(pericope_col, pericopes)
    ingest_chromadb_studynotes(studynote_col, studynotes)

    # Final stats
    print(f"\n{'=' * 50}")
    print("INGESTION COMPLETE")
    print(f"{'=' * 50}")
    print(f"SQLite DB:     {SQLITE_DB}")
    print(f"ChromaDB Dir:  {VECTOR_DIR}")
    print(f"Pericopes:     {len(pericopes)} records")
    print(f"Study Notes:   {len(studynotes)} records")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
