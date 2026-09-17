"""
Embeds a user's query the same way VECTOR_MART embeds document chunks
(same model, bge-m3, and the same model AICTE's arm now uses too) --
vector search only works if query and chunk embeddings live in the same
vector space. Also handles answer generation via Ollama.
"""
import os
import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("EMBEDDING_MODEL", "bge-m3")
GENERATE_MODEL = os.environ.get("LLM_MODEL", "qwen3:8b")


def embed_text(text: str) -> list[float]:
    response = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["embedding"]


def generate_answer(prompt: str) -> str:
    response = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": GENERATE_MODEL, "prompt": prompt, "stream": False},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["response"]


