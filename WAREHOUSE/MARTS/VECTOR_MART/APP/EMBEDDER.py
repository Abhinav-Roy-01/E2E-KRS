"""
Embedding via Ollama's nomic-embed-text. Ported unchanged from the earlier
working version.
"""
import requests

OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL = "nomic-embed-text"


def embed_text(text: str) -> list[float]:
    response = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "prompt": text},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["embedding"]
