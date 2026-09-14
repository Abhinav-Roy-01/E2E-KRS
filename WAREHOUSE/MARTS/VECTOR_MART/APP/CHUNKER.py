"""
Simple character-count chunker with overlap. Ported unchanged from the
earlier working version -- this logic didn't need to change in the rewrite.
"""


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    text = text.strip()
    if len(text) <= chunk_size:
        return [text] if text else []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        start += chunk_size - overlap

    return [c for c in chunks if c]