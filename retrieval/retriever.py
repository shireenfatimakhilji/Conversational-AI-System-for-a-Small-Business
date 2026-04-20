# retrieval/retriever.py
"""
Retrieval module — import this to query the vector store.
Usage:
    from retrieval.retriever import retrieve
    chunks = retrieve("what is your return policy?")
"""

from dataclasses import dataclass
from typing import List, Optional
import chromadb
from sentence_transformers import SentenceTransformer
import threading
import atexit

# ── Configuration ─────────────────────────────────────────────────────────────
import os
CHROMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")
EMBED_MODEL = "all-MiniLM-L6-v2"
COLLECTION  = "crochetzies_docs"
TOP_K       = 3  # number of chunks to retrieve

@dataclass
class Chunk:
    text:     str
    source:   str
    score:    float


class Retriever:
    _instance: Optional['Retriever'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # Only print once
        print("Loading retriever...")
        try:
            self.embedder = SentenceTransformer(EMBED_MODEL, device="cpu")
            self.client = chromadb.PersistentClient(path=CHROMA_DIR)
            self.collection = self.client.get_collection(COLLECTION)
            print(f"Retriever ready — {self.collection.count()} chunks indexed")
            self._initialized = True
        except Exception as e:
            print(f"Failed to load retriever: {e}")
            self._initialized = False
            raise

    def retrieve(self, query: str, top_k: int = TOP_K) -> List[Chunk]:
        """
        Embed the query and return top-k most relevant chunks.
        
        Args:
            query:  The user's question
            top_k:  Number of chunks to return (default 3)
        
        Returns:
            List of Chunk objects with text, source filename, and similarity score
        """
        if not self._initialized:
            return []
        
        try:
            # Embed the query
            query_embedding = self.embedder.encode(query).tolist()

            # Search the vector store
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["documents", "metadatas", "distances"]
            )

            # Build Chunk objects
            chunks = []
            for text, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            ):
                score = 1 - dist  # convert distance to similarity
                chunks.append(Chunk(
                    text=text,
                    source=meta["source"],
                    score=round(score, 3)
                ))

            return chunks
        except Exception as e:
            print(f"[RAG] Retrieval error: {e}")
            return []


# Global lazy instance - NO initialization at module load time!
_retriever_instance = None

def get_retriever() -> Retriever:
    """Lazy initialization - only creates retriever when first used."""
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = Retriever()
    return _retriever_instance

def retrieve(query: str, top_k: int = TOP_K) -> List[Chunk]:
    """Main function — call this to retrieve relevant chunks."""
    try:
        return get_retriever().retrieve(query, top_k)
    except Exception as e:
        print(f"[RAG] Failed to retrieve: {e}")
        return []