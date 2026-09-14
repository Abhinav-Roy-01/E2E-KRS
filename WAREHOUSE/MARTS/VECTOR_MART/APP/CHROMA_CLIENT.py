"""
Chroma client -- lazy connection (only connects on first actual use, not at
import time). This matters: connecting eagerly at import crashed the gateway
earlier in this project if Chroma's container hadn't finished starting yet,
even by a few seconds.
"""
import chromadb

COLLECTION_NAME = "ekrs_chunks"
_collection = None


def _get_collection():
    global _collection
    if _collection is None:
        client = chromadb.HttpClient(host="localhost", port=8001)
        _collection = client.get_or_create_collection(name=COLLECTION_NAME)
    return _collection


def upsert_chunk(chunk_id: str, embedding: list[float], document: str, metadata: dict):
    _get_collection().upsert(
        ids=[chunk_id],
        embeddings=[embedding],
        documents=[document],
        metadatas=[metadata],
    )