"""
09_EMBEDDINGS (part 2) -- turn context text into vectors.

Standardized on the same local Ollama embedding model the document-warehouse
arm uses (bge-m3), instead of a separate local sentence-transformers model.
This is deliberate, not incidental: it means AICTE context vectors and
document-warehouse context vectors live in the SAME embedding space, so the
unified retrieval layer can compare similarity scores across both arms
directly instead of needing a cross-space fusion trick. It also drops the
torch/sentence-transformers dependency (and its multi-GB weight download)
in favor of the Ollama HTTP call already required elsewhere in this project.

Requires: `ollama pull bge-m3` on whatever host OLLAMA_URL points to.
"""
import os
import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434") + "/api/embeddings"
EMBED_MODEL = os.environ.get("EMBEDDING_MODEL", "bge-m3")


def embed_text(text: str) -> list[float]:
    response = requests.post(
        OLLAMA_URL,
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["embedding"]


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Kept plural for compatibility with existing callers (RUN_EMBEDDING_PIPELINE.py,
    HYBRID_RETRIEVER.py) -- Ollama's embeddings endpoint is single-prompt, so this
    loops rather than batching. Fine at pipeline scale; revisit if volume grows."""
    return [embed_text(t) for t in texts]


if __name__ == "__main__":
    print("Calling Ollama for a test embedding (requires `ollama pull bge-m3` first)...")
    vecs = embed_texts(["IIT Delhi has strong industry collaboration."])
    print(f"Embedding dimension: {len(vecs[0])}")
