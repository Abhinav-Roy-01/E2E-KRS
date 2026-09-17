"""
Parser for plain image uploads (jpg/jpeg/png) -- distinct from PDF.py's OCR
fallback, because a photographed document (a WhatsApp photo of a notice, a
phone photo of a circular board) never has a "try direct text extraction
first" path the way a PDF might; it always needs OCR.

Government-document reality check (why this exists at all): a real
institutional intake sees far more photographed/scanned documents than
clean digital PDFs -- a system that only accepts PDFs isn't solving the
actual overload problem. This is the highest-value, lowest-risk addition
for that reason.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # STAGING/APP
from OCR_ENGINE import ocr_image_file  # shared with PARSERS/PDF.py


def parse_image(filepath: str) -> tuple[str, bool]:
    """Returns (text, ocr_used) -- ocr_used is always True here, kept for
    a consistent return shape with PARSERS/PDF.py's parse_pdf()."""
    return ocr_image_file(filepath), True
