# Grimoire Module — Shadow's Memory System
# "The book that remembers everything so Shadow never forgets."
#
# Grimoire handles all of Shadow's persistent memory:
#   - Storing new memories (conversations, research, corrections)
#   - Semantic search (find memories by meaning, not just keywords)
#   - Corrections (user fixes get highest trust level)
#   - Pointer index (lightweight summary for every prompt)
#
# Two storage engines work together:
#   SQLite  = structured data, metadata, full history (the filing cabinet)
#   ChromaDB = vector embeddings, semantic search (the librarian who understands meaning)

from .grimoire import Grimoire
