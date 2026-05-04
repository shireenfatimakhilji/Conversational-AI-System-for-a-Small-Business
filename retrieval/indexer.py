# retrieval/indexer.py
"""
Offline indexing pipeline.
Run this once to process documents and build the vector store.
Run again whenever documents are updated.
"""

import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"
import chromadb
from sentence_transformers import SentenceTransformer

# ── Configuration ─────────────────────────────────────────────────────────────
DOCUMENTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "documents")
import os
CHROMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")
CHUNK_SIZE    = 400   # characters per chunk
CHUNK_OVERLAP = 80    # overlap between chunks
EMBED_MODEL   = "all-MiniLM-L6-v2"  # small, fast, good quality
COLLECTION    = "crochetzies_docs"

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap
    return chunks


def load_documents(docs_dir: str):
    """Load all .txt and .pdf files from documents directory."""
    documents = []
    for filename in os.listdir(docs_dir):
        filepath = os.path.join(docs_dir, filename)
        if filename.endswith(".txt"):
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()
            documents.append({"filename": filename, "text": text})
        elif filename.endswith(".pdf"):
            try:
                from pypdf import PdfReader
                reader = PdfReader(filepath)
                text = "\n".join(page.extract_text() for page in reader.pages)
                documents.append({"filename": filename, "text": text})
            except Exception as e:
                print(f"Could not read {filename}: {e}")
    print(f"Loaded {len(documents)} documents")
    return documents


def build_index():
    """Main indexing pipeline — run this to build/rebuild the vector store."""
    print("Loading embedding model...")
    embedder = SentenceTransformer(EMBED_MODEL)
    print("Embedding model loaded!")

    print("Loading documents...")
    documents = load_documents(DOCUMENTS_DIR)

    print("Chunking documents...")
    all_chunks = []
    all_ids    = []
    all_metas  = []

    for doc in documents:
        chunks = chunk_text(doc["text"])
        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc['filename']}_chunk_{i}"
            all_chunks.append(chunk)
            all_ids.append(chunk_id)
            all_metas.append({
                "source":    doc["filename"],
                "chunk_idx": i
            })

    print(f"Total chunks: {len(all_chunks)}")

    print("Computing embeddings...")
    embeddings = embedder.encode(all_chunks, show_progress_bar=True).tolist()

    print("Storing in ChromaDB...")
    os.makedirs(CHROMA_DIR, exist_ok=True)
    client     = chromadb.PersistentClient(path=CHROMA_DIR)

    # Delete existing collection if rebuilding
    try:
        client.delete_collection(COLLECTION)
        print("Deleted existing collection")
    except Exception:
        pass

    collection = client.get_or_create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"}
    )

    # Add in batches of 100
    batch_size = 100
    for i in range(0, len(all_chunks), batch_size):
        collection.add(
            documents=all_chunks[i:i+batch_size],
            embeddings=embeddings[i:i+batch_size],
            ids=all_ids[i:i+batch_size],
            metadatas=all_metas[i:i+batch_size],
        )
        print(f"Indexed {min(i+batch_size, len(all_chunks))}/{len(all_chunks)} chunks")

    print(f"\nIndex built successfully!")
    print(f"Total chunks indexed: {collection.count()}")
    print(f"Stored at: {CHROMA_DIR}")


if __name__ == "__main__":
    build_index()