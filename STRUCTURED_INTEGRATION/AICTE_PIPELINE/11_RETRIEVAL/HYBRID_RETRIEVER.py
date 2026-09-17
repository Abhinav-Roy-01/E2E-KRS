"""
11_RETRIEVAL — the bridge between the data layer and the LLM.
Routes a natural-language question to Postgres (structured), pgvector
(contextual), or both (hybrid), fuses the results, and hands grounded
context to the LLM for answer synthesis. LLM never invents facts — it only
reasons over what retrieval hands it (design doc Rule 2).
"""
import os
import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3:8b")


def classify_query_type(question: str) -> str:
    """
    TODO: replace with a real LLM-based router. For now, a rough heuristic
    based on Section 16 of the design doc: numeric/count/list questions are
    structured; "why/how/what kind of" questions about qualities are contextual.
    """
    structured_markers = ("how many", "count", "list all", "which state", "rank")
    q = question.lower()
    if any(m in q for m in structured_markers):
        return "structured"
    return "hybrid"


def run_structured_query(question: str) -> str:
    """TODO: Text-to-SQL against Postgres (08_POSTGRESQL). Stub for now."""
    return "[structured retrieval not yet wired up]"


def run_vector_query(question: str, top_k: int = 5) -> list[dict]:
    """Embed the question, then find the closest contextual documents in pgvector."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "09_EMBEDDINGS"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "10_PGVECTOR"))
    from EMBEDDING_GENERATOR import embed_texts
    from VECTOR_STORE import get_connection, similarity_search

    query_embedding = embed_texts([question])[0]
    conn = get_connection()
    results = similarity_search(conn, query_embedding, top_k=top_k)
    conn.close()
    return results


def _mock_synthesize(question: str, structured_result: str, contextual_results: list[dict]) -> str:
    """
    Offline fallback -- no LLM call. Stitches the retrieved context into a
    readable answer so the pipeline stays demoable even if the local Ollama
    instance isn't reachable (e.g. mid-setup, or model not pulled yet).
    synthesize_answer() falls back here automatically on connection failure;
    nothing else in the pipeline needs to change.
    """
    if not contextual_results and not structured_result.strip("[]").strip():
        return f"No grounded data was found to answer: \"{question}\""

    lines = [f"Answer (mock synthesis, no LLM call — retrieved context only):\n"]

    if contextual_results:
        lines.append("Based on the following retrieved context:")
        for r in contextual_results:
            lines.append(f"  • [{r['entity_id']}, similarity={r['similarity']:.2f}] {r['context_text']}")
        lines.append("")
        top = contextual_results[0]
        lines.append(f"Most relevant match: {top['context_text']}")

    if structured_result and "not yet wired up" not in structured_result:
        lines.append(f"\nStructured data: {structured_result}")

    return "\n".join(lines)


def synthesize_answer(question: str, structured_result: str, contextual_results: list[dict]) -> str:
    """
    Grounded answer synthesis via local Qwen3:8B (Ollama) -- deliberately not
    a cloud LLM API. This project's core pitch is that institutional/
    government data never leaves local infra; calling an external API here
    would contradict that on the one step that actually touches retrieved
    data. Falls back to _mock_synthesize() if Ollama isn't reachable, so the
    pipeline stays demoable mid-setup rather than crashing.
    """
    context_block = "\n".join(f"- {r.get('context_text')}" for r in contextual_results) or "(none)"
    prompt = (
        f"Answer the question using ONLY the grounded data below. "
        f"Cite which source each fact came from. Do not invent facts.\n\n"
        f"QUESTION: {question}\n\n"
        f"STRUCTURED DATA (from PostgreSQL): {structured_result}\n\n"
        f"CONTEXTUAL DATA (from pgvector): {context_block}"
    )
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": LLM_MODEL, "prompt": prompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["response"]
    except requests.RequestException as e:
        print(f"[synthesize_answer] Ollama unreachable ({e}), falling back to offline synthesis.")
        return _mock_synthesize(question, structured_result, contextual_results)


def answer_question(question: str) -> str:
    qtype = classify_query_type(question)
    structured_result = run_structured_query(question) if qtype in ("structured", "hybrid") else ""
    contextual_results = run_vector_query(question) if qtype in ("contextual", "hybrid") else []
    return synthesize_answer(question, structured_result, contextual_results)


if __name__ == "__main__":
    print(answer_question("How many approved engineering colleges are there in Uttar Pradesh?"))