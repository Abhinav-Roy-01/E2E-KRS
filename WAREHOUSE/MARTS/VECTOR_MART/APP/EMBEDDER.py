"""
Embedding via a local Ollama model. Standardized on bge-m3 (see repo README,
"Model & Architecture Decisions") so document-arm and AICTE-arm embeddings
live in the same vector space and can be compared/merged directly by the
unified retrieval layer -- nomic-embed-text (the earlier model) is weaker on
multilingual text and used a different space than AICTE's old
sentence-transformers model, which made cross-arm retrieval impossible.
"""
import os
import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434") + "/api/embeddings"
MODEL = os.environ.get("EMBEDDING_MODEL", "bge-m3")


def embed_text(text: str) -> list[float]:
    response = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "prompt": text},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["embedding"]
