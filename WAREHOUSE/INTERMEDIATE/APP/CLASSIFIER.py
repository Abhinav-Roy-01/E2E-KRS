"""
Zero-shot department + doc-type classification via local Ollama model.
Runs on the ORIGINAL-LANGUAGE text (from staging_documents.extracted_text),
not a translation -- avoids compounding translation artifacts into the
classification decision.

Adapted from the earlier working version: now also returns a confidence
score, since intermediate_documents.classification_confidence is what the
routing engine will later use to decide auto-route vs human review.
"""
import json
import os
import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434") + "/api/generate"
MODEL = os.environ.get("LLM_MODEL", "qwen3:8b")

DEPARTMENTS = ["Engineering", "HR", "Finance", "Safety", "Procurement", "Legal"]
DOC_TYPES = ["circular", "invoice", "drawing", "report", "contract", "policy", "notice"]
SENSITIVITY_TIERS = ["public", "internal", "restricted", "confidential"]

PROMPT_TEMPLATE = """You are classifying a government/organizational document.
The document text may be in English or another Indian language -- classify
based on its content and meaning regardless of language.

Departments: {departments}
Document types: {doc_types}
Sensitivity tiers (lowest to highest): {sensitivity_tiers}
    public: meant for public release (notices, circulars with no personal/financial data)
    internal: normal internal business, default when unsure
    restricted: named individuals, internal financial figures, unreleased plans
    confidential: legal disputes, disciplinary matters, security-sensitive content

Document text (may be truncated):
---
{text}
---

Respond with ONLY a JSON object, no other text, in this exact format:
{{"department": "<one of the departments>", "doc_type": "<one of the doc types>", "sensitivity_tier": "<one of the sensitivity tiers>", "deadline": "<YYYY-MM-DD or null>", "confidence": <float 0.0-1.0, your own confidence in this classification>}}
"""


def classify_document(text: str, max_chars: int = 3000) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        departments=", ".join(DEPARTMENTS),
        doc_types=", ".join(DOC_TYPES),
        sensitivity_tiers=", ".join(SENSITIVITY_TIERS),
        text=text[:max_chars],
    )

    response = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "prompt": prompt, "stream": False, "format": "json"},
        timeout=120,
    )
    response.raise_for_status()
    raw_output = response.json()["response"]

    try:
        result = json.loads(raw_output)
    except json.JSONDecodeError:
        result = {"department": None, "doc_type": None, "sensitivity_tier": None, "deadline": None, "confidence": 0.0}

    result.setdefault("confidence", 0.5)
    # Never trust an out-of-vocabulary sensitivity tier into the DB -- the
    # CHECK constraint would reject the whole insert. Fall back to the safer
    # default (internal, not public) rather than crash the pipeline.
    if result.get("sensitivity_tier") not in SENSITIVITY_TIERS:
        result["sensitivity_tier"] = "internal"
    return result
