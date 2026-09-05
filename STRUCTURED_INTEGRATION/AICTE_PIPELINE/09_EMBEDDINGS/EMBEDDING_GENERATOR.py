"""
09_EMBEDDINGS (part 2) — turn context text into vectors.

Uses sentence-transformers locally so the MVP has zero API cost/latency.
Swap the model name in .env / 13_CONFIG/CONFIG.yaml for something stronger
later without touching this file.
"""
import os

_model = None


def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-mpnet-base-v2")
        _model = SentenceTransformer(model_name)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_model()
    return model.encode(texts, batch_size=32, show_progress_bar=False).tolist()


if __name__ == "__main__":
    print("Loading model (first run downloads weights)...")
    vecs = embed_texts(["IIT Delhi has strong industry collaboration."])
    print(f"Embedding dimension: {len(vecs[0])}")
