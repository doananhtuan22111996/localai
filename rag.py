"""
rag.py — RAG (Retrieval-Augmented Generation) for codebase semantic search
Index project files into ChromaDB, then retrieve relevant chunks by query.
Requires: chromadb, ollama (for embeddings via nomic-embed-text)
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

# Index stored per project at ~/.config/localai/index/<project-hash>/
INDEX_ROOT = Path.home() / ".config" / "localai" / "index"

# File extensions to index
INDEXABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java",
    ".c", ".cpp", ".h", ".cs", ".rb", ".php", ".swift", ".kt", ".kts",
    ".m", ".mm", ".vue", ".svelte", ".html", ".css", ".scss",
    ".json", ".yaml", ".yml", ".toml", ".md", ".txt", ".sh",
    ".sql", ".graphql", ".gradle", ".xml",
}

SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "env",
    "dist", "build", ".next", ".cache", ".gradle", ".idea",
    "Pods", "DerivedData", "fastlane",
}

# Chunk size in characters (~250 tokens)
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def _project_hash(path: str) -> str:
    """Generate a short hash for a project directory path."""
    return hashlib.md5(path.encode()).hexdigest()[:12]


def _chunk_text(text: str, file_path: str) -> list[dict]:
    """Split text into overlapping chunks with metadata."""
    chunks = []
    lines = text.splitlines(keepends=True)
    current_chunk = ""
    current_start_line = 1

    for i, line in enumerate(lines, 1):
        current_chunk += line
        if len(current_chunk) >= CHUNK_SIZE:
            chunks.append({
                "text": current_chunk,
                "file": file_path,
                "start_line": current_start_line,
                "end_line": i,
            })
            # Overlap: keep last CHUNK_OVERLAP chars
            overlap_text = current_chunk[-CHUNK_OVERLAP:] if len(current_chunk) > CHUNK_OVERLAP else ""
            current_chunk = overlap_text
            current_start_line = max(1, i - overlap_text.count("\n"))

    # Remaining text
    if current_chunk.strip():
        chunks.append({
            "text": current_chunk,
            "file": file_path,
            "start_line": current_start_line,
            "end_line": len(lines),
        })

    return chunks


def _collect_files(directory: str) -> list[Path]:
    """Collect all indexable files from a directory."""
    root = Path(directory).resolve()
    files = []
    for fpath in root.rglob("*"):
        if not fpath.is_file():
            continue
        if any(part in SKIP_DIRS for part in fpath.parts):
            continue
        if fpath.suffix not in INDEXABLE_EXTENSIONS:
            continue
        # Skip large files (>100KB)
        if fpath.stat().st_size > 100 * 1024:
            continue
        files.append(fpath)
    return files


def index_directory(directory: str, embedding_model: str = "nomic-embed-text") -> str:
    """
    Index all code files in a directory into ChromaDB.
    Uses Ollama for embeddings (nomic-embed-text by default).
    Returns a status message.
    """
    try:
        import chromadb
        from chromadb.config import Settings
    except ImportError:
        return "[Error] chromadb not installed. Run: pip install chromadb"

    root = Path(directory).resolve()
    if not root.is_dir():
        return f"[Error] Not a directory: {directory}"

    proj_hash = _project_hash(str(root))
    index_path = INDEX_ROOT / proj_hash
    index_path.mkdir(parents=True, exist_ok=True)

    # Create ChromaDB client with persistent storage
    client = chromadb.PersistentClient(path=str(index_path))

    # Delete existing collection if re-indexing
    try:
        client.delete_collection("codebase")
    except Exception:
        pass

    collection = client.create_collection(
        name="codebase",
        metadata={"hnsw:space": "cosine"},
    )

    # Collect and chunk files
    files = _collect_files(directory)
    if not files:
        return f"[Warning] No indexable files found in {directory}"

    all_chunks = []
    for fpath in files:
        try:
            text = fpath.read_text(encoding="utf-8", errors="replace")
            rel_path = str(fpath.relative_to(root))
            chunks = _chunk_text(text, rel_path)
            all_chunks.extend(chunks)
        except Exception:
            continue

    if not all_chunks:
        return "[Warning] No content to index."

    # Generate embeddings via Ollama
    try:
        import requests
        ollama_url = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

        documents = []
        metadatas = []
        ids = []
        embeddings = []

        for i, chunk in enumerate(all_chunks):
            # Get embedding from Ollama
            resp = requests.post(
                f"{ollama_url}/api/embeddings",
                json={"model": embedding_model, "prompt": chunk["text"]},
                timeout=30,
            )
            if resp.status_code != 200:
                continue

            embedding = resp.json().get("embedding", [])
            if not embedding:
                continue

            documents.append(chunk["text"])
            metadatas.append({
                "file": chunk["file"],
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
            })
            ids.append(f"chunk_{i}")
            embeddings.append(embedding)

        if not documents:
            return "[Error] Failed to generate embeddings. Is Ollama running with nomic-embed-text?"

        # Add to ChromaDB in batches
        batch_size = 100
        for start in range(0, len(documents), batch_size):
            end = start + batch_size
            collection.add(
                documents=documents[start:end],
                metadatas=metadatas[start:end],
                ids=ids[start:end],
                embeddings=embeddings[start:end],
            )

        return f"[OK] Indexed {len(documents)} chunks from {len(files)} files into {index_path}"

    except requests.ConnectionError:
        return "[Error] Cannot connect to Ollama for embeddings. Run: ollama serve"
    except Exception as e:
        return f"[Error] Indexing failed: {e}"


def semantic_search(query: str, directory: str = None, top_k: int = 5, embedding_model: str = "nomic-embed-text") -> str:
    """
    Search indexed codebase for chunks relevant to a query.
    Returns formatted results with file paths and line numbers.
    """
    try:
        import chromadb
    except ImportError:
        return "[Error] chromadb not installed. Run: pip install chromadb"

    root = Path(directory or os.getcwd()).resolve()
    proj_hash = _project_hash(str(root))
    index_path = INDEX_ROOT / proj_hash

    if not index_path.exists():
        return f"[Error] No index found for {root}. Run /index first."

    client = chromadb.PersistentClient(path=str(index_path))

    try:
        collection = client.get_collection("codebase")
    except Exception:
        return f"[Error] No index found for {root}. Run /index first."

    # Get query embedding from Ollama
    try:
        import requests
        ollama_url = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        resp = requests.post(
            f"{ollama_url}/api/embeddings",
            json={"model": embedding_model, "prompt": query},
            timeout=30,
        )
        if resp.status_code != 200:
            return "[Error] Failed to get query embedding from Ollama."

        query_embedding = resp.json().get("embedding", [])
        if not query_embedding:
            return "[Error] Empty embedding returned."

    except Exception as e:
        return f"[Error] Embedding failed: {e}"

    # Query ChromaDB
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
    )

    if not results["documents"] or not results["documents"][0]:
        return f"No relevant results found for: {query}"

    # Format results
    output_parts = [f"Semantic search results for '{query}':\n"]
    for doc, meta, distance in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        score = 1 - distance  # cosine similarity
        output_parts.append(
            f"--- {meta['file']}:{meta['start_line']}-{meta['end_line']} "
            f"(relevance: {score:.2f}) ---\n{doc}\n"
        )

    return "\n".join(output_parts)
