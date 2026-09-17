"""
Shared PaddleOCR engine, lazily initialized once and reused by both
PARSERS/PDF.py (scanned-PDF fallback) and PARSERS/IMAGE.py (photographed
documents -- e.g. WhatsApp/photo uploads, which arrive as a plain image,
not a PDF, so they always need OCR rather than a "try direct extraction
first" step).

Language-support caveat (carried over from PDF.py, still true here):
PaddleOCR's documented support explicitly confirms Devanagari (Hindi/
Marathi), Telugu, and Tamil. Malayalam and Kannada are NOT explicitly
confirmed as of this writing -- test against a real scan in that language
before trusting this for it specifically.
"""
from paddleocr import PaddleOCR

_ocr_engine = None


def get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        # lang="en" is PaddleOCR's default multi-script detection model;
        # swap per-language if you need to force a specific script.
        _ocr_engine = PaddleOCR(use_angle_cls=True, lang="en")
    return _ocr_engine


def ocr_image_file(filepath: str) -> str:
    """Run OCR directly on an image file (jpg/jpeg/png) and return extracted text."""
    engine = get_ocr_engine()
    result = engine.ocr(filepath, cls=True)
    return "\n".join(line[1][0] for block in result for line in block).strip()
