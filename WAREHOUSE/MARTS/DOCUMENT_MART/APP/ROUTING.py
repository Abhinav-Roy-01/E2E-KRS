"""
Deterministic folder-path builder. The AI (CLASSIFIER.py, upstream) decides
WHAT a document is (department, doc_type) -- this module decides WHERE it
goes, via fixed rules, never by asking an LLM to produce a filesystem path
directly. This is a deliberate architectural decision from the design
discussion: the model should never control the filesystem.
"""
from datetime import datetime

ROUTES = {
    ("Engineering", "drawing"): "Engineering/Drawings",
    ("Engineering", "report"): "Engineering/Reports",
    ("Finance", "invoice"): "Finance/Invoices",
    ("Finance", "contract"): "Finance/Contracts",
    ("HR", "policy"): "HR/Policies",
    ("Legal", "contract"): "Legal/Contracts",
    ("Safety", "circular"): "Safety/Circulars",
}


def build_storage_path(department: str, sensitivity_tier: str, doc_type: str, filename: str) -> str:
    year = datetime.utcnow().year
    subpath = ROUTES.get((department, doc_type), f"{department}/{doc_type}")
    doc_type_leaf = subpath.split("/", 1)[-1]  # drop the department prefix baked into ROUTES' values
    sensitivity_label = (sensitivity_tier or "internal").capitalize()
    return f"{department}/{sensitivity_label}/{doc_type_leaf}/{year}/{filename}"